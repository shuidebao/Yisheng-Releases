from __future__ import annotations

import inspect
import sys
import types
import unittest
from unittest.mock import patch

# GitHub Actions intentionally runs the lightweight source tests without the
# bundled desktop runtime. The tests below only exercise dependency-free
# startup control, so provide an import placeholder when uvicorn is absent.
try:
    import uvicorn  # noqa: F401
except ModuleNotFoundError:
    sys.modules["uvicorn"] = types.ModuleType("uvicorn")

from app.desktop import BACKEND_START_TIMEOUT_SECONDS, DesktopBridge, LocalBackend, wait_for_health


class OverlayStub:
    def __init__(self) -> None:
        self.updates: list[dict[str, object]] = []

    def update(self, **payload: object) -> None:
        self.updates.append(payload)


class DesktopStartupTests(unittest.TestCase):
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

    def test_overlay_scrolls_four_sentences_and_replaces_continuations(self) -> None:
        bridge = DesktopBridge()
        overlay = OverlayStub()
        bridge._native_overlay = overlay

        self.assertEqual(
            bridge.update_overlay({"original": "first", "translation": "第一句", "meta": "1"})["history_count"],
            1,
        )
        self.assertEqual(
            bridge.update_overlay({
                "original": "first continued",
                "translation": "第一句修订",
                "meta": "1",
                "replace_latest": True,
            })["history_count"],
            1,
        )
        self.assertEqual(overlay.updates[-1]["history"], ["第一句修订"])

        bridge.update_overlay({"original": "second", "translation": "第二句", "meta": "2"})
        bridge.update_overlay({"original": "third", "translation": "第三句", "meta": "3"})
        bridge.update_overlay({"original": "fourth", "translation": "第四句", "meta": "4"})
        self.assertEqual(
            overlay.updates[-1]["history"],
            ["第一句修订", "第二句", "第三句", "第四句"],
        )

        result = bridge.update_overlay({"original": "fifth", "translation": "第五句", "meta": "5"})
        self.assertEqual(result["history_count"], 4)
        self.assertEqual(
            overlay.updates[-1]["history"],
            ["第二句", "第三句", "第四句", "第五句"],
        )

        bridge.clear_overlay()
        self.assertEqual(overlay.updates[-1]["history"], [])
        self.assertEqual(bridge.get_overlay_state()["history_count"], 0)

if __name__ == "__main__":
    unittest.main()
