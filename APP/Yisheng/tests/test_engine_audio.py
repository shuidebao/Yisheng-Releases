from __future__ import annotations

import io
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.engine import InterpreterEngine, _transcription_options


class EngineAudioTests(unittest.TestCase):
    def make_engine(self, model: Mock, device: str = "cpu") -> InterpreterEngine:
        engine = object.__new__(InterpreterEngine)
        engine._model_lock = threading.RLock()
        engine._model = model
        engine.model_name = "base"
        engine.active_device = device
        engine.compute_type = "float16" if device == "cuda" else "int8"
        engine.last_error = None
        engine.translator = Mock()
        engine.translator.translate.return_value = SimpleNamespace(text="等我。", ready=True, warning=None)
        return engine

    @staticmethod
    def result():
        return iter([SimpleNamespace(text="Wait for me.")]), SimpleNamespace(language="en", language_probability=.99)

    def test_path_and_decode_options_stay_compatible_and_timings_are_separate(self):
        model = Mock()
        model.transcribe.return_value = self.result()
        engine = self.make_engine(model)
        with patch("app.engine.time.perf_counter", side_effect=[10, 11, 13, 14, 18, 19, 20]):
            result = engine.transcribe(Path("existing.wav"), "en", 3.0)
        model.transcribe.assert_called_once_with("existing.wav", **_transcription_options("en"))
        engine.translator.translate.assert_called_once_with("Wait for me.", "en", "zh")
        self.assertEqual(result.translation, "等我。")
        self.assertEqual(result.latency_ms, 10000)
        self.assertEqual(result.audio_seconds, 3.0)
        self.assertEqual(result.to_dict()["timings_ms"], {
            "lock_wait": 1000, "model_load": 2000, "audio_prepare": 1000,
            "recognition": 4000, "translation": 1000,
        })

    def test_fallback_stream_stays_open_through_lazy_segments_then_closes(self):
        seen = []
        def transcribe(audio, **options):
            seen.append(audio)
            self.assertEqual(options, _transcription_options("en"))
            def segments():
                self.assertFalse(audio.closed)
                self.assertEqual(audio.read(), b"noncanonical audio")
                yield SimpleNamespace(text="Wait for me.")
            return segments(), SimpleNamespace(language="en", language_probability=.99)
        model = Mock()
        model.transcribe.side_effect = transcribe
        result = self.make_engine(model).transcribe(b"noncanonical audio", "en")
        self.assertEqual(result.original, "Wait for me.")
        self.assertTrue(seen[0].closed)

    def test_prepared_samples_are_passed_through_without_string_conversion(self):
        samples = object()
        model = Mock()
        model.transcribe.return_value = self.result()
        with patch("app.engine.prepare_audio_input", return_value=samples):
            self.make_engine(model).transcribe(b"canonical WAV", "ja")
        model.transcribe.assert_called_once_with(samples, **_transcription_options("ja"))

    def test_cuda_lazy_failure_rewinds_stream_before_cpu_retry(self):
        stream = io.BytesIO(b"complete audio")
        def gpu_transcribe(audio, **options):
            self.assertEqual(audio.read(), b"complete audio")
            def segments():
                raise RuntimeError("CUDA runtime failed")
                yield  # A lazy decoder failure must take the same retry path.
            return segments(), SimpleNamespace(language="en")
        def cpu_transcribe(audio, **options):
            self.assertIs(audio, stream)
            self.assertEqual(audio.tell(), 0)
            self.assertEqual(audio.read(), b"complete audio")
            self.assertEqual(options, _transcription_options("en"))
            return self.result()
        gpu, cpu = Mock(), Mock()
        gpu.transcribe.side_effect = gpu_transcribe
        cpu.transcribe.side_effect = cpu_transcribe
        engine = self.make_engine(gpu, "cuda")
        with (
            patch("app.engine.prepare_audio_input", return_value=stream),
            patch("app.engine.ensure_whisper_model", return_value=Path("base")),
            patch.object(engine, "_check_available_memory"),
            patch.object(engine, "_create_model", return_value=cpu) as create,
        ):
            result = engine.transcribe(b"complete audio", "en")
        create.assert_called_once_with(Path("base"), "cpu", "int8")
        self.assertEqual(result.device, "cpu")
        self.assertIn("已自动切换 CPU", result.warning)
        self.assertEqual(result.original, "Wait for me.")
        self.assertTrue(stream.closed)

    def test_cpu_decode_failure_closes_stream_without_translating(self):
        stream = io.BytesIO(b"broken audio")
        model = Mock()
        model.transcribe.side_effect = ValueError("invalid audio")
        engine = self.make_engine(model)
        with patch("app.engine.prepare_audio_input", return_value=stream):
            with self.assertRaisesRegex(ValueError, "invalid audio"):
                engine.transcribe(b"broken audio", "en")
        self.assertTrue(stream.closed)
        engine.translator.translate.assert_not_called()

    def test_memory_errors_remain_actionable(self):
        for during_prepare in (False, True):
            with self.subTest(during_prepare=during_prepare):
                stream = io.BytesIO(b"audio")
                model = Mock()
                model.transcribe.side_effect = MemoryError()
                engine = self.make_engine(model)
                with (
                    patch("app.engine.prepare_audio_input", side_effect=MemoryError() if during_prepare else None, return_value=stream),
                    patch.object(engine, "_memory_message", return_value="运行内存不足"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "运行内存不足"):
                        engine.transcribe(b"audio", "en")
                if not during_prepare:
                    self.assertTrue(stream.closed)
                else:
                    model.transcribe.assert_not_called()
                    stream.close()

    def test_cpu_retry_failure_also_closes_stream(self):
        stream = io.BytesIO(b"audio")
        gpu, cpu = Mock(), Mock()
        gpu.transcribe.side_effect = RuntimeError("CUDA failed")
        cpu.transcribe.side_effect = ValueError("retry failed")
        engine = self.make_engine(gpu, "cuda")
        with (
            patch("app.engine.prepare_audio_input", return_value=stream),
            patch("app.engine.ensure_whisper_model", return_value=Path("base")),
            patch.object(engine, "_check_available_memory"),
            patch.object(engine, "_create_model", return_value=cpu),
        ):
            with self.assertRaisesRegex(ValueError, "retry failed"):
                engine.transcribe(b"audio", "en")
        self.assertTrue(stream.closed)

    def test_continuation_context_still_reaches_translation(self):
        model = Mock()
        model.transcribe.return_value = self.result()
        engine = self.make_engine(model)
        with patch("app.engine.merge_continuation", return_value="Merged sentence.") as merge:
            result = engine.transcribe(Path("existing.wav"), "en", context="Previous part.")
        merge.assert_called_once_with("Previous part.", "Wait for me.", "en")
        model.transcribe.assert_called_once_with("existing.wav", **_transcription_options("en", "Previous part."))
        engine.translator.translate.assert_called_once_with("Merged sentence.", "en", "zh")
        self.assertTrue(result.continued)


if __name__ == "__main__":
    unittest.main()
