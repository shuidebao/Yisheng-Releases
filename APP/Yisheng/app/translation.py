from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path

from .config import ARGOS_MODEL_ROOT, MODEL_ROOT


class TranslationUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class TranslationResult:
    text: str
    source: str
    ready: bool
    warning: str | None = None


class _CTranslate2Model:
    """Lazy, CPU-optimized CTranslate2 model with SentencePiece tokenization."""

    def __init__(
        self,
        model_dir: Path,
        source_spm: Path,
        target_spm: Path,
        *,
        source_eos: bool = False,
        length_penalty: float = 1.0,
    ) -> None:
        self.model_dir = model_dir
        self.source_spm = source_spm
        self.target_spm = target_spm
        self.source_eos = source_eos
        self.length_penalty = length_penalty
        self._translator = None
        self._source_tokenizer = None
        self._target_tokenizer = None

    def available(self) -> bool:
        return all(
            path.is_file()
            for path in (self.model_dir / "model.bin", self.source_spm, self.target_spm)
        )

    def _load(self):
        if not self.available():
            raise TranslationUnavailable("内置翻译模型不完整，请重新安装译声。")
        if self._translator is None:
            try:
                import ctranslate2
                import sentencepiece as spm
            except ImportError as exc:
                raise TranslationUnavailable("翻译运行库不完整，请重新安装译声。") from exc

            # Four CPU threads provides a good latency/load balance on ordinary
            # Windows PCs; CT2 internally schedules the vectorized kernels.
            threads = max(1, min(4, os.cpu_count() or 2))
            self._translator = ctranslate2.Translator(
                str(self.model_dir),
                device="cpu",
                compute_type="int8",
                inter_threads=1,
                intra_threads=threads,
            )
            self._source_tokenizer = spm.SentencePieceProcessor(model_file=str(self.source_spm))
            self._target_tokenizer = spm.SentencePieceProcessor(model_file=str(self.target_spm))
        return self._translator, self._source_tokenizer, self._target_tokenizer

    def translate(self, text: str) -> str:
        translator, source_tokenizer, target_tokenizer = self._load()
        tokens = source_tokenizer.encode(text, out_type=str)
        if self.source_eos:
            tokens.append("</s>")
        result = translator.translate_batch(
            [tokens],
            beam_size=4,
            num_hypotheses=1,
            length_penalty=self.length_penalty,
            replace_unknowns=True,
            max_decoding_length=128,
        )[0]
        return (
            target_tokenizer.decode_pieces(result.hypotheses[0])
            .replace("▁", " ")
            .replace("_", " ")
            .strip()
        )


class OfflineTranslator:
    """Bundled English/Japanese to Chinese translation; never downloads at runtime."""

    def __init__(self) -> None:
        self._lock = threading.RLock()

        # Proven OPUS English-Chinese model from the Argos 1.9 CT2 package.
        # CT2 is called directly, so Stanza and Torch are not required.
        en_root = ARGOS_MODEL_ROOT / "translate-en_zh-1_9"
        self._en_zh = _CTranslate2Model(
            en_root / "model",
            en_root / "sentencepiece.model",
            en_root / "sentencepiece.model",
            length_penalty=0.2,
        )

        # Official Helsinki-NLP Japanese-English model converted to CT2 int8.
        # Japanese then shares the resident English-Chinese model.
        ja_root = MODEL_ROOT / "translations" / "ja_en"
        self._ja_en = _CTranslate2Model(
            ja_root,
            ja_root / "source.spm",
            ja_root / "target.spm",
            source_eos=True,
        )

    def installed_pairs(self) -> list[str]:
        pairs: list[str] = []
        if self._en_zh.available():
            pairs.append("en-zh")
        if self._en_zh.available() and self._ja_en.available():
            pairs.append("ja-zh")
        return pairs

    def can_translate(self, source_code: str, target_code: str = "zh") -> bool:
        if source_code == target_code:
            return True
        if target_code != "zh":
            return False
        if source_code == "en":
            return self._en_zh.available()
        if source_code == "ja":
            return self._ja_en.available() and self._en_zh.available()
        return False

    def translate(self, text: str, source_code: str, target_code: str = "zh") -> TranslationResult:
        if not text:
            return TranslationResult("", source_code, True)
        if source_code == target_code:
            return TranslationResult(text, source_code, True)
        if not self.can_translate(source_code, target_code):
            return TranslationResult(
                "",
                source_code,
                False,
                f"当前离线版仅内置英语、日语 → 中文翻译（识别到 {source_code}）。",
            )

        with self._lock:
            try:
                if source_code == "ja":
                    text = self._ja_en.translate(text)
                translated = self._en_zh.translate(text)
            except TranslationUnavailable:
                raise
            except Exception as exc:
                raise TranslationUnavailable(f"离线翻译失败：{exc}") from exc
        return TranslationResult(translated, source_code, True)

    def install_pair(self, source_code: str, target_code: str = "zh") -> list[str]:
        if self.can_translate(source_code, target_code):
            return []
        raise TranslationUnavailable(
            "译声最终版不在用户电脑上下载模型；内置模型缺失，请重新下载安装包。"
        )
