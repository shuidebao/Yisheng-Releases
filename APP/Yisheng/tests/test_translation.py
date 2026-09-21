from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from app.translation import (
    _CTranslate2Model, _has_multiple_sentences, OfflineTranslator, TranslationUnavailable,
)


class _FakeModel:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[str] = []
        self.loaded = False

    def available(self) -> bool:
        return True

    def translate(self, text: str) -> str:
        self.calls.append(text)
        self.loaded = True
        return f"{self.name}({text})"

    def unload(self) -> None:
        self.loaded = False


class _InvalidResultModel(_FakeModel):
    def translate(self, text: str) -> None:
        return None


def fake_translator() -> OfflineTranslator:
    translator = OfflineTranslator()
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


class TranslationCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.translator = fake_translator()

    def test_exact_repeat_reuses_successful_result(self) -> None:
        first = self.translator.translate("Cover me!", "en", "zh")
        second = self.translator.translate("Cover me!", "en", "zh")
        self.assertEqual(second, first)
        self.assertEqual(self.translator._en_zh.calls, ["Cover me!"])

    def test_original_text_and_both_languages_are_isolated(self) -> None:
        for text in ("Go!", "go!", " Go!", "Go! Go!"):
            self.translator.translate(text, "en", "zh")
        english = self.translator.translate("Go!", "en", "ja")
        chinese = self.translator.translate("Go!", "zh", "ja")
        self.assertEqual(english.text, "en-ja(Go!)")
        self.assertEqual(chinese.text, "en-ja(zh-en(Go!))")
        self.assertEqual(len(self.translator._cache), 6)
        self.assertEqual(self.translator._en_zh.calls, ["Go!", "go!", " Go!", "Go! Go!"])

    def test_pivot_hit_skips_both_models_and_releases_inactive_route(self) -> None:
        first = self.translator.translate("待って！", "ja", "zh")
        self.translator.translate("你好", "zh", "en")
        self.assertTrue(self.translator._zh_en.loaded)
        self.assertEqual(self.translator.translate("待って！", "ja", "zh"), first)
        self.assertEqual(self.translator._ja_en.calls, ["待って！"])
        self.assertEqual(self.translator._en_zh.calls, ["ja-en(待って！)"])
        self.assertFalse(self.translator._zh_en.loaded)

    def test_lru_evicts_oldest_unused_result(self) -> None:
        self.translator._CACHE_MAX_ENTRIES = 2
        for text in ("A", "B", "A", "C", "A", "B"):
            self.translator.translate(text, "en", "zh")
        self.assertEqual(self.translator._en_zh.calls, ["A", "B", "C", "B"])
        self.assertEqual(len(self.translator._cache), 2)

    def test_long_inputs_and_outputs_are_not_retained(self) -> None:
        self.translator._CACHE_MAX_TEXT_CHARS = 8
        with mock.patch.object(self.translator._en_zh, "translate", return_value="译文") as infer:
            for _ in range(2):
                self.translator.translate("A" * 9, "en", "zh")
            self.assertEqual(infer.call_count, 2)
        with mock.patch.object(self.translator._en_zh, "translate", return_value="一二三四五六七八九") as infer:
            for _ in range(2):
                self.translator.translate("hello", "en", "zh")
            self.assertEqual(infer.call_count, 2)
        self.assertFalse(self.translator._cache)

    def test_empty_and_obviously_degenerate_outputs_are_not_cached_or_rewritten(self) -> None:
        for output in ("", "  ", "取" * 128, "开始" + "取" * 12):
            with self.subTest(output=output), mock.patch.object(
                self.translator._en_zh, "translate", return_value=output
            ) as infer:
                for _ in range(2):
                    self.assertEqual(self.translator.translate("hello", "en", "zh").text, output)
                self.assertEqual(infer.call_count, 2)
                self.assertFalse(self.translator._cache)

    def test_normal_repeated_dialogue_is_not_removed(self) -> None:
        output = "走！走！走！"
        with mock.patch.object(self.translator._en_zh, "translate", return_value=output) as infer:
            for _ in range(2):
                self.assertEqual(self.translator.translate("Go! Go! Go!", "en", "zh").text, output)
            self.assertEqual(infer.call_count, 1)

    def test_failed_or_invalid_result_is_retried_not_cached(self) -> None:
        for failure in (RuntimeError("retry"), None):
            with self.subTest(failure=failure), mock.patch.object(
                self.translator._en_zh, "translate", side_effect=[failure, "成功"]
            ) as infer:
                with self.assertRaises(TranslationUnavailable):
                    self.translator.translate("hello", "en", "zh")
                self.assertFalse(self.translator._cache)
                self.assertEqual(self.translator.translate("hello", "en", "zh").text, "成功")
                self.assertEqual(infer.call_count, 2)
            self.translator.unload()

    def test_model_availability_is_checked_even_after_cache_hit(self) -> None:
        self.translator.translate("hello", "en", "zh")
        with mock.patch.object(self.translator._en_zh, "available", return_value=False):
            result = self.translator.translate("hello", "en", "zh")
        self.assertFalse(result.ready)
        self.assertEqual(result.text, "")

    def test_unload_clears_cache_and_next_session_translates_again(self) -> None:
        self.translator.translate("hello", "en", "zh")
        self.assertTrue(self.translator.unload())
        self.assertFalse(self.translator._cache)
        self.assertFalse(self.translator.unload())
        self.translator.translate("hello", "en", "zh")
        self.assertEqual(self.translator._en_zh.calls, ["hello", "hello"])

    def test_concurrent_identical_requests_infer_only_once(self) -> None:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(
                lambda _: self.translator.translate("hello", "en", "zh"), range(16)
            ))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(self.translator._en_zh.calls, ["hello"])

    def test_invalid_input_is_rejected_before_cache_lookup(self) -> None:
        for text in (None, 12, ["hello"]):
            with self.subTest(text=text), self.assertRaisesRegex(TranslationUnavailable, "无效文本"):
                self.translator.translate(text, "en", "zh")
        self.assertFalse(self.translator._cache)


class TranslationSentencePolicyTests(unittest.TestCase):
    def test_complete_sentences_are_detected_without_splitting_context(self) -> None:
        for text in (
            'Could you speak more slowly? I did not understand the last sentence.',
            'Wait here. Do not open the door.',
            'Go! Go! Go!',
            'He said "Wait." Then he left.',
            'Dr. Smith has arrived. Ask him to wait.',
            'No. Take the other path.',
        ):
            with self.subTest(text=text):
                self.assertTrue(_has_multiple_sentences(text))

    def test_abbreviations_initials_decimals_and_ellipses_are_not_sentence_boundaries(self) -> None:
        for text in (
            'Ask Dr. Smith to wait.', 'Mr. Jones is here.',
            'The U.S. team has arrived.', 'Ask J. Smith.',
            'Use e.g. a shield.', 'Take item No. 5.',
            'Arrive on Jan. 3 before noon.', 'Use approx. 3 liters of fuel.',
            'It costs 3.14 dollars.', 'Wait... I am not ready.',
            'This is just one complete sentence.', '', '... Wait',
        ):
            with self.subTest(text=text):
                self.assertFalse(_has_multiple_sentences(text))

    def test_only_english_chinese_route_enables_adaptive_length(self) -> None:
        translator = OfflineTranslator()
        self.assertEqual(translator._en_zh.multi_sentence_length_penalty, 1.0)
        self.assertEqual(translator._en_zh.length_penalty, .2)
        for model in (translator._ja_en, translator._zh_en, translator._en_ja):
            self.assertIsNone(model.multi_sentence_length_penalty)

    def test_multi_sentence_decode_is_one_call_and_preserves_complete_source(self) -> None:
        model = _CTranslate2Model(Path('model'), Path('source'), Path('target'),
            length_penalty=.2, multi_sentence_length_penalty=1.0)
        runtime = mock.Mock()
        runtime.translate_batch.return_value = [SimpleNamespace(hypotheses=[['translated']])]
        source = mock.Mock()
        source.encode.return_value = ['first', 'second']
        target = mock.Mock()
        target.decode_pieces.return_value = '第一句。第二句。'
        for text, penalty in (
            ('Wait here. Do not move.', 1.0), ('Ask Dr. Smith to wait.', .2),
            ('Wait for everyone before you enter the room.', .2),
        ):
            with self.subTest(text=text), mock.patch.object(model, '_load', return_value=(runtime, source, target)):
                runtime.reset_mock()
                source.reset_mock()
                self.assertEqual(model.translate(text), '第一句。第二句。')
                source.encode.assert_called_once_with(text, out_type=str)
                runtime.translate_batch.assert_called_once()
                self.assertEqual(runtime.translate_batch.call_args.args[0], [['first', 'second']])
                self.assertEqual(runtime.translate_batch.call_args.kwargs['length_penalty'], penalty)
                self.assertEqual(runtime.translate_batch.call_args.kwargs['beam_size'], 4)


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
