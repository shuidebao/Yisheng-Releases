from __future__ import annotations

import unittest

from app.native_overlay import NativeLyricOverlay


class KoreanOverlayTests(unittest.TestCase):
    def test_hangul_uses_full_width_fitting(self):
        fit = NativeLyricOverlay._fitted_text_size
        expected = fit("中" * 60, 36, 16, 720, 90)
        self.assertEqual(expected, 24.0)
        # Modern syllables, decomposed Jamo, compatibility Jamo, and both
        # extended Jamo blocks must not take the narrower Latin path.
        for character in ("가", "힣", "\u1100", "\u11ff", "ㄱ", "\u318e",
                          "\ua960", "\ua97c", "\ud7b0", "\ud7fb"):
            with self.subTest(character=character):
                self.assertEqual(fit(character * 60, 36, 16, 720, 90), expected)

    def test_existing_chinese_japanese_english_sizes_are_unchanged(self):
        fit = NativeLyricOverlay._fitted_text_size
        for character, expected in (("中", 24.0), ("あ", 24.0), ("ア", 24.0), ("a", 33.0)):
            with self.subTest(character=character):
                self.assertEqual(fit(character * 60, 36, 16, 720, 90), expected)

    def test_korean_keeps_empty_short_and_minimum_size_behavior(self):
        fit = NativeLyricOverlay._fitted_text_size
        self.assertEqual(fit("", 36, 16, 720, 90), 36)
        self.assertEqual(fit("잠시 기다려 주세요.", 36, 16, 720, 90), 36)
        self.assertEqual(fit("가" * 1000, 36, 16, 720, 90), 16)


if __name__ == "__main__":
    unittest.main()
