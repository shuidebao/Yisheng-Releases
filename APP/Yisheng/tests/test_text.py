from __future__ import annotations

import unittest

from app.text import clean_transcript, merge_continuation


class TranscriptCleanupTests(unittest.TestCase):
    def test_collapses_runaway_single_word(self) -> None:
        self.assertEqual(
            clean_transcript("hello hello hello hello hello world"),
            "hello hello world",
        )

    def test_collapses_runaway_phrase(self) -> None:
        self.assertEqual(
            clean_transcript("we are ready we are ready we are ready now"),
            "we are ready we are ready now",
        )

    def test_preserves_normal_emphasis(self) -> None:
        self.assertEqual(clean_transcript("very very good"), "very very good")

    def test_collapses_cjk_without_spaces(self) -> None:
        self.assertEqual(clean_transcript("谢谢谢谢谢谢谢谢今天好"), "谢谢今天好")
        self.assertEqual(clean_transcript("おはようおはようおはよう"), "おはようおはよう")

    def test_collapses_punctuated_japanese_word_loop(self) -> None:
        self.assertEqual(clean_transcript("お前が、 " * 12), "お前が、 お前が、")

    def test_merges_english_chunk_overlap(self) -> None:
        self.assertEqual(
            merge_continuation(
                "this is one continuous sentence",
                "continuous sentence with a clear ending.",
                "en",
            ),
            "this is one continuous sentence with a clear ending.",
        )

    def test_merges_japanese_chunk_overlap(self) -> None:
        self.assertEqual(
            merge_continuation("これは一つの文章です", "文章です続きがあります。", "ja"),
            "これは一つの文章です続きがあります。",
        )


if __name__ == "__main__":
    unittest.main()
