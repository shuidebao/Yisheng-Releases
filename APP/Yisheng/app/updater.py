from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from . import __version__
from .config import ROOT


LOGGER = logging.getLogger(__name__)
UPDATE_ROOT = ROOT / ".updates"
MANIFEST_URL = os.environ.get(
    "YISHENG_UPDATE_MANIFEST_URL",
    "https://github.com/shuidebao/Yisheng-Releases/releases/latest/download/update.json",
)
MAX_MANIFEST_BYTES = 128 * 1024
CHUNK_BYTES = 1024 * 1024


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = value.strip().split(".")
    if not parts or any(not part.isdigit() for part in parts):
        raise ValueError(f"无效版本号：{value}")
    return tuple(int(part) for part in parts)


def _safe_filename(value: str) -> str:
    name = Path(value).name
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.exe", name, flags=re.IGNORECASE):
        raise ValueError("更新文件名不安全。")
    return name


class UpdateManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._download_thread: threading.Thread | None = None
        self._manifest: dict[str, Any] | None = None
        self._state: dict[str, Any] = {
            "status": "idle",
            "current_version": __version__,
            "available": False,
            "progress": 0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "error": None,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state)

    def _update_state(self, **changes: Any) -> None:
        with self._lock:
            self._state.update(changes)

    def check(self) -> dict[str, Any]:
        self._update_state(status="checking", error=None)
        request = urllib.request.Request(
            MANIFEST_URL,
            headers={"User-Agent": f"Yisheng/{__version__}", "Cache-Control": "no-cache"},
        )
        try:
            with urllib.request.urlopen(request, timeout=7) as response:
                raw = response.read(MAX_MANIFEST_BYTES + 1)
            if len(raw) > MAX_MANIFEST_BYTES:
                raise ValueError("更新信息文件过大。")
            manifest = json.loads(raw.decode("utf-8"))
            latest = str(manifest["version"]).strip()
            download_url = str(manifest["url"]).strip()
            sha256 = str(manifest["sha256"]).strip().upper()
            filename = _safe_filename(str(manifest.get("filename") or Path(download_url).name))
            if not download_url.lower().startswith("https://"):
                raise ValueError("更新下载地址必须使用 HTTPS。")
            if not re.fullmatch(r"[0-9A-F]{64}", sha256):
                raise ValueError("更新文件校验值无效。")
            available = _version_tuple(latest) > _version_tuple(__version__)
            normalized = {
                "version": latest,
                "url": download_url,
                "sha256": sha256,
                "filename": filename,
                "size": int(manifest.get("size") or 0),
                "notes": str(manifest.get("notes") or "修复问题并提升稳定性。")[:2000],
                "mandatory": bool(manifest.get("mandatory", False)),
            }
            with self._lock:
                self._manifest = normalized
                self._state.update(
                    status="available" if available else "current",
                    available=available,
                    latest_version=latest,
                    notes=normalized["notes"],
                    mandatory=normalized["mandatory"],
                    total_bytes=normalized["size"],
                    error=None,
                )
            return self.status()
        except (OSError, ValueError, KeyError, json.JSONDecodeError, urllib.error.URLError) as exc:
            LOGGER.info("Update check unavailable: %s", exc)
            self._update_state(
                status="unavailable",
                available=False,
                error="暂时无法连接更新服务器，当前版本可以继续正常使用。",
            )
            return self.status()

    def start_download(self) -> dict[str, Any]:
        with self._lock:
            if self._download_thread and self._download_thread.is_alive():
                return dict(self._state)
            if not self._manifest or not self._state.get("available"):
                raise RuntimeError("当前没有可下载的新版本。")
            self._state.update(status="downloading", progress=0, error=None)
            self._download_thread = threading.Thread(
                target=self._download,
                name="yisheng-update-download",
                daemon=True,
            )
            self._download_thread.start()
            return dict(self._state)

    def _download(self) -> None:
        assert self._manifest is not None
        manifest = dict(self._manifest)
        UPDATE_ROOT.mkdir(parents=True, exist_ok=True)
        final_path = UPDATE_ROOT / manifest["filename"]
        partial_path = final_path.with_suffix(final_path.suffix + ".part")
        expected_size = int(manifest.get("size") or 0)

        try:
            existing = partial_path.stat().st_size if partial_path.exists() else 0
            headers = {"User-Agent": f"Yisheng/{__version__}"}
            if existing:
                headers["Range"] = f"bytes={existing}-"
            request = urllib.request.Request(manifest["url"], headers=headers)
            response = urllib.request.urlopen(request, timeout=20)
            try:
                resumed = existing > 0 and getattr(response, "status", 200) == 206
                if not resumed:
                    existing = 0
                content_length = int(response.headers.get("Content-Length") or 0)
                total = expected_size or (existing + content_length)
                mode = "ab" if resumed else "wb"
                downloaded = existing
                with partial_path.open(mode) as output:
                    while True:
                        chunk = response.read(CHUNK_BYTES)
                        if not chunk:
                            break
                        output.write(chunk)
                        downloaded += len(chunk)
                        progress = int(downloaded * 100 / total) if total else 0
                        self._update_state(
                            status="downloading",
                            progress=max(0, min(99, progress)),
                            downloaded_bytes=downloaded,
                            total_bytes=total,
                        )
            finally:
                response.close()

            digest = hashlib.sha256()
            with partial_path.open("rb") as source:
                for chunk in iter(lambda: source.read(CHUNK_BYTES), b""):
                    digest.update(chunk)
            if digest.hexdigest().upper() != manifest["sha256"]:
                partial_path.unlink(missing_ok=True)
                raise RuntimeError("新版安装包校验失败，请重新下载。")
            partial_path.replace(final_path)
            self._update_state(
                status="ready",
                progress=100,
                downloaded_bytes=final_path.stat().st_size,
                total_bytes=final_path.stat().st_size,
                installer_path=str(final_path),
                error=None,
            )
        except Exception as exc:
            LOGGER.exception("Update download failed")
            self._update_state(
                status="error",
                error=f"更新下载失败：{exc} 当前版本可以继续使用。",
            )

    def launch_installer(self) -> dict[str, Any]:
        state = self.status()
        path = Path(str(state.get("installer_path") or ""))
        if state.get("status") != "ready" or not path.is_file():
            return {"ok": False, "error": "新版安装包尚未准备完成。"}
        try:
            subprocess.Popen(
                [str(path), "--upgrade", str(ROOT)],
                cwd=str(path.parent),
                close_fds=True,
            )
            return {"ok": True}
        except OSError as exc:
            LOGGER.exception("Could not launch update installer")
            return {"ok": False, "error": f"无法启动更新安装程序：{exc}"}


update_manager = UpdateManager()
