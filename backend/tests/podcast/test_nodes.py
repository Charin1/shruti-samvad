"""
Tests for LangGraph episode pipeline nodes.

Covers the bugs we hit:
- Error state propagating into next node causing KeyError
- Missing state keys crashing nodes
- __end__ terminal event from LangGraph
- Audio path key mismatch
- Per-article summarize failures must not race-write top-level status/error
  keys across parallel Send fan-out branches (only article_summaries, a
  reducer-backed list, is safe to write from summarize_one_node)
"""
import pytest


def make_episode_state(**overrides):
    base = {
        "episode_id": "test-episode-1",
        "target_minutes": 3.0,
        "review_requested": False,
        "articles": [],
        "article_summaries": [],
        "summary": "",
        "podcast_script": "",
        "audio_path": None,
        "status": "summarizing",
        "error": None,
    }
    base.update(overrides)
    return base


def make_article_input(**overrides):
    base = {"article_id": "test-article-1", "clean_text": "OpenAI announced a new model today.", "position": 0}
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# summarize_one_node — per-article, invoked via Send fan-out
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summarize_one_records_error_in_article_summaries_not_top_level(monkeypatch):
    """A failure must ride inside the reducer-backed list, never on the plain
    top-level status/error keys — those would conflict if two parallel
    branches failed in the same superstep."""
    from services.podcast.agent.nodes.summarizer import summarize_one_node

    async def bad_llm(text):
        raise RuntimeError("Ollama connection refused")

    monkeypatch.setattr("services.podcast.agent.nodes.summarizer.generate_summary", bad_llm)
    result = await summarize_one_node(make_article_input())
    assert "status" not in result
    assert "error" not in result
    entry = result["article_summaries"][0]
    assert entry["summary"] is None
    assert "Ollama connection refused" in entry["error"]
    assert entry["article_id"] == "test-article-1"


@pytest.mark.asyncio
async def test_summarize_one_returns_summary_on_success(monkeypatch):
    from services.podcast.agent.nodes.summarizer import summarize_one_node

    async def good_llm(text):
        return "A short summary."

    monkeypatch.setattr("services.podcast.agent.nodes.summarizer.generate_summary", good_llm)
    result = await summarize_one_node(make_article_input(position=2))
    entry = result["article_summaries"][0]
    assert entry["summary"] == "A short summary."
    assert entry["error"] is None
    assert entry["position"] == 2


# ---------------------------------------------------------------------------
# merge_summaries_node — join point after fan-out
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_merge_summaries_sets_error_when_any_article_failed():
    from services.podcast.agent.nodes.merge_summaries import merge_summaries_node

    state = make_episode_state(
        article_summaries=[
            {"article_id": "a0", "position": 0, "summary": "ok", "error": None},
            {"article_id": "a1", "position": 1, "summary": None, "error": "boom"},
        ]
    )
    result = await merge_summaries_node(state)
    assert result["status"] == "error"
    assert result["error"] == "boom"


@pytest.mark.asyncio
async def test_merge_summaries_orders_by_position_regardless_of_list_order(monkeypatch):
    from services.podcast.agent.nodes.merge_summaries import merge_summaries_node

    seen_order = []

    async def fake_merge(summaries):
        seen_order.extend(summaries)
        return "merged"

    monkeypatch.setattr("services.podcast.agent.nodes.merge_summaries.merge_article_summaries", fake_merge)

    # Deliberately out of order (branch 2 "completed" before branch 0/1)
    state = make_episode_state(
        article_summaries=[
            {"article_id": "a2", "position": 2, "summary": "third", "error": None},
            {"article_id": "a0", "position": 0, "summary": "first", "error": None},
            {"article_id": "a1", "position": 1, "summary": "second", "error": None},
        ]
    )
    result = await merge_summaries_node(state)
    assert seen_order == ["first", "second", "third"]
    assert result["summary"] == "merged"
    assert result["status"] == "scripting"


# ---------------------------------------------------------------------------
# scripter — must skip when error already set; must route status based on
# review_requested
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scripter_skips_when_error_propagated():
    """If merge_summaries errored, scripter must return {} without calling LLM."""
    from services.podcast.agent.nodes.scripter import scripter_node

    state = make_episode_state(error="Merging summaries failed: boom", status="error")
    result = await scripter_node(state)
    assert result == {}  # must not crash or call LLM


@pytest.mark.asyncio
async def test_scripter_returns_synthesizing_when_review_not_requested(monkeypatch):
    from services.podcast.agent.nodes.scripter import scripter_node

    realistic_script = "Welcome to the show! " + ("This is today's story. " * 15)

    async def good_llm(summary, target_minutes=3.0):
        return realistic_script

    monkeypatch.setattr("services.podcast.agent.nodes.scripter.generate_podcast_script", good_llm)
    state = make_episode_state(summary="A short summary.", status="scripting", review_requested=False)
    result = await scripter_node(state)
    assert result["status"] == "synthesizing"
    assert result["podcast_script"] == realistic_script.strip()


@pytest.mark.asyncio
async def test_scripter_returns_awaiting_review_when_review_requested(monkeypatch):
    from services.podcast.agent.nodes.scripter import scripter_node

    realistic_script = "Welcome to the show! " + ("This is today's story. " * 15)

    async def good_llm(summary, target_minutes=3.0):
        return realistic_script

    monkeypatch.setattr("services.podcast.agent.nodes.scripter.generate_podcast_script", good_llm)
    state = make_episode_state(summary="A short summary.", status="scripting", review_requested=True)
    result = await scripter_node(state)
    assert result["status"] == "awaiting_review"


@pytest.mark.asyncio
async def test_scripter_errors_on_too_short_output(monkeypatch):
    """A near-empty or truncated LLM response must not be sent to TTS silently."""
    from services.podcast.agent.nodes.scripter import scripter_node

    async def bad_llm(summary, target_minutes=3.0):
        return "Okay."

    monkeypatch.setattr("services.podcast.agent.nodes.scripter.generate_podcast_script", bad_llm)
    state = make_episode_state(summary="A short summary.", status="scripting")
    result = await scripter_node(state)
    assert result["status"] == "error"
    assert "too short" in result["error"]


@pytest.mark.asyncio
async def test_scripter_strips_markdown_and_labels(monkeypatch):
    """LLMs sometimes ignore 'no markdown' instructions — TTS must not read literal asterisks."""
    from services.podcast.agent.nodes.scripter import scripter_node

    raw = (
        "Here's your script:\n"
        "HOST: **Welcome** to the show! " + ("Today we cover something interesting. " * 10)
    )

    async def markdown_llm(summary, target_minutes=3.0):
        return raw

    monkeypatch.setattr("services.podcast.agent.nodes.scripter.generate_podcast_script", markdown_llm)
    state = make_episode_state(summary="A short summary.", status="scripting")
    result = await scripter_node(state)
    assert result["status"] == "synthesizing"
    assert "**" not in result["podcast_script"]
    assert "HOST:" not in result["podcast_script"]
    assert "Here's your script" not in result["podcast_script"]


# ---------------------------------------------------------------------------
# review_gate — no-op passthrough (the interrupt_after target)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_review_gate_is_a_noop():
    from services.podcast.agent.nodes.review_gate import review_gate_node

    result = await review_gate_node(make_episode_state(status="awaiting_review"))
    assert result == {}


# ---------------------------------------------------------------------------
# tts node — must skip when error already set
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tts_skips_when_error_propagated():
    from services.podcast.agent.nodes.tts import tts_node

    state = make_episode_state(error="Scripting failed", status="error")
    result = await tts_node(state)
    assert result == {}


@pytest.mark.asyncio
async def test_tts_returns_saving_status_on_success(monkeypatch, tmp_path):
    from services.podcast.agent.nodes.tts import tts_node

    async def good_synth(text, path, **kwargs):
        # Write a dummy file so saver can check it exists
        open(path, "w").close()
        return True

    monkeypatch.setattr(
        "services.podcast.agent.nodes.tts.tts_service.synthesize", good_synth
    )
    state = make_episode_state(podcast_script="Welcome to the show!", status="synthesizing")
    result = await tts_node(state)
    assert result["status"] == "saving"
    assert result.get("audio_path") is not None  # key must be "audio_path", not "audio_file_path"


# ---------------------------------------------------------------------------
# saver node — must skip when error already set
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_saver_skips_when_error_propagated():
    from services.podcast.agent.nodes.saver import saver_node

    state = make_episode_state(error="TTS failed", status="error")
    result = await saver_node(state)
    assert result == {}


@pytest.mark.asyncio
async def test_saver_errors_when_audio_file_missing():
    from services.podcast.agent.nodes.saver import saver_node

    state = make_episode_state(audio_path="/tmp/nonexistent-file.wav", status="saving")
    result = await saver_node(state)
    assert result["status"] == "error"
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_saver_returns_done_status(monkeypatch, tmp_path):
    from services.podcast.agent.nodes.saver import saver_node

    wav = tmp_path / "test.wav"
    wav.write_bytes(b"RIFF")  # dummy file

    class FakeSegment:
        @staticmethod
        def from_wav(path):
            return FakeSegment()

        def export(self, path, **kwargs):
            open(path, "w").close()

    monkeypatch.setattr("services.podcast.agent.nodes.saver.AudioSegment", FakeSegment)
    monkeypatch.setenv("AUDIO_STORAGE_PATH", str(tmp_path))

    state = make_episode_state(audio_path=str(wav), status="saving")
    result = await saver_node(state)
    assert result["status"] == "done"
    assert result.get("audio_path", "").endswith(".mp3")


# ---------------------------------------------------------------------------
# LangGraph terminal event guard
# ---------------------------------------------------------------------------

def test_end_event_is_not_a_dict():
    """LangGraph emits {"__end__": None} — must not be processed as a state update."""
    terminal = {"__end__": None}
    node_name = next(iter(terminal))
    state_update = terminal[node_name]
    assert not isinstance(state_update, dict)  # our guard: `if not isinstance(state_update, dict): continue`
