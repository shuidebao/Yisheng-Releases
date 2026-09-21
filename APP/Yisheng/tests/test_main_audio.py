from __future__ import annotations

import json
import unittest
from unittest.mock import Mock, patch

try:
    import fastapi  # noqa: F401
except ModuleNotFoundError:
    main = None
else:
    from app import main


@unittest.skipIf(main is None, "FastAPI is only included in the bundled desktop runtime")
class MainAudioTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def request(body: bytes, content_type: str = "audio/wav"):
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}
        return main.Request({"type": "http", "headers": [(b"content-type", content_type.encode())]}, receive)

    async def test_uploads_reach_worker_as_exact_bytes_without_temp_files(self):
        for content_type, language, source in (("audio/wav", "en", "en"), ("audio/webm", "auto", None)):
            with self.subTest(content_type=content_type):
                result = Mock()
                result.to_dict.return_value = {"original": "test", "timings_ms": {"recognition": 100}}
                audio = b"complete uploaded audio"
                with (
                    patch.object(main.engine, "transcribe", return_value=result) as transcribe,
                    patch("tempfile.NamedTemporaryFile", side_effect=AssertionError("must not create temp audio")),
                ):
                    response = await main.transcribe(self.request(audio, content_type), language, 2.5, "context", "zh")
                transcribe.assert_called_once_with(audio, source, 2.5, "context", "zh")
                self.assertEqual(json.loads(response.body), result.to_dict.return_value)

    async def test_korean_source_target_and_auto_reach_inference(self):
        for source, target in (("ko", "zh"), ("zh", "ko"), ("en", "ko"), ("auto", "ko")):
            with self.subTest(source=source, target=target):
                result = Mock()
                result.to_dict.return_value = {"original": "안녕하세요", "target_language": target}
                with patch.object(main.engine, "transcribe", return_value=result) as infer:
                    response = await main.transcribe(self.request(b"audio"), source, 1.0, "", target)
                infer.assert_called_once_with(b"audio", None if source == "auto" else source, 1.0, "", target)
                self.assertEqual(json.loads(response.body)["target_language"], target)

    async def test_korean_model_check_uses_existing_offline_route(self):
        with patch.object(main.engine.translator, "install_pair", return_value=[]) as check:
            result = await main.install_translation_model("zh", "ko")
        check.assert_called_once_with("zh", "ko")
        self.assertTrue(result["ok"])

    async def test_invalid_inputs_are_rejected_before_inference(self):
        cases = [(b"", "en", "zh", 400), (b"oversize", "en", "zh", 413),
                 (b"a", "xx", "zh", 400), (b"a", "en", "xx", 400)]
        for body, language, target, status in cases:
            with self.subTest(body=body, language=language, target=target):
                with patch.object(main, "MAX_AUDIO_BYTES", 4), patch.object(main.engine, "transcribe") as transcribe:
                    with self.assertRaises(main.HTTPException) as caught:
                        await main.transcribe(self.request(body), language, 1.0, "", target)
                self.assertEqual(caught.exception.status_code, status)
                transcribe.assert_not_called()

    async def test_inference_errors_keep_existing_http_status(self):
        for error, status in ((RuntimeError("not ready"), 503), (ValueError("bad audio"), 500)):
            with self.subTest(status=status):
                with patch.object(main.engine, "transcribe", side_effect=error), patch.object(main.logging, "exception"):
                    with self.assertRaises(main.HTTPException) as caught:
                        await main.transcribe(self.request(b"bad"), "en", 1.0, "", "zh")
                self.assertEqual(caught.exception.status_code, status)


if __name__ == "__main__":
    unittest.main()
