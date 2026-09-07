"""Bounded, pause-delimited PCM chunks for live interpretation.

Use the already bundled Silero detector, not amplitude alone: game music and
sound effects are not necessarily speech. No additional model download or GPU
is needed. Keep the detector injectable so boundary tests need no ML runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


SAMPLE_RATE = 16000


def detect_speech(pcm: bytes) -> list[dict]:
    import numpy as np
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    audio = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
    if not audio.size or np.max(np.abs(audio)) < 48 / 32768:
        return []
    return get_speech_timestamps(
        audio,
        VadOptions(min_speech_duration_ms=160, min_silence_duration_ms=600, speech_pad_ms=0),
    )


@dataclass(frozen=True)
class SpeechChunk:
    pcm: bytes
    started_at: float
    ended_at: float
    continuation: bool


class SpeechChunker:
    """Inspect at most eight seconds, at 256 ms intervals, on one CPU thread.

    Natural pauses finish a sentence. Only a hard duration limit keeps overlap
    and marks the next result as a continuation. Source timestamps are based on
    captured samples, never on the speed of recognition or HTTP delivery.
    """

    def __init__(
        self,
        max_seconds: float = 8.0,
        overlap_seconds: float = .6,
        detector: Callable[[bytes], list[dict]] = detect_speech,
    ) -> None:
        self.max_samples = int(SAMPLE_RATE * min(8.0, max(3.0, max_seconds)))
        self.overlap_samples = int(SAMPLE_RATE * min(1.0, max(0.0, overlap_seconds)))
        self.pad_samples = int(SAMPLE_RATE * .16)
        self.silence_samples = int(SAMPLE_RATE * .6)
        self.check_samples = 4096
        self.detector = detector
        self._buffer = bytearray()
        self._offset = 0
        self._unchecked = 0
        self._continuation = False
        self._retained_samples = 0

    def feed(self, pcm: bytes) -> list[SpeechChunk]:
        if len(pcm) % 2:
            raise ValueError("Expected mono 16-bit PCM")
        chunks = []
        # Also bound memory if a caller submits a large buffer in one operation.
        for position in range(0, len(pcm), self.check_samples * 2):
            part = pcm[position : position + self.check_samples * 2]
            self._buffer.extend(part)
            self._unchecked += len(part) // 2
            if self._unchecked >= self.check_samples or len(self._buffer) // 2 >= self.max_samples:
                chunks.extend(self._inspect())
                self._unchecked = 0
        return chunks

    def finish(self) -> list[SpeechChunk]:
        chunks = self._inspect(final=True)
        self._discard(len(self._buffer) // 2)
        self._continuation = False
        self._retained_samples = 0
        return chunks

    def _discard(self, samples: int) -> None:
        del self._buffer[: samples * 2]
        self._offset += samples
        self._retained_samples = max(0, self._retained_samples - samples)

    def _chunk(self, start: int, end: int) -> SpeechChunk:
        return SpeechChunk(
            bytes(self._buffer[start * 2 : end * 2]),
            (self._offset + start) / SAMPLE_RATE,
            (self._offset + end) / SAMPLE_RATE,
            self._continuation,
        )

    def _inspect(self, final: bool = False) -> list[SpeechChunk]:
        chunks = []
        while self._buffer:
            size = len(self._buffer) // 2
            ranges = self.detector(bytes(self._buffer))
            if not ranges:
                # Preserve a short lead-in for quiet consonants at speech onset.
                self._discard(max(0, size - SAMPLE_RATE))
                self._continuation = False
                self._retained_samples = 0
                break
            first = ranges[0]
            start = 0 if self._continuation else max(0, first["start"] - self.pad_samples)
            end = first["end"]
            complete = size - end >= self.silence_samples
            if complete or final:
                end = min(size, end + self.pad_samples)
                # A retained overlap followed only by silence must not be emitted
                # a second time when the user stops or a sentence ends.
                if first["end"] > self._retained_samples + int(.08 * SAMPLE_RATE):
                    chunks.append(self._chunk(start, end))
                self._discard(end)
                self._continuation = False
                self._retained_samples = 0
                continue
            if start:
                self._discard(start)
                size -= start
            if size >= self.max_samples:
                chunks.append(self._chunk(0, self.max_samples))
                self._discard(self.max_samples - self.overlap_samples)
                self._retained_samples = self.overlap_samples
                self._continuation = True
                continue
            break
        return chunks
