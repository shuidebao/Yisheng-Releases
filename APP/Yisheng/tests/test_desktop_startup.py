from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from app.desktop import BACKEND_START_TIMEOUT_SECONDS, LocalBackend, wait_for_health


class DesktopStartupTests(unittest.TestCase):
    def test_cold_start_budget_allows_slow_first_model_load(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
