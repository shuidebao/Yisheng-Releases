from __future__ import annotations

import json
import os
import shutil
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from . import __version__
from .config import WHISPER_MODEL_ROOT


ALLOWED_MODELS = {"tiny", "base", "small", "medium"}
REQUIRED_FILES = ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt")
MODEL_SPECS: dict[str, dict[str, Any]] = {
    "tiny": {"label": "Tiny", "model_bytes": 75_538_270, "total_bytes": 78_203_619, "bundled": False},
    "base": {"label": "Base", "model_bytes": 145_217_532, "total_bytes": 147_882_941, "bundled": True},
    "small": {"label": "Small", "model_bytes": 483_546_902, "total_bytes": 486_212_372, "bundled": False},
    "medium": {"label": "Medium", "model_bytes": 1_527_906_378, "total_bytes": 1_530_571_735, "bundled": False},
}
_source_override = os.environ.get("YISHENG_WHISPER_MODEL_URL")
MODEL_SOURCES = (
    [("自定义源", _source_override)]
    if _source_override
    else [
        (
            "国内 ModelScope",
            "https://modelscope.cn/models/Systran/faster-whisper-{model}/resolve/master/{filename}",
        ),
        (
            "官方备用源",
            "https://huggingface.co/Systran/faster-whisper-{model}/resolve/main/{filename}?download=true",
        ),
    ]
)
CHUNK_BYTES = 1024 * 1024
DISK_RESERVE_BYTES = 512 * 1024 * 1024

_state_lock = threading.RLock()
_download_threads: dict[str, threading.Thread] = {}
_download_states: dict[str, dict[str, Any]] = {}


def model_directory(model: str) -> Path:
    if model not in ALLOWED_MODELS:
        raise ValueError(f"不支持的模型：{model}")
    return WHISPER_MODEL_ROOT / "local" / model


def model_ready(model: str) -> bool:
    directory = model_directory(model)
    if not all((directory / name).is_file() and (directory / name).stat().st_size > 0 for name in REQUIRED_FILES):
        return False
    if (directory / "model.bin").stat().st_size != int(MODEL_SPECS[model]["model_bytes"]):
        return False
    try:
        json.loads((directory / "config.json").read_text(encoding="utf-8"))
        json.loads((directory / "tokenizer.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return False
    return True


def _legacy_cache(model: str) -> Path:
    return WHISPER_MODEL_ROOT / f"models--Systran--faster-whisper-{model}"


def _copy_file(source: Path, target: Path) -> None:
    if target.is_file() and target.stat().st_size == source.stat().st_size:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def _materialize_legacy_cache(model: str, destination: Path) -> None:
    """Convert an old snapshot-style cache into ordinary local files."""
    cache = _legacy_cache(model)
    if not cache.is_dir():
        return
    snapshots = cache / "snapshots"
    if snapshots.is_dir():
        for snapshot in snapshots.iterdir():
            if not snapshot.is_dir():
                continue
            for name in REQUIRED_FILES:
                source = snapshot / name
                if source.is_file():
                    _copy_file(source, destination / name)
    tree_files = list((cache / "trees").glob("*.json")) if (cache / "trees").is_dir() else []
    for tree_file in tree_files:
        try:
            files = json.loads(tree_file.read_text(encoding="utf-8")).get("files", {})
        except (OSError, ValueError):
            continue
        for name in REQUIRED_FILES:
            if (destination / name).is_file():
                continue
            metadata = files.get(name, {})
            for identifier in (metadata.get("blob_id"), metadata.get("lfs_sha256")):
                if not identifier:
                    continue
                source = cache / "blobs" / identifier
                if source.is_file():
                    _copy_file(source, destination / name)
                    break


def _directory_bytes(path: Path) -> int:
    if not path.is_dir():
        return 0
    total = 0
    for item in path.iterdir():
        if item.is_file() and (item.name in REQUIRED_FILES or item.name.endswith(".part")):
            try:
                total += item.stat().st_size
            except OSError:
                pass
    return total


def _default_state(model: str) -> dict[str, Any]:
    installed = model_ready(model)
    spec = MODEL_SPECS[model]
    downloaded = int(spec["total_bytes"]) if installed else _directory_bytes(model_directory(model))
    return {
        "model": model,
        "label": spec["label"],
        "bundled": bool(spec["bundled"]),
        "installed": installed,
        "status": "ready" if installed else "idle",
        "progress": 100 if installed else min(99, int(downloaded * 100 / int(spec["total_bytes"]))),
        "downloaded_bytes": downloaded,
        "total_bytes": int(spec["total_bytes"]),
        "source": None,
        "error": None,
    }


def model_status(model: str) -> dict[str, Any]:
    if model not in ALLOWED_MODELS:
        raise ValueError(f"不支持的模型：{model}")
    with _state_lock:
        state = _download_states.get(model)
        if state is None:
            state = _default_state(model)
            _download_states[model] = state
        elif model_ready(model) and state.get("status") != "downloading":
            state.update(installed=True, status="ready", progress=100, error=None)
        return dict(state)


def models_status() -> dict[str, dict[str, Any]]:
    return {model: model_status(model) for model in ("tiny", "base", "small", "medium")}


def _set_state(model: str, **changes: Any) -> None:
    with _state_lock:
        state = _download_states.setdefault(model, _default_state(model))
        state.update(changes)


def _download_file_from_source(
    model: str,
    filename: str,
    destination: Path,
    completed_before: int,
    source_name: str,
    source_template: str,
) -> None:
    if destination.is_file() and destination.stat().st_size > 0:
        if filename != "model.bin" or destination.stat().st_size == int(MODEL_SPECS[model]["model_bytes"]):
            return
    partial = destination.with_name(destination.name + ".part")
    existing = partial.stat().st_size if partial.is_file() else 0
    headers = {"User-Agent": f"Yisheng/{__version__}"}
    if existing:
        headers["Range"] = f"bytes={existing}-"
    url = source_template.format(model=model, filename=filename)
    response = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20)
    try:
        resumed = existing > 0 and getattr(response, "status", 200) == 206
        if not resumed:
            existing = 0
        mode = "ab" if resumed else "wb"
        downloaded = existing
        with partial.open(mode) as output:
            while True:
                chunk = response.read(CHUNK_BYTES)
                if not chunk:
                    break
                output.write(chunk)
                downloaded += len(chunk)
                total_downloaded = completed_before + downloaded
                total_bytes = int(MODEL_SPECS[model]["total_bytes"])
                progress = min(99, int(total_downloaded * 100 / total_bytes))
                _set_state(
                    model,
                    status="downloading",
                    progress=max(0, progress),
                    downloaded_bytes=total_downloaded,
                    total_bytes=total_bytes,
                    source=source_name,
                    error=None,
                )
    finally:
        response.close()
    partial.replace(destination)


def _download_file(model: str, filename: str, destination: Path, completed_before: int) -> None:
    if destination.is_file() and destination.stat().st_size > 0:
        if filename != "model.bin" or destination.stat().st_size == int(MODEL_SPECS[model]["model_bytes"]):
            return
    failures: list[str] = []
    for source_name, source_template in MODEL_SOURCES:
        try:
            _set_state(model, source=source_name)
            _download_file_from_source(
                model,
                filename,
                destination,
                completed_before,
                source_name,
                source_template,
            )
            return
        except (OSError, urllib.error.URLError) as exc:
            failures.append(f"{source_name}：{exc}")
    raise RuntimeError("；".join(failures) or "没有可用的模型下载源。")


def _validate_download(model: str) -> None:
    directory = model_directory(model)
    expected = int(MODEL_SPECS[model]["model_bytes"])
    actual = (directory / "model.bin").stat().st_size if (directory / "model.bin").is_file() else 0
    if actual != expected:
        raise RuntimeError(f"模型主文件大小不正确：实际 {actual}，预期 {expected}。")
    if not model_ready(model):
        raise RuntimeError("模型文件不完整或配置校验失败。")


def _download_model(model: str) -> None:
    destination = model_directory(model)
    destination.mkdir(parents=True, exist_ok=True)
    total_bytes = int(MODEL_SPECS[model]["total_bytes"])
    try:
        free_bytes = shutil.disk_usage(destination).free
        existing_bytes = _directory_bytes(destination)
        required = max(0, total_bytes - existing_bytes) + DISK_RESERVE_BYTES
        if free_bytes < required:
            shortage = required - free_bytes
            raise RuntimeError(f"磁盘空间不足，还需要约 {shortage / 1024 / 1024:.0f} MB 可用空间。")
        completed = 0
        for filename in REQUIRED_FILES:
            target = destination / filename
            _download_file(model, filename, target, completed)
            completed += target.stat().st_size
            _set_state(model, downloaded_bytes=completed)
        _validate_download(model)
        _set_state(
            model,
            installed=True,
            status="ready",
            progress=100,
            downloaded_bytes=total_bytes,
            total_bytes=total_bytes,
            source=_download_states.get(model, {}).get("source"),
            error=None,
        )
    except (OSError, RuntimeError, ValueError, urllib.error.URLError) as exc:
        detail = str(exc)
        if isinstance(exc, OSError) and getattr(exc, "winerror", None) == 112:
            detail = "磁盘空间不足，请释放空间后重试。"
        _set_state(
            model,
            installed=False,
            status="error",
            error=f"{MODEL_SPECS[model]['label']} 下载失败：{detail} Base 模型仍可继续使用。",
        )


def start_model_download(model: str) -> dict[str, Any]:
    if model not in ALLOWED_MODELS:
        raise ValueError(f"不支持的模型：{model}")
    if model_ready(model):
        return model_status(model)
    if model == "base":
        raise RuntimeError("内置 Base 模型不完整，请重新安装译声。")
    with _state_lock:
        thread = _download_threads.get(model)
        if thread and thread.is_alive():
            return model_status(model)
        _download_states[model] = _default_state(model)
        _download_states[model].update(status="downloading", error=None)
        thread = threading.Thread(
            target=_download_model,
            args=(model,),
            name=f"yisheng-model-{model}",
            daemon=True,
        )
        _download_threads[model] = thread
        thread.start()
        return dict(_download_states[model])


def ensure_whisper_model(model: str) -> Path:
    """Return a complete local model directory without Windows symlinks."""
    destination = model_directory(model)
    destination.mkdir(parents=True, exist_ok=True)
    _materialize_legacy_cache(model, destination)
    if model_ready(model):
        return destination
    state = model_status(model)
    if state["status"] == "downloading":
        raise RuntimeError(f"{MODEL_SPECS[model]['label']} 模型正在下载，请等待完成。")
    if model == "base":
        raise RuntimeError("内置 Base 识别模型不完整，请重新安装译声。")
    raise RuntimeError(f"{MODEL_SPECS[model]['label']} 模型尚未安装，请在设置中下载。")
