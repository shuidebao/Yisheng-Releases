from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app.cache as cache


class CacheManagementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.sandbox = Path(self.temp.name)
        self.root = self.sandbox / "app"
        self.model_root = self.root / ".models"
        self.whisper_root = self.model_root / "whisper"
        self.argos_state = self.model_root / "argos-state"
        self.webview_profile = self.model_root / "webview-profile"
        self.marker = self.model_root / "clear-webview-cache"
        self.temp_audio_root = self.sandbox / "temp"
        self.temp_audio_root.mkdir(parents=True)

        patchers = (
            patch.object(cache, "ROOT", self.root),
            patch.object(cache, "MODEL_ROOT", self.model_root),
            patch.object(cache, "WHISPER_MODEL_ROOT", self.whisper_root),
            patch.object(cache, "ARGOS_STATE_ROOT", self.argos_state),
            patch.object(cache, "WEBVIEW_PROFILE", self.webview_profile),
            patch.object(cache, "WEBVIEW_CLEAR_MARKER", self.marker),
            patch.object(cache, "ALLOWED_MODELS", set()),
            patch.object(cache.tempfile, "gettempdir", return_value=str(self.temp_audio_root)),
        )
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def _write(path: Path, size: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)

    def test_clear_cache_removes_immediate_items_then_webview_on_restart(self) -> None:
        audio = self.temp_audio_root / "yisheng-audio-stale.wav"
        old_log = self.root / "logs" / "desktop.log.1"
        argos_cache = self.argos_state / "cache" / "tokens.bin"
        browser_cache = self.webview_profile / "Cache" / "data.bin"
        code_cache = self.webview_profile / "Code Cache" / "script.bin"
        for path, size in ((audio, 3), (old_log, 4), (argos_cache, 5), (browser_cache, 6), (code_cache, 7)):
            self._write(path, size)

        before = cache.cache_status()
        self.assertEqual(before["immediate_cache_bytes"], 12)
        self.assertEqual(before["webview_cache_bytes"], 13)
        self.assertEqual(before["cache_bytes"], 25)

        cleared = cache.clear_cache()
        self.assertEqual(cleared["removed_bytes"], 12)
        self.assertEqual(cleared["pending_restart_bytes"], 13)
        self.assertTrue(cleared["restart_required"])
        self.assertTrue(self.marker.is_file())
        self.assertFalse(audio.exists())
        self.assertFalse(old_log.exists())
        self.assertFalse(argos_cache.exists())
        self.assertTrue(browser_cache.is_file())

        restarted = cache.clear_webview_cache_on_start()
        self.assertEqual(restarted["removed_bytes"], 13)
        self.assertEqual(restarted["skipped_items"], 0)
        self.assertFalse(self.marker.exists())
        self.assertFalse(browser_cache.exists())
        self.assertFalse(code_cache.exists())
        self.assertEqual(cache.cache_status()["cache_bytes"], 0)

    def test_locked_cache_item_is_reported_for_retry(self) -> None:
        locked = self.argos_state / "cache" / "busy.bin"
        self._write(locked, 8)

        with patch.object(cache.shutil, "rmtree", side_effect=OSError("busy")):
            result = cache.clear_cache()

        self.assertEqual(result["removed_bytes"], 0)
        self.assertEqual(result["skipped_items"], 1)
        self.assertTrue(locked.is_file())
        self.assertEqual(result["immediate_cache_bytes"], 8)

    def test_downloaded_model_files_are_preserved(self) -> None:
        model_dir = self.whisper_root / "base"
        model_file = model_dir / "model.bin"
        model_metadata = model_dir / ".cache" / "metadata.json"
        self._write(model_file, 11)
        self._write(model_metadata, 5)

        with (
            patch.object(cache, "ALLOWED_MODELS", {"base"}),
            patch.object(cache, "model_ready", return_value=True),
            patch.object(cache, "model_directory", return_value=model_dir),
        ):
            result = cache.clear_cache()

        self.assertTrue(result["models_preserved"])
        self.assertTrue(model_file.is_file())
        self.assertFalse(model_metadata.exists())


if __name__ == "__main__":
    unittest.main()