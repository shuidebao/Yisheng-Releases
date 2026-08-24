from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from app.translation import _CTranslate2Model, OfflineTranslator, TranslationUnavailable


class _FakeModel:
    def __init__(self, name: str) -> None:
        self.name = name

    def available(self) -> bool:
        return True

    def translate(self, text: str) -> str:
        return f"{self.name}({text})"

    def unload(self) -> None:
        return None


class _InvalidResultModel(_FakeModel):
    def translate(self, text: str) -> None:
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

    def test_invalid_pivot_result_is_reported_without_none_type_error(self) -> None:
        invalid = _InvalidResultModel("ja-en")
        self.translator._ja_en = invalid
        self.translator._models["ja-en"] = invalid

        with self.assertRaisesRegex(TranslationUnavailable, "无效结果"):
            self.translator.translate("こんにちは", "ja", "zh")


class TranslationModelStateTests(unittest.TestCase):
    def test_incomplete_loaded_state_is_rebuilt_as_one_unit(self) -> None:
        model = _CTranslate2Model(Path("model"), Path("source.spm"), Path("target.spm"))
        stale_translator = object()
        rebuilt_translator = object()
        source_tokenizer = object()
        target_tokenizer = object()
        tokenizers = iter((source_tokenizer, target_tokenizer))
        model._translator = stale_translator

        fake_ctranslate2 = SimpleNamespace(Translator=lambda *args, **kwargs: rebuilt_translator)
        fake_sentencepiece = SimpleNamespace(
            SentencePieceProcessor=lambda **kwargs: next(tokenizers)
        )
        with (
            mock.patch.object(model, "available", return_value=True),
            mock.patch.dict(
                "sys.modules",
                {"ctranslate2": fake_ctranslate2, "sentencepiece": fake_sentencepiece},
            ),
        ):
            loaded = model._load()

        self.assertEqual(loaded, (rebuilt_translator, source_tokenizer, target_tokenizer))

    def test_non_string_model_input_has_actionable_error(self) -> None:
        model = _CTranslate2Model(Path("model"), Path("source.spm"), Path("target.spm"))
        with self.assertRaisesRegex(TranslationUnavailable, "无效文本"):
            model.translate(None)


if __name__ == "__main__":
    unittest.main()
