from __future__ import annotations

import unittest

from app.engine import _transcription_options


class TranscriptionOptionsTests(unittest.TestCase):
    def test_japanese_uses_more_accurate_decode_and_recent_context(self) -> None:
        context = "前の文です。" * 20
        options = _transcription_options("ja", context)

        self.assertEqual(options["language"], "ja")
        self.assertEqual(options["beam_size"], 3)
        self.assertEqual(options["initial_prompt"], context[-80:])
        self.assertEqual(options["vad_parameters"]["min_silence_duration_ms"], 450)
        self.assertEqual(options["vad_parameters"]["speech_pad_ms"], 180)

    def test_english_uses_context_with_moderate_decode_cost(self) -> None:
        context = "This is the previous part of a continuous sentence. " * 4
        options = _transcription_options("en", context)

        self.assertEqual(options["beam_size"], 2)
        self.assertEqual(options["initial_prompt"], context.strip()[-120:])
        self.assertEqual(options["vad_parameters"]["min_silence_duration_ms"], 380)
        self.assertEqual(options["vad_parameters"]["speech_pad_ms"], 160)

    def test_chinese_keeps_low_latency_defaults(self) -> None:
        options = _transcription_options("zh", "上一句话")

        self.assertEqual(options["beam_size"], 1)
        self.assertNotIn("initial_prompt", options)
        self.assertEqual(options["vad_parameters"]["min_silence_duration_ms"], 280)


if __name__ == "__main__":
    unittest.main()
