from __future__ import annotations

import unittest

from app.translation import OfflineTranslator


class _FakeModel:
    def __init__(self, name: str) -> None:
        self.name = name

    def available(self) -> bool:
        return True

    def translate(self, text: str) -> str:
        return f"{self.name}({text})"

    def unload(self) -> None:
        return None


def fake_translator() -> OfflineTranslator:
    translator = OfflineTranslator.__new__(OfflineTranslator)
    import threading

    translator._lock = threading.RLock()
    translator._en_zh = _FakeModel("en-zh")
    translator._ja_en = _FakeModel("ja-en")
    translator._zh_en = _FakeModel("zh-en")
    translator._en_ja = _FakeModel("en-ja")
    translator._models = {
        "en-zh": translator._en_zh,
        "ja-en": translator._ja_en,
        "zh-en": translator._zh_en,
        "en-ja": translator._en_ja,
    }
    return translator


class ThreeLanguageTranslationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.translator = fake_translator()

    def test_all_six_cross_language_pairs_are_available(self) -> None:
        self.assertEqual(
            set(self.translator.installed_pairs()),
            {"zh-ja", "zh-en", "ja-zh", "ja-en", "en-zh", "en-ja"},
        )

    def test_direct_routes_use_one_model(self) -> None:
        self.assertEqual(self.translator.translate("hello", "en", "zh").text, "en-zh(hello)")
        self.assertEqual(self.translator.translate("hello", "en", "ja").text, "en-ja(hello)")
        self.assertEqual(self.translator.translate("你好", "zh", "en").text, "zh-en(你好)")
        self.assertEqual(self.translator.translate("こんにちは", "ja", "en").text, "ja-en(こんにちは)")

    def test_japanese_chinese_routes_pivot_through_english(self) -> None:
        self.assertEqual(
            self.translator.translate("こんにちは", "ja", "zh").text,
            "en-zh(ja-en(こんにちは))",
        )
        self.assertEqual(
            self.translator.translate("你好", "zh", "ja").text,
            "en-ja(zh-en(你好))",
        )

    def test_same_language_returns_original_text(self) -> None:
        for language in ("zh", "ja", "en"):
            result = self.translator.translate("same", language, language)
            self.assertTrue(result.ready)
            self.assertEqual(result.text, "same")


if __name__ == "__main__":
    unittest.main()
