from __future__ import annotations

import re
import unittest
from pathlib import Path

import app
from app.config import HardwareInfo, recommended_profile
from app.updater import _safe_filename, _version_tuple


class ProjectMetadataTests(unittest.TestCase):
    def test_version_comes_from_version_file(self) -> None:
        root = Path(__file__).resolve().parent.parent
        self.assertEqual(app.__version__, (root / "VERSION").read_text(encoding="utf-8").strip())
        self.assertRegex(app.__version__, r"^\d+\.\d+\.\d+$")

    def test_developer_and_repository_are_declared(self) -> None:
        self.assertEqual(app.DEVELOPER, "Huyuanhao")
        self.assertEqual(
            app.OFFICIAL_REPOSITORY,
            "https://github.com/shuidebao/Yisheng-Releases",
        )

    def test_standard_installer_name_is_update_safe(self) -> None:
        filename = f"YiSheng-Setup-{app.__version__}.exe"
        self.assertEqual(
            _safe_filename(filename),
            filename,
        )
        self.assertGreater(_version_tuple(app.__version__), _version_tuple("1.0.11"))

    def test_installer_shortcuts_are_locale_safe_and_nonfatal(self) -> None:
        repository = Path(__file__).resolve().parents[3]
        source = (repository / "installer" / "OfflineInstaller.cs").read_text(encoding="utf-8")
        self.assertIn('SpecialFolder.Programs), "Yisheng"', source)
        self.assertNotIn('SpecialFolder.Programs), "译声"', source)
        self.assertIn("string shortcutWarning = createShortcuts ? CreateShortcuts(target) : null;", source)
        self.assertIn("UseShellExecute = false", source)

    def test_about_elements_exist(self) -> None:
        root = Path(__file__).resolve().parent.parent
        html = (root / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="aboutVersion"', html)
        self.assertIn('id="officialRepository"', html)
        self.assertIn("Huyuanhao", html)
        self.assertIsNotNone(re.search(r"Copyright\s+©\s+2026\s+Huyuanhao", html))

    def test_chinese_english_interface_switch_is_discoverable(self) -> None:
        root = Path(__file__).resolve().parent.parent
        html = (root / "static" / "index.html").read_text(encoding="utf-8")
        script = (root / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="languageToggle"', html)
        self.assertIn('data-ui-language="zh"', html)
        self.assertIn('data-ui-language="en"', html)
        self.assertIn("🇨🇳", html)
        self.assertIn(">中文</strong>", html)
        self.assertIn("🇺🇸", html)
        self.assertIn(">English</strong>", html)
        self.assertNotIn("\ufffd", html)
        self.assertIn('localStorage.setItem("yisheng-ui-language"', script)
        self.assertIn("set_ui_language", script)

    def test_default_cpu_profile_uses_low_latency_chunks(self) -> None:
        hardware = HardwareInfo("Windows", "CPU", 16.0, 8.0, None, None, False)
        self.assertEqual(recommended_profile(hardware)["chunk_seconds"], 1.8)

    def test_ready_gpu_profile_uses_faster_rolling_chunks(self) -> None:
        hardware = HardwareInfo("Windows", "CPU", 16.0, 8.0, "GPU", 8192, True)
        self.assertEqual(recommended_profile(hardware)["chunk_seconds"], 1.4)


if __name__ == "__main__":
    unittest.main()
