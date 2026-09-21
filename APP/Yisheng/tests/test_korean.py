from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from app.text import clean_transcript, merge_continuation
from app.translation import OfflineTranslator, TRANSLATION_LANGUAGES
from test_translation import _FakeModel, fake_translator


def four_language_translator():
    translator = fake_translator()
    translator._ko_en = _FakeModel('ko-en')
    translator._en_ko = _FakeModel('en-ko')
    translator._models.update({'ko-en': translator._ko_en, 'en-ko': translator._en_ko})
    return translator


class KoreanTranslationTests(unittest.TestCase):
    def test_offline_installer_requires_both_korean_models_and_licenses(self):
        repository = Path(__file__).resolve().parents[3]
        build = (repository / 'build_offline_installer.ps1').read_text(encoding='utf-8')
        installer = (repository / 'installer/OfflineInstaller.cs').read_text(encoding='utf-8')
        for route in ('ko_en', 'en_ko'):
            for filename in ('model.bin', 'source.spm', 'target.spm', 'config.json',
                             'LICENSE', 'YISHENG-MODEL-NOTICE.md'):
                self.assertIn(f'.models\\translations\\{route}\\{filename}', build)
                self.assertIn(f'Path.Combine(".models", "translations", "{route}", "{filename}")', installer)

    def test_all_twelve_routes_available_without_loading_models(self):
        translator = four_language_translator()
        self.assertEqual(set(translator.installed_pairs()), {
            f'{source}-{target}' for source in TRANSLATION_LANGUAGES
            for target in TRANSLATION_LANGUAGES if source != target
        })
        self.assertTrue(all(not model.loaded for model in translator._models.values()))

    def test_six_korean_routes_and_identity(self):
        translator = four_language_translator()
        cases = [('ko', 'en', 'ko-en(안녕하세요)'),
                 ('en', 'ko', 'en-ko(안녕하세요)'),
                 ('ko', 'zh', 'en-zh(ko-en(안녕하세요))'),
                 ('zh', 'ko', 'en-ko(zh-en(안녕하세요))'),
                 ('ko', 'ja', 'en-ja(ko-en(안녕하세요))'),
                 ('ja', 'ko', 'en-ko(ja-en(안녕하세요))')]
        for source, target, expected in cases:
            with self.subTest(source=source, target=target):
                result = translator.translate('안녕하세요', source, target)
                self.assertTrue(result.ready)
                self.assertEqual(result.text, expected)
                self.assertLessEqual(sum(model.loaded for model in translator._models.values()), 2)
        self.assertTrue(translator.can_translate('ko', 'ko'))
        self.assertEqual(translator.translate('안녕하세요', 'ko', 'ko').text, '안녕하세요')

    def test_missing_korean_model_does_not_disable_existing_languages(self):
        translator = four_language_translator()
        with mock.patch.object(translator._ko_en, 'available', return_value=False):
            self.assertFalse(translator.translate('안녕하세요', 'ko', 'zh').ready)
            self.assertFalse(translator._en_zh.calls)
            self.assertTrue(translator.can_translate('en', 'zh'))
            self.assertTrue(translator.can_translate('zh', 'ja'))
            self.assertTrue(translator.can_translate('en', 'ko'))

    def test_korean_cache_is_direction_specific_and_cleared_on_release(self):
        translator = four_language_translator()
        first = translator.translate('안녕하세요', 'ko', 'zh')
        self.assertEqual(translator.translate('안녕하세요', 'ko', 'zh'), first)
        self.assertEqual(translator._ko_en.calls, ['안녕하세요'])
        translator.translate('안녕하세요', 'ko', 'ja')
        self.assertEqual(len(translator._ko_en.calls), 2)
        self.assertTrue(translator.unload())
        self.assertFalse(translator._cache)
        self.assertTrue(all(not model.loaded for model in translator._models.values()))

    def test_new_models_are_lazy_and_keep_decode_defaults(self):
        translator = OfflineTranslator()
        for model in (translator._ko_en, translator._en_ko):
            self.assertFalse(model.loaded)
            self.assertTrue(model.source_eos)
            self.assertEqual(model.source_spm.name, 'source.spm')
            self.assertEqual(model.target_spm.name, 'target.spm')
            self.assertEqual(model.length_penalty, 1.0)
            self.assertIsNone(model.multi_sentence_length_penalty)
        self.assertFalse(translator.can_translate('fr', 'ko'))
        self.assertFalse(translator.can_translate('ko', 'fr'))


class KoreanTextTests(unittest.TestCase):
    def test_normal_korean_spaces_are_preserved(self):
        self.assertEqual(clean_transcript('  문을 열지 마세요.  '), '문을 열지 마세요.')
        self.assertEqual(merge_continuation('저는 지금 집에', '지금 집에 가고 있어요.', 'ko'),
                         '저는 지금 집에 가고 있어요.')

    def test_nonoverlapping_korean_words_are_separated(self):
        self.assertEqual(merge_continuation('잠시 기다려 주세요.', '곧 돌아올게요.', 'ko'),
                         '잠시 기다려 주세요. 곧 돌아올게요.')


if __name__ == '__main__':
    unittest.main()
