from __future__ import annotations

import struct
import unittest

from app.speech_chunker import SAMPLE_RATE, SpeechChunker


def pcm(seconds, voiced=True):
    return struct.pack("<h", 1000 if voiced else 0) * round(seconds * SAMPLE_RATE)


def deterministic_detector(raw):
    # Match the timestamp API's treatment of speech still in progress.
    samples = memoryview(raw).cast("h")
    spans, start, last = [], None, 0
    for i, value in enumerate(samples):
        if value:
            if start is None:
                start = i
            last = i + 1
        elif start is not None and i - last >= .6 * SAMPLE_RATE:
            spans.append({"start": start, "end": last})
            start = None
    if start is not None:
        spans.append({"start": start, "end": len(samples)})
    return spans


class SpeechChunkerTests(unittest.TestCase):
    def chunker(self, **kwargs):
        return SpeechChunker(detector=deterministic_detector, **kwargs)

    def test_silence_is_bounded_and_never_transcribed(self):
        chunker = self.chunker()
        self.assertEqual(chunker.feed(pcm(30, False)), [])
        self.assertLessEqual(len(chunker._buffer), (SAMPLE_RATE + 4096) * 2)
        self.assertEqual(chunker.finish(), [])

    def test_natural_pause_preserves_complete_sentences_without_overlap(self):
        chunker = self.chunker()
        chunks = chunker.feed(pcm(3) + pcm(.9, False) + pcm(2) + pcm(.9, False))
        self.assertEqual(len(chunks), 2)
        self.assertTrue(all(not c.continuation for c in chunks))
        self.assertLess(chunks[0].ended_at, chunks[1].started_at)
        self.assertGreater(chunks[0].ended_at - chunks[0].started_at, 3)
        self.assertEqual(chunker.finish(), [])

    def test_short_command_is_kept_when_stopping(self):
        chunker = self.chunker()
        self.assertEqual(chunker.feed(pcm(.3)), [])
        chunks = chunker.finish()
        self.assertEqual(len(chunks), 1)
        self.assertAlmostEqual(chunks[0].ended_at, .3)
        self.assertEqual(chunker.finish(), [])

    def test_hard_cut_only_carries_overlap_and_continuation(self):
        chunker = self.chunker(max_seconds=3)
        chunks = chunker.feed(pcm(4) + pcm(.9, False))
        self.assertEqual(len(chunks), 2)
        self.assertFalse(chunks[0].continuation)
        self.assertTrue(chunks[1].continuation)
        self.assertAlmostEqual(chunks[0].ended_at - chunks[1].started_at, .6)
        following = chunker.feed(pcm(1) + pcm(.9, False))
        self.assertFalse(following[0].continuation)

    def test_stop_does_not_emit_retained_overlap_twice(self):
        chunker = self.chunker(max_seconds=3)
        self.assertEqual(len(chunker.feed(pcm(3))), 1)
        self.assertEqual(chunker.finish(), [])

    def test_timestamps_use_source_time_including_quiet(self):
        chunker = self.chunker()
        chunker.feed(pcm(20, False))
        chunks = chunker.feed(pcm(1) + pcm(.9, False))
        self.assertGreaterEqual(chunks[0].started_at, 19.8)
        self.assertLess(chunks[0].ended_at, 21.3)

    def test_rejects_partial_pcm_sample(self):
        with self.assertRaises(ValueError):
            self.chunker().feed(b"x")


if __name__ == "__main__":
    unittest.main()
