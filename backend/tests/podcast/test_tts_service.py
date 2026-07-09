"""
Tests for the chunked/threaded TTS service.

Covers:
- Sentence-bounded chunking keeps chunks near the size limit without losing text
- Missing model/voice assets raise a distinct, catchable error
- synthesize() chunks the script, reports progress per chunk, and writes output
"""
import numpy as np
import pytest

from services.podcast.services.tts import (
    TTSAssetsMissing,
    TTSService,
    _split_into_speech_chunks,
)


def test_split_into_speech_chunks_respects_max_chars_and_keeps_all_text():
    text = "Sentence one is here. Sentence two follows now. Sentence three ends it."
    chunks = _split_into_speech_chunks(text, max_chars=30)
    assert len(chunks) > 1
    rejoined = " ".join(chunks)
    for fragment in ["Sentence one", "Sentence two", "Sentence three"]:
        assert fragment in rejoined


def test_split_into_speech_chunks_single_chunk_for_short_text():
    text = "Just one short sentence."
    chunks = _split_into_speech_chunks(text, max_chars=400)
    assert chunks == [text]


def test_ensure_ready_raises_when_assets_missing(tmp_path):
    service = TTSService(
        model_path=str(tmp_path / "missing.onnx"),
        voices_path=str(tmp_path / "missing.bin"),
    )
    with pytest.raises(TTSAssetsMissing):
        service.ensure_ready()


@pytest.mark.asyncio
async def test_synthesize_chunks_text_reports_progress_and_writes_file(monkeypatch, tmp_path):
    service = TTSService(model_path="unused", voices_path="unused")
    monkeypatch.setattr(service, "ensure_ready", lambda: None)

    calls = []

    def fake_chunk_sync(chunk, voice, speed):
        calls.append(chunk)
        return np.zeros(10, dtype=np.float32), 24000

    monkeypatch.setattr(service, "_synthesize_chunk_sync", fake_chunk_sync)

    progress_events = []

    async def on_progress(done, total):
        progress_events.append((done, total))

    text = "First sentence here. Second sentence follows. Third one wraps up."
    output_path = tmp_path / "out.wav"

    result = await service.synthesize(text, str(output_path), on_progress=on_progress)

    assert result is True
    assert output_path.exists()
    assert len(calls) == len(progress_events) == len(_split_into_speech_chunks(text))
    assert progress_events[-1][0] == progress_events[-1][1]  # last event reaches 100%
    assert all(done <= total for done, total in progress_events)


@pytest.mark.asyncio
async def test_synthesize_does_not_block_event_loop(monkeypatch, tmp_path):
    """The Kokoro call must run off-thread — a synchronous sleep in the fake
    chunk function must not block a concurrently scheduled asyncio task."""
    import asyncio
    import time

    service = TTSService(model_path="unused", voices_path="unused")
    monkeypatch.setattr(service, "ensure_ready", lambda: None)

    def slow_chunk_sync(chunk, voice, speed):
        time.sleep(0.2)
        return np.zeros(10, dtype=np.float32), 24000

    monkeypatch.setattr(service, "_synthesize_chunk_sync", slow_chunk_sync)

    tick_count = 0

    async def ticker():
        nonlocal tick_count
        for _ in range(3):
            await asyncio.sleep(0.05)
            tick_count += 1

    output_path = tmp_path / "out.wav"
    await asyncio.gather(
        service.synthesize("Only one short sentence here.", str(output_path)),
        ticker(),
    )

    assert tick_count == 3  # ticker made progress concurrently instead of being frozen out
