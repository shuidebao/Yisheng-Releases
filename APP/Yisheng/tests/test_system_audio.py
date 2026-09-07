from __future__ import annotations

import io
import types
import unittest
import wave
from unittest.mock import patch

from app.speech_chunker import SpeechChunk
from app.system_audio import AudioChunk, LoopbackDevice, SystemAudioManager


class SystemAudioTests(unittest.TestCase):
    def test_bounded_queue_reports_loss_and_keeps_sequence_gaps(self):
        manager = SystemAudioManager()
        for sequence in (1, 2, 3):
            manager._enqueue(AudioChunk(b"pcm", 1, .2, sequence=sequence))
        self.assertEqual(manager.status()["dropped_chunks"], 1)
        self.assertEqual(manager.get_chunk(.05).sequence, 2)
        self.assertEqual(manager.get_chunk(.05).sequence, 3)
        self.assertIsNone(manager.get_chunk(.05))

    def test_capture_flushes_tail_as_mono_16khz_with_source_metadata(self):
        manager = SystemAudioManager()
        manager._device = LoopbackDevice(1, "Test output", 2, 48000, True)
        submitted = []
        tail = b"\x00\x04" * 4800
        class Chunker:
            def __init__(self, *args):
                pass
            def feed(self, data):
                submitted.append(data)
                return []
            def finish(self):
                return [SpeechChunk(tail, 2.0, 2.3, False)]
        class Stream:
            def read(self, *_args, **_kwargs):
                manager._stop.set()
                return b"\x00\x04\x00\x04" * 1024
            def stop_stream(self):
                pass
            def close(self):
                pass
        class Audio:
            def open(self, **_kwargs):
                return Stream()
            def terminate(self):
                pass
        module = types.SimpleNamespace(PyAudio=Audio, paInt16=16)
        with patch.object(manager, "_pyaudio_module", return_value=module), patch("app.system_audio.SpeechChunker", Chunker):
            manager._capture_loop()
        self.assertTrue(submitted)
        self.assertLess(len(submitted[0]), 1024 * 2)
        chunk = manager.get_chunk(.05)
        self.assertEqual((chunk.sequence, chunk.started_at, chunk.ended_at, chunk.continuation), (1, 2.0, 2.3, False))
        with wave.open(io.BytesIO(chunk.wav), "rb") as wav:
            self.assertEqual((wav.getnchannels(), wav.getframerate(), wav.getnframes()), (1, 16000, 4800))
        self.assertAlmostEqual(chunk.duration, .3)


if __name__ == "__main__":
    unittest.main()
