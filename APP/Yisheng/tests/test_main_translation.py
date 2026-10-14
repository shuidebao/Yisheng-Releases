from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import PropertyMock, patch

try:
    import fastapi  # noqa: F401
except ModuleNotFoundError:
    main = None
else:
    from app import main

from test_engine_translation_mode import make_engine
from app.translation import TranslationResult


@unittest.skipIf(main is None, "FastAPI is only included in the bundled desktop runtime")
class TranslationHttpTests(unittest.IsolatedAsyncioTestCase):
    async def request(self, path, data=None, *, host="127.0.0.1:8765", origin=None, extra_headers=(), method="POST", raw=None, query=""):
        body = raw if raw is not None else json.dumps(data).encode()
        headers = [(b"host", host.encode()), (b"content-type", b"application/json")]
        if origin is not None:
            headers.append((b"origin", origin.encode()))
        headers.extend(extra_headers)
        scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
                 "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
                 "root_path": "", "query_string": query.encode(), "http_version": "1.1", "headers": headers,
                 "server": ("127.0.0.1", 8765), "client": ("127.0.0.1", 2345)}
        sent, received = [], False
        finished = asyncio.Event()
        async def receive():
            nonlocal received
            if not received:
                received = True
                return {"type": "http.request", "body": body, "more_body": False}
            await finished.wait()
            return {"type": "http.disconnect"}
        async def send(message):
            sent.append(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                finished.set()
        await asyncio.wait_for(main.app(scope, receive, send), 5)
        status = next(item["status"] for item in sent if item["type"] == "http.response.start")
        content = b"".join(item.get("body", b"") for item in sent if item["type"] == "http.response.body")
        return status, content.decode()

    async def test_consent_config_status_test_and_clear_secret(self):
        engine = make_engine()
        config = {"mode": "api", "base_url": "https://example.invalid/v1", "model": "model", "api_key": "PRIVATE_KEY", "consent": True}
        with patch.object(main, "engine", engine), patch.object(type(main.system_audio), "running", new_callable=PropertyMock, return_value=False):
            code, _ = await self.request("/api/translation/config", {**config, "consent": False})
            self.assertEqual(code, 400)
            with patch("app.engine.ApiTranslator.translate", return_value=TranslationResult("你好。", "en", True)) as translate:
                code, body = await self.request("/api/translation/test", config)
                self.assertEqual(code, 200, body)
                self.assertEqual(engine.translation_status()["mode"], "local")
                translate.assert_called_once_with("Hello.", "en", "zh")
            code, body = await self.request("/api/translation/config", config, origin="http://127.0.0.1:8765")
            self.assertEqual(code, 200, body)
            self.assertNotIn("PRIVATE_KEY", body)
            code, body = await self.request("/api/status", method="GET")
            self.assertEqual(code, 200)
            self.assertNotIn("PRIVATE_KEY", body)
            self.assertEqual(json.loads(body)["translation"]["mode"], "api")
            code, body = await self.request("/api/translation/config", {"mode": "local"})
            self.assertEqual(code, 200)
            self.assertIsNone(engine._api_translator)

    async def test_validation_never_echoes_keys_even_for_malformed_json(self):
        for raw in (b'{"api_key":"PRIVATE_KEY",',
                    b'{"api_key":{"PRIVATE_KEY":true}}',
                    json.dumps({"api_key": "PRIVATE_KEY" * 500}).encode(),
                    b'{"mode":"PRIVATE_KEY"}'):
            for path in ("/api/translation/config", "/api/translation/test"):
                code, body = await self.request(path, raw=raw)
                self.assertEqual(code, 422, body)
                self.assertNotIn("PRIVATE_KEY", body)

    async def test_audio_requires_matching_applied_translation_revision(self):
        engine = make_engine()
        engine.configure_translation("api", "https://example.invalid/v1", "model", "PRIVATE_KEY", True)
        with patch.object(main, "engine", engine), patch.object(
            engine._api_translator, "translate", return_value=TranslationResult("等我。", "en", True)
        ) as translate:
            for query in ("language=en", "language=en&translation_revision=0"):
                code, body = await self.request("/api/transcribe", raw=b"audio", query=query)
                self.assertEqual(code, 503, body)
                self.assertNotIn("PRIVATE_KEY", body)
            translate.assert_not_called()
            engine._model.transcribe.assert_not_called()
            code, body = await self.request("/api/transcribe", raw=b"audio", query="language=en&translation_revision=1")
            self.assertEqual(code, 200, body)
            self.assertEqual(json.loads(body)["translation_mode"], "api")
            translate.assert_called_once_with("Wait for me.", "en", "zh")

    async def test_cross_origin_and_rebinding_are_blocked_before_mutation(self):
        cases = ({"host": "attacker.invalid:8765"}, {"origin": "https://attacker.invalid"},
                 {"origin": "null"}, {"origin": "http://127.0.0.1:9999"},
                 {"extra_headers": [(b"sec-fetch-site", b"cross-site")]})
        for path in ("/api/translation/config", "/api/translation/test", "/api/transcribe", "/api/status"):
            for headers in cases:
                code, _ = await self.request(path, {"mode": "local"}, **headers)
                self.assertEqual(code, 403, (path, headers))

    async def test_system_capture_prevents_switch_and_connection_test(self):
        with patch.object(type(main.system_audio), "running", new_callable=PropertyMock, return_value=True):
            with patch.object(main.engine, "configure_translation") as configure:
                code, _ = await self.request("/api/translation/config", {"mode": "local"})
                self.assertEqual(code, 409)
                configure.assert_not_called()
            with patch.object(main.engine, "test_translation_api") as test:
                code, _ = await self.request("/api/translation/test", {"mode": "api"})
                self.assertEqual(code, 409)
                test.assert_not_called()

    async def test_secret_requests_require_bounded_json(self):
        for path in ("/api/translation/config", "/api/translation/test"):
            code, body = await self.request(path, raw=b"PRIVATE_KEY" * 2000)
            self.assertEqual(code, 413)
            self.assertNotIn("PRIVATE_KEY", body)
            code, body = await self.request(path, raw=b"api_key=PRIVATE_KEY", extra_headers=[(b"content-type", b"text/plain")])
            self.assertEqual(code, 415)
            self.assertNotIn("PRIVATE_KEY", body)


if __name__ == "__main__":
    unittest.main()
