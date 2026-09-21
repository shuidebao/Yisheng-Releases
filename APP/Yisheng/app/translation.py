from __future__ import annotations

import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from .config import ARGOS_MODEL_ROOT, MODEL_ROOT, performance_cpu_threads

TRANSLATION_LANGUAGES = ("zh", "ja", "en", "ko")


class TranslationUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class TranslationResult:
    text: str
    source: str
    ready: bool
    warning: str | None = None


def _has_multiple_sentences(text: str) -> bool:
    """Conservatively recognize complete English sentences, without splitting them."""
    abbreviations = {'mr', 'mrs', 'ms', 'dr', 'prof', 'sr', 'jr', 'st',
                     'vs', 'etc', 'e.g', 'i.e', 'fig', 'inc', 'ltd', 'approx',
                     'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'sept',
                     'oct', 'nov', 'dec'}
    for boundary in re.finditer(r'''[.!?]["'”’\)\]]*\s+(?=\S)''', text):
        position = boundary.start()
        if not any(char.isalnum() for char in text[:position]):
            continue
        if text[position] == '.':
            if position and text[position - 1] == '.':  # an ellipsis is not a new sentence
                continue
            word = re.search(r'([A-Za-z][A-Za-z.]*)\.$', text[:position + 1])
            if word:
                token = word[1].casefold()
                if token == 'no' and text[boundary.end():boundary.end() + 1].isdigit():
                    continue  # "No. 5", but not the independent reply "No. Go back."
                if token in abbreviations or all(len(part) == 1 for part in token.split('.')):
                    continue  # initials, acronyms, and common titles
        return True
    return False


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
        multi_sentence_length_penalty: float | None = None,
    ) -> None:
        self.model_dir = model_dir
        self.source_spm = source_spm
        self.target_spm = target_spm
        self.source_eos = source_eos
        self.length_penalty = length_penalty
        self.multi_sentence_length_penalty = multi_sentence_length_penalty
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
        components = (
            self._translator,
            self._source_tokenizer,
            self._target_tokenizer,
        )
        if any(component is None for component in components):
            # Loading can fail after CTranslate2 has initialized but before both
            # SentencePiece processors are ready. Never retain that partial
            # state: the next utterance must rebuild the complete model instead
            # of calling encode/decode on None.
            self.unload()
            try:
                import ctranslate2
                import sentencepiece as spm
            except ImportError as exc:
                raise TranslationUnavailable("翻译运行库不完整，请重新安装译声。") from exc

            # Leave CPU headroom for games and other foreground applications.
            threads = performance_cpu_threads()
            translator = ctranslate2.Translator(
                str(self.model_dir),
                device="cpu",
                compute_type="int8",
                inter_threads=1,
                intra_threads=threads,
            )
            source_tokenizer = spm.SentencePieceProcessor(model_file=str(self.source_spm))
            target_tokenizer = spm.SentencePieceProcessor(model_file=str(self.target_spm))
            self._translator = translator
            self._source_tokenizer = source_tokenizer
            self._target_tokenizer = target_tokenizer
        return self._translator, self._source_tokenizer, self._target_tokenizer

    def translate(self, text: str) -> str:
        if not isinstance(text, str):
            raise TranslationUnavailable("离线翻译收到无效文本，请重试。")
        if not text.strip():
            return ""
        translator, source_tokenizer, target_tokenizer = self._load()
        tokens = source_tokenizer.encode(text, out_type=str)
        if self.source_eos:
            tokens.append("</s>")
        # The bundled EN->ZH model's short-answer bias can omit a second
        # sentence. Keep the whole input/context and normalize longer outputs
        # only for explicit multi-sentence inputs; single sentences keep their
        # established settings. This adds no second inference or larger model.
        length_penalty = self.length_penalty
        if self.multi_sentence_length_penalty is not None and _has_multiple_sentences(text):
            length_penalty = self.multi_sentence_length_penalty
        result = translator.translate_batch(
            [tokens],
            beam_size=4,
            num_hypotheses=1,
            length_penalty=length_penalty,
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
        unload_model = getattr(self._translator, "unload_model", None)
        if callable(unload_model):
            try:
                unload_model()
            except Exception:
                pass
        self._translator = None
        self._source_tokenizer = None
        self._target_tokenizer = None

    @property
    def loaded(self) -> bool:
        return any(component is not None for component in (
            self._translator,
            self._source_tokenizer,
            self._target_tokenizer,
        ))


class OfflineTranslator:
    """Bundled Chinese/English/Japanese/Korean translation; no runtime downloads."""

    _CACHE_MAX_ENTRIES = 128
    _CACHE_MAX_TEXT_CHARS = 1024

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # Session-local exact matches only: never reuse a similar/partial line,
        # persist dialogue to disk, or retain an unbounded transcript in memory.
        self._cache: OrderedDict[tuple[str, str, str], TranslationResult] = OrderedDict()

        # Proven OPUS English-Chinese model from the Argos 1.9 CT2 package.
        # CT2 is called directly, so Stanza and Torch are not required.
        en_root = ARGOS_MODEL_ROOT / "translate-en_zh-1_9"
        self._en_zh = _CTranslate2Model(
            en_root / "model",
            en_root / "sentencepiece.model",
            en_root / "sentencepiece.model",
            length_penalty=0.2,
            multi_sentence_length_penalty=1.0,
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

        # Official OPUS-MT Korean models converted to CT2 int8. Korean shares
        # the English pivot; these stay unloaded until actually requested.
        ko_source_root = MODEL_ROOT / "translations" / "ko_en"
        self._ko_en = _CTranslate2Model(
            ko_source_root,
            ko_source_root / "source.spm",
            ko_source_root / "target.spm",
            source_eos=True,
        )
        ko_target_root = MODEL_ROOT / "translations" / "en_ko"
        self._en_ko = _CTranslate2Model(
            ko_target_root,
            ko_target_root / "source.spm",
            ko_target_root / "target.spm",
            source_eos=True,
        )

        self._models = {
            "en-zh": self._en_zh,
            "ja-en": self._ja_en,
            "zh-en": self._zh_en,
            "en-ja": self._en_ja,
            "ko-en": self._ko_en,
            "en-ko": self._en_ko,
        }

    def _route(self, source_code: str, target_code: str) -> list[_CTranslate2Model]:
        if source_code == target_code:
            return []
        direct = self._models.get(f"{source_code}-{target_code}")
        if direct is not None:
            return [direct]
        to_english = self._models.get(f"{source_code}-en")
        from_english = self._models.get(f"en-{target_code}")
        if to_english is not None and from_english is not None:
            return [to_english, from_english]
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
            for source in TRANSLATION_LANGUAGES
            for target in TRANSLATION_LANGUAGES
            if source != target and self.can_translate(source, target)
        ]

    def can_translate(self, source_code: str, target_code: str = "zh") -> bool:
        if source_code == target_code:
            return source_code in TRANSLATION_LANGUAGES
        if source_code not in TRANSLATION_LANGUAGES or target_code not in TRANSLATION_LANGUAGES:
            return False
        route = self._route(source_code, target_code)
        return bool(route) and all(model.available() for model in route)

    def translate(self, text: str, source_code: str, target_code: str = "zh") -> TranslationResult:
        if not isinstance(text, str):
            raise TranslationUnavailable("离线翻译收到无效文本，请重试。")
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
                cache_key = (text, source_code, target_code)
                cached = self._cache.get(cache_key)
                if cached is not None:
                    self._cache.move_to_end(cache_key)
                    return cached
                translated = text
                for model in route:
                    translated = model.translate(translated)
                    if not isinstance(translated, str):
                        raise TranslationUnavailable("离线翻译模型返回了无效结果，请重试。")
                result = TranslationResult(translated, source_code, True)
                if (
                    text.strip()
                    and translated.strip()
                    and len(text) <= self._CACHE_MAX_TEXT_CHARS
                    and len(translated) <= self._CACHE_MAX_TEXT_CHARS
                    # A broken decode can repeat one character to its token
                    # limit. Do not preserve that failure as a cache hit; this
                    # guard does not remove/rewrite any returned dialogue.
                    and re.search(r"(\S)\1{11,}", translated) is None
                ):
                    self._cache[cache_key] = result
                    self._cache.move_to_end(cache_key)
                    while len(self._cache) > self._CACHE_MAX_ENTRIES:
                        self._cache.popitem(last=False)
            except TranslationUnavailable:
                raise
            except Exception as exc:
                raise TranslationUnavailable(f"离线翻译失败：{exc}") from exc
        return result

    def install_pair(self, source_code: str, target_code: str = "zh") -> list[str]:
        if self.can_translate(source_code, target_code):
            return []
        raise TranslationUnavailable(
            "译声不在用户电脑上临时下载翻译模型；内置模型缺失，请重新下载安装包。"
        )

    def unload(self) -> bool:
        """Release all resident translation routes and report whether any were loaded."""
        with self._lock:
            self._cache.clear()
            released = any(model.loaded for model in self._models.values())
            for model in self._models.values():
                model.unload()
            return released
