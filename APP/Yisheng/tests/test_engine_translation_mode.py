from __future__ import annotations

import json
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.config import HardwareInfo
from app.engine import InterpreterEngine
from app.translation import TranslationResult


def make_engine() -> InterpreterEngine:
    hardware = HardwareInfo("Windows", "Test CPU", 16, 8, None, None, False)
    with patch("app.engine.detect_hardware", return_value=hardware):
        engine = InterpreterEngine()
    engine.translator = Mock()
    engine.translator.installed_pairs.return_value = []
    engine.translator.unload.return_value = False
    engine.translator.translate.return_value = TranslationResult("本地译文", "en", True)
    model = Mock()
    model.transcribe.side_effect = lambda *args, **kwargs: (
        iter([SimpleNamespace(text="Wait for me.")]),
        SimpleNamespace(language="en", language_probability=1),
    )
    engine._model = model
    return engine


class TranslationModeTests(unittest.TestCase):
    def test_default_is_local_without_creating_api_client(self):
        with patch("app.engine.ApiTranslator") as client:
            engine = make_engine()
            result = engine.transcribe(b"fake audio", "en")
        client.assert_not_called()
        self.assertEqual(result.translation_mode, "local")
        self.assertEqual(result.translation, "本地译文")
        self.assertEqual(engine.translation_status()["mode"], "local")

    def test_opt_in_routes_only_recognized_text_and_never_falls_back(self):
        engine = make_engine()
        engine.configure_translation("api", "https://example.invalid/v1", "model", "secret", True)
        with patch.object(engine._api_translator, "translate", return_value=TranslationResult("API 译文", "en", True)) as translate:
            result = engine.transcribe(b"private audio bytes", "en", target_language="ko", translation_revision=1)
        translate.assert_called_once_with("Wait for me.", "en", "ko")
        engine.translator.translate.assert_not_called()
        self.assertEqual(result.translation_mode, "api")
        self.assertEqual(result.translation, "API 译文")
        with patch.object(engine._api_translator, "translate", return_value=TranslationResult("", "en", False, "API 翻译失败：限流")):
            failed = engine.transcribe(b"audio", "en", translation_revision=1)
        self.assertEqual(failed.original, "Wait for me.")
        self.assertFalse(failed.translation_ready)
        engine.translator.translate.assert_not_called()

    def test_unexpected_provider_error_never_leaks_key_or_audio(self):
        engine = make_engine()
        engine.configure_translation("api", "https://example.invalid/v1", "model", "SECRET", True)
        with patch.object(engine._api_translator, "translate", side_effect=ValueError("SECRET private text")):
            with self.assertLogs("app.engine", "WARNING") as logs:
                result = engine.transcribe(b"private audio", "en", translation_revision=1)
        self.assertNotIn("SECRET", result.warning + repr(logs.output))
        self.assertNotIn("private text", result.warning + repr(logs.output))

    def test_configuration_is_atomic_requires_consent_and_redacts_status(self):
        engine = make_engine()
        for consent in (False, "true", 1):
            with self.assertRaises(ValueError):
                engine.configure_translation("api", "https://example.invalid/v1", "model", "SECRET", consent)
        self.assertEqual(engine.translation_status()["mode"], "local")
        applied = engine.configure_translation("api", "https://example.invalid/v1", "model", "SECRET", True)
        self.assertNotIn("SECRET", json.dumps(applied))
        previous = engine._api_translator
        with self.assertRaises(ValueError):
            engine.configure_translation("api", "http://example.invalid/v1", "model", "SECRET", True)
        self.assertIs(engine._api_translator, previous)
        engine.configure_translation("api", "https://example.invalid/v1/chat/completions", "model", None, True)
        self.assertEqual(engine._api_translator.settings.api_key, "SECRET")
        for url, model in (("https://other.invalid/v1", "model"), ("https://example.invalid/v1", "other")):
            with self.assertRaises(ValueError):
                engine.configure_translation("api", url, model, None, True)
        engine.configure_translation("local")
        self.assertIsNone(engine._api_translator)
        self.assertFalse(engine.translation_status()["has_api_key"])
        result = engine.transcribe(b"audio", "en")
        self.assertEqual(result.translation_mode, "local")
        self.assertEqual(result.translation, "本地译文")

    def test_connection_test_is_explicit_fixed_text_and_does_not_apply(self):
        engine = make_engine()
        with patch("app.engine.ApiTranslator.translate", return_value=TranslationResult("你好。", "en", True)) as translate:
            with self.assertRaises(ValueError):
                engine.test_translation_api("https://example.invalid/v1", "model", "SECRET")
            translate.assert_not_called()
            result = engine.test_translation_api("https://example.invalid/v1", "model", "SECRET", True)
        translate.assert_called_once_with("Hello.", "en", "zh")
        self.assertTrue(result["ok"])
        self.assertEqual(engine.translation_status()["mode"], "local")

    def test_stale_or_unbound_audio_never_reaches_api_or_recognition(self):
        engine = make_engine()
        self.assertEqual(engine.translation_status()["revision"], 0)
        engine.configure_translation("api", "https://example.invalid/v1", "model", "SECRET", True)
        self.assertEqual(engine.translation_status()["revision"], 1)
        with patch.object(engine._api_translator, "translate") as translate:
            for revision in (None, 0, -1, 2):
                with self.subTest(revision=revision), self.assertRaisesRegex(RuntimeError, "翻译设置"):
                    engine.transcribe(b"private audio", "en", translation_revision=revision)
            translate.assert_not_called()
            engine._model.transcribe.assert_not_called()
        engine.configure_translation("local")
        self.assertEqual(engine.translation_status()["revision"], 2)
        with self.assertRaisesRegex(RuntimeError, "翻译设置"):
            engine.transcribe(b"old cloud audio", "en", translation_revision=1)
        self.assertEqual(engine.transcribe(b"new audio", "en", translation_revision=2).translation_mode, "local")

    def test_failed_config_and_connection_test_keep_revision(self):
        engine = make_engine()
        with self.assertRaises(ValueError):
            engine.configure_translation("api", "http://example.invalid", "model", "", True)
        with patch("app.engine.ApiTranslator.translate", return_value=TranslationResult("你好", "en", True)):
            engine.test_translation_api("https://example.invalid/v1", "model", "", True)
        self.assertEqual(engine.translation_status()["revision"], 0)

    def test_unbound_local_request_waiting_for_lock_cannot_inherit_new_settings(self):
        engine = make_engine()
        entered, errors = threading.Event(), []
        lock = threading.RLock()

        class ObservedLock:
            acquire = lock.acquire
            release = lock.release

            def __enter__(self):
                entered.set()
                lock.acquire()

            def __exit__(self, *args):
                lock.release()

        engine._model_lock = ObservedLock()
        def transcribe():
            try:
                engine.transcribe(b"old local recording", "en")
            except RuntimeError as exc:
                errors.append(str(exc))

        lock.acquire()
        worker = threading.Thread(target=transcribe)
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            engine.configure_translation("api", "https://example.invalid/v1", "model", "", True)
            engine.configure_translation("local")
        finally:
            lock.release()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIn("翻译设置", errors[0])
        engine._model.transcribe.assert_not_called()

    def test_busy_inference_rejects_mode_switch_and_test(self):
        engine = make_engine()
        held, finish = threading.Event(), threading.Event()
        def worker():
            with engine._model_lock:
                held.set()
                finish.wait(3)
        thread = threading.Thread(target=worker)
        thread.start()
        try:
            self.assertTrue(held.wait(2))
            with self.assertRaises(RuntimeError):
                engine.configure_translation("local")
            with self.assertRaises(RuntimeError):
                engine.test_translation_api("https://example.invalid/v1", "model", "", True)
        finally:
            finish.set()
            thread.join(3)

    def test_release_keeps_explicit_session_config_but_new_engine_is_local(self):
        engine = make_engine()
        engine.configure_translation("api", "https://example.invalid/v1", "model", "SECRET", True)
        provider = engine._api_translator
        with patch.object(provider, "unload", return_value=False) as unload:
            engine.release()
        unload.assert_called_once_with()
        self.assertIs(engine._api_translator, provider)
        self.assertEqual(make_engine().translation_status()["mode"], "local")


if __name__ == "__main__":
    unittest.main()
