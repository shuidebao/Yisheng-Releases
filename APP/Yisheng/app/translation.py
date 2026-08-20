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

    def unload(self) -> None:
        """Release an inactive route so language switching does not grow RAM forever."""
        self._translator = None
        self._source_tokenizer = None
        self._target_tokenizer = None


class OfflineTranslator:
    """Bundled Chinese/English/Japanese translation; never downloads at runtime."""

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

        # Official Argos Chinese-English 1.9 CT2 package.
        zh_root = ARGOS_MODEL_ROOT / "translate-zh_en-1_9"
        self._zh_en = _CTranslate2Model(
            zh_root / "model",
            zh_root / "sentencepiece.model",
            zh_root / "sentencepiece.model",
        )

        # Official Argos English-Japanese 1.1 CT2 package.
        ja_target_root = ARGOS_MODEL_ROOT / "en_ja"
        self._en_ja = _CTranslate2Model(
            ja_target_root / "model",
            ja_target_root / "sentencepiece.model",
            ja_target_root / "sentencepiece.model",
        )

        self._models = {
            "en-zh": self._en_zh,
            "ja-en": self._ja_en,
            "zh-en": self._zh_en,
            "en-ja": self._en_ja,
        }

    def _route(self, source_code: str, target_code: str) -> list[_CTranslate2Model]:
        if source_code == target_code:
            return []
        direct = self._models.get(f"{source_code}-{target_code}")
        if direct is not None:
            return [direct]
        if source_code == "ja" and target_code == "zh":
            return [self._ja_en, self._en_zh]
        if source_code == "zh" and target_code == "ja":
            return [self._zh_en, self._en_ja]
        return []

    def _activate(self, route: list[_CTranslate2Model]) -> None:
        # At most two translation models stay resident. This matters after users
        # switch among several language directions in one desktop session.
        active = {id(model) for model in route}
        for model in self._models.values():
            if id(model) not in active:
                model.unload()

    def installed_pairs(self) -> list[str]:
        return [
            f"{source}-{target}"
            for source in ("zh", "ja", "en")
            for target in ("zh", "ja", "en")
            if source != target and self.can_translate(source, target)
        ]

    def can_translate(self, source_code: str, target_code: str = "zh") -> bool:
        if source_code == target_code:
            return source_code in {"zh", "ja", "en"}
        if source_code not in {"zh", "ja", "en"} or target_code not in {"zh", "ja", "en"}:
            return False
        route = self._route(source_code, target_code)
        return bool(route) and all(model.available() for model in route)

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
                f"当前离线版无法完成 {source_code} → {target_code} 翻译，请重新安装译声。",
            )

        with self._lock:
            try:
                route = self._route(source_code, target_code)
                self._activate(route)
                translated = text
                for model in route:
                    translated = model.translate(translated)
            except TranslationUnavailable:
                raise
            except Exception as exc:
                raise TranslationUnavailable(f"离线翻译失败：{exc}") from exc
        return TranslationResult(translated, source_code, True)

    def install_pair(self, source_code: str, target_code: str = "zh") -> list[str]:
        if self.can_translate(source_code, target_code):
            return []
        raise TranslationUnavailable(
            "译声不在用户电脑上临时下载翻译模型；内置模型缺失，请重新下载安装包。"
        )
