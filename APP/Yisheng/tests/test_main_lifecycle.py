from __future__ import annotations

import unittest
from unittest.mock import patch

try:
    import fastapi  # noqa: F401
except ModuleNotFoundError:
    main = None
else:
    from app import main


@unittest.skipIf(main is None, "FastAPI is only included in the bundled desktop runtime")
class MainLifecycleTests(unittest.IsolatedAsyncioTestCase):
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