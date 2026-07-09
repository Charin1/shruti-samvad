"""
Tests for the episode map-reduce graph: fan-out summarization, ordering
under out-of-order completion, the human-review interrupt/resume, and error
propagation from a failed fan-out branch.

Uses MemorySaver (in-memory) rather than the real SQLite checkpointer file,
and monkeypatches the LLM/TTS service calls so these tests are hermetic and
fast — no Ollama/Kokoro/network required.
"""
import asyncio

import pytest
from langgraph.checkpoint.memory import MemorySaver

from services.podcast.agent.graph import build_episode_graph


def make_initial_state(articles, review_requested=False, target_minutes=3.0):
    return {
        "episode_id": "ep-1",
        "target_minutes": target_minutes,
        "review_requested": review_requested,
        "articles": articles,
        "article_summaries": [],
        "summary": "",
        "podcast_script": "",
        "audio_path": None,
        "status": "summarizing",
        "error": None,
    }


def _patch_pipeline(monkeypatch, script_text="Welcome to the show! " + ("Today's story continues. " * 15)):
    """Patch every external call (LLM + TTS) so the graph runs with no network/model deps."""

    async def fake_generate_summary(text):
        # Deliberately out-of-order-friendly: summary echoes input so we can
        # assert merge ordering independent of completion order.
        await asyncio.sleep(0.01 if "slow" in text else 0)
        return f"summary-of[{text}]"

    async def fake_merge_article_summaries(summaries):
        return " | ".join(summaries)

    async def fake_generate_podcast_script(summary, target_minutes=3.0):
        return script_text

    async def fake_synthesize(text, path, **kwargs):
        open(path, "w").close()
        return True

    class FakeSegment:
        @staticmethod
        def from_wav(path):
            return FakeSegment()

        def export(self, path, **kwargs):
            open(path, "w").close()

    monkeypatch.setattr("services.podcast.agent.nodes.summarizer.generate_summary", fake_generate_summary)
    monkeypatch.setattr("services.podcast.agent.nodes.merge_summaries.merge_article_summaries", fake_merge_article_summaries)
    monkeypatch.setattr("services.podcast.agent.nodes.scripter.generate_podcast_script", fake_generate_podcast_script)
    monkeypatch.setattr("services.podcast.services.tts.tts_service.synthesize", fake_synthesize)
    monkeypatch.setattr("services.podcast.services.status.publish_status", lambda *a, **k: asyncio.sleep(0))
    monkeypatch.setattr("services.podcast.agent.nodes.saver.AudioSegment", FakeSegment)


@pytest.mark.asyncio
async def test_fan_out_merges_summaries_in_position_order_regardless_of_completion_order(monkeypatch, tmp_path):
    _patch_pipeline(monkeypatch)
    monkeypatch.setenv("AUDIO_STORAGE_PATH", str(tmp_path))

    graph = build_episode_graph(MemorySaver())
    config = {"configurable": {"thread_id": "ep-order"}}

    articles = [
        {"article_id": "a0", "clean_text": "slow first article", "position": 0},
        {"article_id": "a1", "clean_text": "fast second article", "position": 1},
        {"article_id": "a2", "clean_text": "slow third article", "position": 2},
    ]

    final_state = None
    async for event in graph.astream(make_initial_state(articles), config=config):
        node_name = next(iter(event))
        update = event[node_name]
        if isinstance(update, dict):
            final_state = update

    snapshot = await graph.aget_state(config)
    assert not snapshot.next  # graph reached END, did not pause
    merged_summary = snapshot.values["summary"]
    assert merged_summary == (
        "summary-of[slow first article] | summary-of[fast second article] | summary-of[slow third article]"
    )
    assert snapshot.values["status"] == "done"
    assert snapshot.values["audio_path"].endswith("ep-1.mp3")


@pytest.mark.asyncio
async def test_review_requested_pauses_after_review_gate(monkeypatch, tmp_path):
    _patch_pipeline(monkeypatch)
    monkeypatch.setenv("AUDIO_STORAGE_PATH", str(tmp_path))

    graph = build_episode_graph(MemorySaver())
    config = {"configurable": {"thread_id": "ep-review"}}

    articles = [{"article_id": "a0", "clean_text": "one article", "position": 0}]

    async for _ in graph.astream(make_initial_state(articles, review_requested=True), config=config):
        pass

    snapshot = await graph.aget_state(config)
    assert snapshot.next  # graph paused, did not reach END
    assert snapshot.values["status"] == "awaiting_review"
    assert snapshot.values["podcast_script"]  # script was generated before the pause
    assert snapshot.values.get("audio_path") is None  # tts/save never ran


@pytest.mark.asyncio
async def test_resume_after_review_uses_edited_script(monkeypatch, tmp_path):
    _patch_pipeline(monkeypatch)
    monkeypatch.setenv("AUDIO_STORAGE_PATH", str(tmp_path))

    graph = build_episode_graph(MemorySaver())
    config = {"configurable": {"thread_id": "ep-resume"}}

    articles = [{"article_id": "a0", "clean_text": "one article", "position": 0}]

    async for _ in graph.astream(make_initial_state(articles, review_requested=True), config=config):
        pass
    assert (await graph.aget_state(config)).next  # confirm paused

    edited_script = "This is the human-edited narration. " * 5
    await graph.aupdate_state(config, {"podcast_script": edited_script})

    async for _ in graph.astream(None, config=config):
        pass

    snapshot = await graph.aget_state(config)
    assert not snapshot.next  # resumed all the way to END
    assert snapshot.values["status"] == "done"
    assert snapshot.values["podcast_script"] == edited_script


@pytest.mark.asyncio
async def test_failed_summary_branch_sets_error_without_reaching_review_or_tts(monkeypatch, tmp_path):
    monkeypatch.setenv("AUDIO_STORAGE_PATH", str(tmp_path))

    async def failing_generate_summary(text):
        if "bad" in text:
            raise RuntimeError("boom")
        return f"summary-of[{text}]"

    async def fake_merge_article_summaries(summaries):
        return " | ".join(summaries)

    monkeypatch.setattr("services.podcast.agent.nodes.summarizer.generate_summary", failing_generate_summary)
    monkeypatch.setattr("services.podcast.agent.nodes.merge_summaries.merge_article_summaries", fake_merge_article_summaries)

    graph = build_episode_graph(MemorySaver())
    config = {"configurable": {"thread_id": "ep-fail"}}

    articles = [
        {"article_id": "a0", "clean_text": "good article", "position": 0},
        {"article_id": "a1", "clean_text": "bad article", "position": 1},
    ]

    async for _ in graph.astream(make_initial_state(articles), config=config):
        pass

    snapshot = await graph.aget_state(config)
    assert not snapshot.next  # error routes straight to END, doesn't hang or loop
    assert snapshot.values["status"] == "error"
    assert "boom" in snapshot.values["error"]
    assert snapshot.values.get("audio_path") is None
