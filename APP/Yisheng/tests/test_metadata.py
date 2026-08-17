from __future__ import annotations

import re
import unittest
from pathlib import Path

import app
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
        self.assertEqual(
            _safe_filename("YiSheng-Setup-1.0.11.exe"),
            "YiSheng-Setup-1.0.11.exe",
        )
        self.assertGreater(_version_tuple("1.0.11"), _version_tuple("1.0.10"))

    def test_about_elements_exist(self) -> None:
        root = Path(__file__).resolve().parent.parent
        html = (root / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="aboutVersion"', html)
        self.assertIn('id="officialRepository"', html)
        self.assertIn("Huyuanhao", html)
        self.assertIsNotNone(re.search(r"Copyright\s+©\s+2026\s+Huyuanhao", html))


if __name__ == "__main__":
    unittest.main()
