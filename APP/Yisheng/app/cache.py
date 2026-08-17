from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Iterable

from .config import MODEL_ROOT, ROOT, WHISPER_MODEL_ROOT
from .whisper_models import ALLOWED_MODELS, model_directory, model_ready


WEBVIEW_PROFILE = MODEL_ROOT / "webview-profile"
WEBVIEW_CLEAR_MARKER = MODEL_ROOT / "clear-webview-cache"
TEMP_AUDIO_PREFIX = "yisheng-audio-"
WEBVIEW_CACHE_PATHS = (
    "Cache",
    "Code Cache",
    "GPUCache",
    "DawnCache",
    "GrShaderCache",
    "ShaderCache",
    "Service Worker/CacheStorage",
)


def _path_size(path: Path) -> int:
    try:
        if path.is_file():
            return path.stat().st_size
        if path.is_dir():
            return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
    except OSError:
        return 0
    return 0


def _temporary_audio_files() -> Iterable[Path]:
    try:
        yield from Path(tempfile.gettempdir()).glob(f"{TEMP_AUDIO_PREFIX}*")
    except OSError:
        return


def _safe_cache_targets() -> list[Path]:
    targets: list[Path] = list(_temporary_audio_files())
    targets.extend((ROOT / "logs").glob("desktop.log.*"))

    if WHISPER_MODEL_ROOT.exists():
        targets.extend(WHISPER_MODEL_ROOT.rglob("*.incomplete"))
        targets.extend(WHISPER_MODEL_ROOT.rglob("*.lock"))

    for model in sorted(ALLOWED_MODELS):
        if not model_ready(model):
            continue
        # Once ordinary local files are complete, Hugging Face metadata and the
        # former snapshot-style cache are redundant. The model itself is kept.
        targets.append(model_directory(model) / ".cache")
        targets.append(WHISPER_MODEL_ROOT / f"models--Systran--faster-whisper-{model}")

    return targets


def _unique_existing(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        try:
            key = str(path.resolve()).casefold()
        except OSError:
            key = str(path.absolute()).casefold()
        if key in seen or not path.exists():
            continue
        seen.add(key)
        result.append(path)
    return result


def cache_status() -> dict[str, object]:
    targets = _unique_existing(_safe_cache_targets())
    installed = [model for model in sorted(ALLOWED_MODELS) if model_ready(model)]
    model_bytes = sum(_path_size(model_directory(model)) for model in installed)
    return {
        "cache_bytes": sum(_path_size(path) for path in targets),
        "cache_items": len(targets),
        "model_bytes": model_bytes,
        "installed_models": installed,
        "models_preserved": True,
    }


def clear_cache() -> dict[str, object]:
    removed_bytes = 0
    removed_items = 0
    skipped_items = 0

    for path in _unique_existing(_safe_cache_targets()):
        size = _path_size(path)
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
            removed_bytes += size
            removed_items += 1
        except OSError:
            # A file can be briefly locked by Windows. It remains visible in
            # cache status and can be retried on the next click.
            skipped_items += 1

    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        WEBVIEW_CLEAR_MARKER.touch(exist_ok=True)
        restart_required = True
    except OSError:
        restart_required = False

    status = cache_status()
    return {
        "ok": True,
        "removed_bytes": removed_bytes,
        "removed_items": removed_items,
        "skipped_items": skipped_items,
        "restart_required": restart_required,
        **status,
    }


def clear_webview_cache_on_start() -> dict[str, int | bool]:
    """Finish browser-cache cleanup before WebView opens its profile."""
    if not WEBVIEW_CLEAR_MARKER.exists():
        return {"requested": False, "removed_bytes": 0, "removed_items": 0}

    removed_bytes = 0
    removed_items = 0
    for relative in WEBVIEW_CACHE_PATHS:
        target = WEBVIEW_PROFILE / Path(relative)
        if not target.exists():
            continue
        size = _path_size(target)
        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink(missing_ok=True)
            removed_bytes += size
            removed_items += 1
        except OSError:
            continue
    try:
        WEBVIEW_CLEAR_MARKER.unlink(missing_ok=True)
    except OSError:
        pass
    return {"requested": True, "removed_bytes": removed_bytes, "removed_items": removed_items}
