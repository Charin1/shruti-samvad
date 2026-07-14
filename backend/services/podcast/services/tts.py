import asyncio
import os
import re

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

DEFAULT_MODEL_PATH = os.getenv("KOKORO_MODEL_PATH", "model.onnx")
DEFAULT_VOICES_PATH = os.getenv("KOKORO_VOICES_PATH", "voices.bin")

# Splitting on sentence boundaries keeps each Kokoro call small (bounded
# latency and memory per call), lets us report real synthesis progress
# instead of one opaque multi-minute step, and avoids handing the model an
# entire script in one shot.
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')
_MAX_CHUNK_CHARS = 400


def _split_into_speech_chunks(text: str, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks or [text]


class TTSAssetsMissing(RuntimeError):
    """Raised when the Kokoro model/voice files are not present on disk."""


class TTSService:
    def __init__(self, model_path: str = DEFAULT_MODEL_PATH, voices_path: str = DEFAULT_VOICES_PATH):
        self.model_path = model_path
        self.voices_path = voices_path
        self._kokoro: Kokoro | None = None

    def assets_available(self) -> bool:
        return os.path.exists(self.model_path) and os.path.exists(self.voices_path)

    def ensure_ready(self) -> None:
        """
        Verify model/voice assets exist and load the model.

        Intended to be called once at worker startup so a missing model
        surfaces immediately and loudly, instead of failing deep inside a
        job after the LLM steps have already run.
        """
        if not self.assets_available():
            raise TTSAssetsMissing(
                f"Kokoro model/voice files not found (model={self.model_path}, "
                f"voices={self.voices_path})"
            )
        if self._kokoro is None:
            self._kokoro = Kokoro(self.model_path, self.voices_path)

    def get_voices(self) -> list[str]:
        """Return list of available voices."""
        self.ensure_ready()
        return sorted(list(self._kokoro.get_voices()))

    def _synthesize_chunk_sync(self, chunk: str, voice: str, speed: float):
        return self._kokoro.create(chunk, voice=voice, speed=speed, lang="en-us")

    async def synthesize(
        self,
        text: str,
        output_path: str,
        voice: str = "af_sky",
        voice_cohost: Optional[str] = None,
        podcast_format: str = "monologue",
        speed: float = 1.0,
        on_progress=None,
    ) -> bool:
        """
        Synthesize text to a WAV file. Supports monologue (single voice) and dialogue
        (multiple voices split by paragraph prefixes 'Host:' and 'Co-Host:').

        Text is split into sentence-bounded chunks and each chunk is
        synthesized in a worker thread. Resulting samples are
        concatenated into a single output file.
        """
        from typing import Optional
        self.ensure_ready()

        # Build list of (chunk_text, voice_to_use)
        dialogue_chunks: list[tuple[str, str]] = []

        if podcast_format == "dialogue" and voice_cohost:
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for p in paragraphs:
                # Check for speaker prefix
                import re
                m = re.match(r'^(Host|Co-Host|Aarav|Ananya|Speaker\s*[12]):\s*(.*)', p, re.IGNORECASE)
                if m:
                    speaker = m.group(1).lower()
                    body = m.group(2).strip()
                    # Assign voice based on speaker label
                    current_voice = voice_cohost if "co-host" in speaker or "ananya" in speaker or "2" in speaker else voice
                else:
                    body = p
                    current_voice = voice
                
                # Split the turn's body into sentence-bounded chunks
                chunks = _split_into_speech_chunks(body)
                for c in chunks:
                    dialogue_chunks.append((c, current_voice))
        else:
            chunks = _split_into_speech_chunks(text)
            for c in chunks:
                dialogue_chunks.append((c, voice))

        if not dialogue_chunks:
            dialogue_chunks = [("Hello", voice)]

        all_samples = []
        sample_rate = None

        for i, (chunk, chunk_voice) in enumerate(dialogue_chunks):
            samples, sample_rate = await asyncio.to_thread(
                self._synthesize_chunk_sync, chunk, chunk_voice, speed
            )
            all_samples.append(samples)
            if on_progress:
                await on_progress(i + 1, len(dialogue_chunks))

        merged = np.concatenate(all_samples) if len(all_samples) > 1 else all_samples[0]
        sf.write(output_path, merged, sample_rate)
        return True


# Singleton instance
tts_service = TTSService()
