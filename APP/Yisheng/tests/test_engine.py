from __future__ import annotations

import threading
import unittest
from unittest.mock import patch

from app.config import HardwareInfo, performance_cpu_threads
from app.engine import InterpreterEngine, _transcription_options


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


class PerformanceProfileTests(unittest.TestCase):
    @staticmethod
    def _hardware(cuda_ready: bool = True) -> HardwareInfo:
        return HardwareInfo(
            "Windows",
            "Test CPU",
            16.0,
            8.0,
            "Test GPU" if cuda_ready else None,
            8192 if cuda_ready else None,
            cuda_ready,
        )

    def test_inference_threads_leave_headroom_for_games(self) -> None:
        self.assertEqual(performance_cpu_threads(2), 1)
        self.assertEqual(performance_cpu_threads(4), 2)
        self.assertEqual(performance_cpu_threads(32), 2)

    def test_auto_device_reserves_gpu_but_explicit_cuda_remains_available(self) -> None:
        engine = object.__new__(InterpreterEngine)
        engine.hardware = self._hardware()

        engine.requested_device = "auto"
        engine._choose_device()
        self.assertEqual(engine.active_device, "cpu")
        self.assertEqual(engine.compute_type, "int8")

        engine.requested_device = "cuda"
        engine._choose_device()
        self.assertEqual(engine.active_device, "cuda")
        self.assertEqual(engine.compute_type, "float16")

    def test_release_drops_recognition_and_translation_models(self) -> None:
        class TranslatorStub:
            def __init__(self) -> None:
                self.calls = 0

            def unload(self) -> bool:
                self.calls += 1
                return True

        engine = object.__new__(InterpreterEngine)
        engine._model = object()
        engine._model_lock = threading.RLock()
        engine.translator = TranslatorStub()

        with patch("app.engine.gc.collect") as collect:
            result = engine.release()

        self.assertIsNone(engine._model)
        self.assertEqual(engine.translator.calls, 1)
        self.assertTrue(result["released"])
        collect.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
