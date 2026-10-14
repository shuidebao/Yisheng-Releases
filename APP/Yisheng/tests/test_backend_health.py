from __future__ import annotations

import os
import sys
import threading
import types
import unittest
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import MagicMock, Mock, patch

# CI deliberately omits the bundled desktop/ML runtime. Health probing uses
# only the standard library, so an import placeholder is sufficient here.
try:
    import uvicorn  # noqa: F401
except ModuleNotFoundError:
    sys.modules["uvicorn"] = types.ModuleType("uvicorn")

from app.desktop import wait_for_health


@contextmanager
def local_http_server(
    status: int = 200,
    body: bytes = b'{"ok":true}',
    headers: dict[str, str] | None = None,
):
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(self.path)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.01},
        daemon=True,
    )
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
        if worker.is_alive():
            raise AssertionError("Local health-test HTTP server did not stop")


class AdvancingClock:
    """Bound even broken retry loops, without imposing real test delays."""

    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        self.now += 0.001
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def response_with(body: bytes, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.read.return_value = body
    response.__enter__.return_value = response
    return response


class BackendHealthTests(unittest.TestCase):
    def test_direct_loopback_health_is_ready(self) -> None:
        with local_http_server() as (url, requests):
            self.assertTrue(wait_for_health(url, timeout=2.0))
        self.assertEqual(requests, ["/api/health"])

    def test_health_bypasses_proxy_without_changing_global_network_settings(self) -> None:
        original_opener = urllib.request._opener
        original_environment = dict(os.environ)
        real_build_opener = urllib.request.build_opener
        with (
            local_http_server() as (url, health_requests),
            local_http_server(502, b"fake proxy rejection") as (proxy_url, proxy_requests),
            patch("urllib.request.getproxies", return_value={"http": proxy_url}),
            patch("urllib.request.proxy_bypass", return_value=False),
        ):
            # Establish that this setup would intercept the old default opener.
            with self.assertRaises(urllib.error.HTTPError) as intercepted:
                real_build_opener().open(f"{url}/api/health", timeout=2.0)
            self.assertEqual(intercepted.exception.code, 502)
            intercepted.exception.close()
            self.assertEqual(proxy_requests, [f"{url}/api/health"])
            self.assertEqual(health_requests, [])
            proxy_requests.clear()

            with (
                patch("urllib.request.build_opener", wraps=real_build_opener) as build_opener,
                patch("urllib.request.install_opener") as install_opener,
                patch("urllib.request.urlopen", side_effect=AssertionError("Global opener used")),
            ):
                self.assertTrue(wait_for_health(url, timeout=2.0))
            install_opener.assert_not_called()
            build_opener.assert_called_once()
            handlers = build_opener.call_args.args
            self.assertTrue(any(
                isinstance(handler, urllib.request.ProxyHandler) and handler.proxies == {}
                for handler in handlers
            ))
            self.assertEqual(proxy_requests, [])
            self.assertEqual(health_requests, ["/api/health"])
        self.assertIs(urllib.request._opener, original_opener)
        # Do not dump environment values (potential credentials) on failure.
        self.assertTrue(dict(os.environ) == original_environment, "Environment was changed")

    def test_connection_refused_is_retried_then_succeeds(self) -> None:
        opener = Mock()
        opener.open.side_effect = [
            urllib.error.URLError(ConnectionRefusedError("backend not listening yet")),
            response_with(b'{"ok":true}'),
        ]
        clock = AdvancingClock()
        with (
            patch("app.desktop.urllib.request.build_opener", return_value=opener),
            patch("app.desktop.time.monotonic", side_effect=clock.monotonic),
            patch("app.desktop.time.sleep", side_effect=clock.sleep) as sleep,
        ):
            self.assertTrue(wait_for_health("http://127.0.0.1:12345", timeout=1.0))
        self.assertEqual(opener.open.call_count, 2)
        sleep.assert_called_once()
        self.assertGreater(sleep.call_args.args[0], 0)

    def test_health_does_not_follow_redirect_to_another_endpoint(self) -> None:
        with (
            local_http_server() as (target_url, target_requests),
            local_http_server(302, b"", {"Location": target_url}) as (url, redirect_requests),
            self.assertLogs("yisheng.desktop", level="WARNING") as captured,
        ):
            self.assertFalse(wait_for_health(url, timeout=0.25))
        self.assertEqual(target_requests, [])
        self.assertGreater(len(redirect_requests), 0)
        self.assertTrue(all(path == "/api/health" for path in redirect_requests))
        self.assertIn("302", captured.records[-1].getMessage())

    def test_final_failure_reports_endpoint_attempts_and_last_error_once(self) -> None:
        url = "http://127.0.0.1:12345"
        opener = Mock()
        opener.open.side_effect = urllib.error.URLError("test connection refused")
        clock = AdvancingClock()
        with (
            patch("app.desktop.urllib.request.build_opener", return_value=opener),
            patch("app.desktop.time.monotonic", side_effect=clock.monotonic),
            patch("app.desktop.time.sleep", side_effect=clock.sleep),
            self.assertLogs("yisheng.desktop", level="WARNING") as captured,
        ):
            self.assertFalse(wait_for_health(url, timeout=0.25))
        self.assertEqual(len(captured.records), 1)
        message = captured.records[0].getMessage()
        self.assertIn(f"{url}/api/health", message)
        self.assertIn("attempt", message.lower())
        self.assertIn("last_error", message)
        self.assertIn("test connection refused", message)
        self.assertGreater(opener.open.call_count, 1)

    def test_invalid_or_not_ready_payloads_wait_between_retries(self) -> None:
        for body in (b"not json", b"null", b"[]", b'"ok"', b'{"ok":false}', b'{"ok":1}'):
            with self.subTest(body=body):
                opener = Mock()
                opener.open.return_value = response_with(body)
                clock = AdvancingClock()
                with (
                    patch("app.desktop.urllib.request.build_opener", return_value=opener),
                    patch("app.desktop.time.monotonic", side_effect=clock.monotonic),
                    patch("app.desktop.time.sleep", side_effect=clock.sleep) as sleep,
                    self.assertLogs("yisheng.desktop", level="WARNING"),
                ):
                    self.assertFalse(wait_for_health("http://127.0.0.1:12345", timeout=0.25))
                self.assertGreater(sleep.call_count, 0)
                self.assertLessEqual(opener.open.call_count, 4)
                self.assertTrue(all(call.args[0] > 0 for call in sleep.call_args_list))

    def test_non_200_response_cannot_mark_backend_ready(self) -> None:
        opener = Mock()
        opener.open.return_value = response_with(b'{"ok":true}', status=503)
        clock = AdvancingClock()
        with (
            patch("app.desktop.urllib.request.build_opener", return_value=opener),
            patch("app.desktop.time.monotonic", side_effect=clock.monotonic),
            patch("app.desktop.time.sleep", side_effect=clock.sleep) as sleep,
            self.assertLogs("yisheng.desktop", level="WARNING"),
        ):
            self.assertFalse(wait_for_health("http://127.0.0.1:12345", timeout=0.25))
        self.assertGreater(sleep.call_count, 0)

    def test_ended_backend_does_not_send_request_or_wait(self) -> None:
        opener = Mock()
        with (
            patch("app.desktop.urllib.request.build_opener", return_value=opener),
            patch("app.desktop.time.sleep") as sleep,
        ):
            self.assertFalse(wait_for_health(
                "http://127.0.0.1:12345", timeout=120.0, is_running=lambda: False,
            ))
        opener.open.assert_not_called()
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
