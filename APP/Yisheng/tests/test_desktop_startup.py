from __future__ import annotations

import inspect
import ast
import sys
import types
import unittest
from unittest.mock import Mock, patch

# GitHub Actions intentionally runs the lightweight source tests without the
# bundled desktop runtime. The tests below only exercise dependency-free
# startup control, so provide an import placeholder when uvicorn is absent.
try:
    import uvicorn  # noqa: F401
except ModuleNotFoundError:
    sys.modules["uvicorn"] = types.ModuleType("uvicorn")

from app.desktop import BACKEND_START_TIMEOUT_SECONDS, DesktopBridge, LocalBackend, wait_for_health, main


class OverlayStub:
    def __init__(self) -> None:
        self.updates: list[dict[str, object]] = []

    def update(self, **payload: object) -> None:
        self.updates.append(payload)


class DesktopStartupTests(unittest.TestCase):
    def test_backend_stop_waits_for_lifespan_before_discarding_owner(self) -> None:
        backend = LocalBackend(port=1)
        server = types.SimpleNamespace(started=True, should_exit=False)
        thread = Mock()
        thread.is_alive.side_effect = [True, False]
        backend._server, backend._thread = server, thread
        self.assertTrue(backend.stop())
        thread.join.assert_called_once_with(timeout=None)
        self.assertTrue(server.should_exit)
        self.assertIsNone(backend._server)
        self.assertIsNone(backend._thread)

    def test_bounded_stop_retains_live_backend_for_retry(self) -> None:
        backend = LocalBackend(port=1)
        server = types.SimpleNamespace(started=True, should_exit=False)
        thread = Mock()
        thread.is_alive.return_value = True
        backend._server, backend._thread = server, thread
        with self.assertLogs('yisheng.desktop', level='WARNING'):
            self.assertFalse(backend.stop(timeout=0.01))
        thread.join.assert_called_once_with(timeout=0.01)
        self.assertIs(backend._server, server)
        self.assertIs(backend._thread, thread)
        self.assertTrue(backend.running)
        with self.assertRaisesRegex(RuntimeError, '正在启动或退出'):
            backend.start()
        thread.is_alive.side_effect = [True, False]
        self.assertTrue(backend.stop())
        self.assertIsNone(backend._thread)

    def test_stopped_backend_can_be_stopped_again(self) -> None:
        backend = LocalBackend(port=1)
        self.assertTrue(backend.stop())
        self.assertTrue(backend.stop())
        self.assertFalse(backend.running)

    def test_health_timeout_uses_bounded_stop_before_reporting_failure(self) -> None:
        backend = LocalBackend(port=1)
        with (
            patch('app.desktop.uvicorn.Config', create=True),
            patch('app.desktop.uvicorn.Server', create=True),
            patch('app.desktop.threading.Thread') as thread,
            patch('app.desktop.wait_for_health', return_value=False),
            patch.object(backend, 'stop', return_value=False) as stop,
        ):
            thread.return_value.is_alive.return_value = True
            with self.assertRaisesRegex(RuntimeError, '超过'):
                backend.start(timeout=0.01)
        stop.assert_called_once_with(timeout=5.0)

    def test_desktop_does_not_repeat_pywebviews_global_exit(self) -> None:
        tree = ast.parse(inspect.getsource(main))
        repeated_exits = [node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "Exit" and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "Application"]
        self.assertEqual(repeated_exits, [])

    def test_startup_budget_allows_slow_first_runtime_initialization(self) -> None:
        default = inspect.signature(LocalBackend.start).parameters["timeout"].default
        self.assertEqual(default, BACKEND_START_TIMEOUT_SECONDS)
        self.assertGreaterEqual(default, 90.0)

    def test_health_wait_stops_immediately_if_backend_thread_exits(self) -> None:
        with patch("app.desktop.urllib.request.urlopen") as urlopen:
            self.assertFalse(
                wait_for_health(
                    "http://127.0.0.1:1",
                    timeout=BACKEND_START_TIMEOUT_SECONDS,
                    is_running=lambda: False,
                )
            )
        urlopen.assert_not_called()

    def test_overlay_only_renders_the_current_sentence(self) -> None:
        bridge = DesktopBridge()
        overlay = OverlayStub()
        bridge._native_overlay = overlay

        for number in range(1, 6):
            with self.subTest(sentence=number):
                current = {
                    "original": f"Sentence {number}.",
                    "translation": f"第 {number} 句。",
                    "meta": str(number),
                }
                self.assertEqual(bridge.update_overlay(current), {"ok": True})
                self.assertEqual(overlay.updates[-1], current)
                self.assertEqual(bridge.get_overlay_snapshot(), current)
                self.assertEqual(
                    bridge.get_overlay_state(),
                    {**current, "locked": False, "ui_language": "zh"},
                )
        self.assertEqual(len(overlay.updates), 5)

        # Showing an existing mini window re-renders only the latest sentence.
        bridge._render_overlay()
        self.assertEqual(overlay.updates[-1], current)

    def test_overlay_continuations_and_repetitions_replace_current_text(self) -> None:
        bridge = DesktopBridge()
        overlay = OverlayStub()
        bridge._native_overlay = overlay
        bridge.update_overlay({"original": "first", "translation": "第一句", "meta": "1"})
        revised = {"original": "first continued", "translation": "第一句修订", "meta": "2"}

        # Older frontends may still send the former queue flags. They must not
        # restore history or prevent the current sentence from being replaced.
        for replace_latest in (True, False):
            with self.subTest(replace_latest=replace_latest):
                self.assertEqual(bridge.update_overlay({
                    **revised,
                    "replace_latest": replace_latest,
                    "history": ["第一句"],
                    "history_count": 1,
                }), {"ok": True})
                self.assertEqual(overlay.updates[-1], revised)
                self.assertEqual(bridge.get_overlay_snapshot(), revised)
        self.assertEqual(len(overlay.updates), 3)

    def test_overlay_clear_removes_current_text_and_snapshot_is_a_copy(self) -> None:
        bridge = DesktopBridge()
        overlay = OverlayStub()
        bridge._native_overlay = overlay
        empty = {"original": "", "translation": "", "meta": ""}
        self.assertEqual(bridge.get_overlay_snapshot(), empty)
        current = {"original": "current", "translation": "当前句", "meta": "1"}
        bridge.update_overlay(current)
        snapshot = bridge.get_overlay_snapshot()
        snapshot["translation"] = "not current"
        self.assertEqual(bridge.get_overlay_snapshot(), current)

        self.assertEqual(bridge.clear_overlay(), {"ok": True})
        self.assertEqual(overlay.updates[-1], empty)
        self.assertEqual(bridge.get_overlay_snapshot(), empty)
        self.assertEqual(bridge.get_overlay_state(), {**empty, "locked": False, "ui_language": "zh"})
        bridge._render_overlay()
        self.assertEqual(overlay.updates[-1], empty)
        following = {"original": "next", "translation": "下一句", "meta": "2"}
        bridge.update_overlay(following)
        self.assertEqual(overlay.updates[-1], following)

if __name__ == "__main__":
    unittest.main()
