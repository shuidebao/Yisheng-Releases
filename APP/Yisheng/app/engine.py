from __future__ import annotations

import gc
import io
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .audio_input import prepare_audio_input
from .api_translation import ApiTranslationSettings, ApiTranslator
from .config import (
    WHISPER_MODEL_ROOT,
    HardwareInfo,
    detect_hardware,
    memory_gb,
    performance_cpu_threads,
    recommended_profile,
)
from .text import clean_transcript, merge_continuation
from .translation import OfflineTranslator, TranslationResult
from .whisper_models import ALLOWED_MODELS, ensure_whisper_model


LOGGER = logging.getLogger(__name__)


def _transcription_options(source_language: str | None, context: str = "") -> dict:
    """Return conservative decode settings, with extra context for Japanese and English."""
    japanese = source_language == "ja"
    english = source_language == "en"
    options = {
        "language": source_language or None,
        "beam_size": 3 if japanese else 2 if english else 1,
        "best_of": 1,
        "condition_on_previous_text": False,
        "no_repeat_ngram_size": 3,
        "vad_filter": True,
        "vad_parameters": {
            "min_silence_duration_ms": 450 if japanese else 380 if english else 280,
            "speech_pad_ms": 180 if japanese else 160 if english else 120,
        },
        "compression_ratio_threshold": 2.0,
        "log_prob_threshold": -0.8,
        "no_speech_threshold": 0.55,
        "hallucination_silence_threshold": 1.0,
        "temperature": 0.0,
    }
    prompt = context.strip()
    if (japanese or english) and prompt:
        # A short tail helps Whisper keep words and sentence endings across
        # rolling chunks without letting an old mistake dominate the next one.
        prompt_chars = 80 if japanese else 120
        options["initial_prompt"] = prompt[-prompt_chars:]
    return options


@dataclass
class TranscriptResult:
    original: str
    translation: str
    language: str
    target_language: str
    language_probability: float
    latency_ms: int
    audio_seconds: float
    device: str
    model: str
    translation_ready: bool
    continued: bool = False
    warning: str | None = None
    # Backend processing only: capture/endpointing and frontend queue time are
    # not included. Keep the existing latency_ms meaning for old frontends.
    timings_ms: dict[str, float] = field(default_factory=dict)
    translation_mode: str = "local"

    def to_dict(self) -> dict:
        return asdict(self)


class InterpreterEngine:
    ALLOWED_MODELS = ALLOWED_MODELS
    ALLOWED_DEVICES = {"auto", "cpu", "cuda"}
    MIN_AVAILABLE_RAM_GB = {"tiny": 0.7, "base": 1.0, "small": 2.0, "medium": 4.0}

    def __init__(self) -> None:
        self.hardware: HardwareInfo = detect_hardware()
        profile = recommended_profile(self.hardware)
        self.model_name = str(profile["model"])
        self.requested_device = "auto"
        self.active_device = str(profile["device"])
        self.compute_type = str(profile["compute_type"])
        self._model = None
        self._model_lock = threading.RLock()
        self.translator = OfflineTranslator()
        self._api_translator: ApiTranslator | None = None
        self._translation_revision = 0
        self._translation_snapshot = (None, 0)
        self.last_error: str | None = None

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def status(self) -> dict:
        profile = recommended_profile(self.hardware)
        return {
            "hardware": self.hardware.to_dict(),
            "recommended": profile,
            "engine": {
                "loaded": self.loaded,
                "model": self.model_name,
                "requested_device": self.requested_device,
                "active_device": self.active_device,
                "compute_type": self.compute_type,
                "last_error": self.last_error,
            },
            "translation_pairs": self.translator.installed_pairs(),
            "translation": self.translation_status(),
        }

    def translation_status(self) -> dict:
        # Read mode and revision together without waiting for ongoing inference.
        provider, revision = getattr(self, "_translation_snapshot", (None, 0))
        return {
            "mode": "api" if provider is not None else "local",
            "base_url": provider.settings.base_url if provider is not None else "",
            "model": provider.settings.model if provider is not None else "",
            "has_api_key": bool(provider.settings.api_key) if provider is not None else False,
            "revision": revision,
        }

    def _api_settings(self, base_url: str, model: str, api_key: str | None) -> ApiTranslationSettings:
        settings = ApiTranslationSettings(base_url=base_url, model=model, api_key=api_key or "")
        if api_key is None:
            previous = getattr(self, "_api_translator", None)
            if previous is None or (
                previous.settings.base_url != settings.base_url or previous.settings.model != settings.model
            ):
                raise ValueError("服务地址或模型已改变，请重新填写密钥；无需密钥的服务请明确留空。")
            settings = ApiTranslationSettings(settings.base_url, settings.model, previous.settings.api_key)
        return settings

    def configure_translation(
        self, mode: str = "local", base_url: str = "", model: str = "",
        api_key: str | None = None, consent: bool = False,
    ) -> dict:
        if mode not in {"local", "api"}:
            raise ValueError("不支持的翻译模式。")
        if mode == "api" and consent is not True:
            raise ValueError("请先确认文字会发送到所选 API 服务，且可能产生费用。")
        if not self._model_lock.acquire(blocking=False):
            raise RuntimeError("正在处理语音或测试 API，请停止同传并等待完成后再切换。")
        try:
            # Construct and validate before replacing the working configuration.
            candidate = ApiTranslator(self._api_settings(base_url, model, api_key)) if mode == "api" else None
            previous = getattr(self, "_api_translator", None)
            self.translator.unload()
            if previous is not None:
                previous.unload()
            self._api_translator = candidate
            self._translation_revision = getattr(self, "_translation_revision", 0) + 1
            self._translation_snapshot = (candidate, self._translation_revision)
            return self.status()
        finally:
            self._model_lock.release()

    def test_translation_api(
        self, base_url: str, model: str, api_key: str | None = None, consent: bool = False,
    ) -> dict:
        if consent is not True:
            raise ValueError("测试会发送一句测试文字并可能产生费用，请先确认。")
        if not self._model_lock.acquire(blocking=False):
            raise RuntimeError("正在处理语音或测试 API，请等待完成后再测试。")
        try:
            provider = ApiTranslator(self._api_settings(base_url, model, api_key))
            started = time.perf_counter()
            result = provider.translate("Hello.", "en", "zh")
            if not result.ready:
                raise RuntimeError(result.warning or "API 翻译测试失败，请检查设置。")
            return {"ok": True, "translation": result.text,
                    "latency_ms": round((time.perf_counter() - started) * 1000)}
        finally:
            self._model_lock.release()

    def configure(self, model: str, device: str) -> dict:
        if model not in self.ALLOWED_MODELS:
            raise ValueError(f"不支持的模型：{model}")
        if device not in self.ALLOWED_DEVICES:
            raise ValueError(f"不支持的设备：{device}")
        # Validate the bundled model before committing the selection.
        ensure_whisper_model(model)
        with self._model_lock:
            changed = model != self.model_name or device != self.requested_device
            self.model_name = model
            self.requested_device = device
            if changed:
                self._model = None
                gc.collect()
            self._choose_device()
            self.last_error = None
        return self.status()

    def _choose_device(self) -> None:
        # Automatic mode reserves the GPU for games. CUDA remains available as
        # an explicit opt-in for users who prefer maximum recognition speed.
        wants_cuda = self.requested_device == "cuda"
        if wants_cuda:
            self.active_device = "cuda"
            self.compute_type = "float16"
        else:
            self.active_device = "cpu"
            self.compute_type = "int8"

    @staticmethod
    def _is_memory_error(exc: BaseException) -> bool:
        detail = str(exc).casefold()
        markers = (
            "out of memory",
            "bad allocation",
            "bad_alloc",
            "cannot allocate memory",
            "not enough memory",
            "insufficient memory",
            "paging file",
            "pagefile",
            "winerror 8",
            "winerror 1455",
            "内存不足",
            "页面文件",
        )
        return isinstance(exc, MemoryError) or any(marker in detail for marker in markers)

    def _memory_message(self) -> str:
        _, available = memory_gb()
        required = self.MIN_AVAILABLE_RAM_GB.get(self.model_name, 1.0)
        current = f"当前可用约 {available:.1f} GB，" if available else ""
        smaller = "请关闭其他程序后重试"
        if self.model_name in {"small", "medium"}:
            smaller += "，或改用 Base 模型"
        return f"运行内存不足：{current}{self.model_name} 模型至少需要约 {required:.1f} GB 可用内存。{smaller}。"

    def _check_available_memory(self) -> None:
        # CUDA normally uses video memory, but CPU is still the automatic
        # fallback. Keep enough system RAM available for either path.
        _, available = memory_gb()
        required = self.MIN_AVAILABLE_RAM_GB.get(self.model_name, 1.0)
        if available and available < required:
            raise RuntimeError(self._memory_message())

    def _create_model(self, model_path: Path, device: str, compute_type: str):
        from faster_whisper import WhisperModel

        try:
            return WhisperModel(
                str(model_path),
                device=device,
                compute_type=compute_type,
                cpu_threads=performance_cpu_threads(),
                num_workers=1,
            )
        except Exception as exc:
            if self._is_memory_error(exc):
                raise RuntimeError(self._memory_message()) from exc
            raise

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("尚未安装语音引擎，请先运行 setup.ps1。") from exc

        WHISPER_MODEL_ROOT.mkdir(parents=True, exist_ok=True)
        self._choose_device()
        self._check_available_memory()
        LOGGER.info("Loading Whisper %s on %s", self.model_name, self.active_device)
        model_path = ensure_whisper_model(self.model_name)
        try:
            self._model = self._create_model(model_path, self.active_device, self.compute_type)
        except Exception as exc:
            if self.active_device != "cuda":
                raise
            LOGGER.warning("CUDA load failed, falling back to CPU: %s", exc)
            self.last_error = f"GPU 初始化失败，已自动切换 CPU：{exc}"
            self.active_device = "cpu"
            self.compute_type = "int8"
            self._check_available_memory()
            self._model = self._create_model(model_path, "cpu", "int8")
        return self._model

    def warm_up(self) -> None:
        """Load the selected ASR model before the first live audio chunk."""
        try:
            with self._model_lock:
                self._load_model()
        except Exception as exc:
            # Startup must remain usable even when a selected optional model or
            # GPU runtime is unavailable. The normal transcription path will
            # surface the same actionable error when the user starts listening.
            self.last_error = f"语音模型预加载失败：{exc}"
            LOGGER.warning("ASR warm-up failed: %s", exc)

    def prepare(self) -> dict:
        """Load the selected model only when the user starts interpreting."""
        with self._model_lock:
            self.last_error = None
            self._load_model()
        return self.status()

    def release(self) -> dict[str, bool]:
        """Release resident recognition and translation models while idle."""
        with self._model_lock:
            recognition_model = self._model
            recognition_released = recognition_model is not None
            if recognition_model is not None:
                runtime_model = getattr(recognition_model, "model", None)
                unload_model = getattr(runtime_model, "unload_model", None)
                if callable(unload_model):
                    try:
                        unload_model()
                    except Exception:
                        LOGGER.debug("Could not explicitly unload ASR model", exc_info=True)
            self._model = None
            translation_released = self.translator.unload()
            provider = getattr(self, "_api_translator", None)
            if provider is not None:
                translation_released = provider.unload() or translation_released
            gc.collect()
        return {
            "ok": True,
            "recognition_released": recognition_released,
            "translation_released": translation_released,
            "released": recognition_released or translation_released,
        }

    def transcribe(
        self,
        media_path: Path | bytes,
        source_language: str | None,
        audio_seconds: float = 0.0,
        context: str = "",
        target_language: str = "zh",
        translation_revision: int | None = None,
    ) -> TranscriptResult:
        started = time.perf_counter()
        submitted_revision = getattr(self, "_translation_revision", 0)
        with self._model_lock:
            current_revision = getattr(self, "_translation_revision", 0)
            # A queued local recording must never inherit a newly configured
            # cloud destination. API submissions require an explicit snapshot
            # of the settings used when that recording session began.
            if (
                (translation_revision is not None and translation_revision != current_revision)
                or (translation_revision is None and (
                    getattr(self, "_api_translator", None) is not None
                    or submitted_revision != current_revision
                ))
            ):
                raise RuntimeError("翻译设置已变化或未确认，请停止后重新开始同传。")
            lock_acquired = time.perf_counter()
            model = self._load_model()
            model_ready = time.perf_counter()
            decode_options = _transcription_options(source_language, context)
            try:
                audio = prepare_audio_input(media_path)
            except MemoryError as exc:
                raise RuntimeError(self._memory_message()) from exc
            audio_ready = time.perf_counter()
            try:
                try:
                    segments, info = model.transcribe(audio, **decode_options)
                    original = clean_transcript(" ".join(segment.text for segment in segments))
                except Exception as exc:
                    # Some CUDA linkage failures only surface on the first inference.
                    if self.active_device != "cuda":
                        if self._is_memory_error(exc):
                            raise RuntimeError(self._memory_message()) from exc
                        raise
                    self.last_error = f"GPU 推理失败，已自动切换 CPU：{exc}"
                    self._model = None
                    self.active_device = "cpu"
                    self.compute_type = "int8"
                    self._check_available_memory()
                    self._model = self._create_model(ensure_whisper_model(self.model_name), "cpu", "int8")
                    # PyAV may already have consumed an in-memory fallback
                    # stream before a CUDA generator raises. Retry from byte 0.
                    if isinstance(audio, io.BytesIO):
                        audio.seek(0)
                    segments, info = self._model.transcribe(audio, **decode_options)
                    original = clean_transcript(" ".join(segment.text for segment in segments))
            finally:
                if isinstance(audio, io.BytesIO):
                    audio.close()

            detected = getattr(info, "language", None) or source_language or "en"
            probability = float(getattr(info, "language_probability", 0.0) or 0.0)
            continued = bool(context.strip() and original)
            if continued:
                original = merge_continuation(context, original, detected)
            recognition_finished = time.perf_counter()
            provider = getattr(self, "_api_translator", None)
            translation_mode = "api" if provider is not None else "local"
            if provider is None:
                translated = self.translator.translate(original, detected, target_language)
            else:
                try:
                    translated = provider.translate(original, detected, target_language)
                except Exception:
                    # Never attach provider exceptions: URLs/headers may contain credentials.
                    LOGGER.warning("API translation failed unexpectedly")
                    translated = TranslationResult("", detected, False, "API 翻译失败，请检查服务配置后重试。")
            translation_finished = time.perf_counter()

        latency = int((time.perf_counter() - started) * 1000)
        return TranscriptResult(
            original=original,
            translation=translated.text,
            language=detected,
            target_language=target_language,
            language_probability=round(probability, 3),
            latency_ms=latency,
            audio_seconds=round(audio_seconds, 2),
            device=self.active_device,
            model=self.model_name,
            translation_ready=translated.ready,
            continued=continued,
            warning=translated.warning or self.last_error,
            translation_mode=translation_mode,
            timings_ms={
                "lock_wait": round((lock_acquired - started) * 1000, 3),
                "model_load": round((model_ready - lock_acquired) * 1000, 3),
                "audio_prepare": round((audio_ready - model_ready) * 1000, 3),
                "recognition": round((recognition_finished - audio_ready) * 1000, 3),
                "translation": round((translation_finished - recognition_finished) * 1000, 3),
            },
        )
