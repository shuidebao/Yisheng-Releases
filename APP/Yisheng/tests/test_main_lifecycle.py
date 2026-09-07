from __future__ import annotations

import unittest
from unittest.mock import patch
from app.system_audio import AudioChunk

try:
    import fastapi  # noqa: F401
except ModuleNotFoundError:
    main = None
else:
    from app import main


@unittest.skipIf(main is None, "FastAPI is only included in the bundled desktop runtime")
class MainLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_system_chunk_exposes_capture_boundaries(self) -> None:
        chunk = AudioChunk(b"wave", 3.0, .2, 4, True, 7.4, 10.4)
        with patch.object(main.system_audio, "get_chunk", return_value=chunk):
            response = await main.system_audio_chunk(.05)
        self.assertEqual(response.headers["X-Audio-Sequence"], "4")
        self.assertEqual(response.headers["X-Audio-Continuation"], "1")
        self.assertEqual(response.headers["X-Audio-Started-At"], "7.400")
        self.assertEqual(response.headers["X-Audio-Ended-At"], "10.400")
        self.assertEqual(main.SystemAudioConfig().chunk_seconds, 8.0)

    async def test_startup_stays_lazy_and_shutdown_releases_models(self) -> None:
        with (
            patch.object(main.engine, "prepare") as prepare,
            patch.object(main.engine, "release", return_value={"ok": True}) as release,
            patch.object(main.system_audio, "stop", return_value={"ok": True}) as stop,
        ):
            async with main.lifespan(None):
                prepare.assert_not_called()
                release.assert_not_called()

        stop.assert_called_once_with()
        release.assert_called_once_with()

    async def test_clear_cache_releases_memory_before_disk_cache(self) -> None:
        with (
            patch.object(main.engine, "release", return_value={"released": True}) as release,
            patch.object(main, "clear_cache", return_value={"ok": True, "removed_bytes": 9}) as clear,
        ):
            result = await main.clear_app_cache()

        release.assert_called_once_with()
        clear.assert_called_once_with()
        self.assertTrue(result["memory_released"])
        self.assertEqual(result["removed_bytes"], 9)


if __name__ == "__main__":
    unittest.main()
