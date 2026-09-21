from __future__ import annotations

import itertools
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import native_overlay


class OverlayPresentationTests(unittest.TestCase):
    SIZES = tuple(itertools.product((480, 760, 920, 1800), (300, 360, 700)))
    REGIONS = ("original_label", "original", "translation_label", "translation", "meta")

    def test_content_regions_stay_inside_supported_window_sizes(self):
        for (width, height), locked in itertools.product(self.SIZES, (False, True)):
            with self.subTest(width=width, height=height, locked=locked):
                layout = native_overlay.subtitle_layout(width, height, locked)
                self.assertEqual(set(layout), set(self.REGIONS))
                for name, rectangle in layout.items():
                    with self.subTest(region=name):
                        self.assertEqual(len(rectangle), 4)
                        self.assertTrue(all(math.isfinite(value) for value in rectangle))
                        x, y, region_width, region_height = rectangle
                        self.assertGreaterEqual(x, 0)
                        self.assertGreaterEqual(y, 0)
                        self.assertGreater(region_width, 0)
                        self.assertGreater(region_height, 0)
                        self.assertLessEqual(x + region_width, width)
                        self.assertLessEqual(y + region_height, height)

    def test_labels_text_and_footer_have_distinct_vertical_space(self):
        for (width, height), locked in itertools.product(self.SIZES, (False, True)):
            with self.subTest(width=width, height=height, locked=locked):
                layout = native_overlay.subtitle_layout(width, height, locked)
                for upper, lower in zip(self.REGIONS, self.REGIONS[1:]):
                    self.assertLessEqual(
                        layout[upper][1] + layout[upper][3], layout[lower][1],
                        f"{upper} overlaps {lower}",
                    )
                # The translation remains the main reading area, allowing a
                # slightly shorter box in the smallest supported window.
                self.assertGreaterEqual(layout["translation"][3], layout["original"][3] * 0.75)

    def test_locked_layout_reserves_space_for_unlock_control(self):
        for width, height in self.SIZES:
            with self.subTest(width=width, height=height):
                layout = native_overlay.subtitle_layout(width, height, True)
                self.assertGreaterEqual(min(region[1] for region in layout.values()), 40)

    def test_default_background_is_readable_but_not_opaque(self):
        self.assertEqual(native_overlay.DEFAULT_TRANSPARENCY, 28)
        self.assertGreater(native_overlay.DEFAULT_TRANSPARENCY, 0)
        self.assertLess(native_overlay.DEFAULT_TRANSPARENCY, 100)

    def test_missing_config_uses_light_translation_default_without_writing_config(self):
        with tempfile.TemporaryDirectory() as directory:
            style_path = Path(directory) / "overlay-style.json"
            with patch.object(native_overlay, "STYLE_PATH", style_path):
                style = native_overlay._load_style()
            self.assertEqual(style, native_overlay.DEFAULT_STYLE)
            color = style["translation_color"]
            channels = [int(color[offset:offset + 2], 16) for offset in (1, 3, 5)]
            self.assertTrue(all(channel >= 230 for channel in channels))
            self.assertFalse(style_path.exists())

    def test_explicit_legacy_font_sizes_and_colors_are_preserved(self):
        saved = {
            "original_size": 21,
            "translation_size": 35,
            "original_color": "#66ccff",
            "translation_color": "#c7ff61",
        }
        with tempfile.TemporaryDirectory() as directory:
            style_path = Path(directory) / "overlay-style.json"
            style_path.write_text(json.dumps(saved), encoding="utf-8")
            original_file = style_path.read_bytes()
            with patch.object(native_overlay, "STYLE_PATH", style_path):
                style = native_overlay._load_style()
            self.assertEqual(style["original_size"], saved["original_size"])
            self.assertEqual(style["translation_size"], saved["translation_size"])
            self.assertEqual(style["original_color"], saved["original_color"].upper())
            self.assertEqual(style["translation_color"], saved["translation_color"].upper())
            self.assertEqual(style_path.read_bytes(), original_file)

    def test_partial_config_only_fills_missing_preferences_from_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            style_path = Path(directory) / "overlay-style.json"
            style_path.write_text(json.dumps({"translation_color": "#C7FF61"}), encoding="utf-8")
            defaults = dict(native_overlay.DEFAULT_STYLE)
            with patch.object(native_overlay, "STYLE_PATH", style_path):
                style = native_overlay._load_style()
            self.assertEqual(style["translation_color"], "#C7FF61")
            for name in ("original_size", "translation_size", "original_color"):
                self.assertEqual(style[name], defaults[name])
            self.assertEqual(native_overlay.DEFAULT_STYLE, defaults)


if __name__ == "__main__":
    unittest.main()
