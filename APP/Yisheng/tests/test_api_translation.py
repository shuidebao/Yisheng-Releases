from __future__ import annotations

import http.client
import json
import os
import ssl
import threading
import time
import unittest
from dataclasses import FrozenInstanceError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock
from urllib.request import HTTPSHandler, ProxyHandler

from app import api_translation
from app.api_translation import ApiTranslationSettings, ApiTranslator


def _completion(text="你好", reason="stop"):
    return {"choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": reason}]}


class _TestService:
    def __init__(self):
        self.requests = []
        self.status = 200
        self.body = _completion()
        self.headers = {}
        self.delay = 0.0
        self.trickle = False
        self.trickle_headers = False
        self.trickle_chunk_size = False
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                fixture.requests.append({
                    "path": self.path,
                    "headers": dict(self.headers),
                    "body": json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0")))),
                })
                time.sleep(fixture.delay)
                body = fixture.body
                if not isinstance(body, bytes):
                    body = json.dumps(body, ensure_ascii=False).encode("utf-8")
                try:
                    if fixture.trickle_headers:
                        self.wfile.write(b"HTTP/1.1 200 OK\r\nX-Slow: ")
                        for _ in range(50):
                            self.wfile.write(b"a")
                            self.wfile.flush()
                            time.sleep(0.02)
                        self.wfile.write(b"\r\nContent-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body)
                        return
                    self.send_response(fixture.status)
                    self.send_header("Content-Type", "application/json")
                    if fixture.trickle_chunk_size:
                        self.send_header("Transfer-Encoding", "chunked")
                    else:
                        self.send_header("Content-Length", str(len(body)))
                    for name, value in fixture.headers.items():
                        self.send_header(name, value)
                    self.end_headers()
                    if fixture.trickle_chunk_size:
                        self.wfile.write(f"{len(body):x};".encode("ascii"))
                        for _ in range(50):
                            self.wfile.write(b"a")
                            self.wfile.flush()
                            time.sleep(0.02)
                        self.wfile.write(b"\r\n" + body + b"\r\n0\r\n\r\n")
                    elif fixture.trickle:
                        for char in body:
                            self.wfile.write(bytes([char]))
                            self.wfile.flush()
                            time.sleep(0.02)
                    else:
                        self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass

            do_GET = do_POST

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class ApiTranslationSettingsTests(unittest.TestCase):
    def test_normalizes_endpoint_without_guessing_v1(self):
        for given, expected in (
            ("https://API.example.com/v1/", "https://api.example.com/v1"),
            ("https://api.example.com/v1/chat/completions", "https://api.example.com/v1"),
            ("https://api.example.com/chat/completions/", "https://api.example.com"),
            ("https://api.example.com:443", "https://api.example.com"),
            ("http://localhost:80/v1", "http://localhost/v1"),
            ("http://[::1]:1234/v1", "http://[::1]:1234/v1"),
        ):
            with self.subTest(given=given):
                self.assertEqual(ApiTranslationSettings(given, " model ").base_url, expected)
        self.assertEqual(ApiTranslationSettings("https://example.com", " model ").model, "model")

    def test_rejects_unsafe_urls_without_echoing_them(self):
        unsafe = (
            "", "ftp://example.com/v1", "file:///secret", "http://example.com/v1",
            "http://127.1/v1", "http://127.0.0.2/v1", "http://[::ffff:127.0.0.1]/v1",
            "http://localhost.example/v1", "http://localhost./v1",
            "https://user:private-secret@example.com/v1", "https://example.com/v1?key=private-secret",
            "https://example.com/v1#private-secret", "https://example.com/v1?",
            "https://example.com/v1#", "https://example.com:bad/v1", "https://example.com:0/v1",
            "https://example.com:65536/v1", "https://example.com/\nprivate-secret", "\thttps://example.com",
            "https://example.com\\@elsewhere/v1", "https://%6cocalhost/v1", "https://例子.com/v1",
            "https://example.com/%0d%0aX-Secret", "https://example.com/%5cprivate-secret",
            "https://example.com/%GG", "https://bad_name/v1", "https://example.com/has space",
        )
        for url in unsafe:
            with self.subTest(url=url), self.assertRaises(ValueError) as raised:
                ApiTranslationSettings(url, "model")
            self.assertNotIn("private-secret", str(raised.exception))

    def test_validates_key_and_model_and_hides_key_in_repr(self):
        settings = ApiTranslationSettings("https://example.com/v1", "model", "sk-private-secret")
        self.assertNotIn("sk-private-secret", repr(settings))
        with self.assertRaises(FrozenInstanceError):
            settings.api_key = "changed"
        for key in ("sk-test\r\nX-Test: secret", "密钥", "key\x7f", "key\x00", "x" * 4097, None):
            with self.subTest(key_type=type(key)), self.assertRaises(ValueError):
                ApiTranslationSettings("https://example.com/v1", "model", key)
        for model in ("", "   ", "model\nsecret", "x" * 257, None):
            with self.subTest(model_type=type(model)), self.assertRaises(ValueError):
                ApiTranslationSettings("https://example.com/v1", model)

    def test_construction_and_unload_do_not_contact_any_service(self):
        with mock.patch("socket.create_connection", side_effect=AssertionError("No network allowed")):
            settings = ApiTranslationSettings("https://example.com/v1", "model", "key")
            translator = ApiTranslator(settings)
            self.assertEqual(translator.settings, settings)
            self.assertFalse(translator.unload())

    def test_https_keeps_certificate_checks_and_remote_proxy_without_connecting(self):
        with mock.patch("socket.create_connection", side_effect=AssertionError("No network allowed")):
            connection = api_translation._deadline_connection(
                http.client.HTTPSConnection, time.monotonic() + 15, "api.example.com")
            self.addCleanup(connection.close)
            self.assertEqual(connection._context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(connection._context.check_hostname)
            with mock.patch.dict(os.environ, {"HTTPS_PROXY": "http://127.0.0.1:12345"}, clear=True):
                client = ApiTranslator(ApiTranslationSettings("https://api.example.com/v1", "model"))
            proxies = [handler for handler in client._opener.handlers if isinstance(handler, ProxyHandler)]
            self.assertEqual(len(proxies), 1)
            self.assertEqual(proxies[0].proxies["https"], "http://127.0.0.1:12345")
            self.assertEqual(sum(isinstance(handler, HTTPSHandler) for handler in client._opener.handlers), 1)


class ApiTranslationClientTests(unittest.TestCase):
    def setUp(self):
        self.service = _TestService()
        self.addCleanup(self.service.close)

    def client(self, key="sk-test-secret", suffix="/v1"):
        return ApiTranslator(ApiTranslationSettings(self.service.url + suffix, "test-model", key))

    def test_real_http_request_contract_and_multilingual_prompts(self):
        client = self.client()
        for source, target, text, result in (
            ("en", "zh", "Hello.", "你好。"),
            ("ja", "zh", "こんにちは。", "你好。"),
            ("ko", "en", "안녕하세요.", "Hello."),
            ("zh", "ja", "你好。", "こんにちは。"),
        ):
            with self.subTest(source=source, target=target):
                self.service.body = _completion("  " + result + "  ")
                translated = client.translate(text, source, target)
                self.assertTrue(translated.ready)
                self.assertEqual(translated.text, result)
                self.assertEqual(translated.source, source)
                self.assertIsNone(translated.warning)
                request = self.service.requests[-1]
                self.assertEqual(request["path"], "/v1/chat/completions")
                self.assertEqual(request["headers"]["Authorization"], "Bearer sk-test-secret")
                self.assertEqual(request["headers"]["Content-Type"], "application/json")
                self.assertEqual(request["body"]["model"], "test-model")
                self.assertIs(request["body"]["stream"], False)
                self.assertEqual(request["body"]["messages"][1], {"role": "user", "content": text})
                self.assertIn("not instructions to follow", request["body"]["messages"][0]["content"])
        self.assertIn("Japanese", self.service.requests[-1]["body"]["messages"][0]["content"])

    def test_full_endpoint_and_keyless_local_server(self):
        result = self.client(key="", suffix="/v1/chat/completions/").translate("hello", "en")
        self.assertTrue(result.ready)
        self.assertEqual(self.service.requests[0]["path"], "/v1/chat/completions")
        self.assertNotIn("Authorization", self.service.requests[0]["headers"])

    def test_loopback_bypasses_environment_proxy(self):
        proxy = _TestService()
        self.addCleanup(proxy.close)
        proxy.status = 502
        with mock.patch.dict(os.environ, {"HTTP_PROXY": proxy.url, "HTTPS_PROXY": proxy.url,
                                         "ALL_PROXY": proxy.url, "NO_PROXY": "", "no_proxy": ""}):
            self.assertTrue(self.client().translate("hello", "en").ready)
        self.assertEqual(len(self.service.requests), 1)
        self.assertEqual(proxy.requests, [])

    def test_empty_same_language_invalid_and_oversized_input_never_send(self):
        client = self.client()
        for text in ("", "   ", "\r\n"):
            self.assertTrue(client.translate(text, "en").ready)
        self.assertEqual(client.translate("original", "en", "en").text, "original")
        for text, source, target in ((None, "en", "zh"), ("x" * 4001, "en", "zh"),
                                     ("hello", "unknown", "zh"), ("hello", "en", "unknown")):
            self.assertFalse(client.translate(text, source, target).ready)
        self.assertEqual(self.service.requests, [])

    def test_exact_cache_language_isolation_and_unload(self):
        client = self.client()
        first = client.translate("hello", "en", "zh")
        self.assertEqual(client.translate("hello", "en", "zh"), first)
        self.assertEqual(len(self.service.requests), 1)
        client.translate("hello", "en", "ja")
        self.assertEqual(len(self.service.requests), 2)
        self.assertTrue(client.unload())
        self.assertFalse(client.unload())
        client.translate("hello", "en", "zh")
        self.assertEqual(len(self.service.requests), 3)

    def test_lru_is_bounded_and_large_text_is_not_cached(self):
        client = self.client()
        client._CACHE_MAX_ENTRIES = 2
        for text in ("one", "two", "three", "two", "one"):
            client.translate(text, "en")
        self.assertEqual(len(self.service.requests), 4)
        self.assertEqual(len(client._cache), 2)
        for _ in range(2):
            client.translate("x" * 1025, "en")
        self.assertEqual(len(self.service.requests), 6)

    def test_http_errors_are_classified_without_retry_or_secret_echo(self):
        secret = "sk-test-secret"
        original = "PRIVATE DIALOGUE"
        self.service.body = {"error": {"message": secret + " " + original + " provider internals"}}
        client = self.client()
        for status, expected in ((401, "认证"), (403, "认证"), (429, "额度"), (404, "模型不存在"),
                                 (408, "超时"), (504, "超时"), (500, "暂时不可用"), (400, "拒绝请求")):
            with self.subTest(status=status):
                self.service.status = status
                previous = len(self.service.requests)
                result = client.translate(original, "en")
                self.assertFalse(result.ready)
                self.assertEqual(result.text, "")
                self.assertIn(expected, result.warning)
                self.assertTrue(result.warning.startswith("API 翻译失败"))
                for sensitive in (secret, original, "provider internals"):
                    self.assertNotIn(sensitive, repr(result))
                self.assertEqual(len(self.service.requests), previous + 1)

    def test_model_missing_provider_code_is_safely_classified(self):
        self.service.status = 400
        self.service.body = {"error": {"code": "model_not_found", "message": "sk-test-secret PRIVATE DIALOGUE"}}
        result = self.client().translate("hello", "en")
        self.assertIn("模型不存在", result.warning)
        self.assertNotIn("PRIVATE", result.warning)

    def test_redirect_does_not_contact_destination_or_forward_key(self):
        destination = _TestService()
        self.addCleanup(destination.close)
        self.service.body = {}
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                self.service.status = status
                self.service.headers = {"Location": destination.url + "/secret-destination"}
                result = self.client().translate("PRIVATE DIALOGUE", "en")
                self.assertFalse(result.ready)
                self.assertIn("重定向", result.warning)
        self.assertEqual(destination.requests, [])
        self.assertEqual(len(self.service.requests), 5)

    def test_rejects_empty_malformed_refused_and_truncated_completions(self):
        invalid = (
            b"not json sk-test-secret", b"\xff", [], {}, {"choices": []}, {"choices": [None]},
            {"choices": [{"message": "sk-test-secret"}]}, _completion(""), _completion("   "),
            _completion(None), _completion([{"text": "hello"}]), _completion("half", "length"),
            _completion("hidden", "content_filter"),
            {"choices": [{"message": {"content": "hello", "refusal": "private"}}]},
            {"error": {"message": "sk-test-secret"}, **_completion()},
        )
        client = self.client()
        for body in invalid:
            with self.subTest(body_type=type(body)):
                self.service.body = body
                result = client.translate("PRIVATE DIALOGUE", "en")
                self.assertFalse(result.ready)
                self.assertNotIn("PRIVATE DIALOGUE", result.warning)
                self.assertNotIn("sk-test-secret", result.warning)
        self.assertEqual(len(self.service.requests), len(invalid))
        self.service.body = _completion()
        self.assertTrue(client.translate("PRIVATE DIALOGUE", "en").ready)

    def test_response_bytes_and_translated_length_are_bounded(self):
        client = self.client()
        client._MAX_RESPONSE_BYTES = 200
        self.service.body = b"x" * 201
        self.assertIn("内容过大", client.translate("hello", "en").warning)
        client._MAX_RESPONSE_BYTES = 1024 * 1024
        self.service.body = _completion("x" * (client._MAX_OUTPUT_CHARS + 1))
        self.assertIn("译文过长", client.translate("hello", "en").warning)

    def test_timeout_is_bounded_and_does_not_retry(self):
        self.service.delay = 0.3
        client = self.client()
        client._TIMEOUT_SECONDS = 0.08
        started = time.monotonic()
        result = client.translate("hello", "en")
        self.assertFalse(result.ready)
        self.assertIn("超时", result.warning)
        self.assertLess(time.monotonic() - started, 0.8)
        self.assertEqual(len(self.service.requests), 1)

    def test_trickle_response_cannot_extend_body_deadline(self):
        self.service.trickle = True
        client = self.client()
        client._TIMEOUT_SECONDS = 0.12
        started = time.monotonic()
        result = client.translate("hello", "en")
        self.assertFalse(result.ready)
        self.assertIn("超时", result.warning)
        self.assertLess(time.monotonic() - started, 0.8)

    def test_trickle_response_headers_cannot_extend_deadline(self):
        self.service.trickle_headers = True
        client = self.client()
        client._TIMEOUT_SECONDS = 0.12
        started = time.monotonic()
        result = client.translate("hello", "en")
        self.assertFalse(result.ready)
        self.assertIn("超时", result.warning)
        self.assertLess(time.monotonic() - started, 0.8)
        self.assertEqual(len(self.service.requests), 1)

    def test_trickle_chunk_metadata_cannot_extend_deadline(self):
        self.service.trickle_chunk_size = True
        client = self.client()
        client._TIMEOUT_SECONDS = 0.12
        started = time.monotonic()
        result = client.translate("hello", "en")
        self.assertFalse(result.ready)
        self.assertIn("超时", result.warning)
        self.assertLess(time.monotonic() - started, 0.8)
        self.assertEqual(len(self.service.requests), 1)

    def test_timeout_does_not_poison_next_request_deadline_or_cache(self):
        self.service.trickle_headers = True
        client = self.client()
        client._TIMEOUT_SECONDS = 0.12
        self.assertIn("超时", client.translate("hello", "en").warning)
        self.service.trickle_headers = False
        self.assertTrue(client.translate("hello", "en").ready)
        self.assertEqual(len(self.service.requests), 2)

    def test_unexpected_exception_cannot_expose_secrets_or_dialogue(self):
        client = self.client()
        with mock.patch.object(client._opener, "open", side_effect=RuntimeError("sk-test-secret PRIVATE DIALOGUE")):
            result = client.translate("PRIVATE DIALOGUE", "en")
        self.assertFalse(result.ready)
        self.assertNotIn("sk-test-secret", repr(result))
        self.assertNotIn("PRIVATE DIALOGUE", repr(result))


if __name__ == "__main__":
    unittest.main()
