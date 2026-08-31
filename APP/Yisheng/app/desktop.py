from __future__ import annotations

import ctypes
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import uvicorn

from . import APP_NAME, COPYRIGHT, DEVELOPER, OFFICIAL_REPOSITORY, __version__
from .cache import clear_webview_cache_on_start
from .config import ROOT, detect_hardware
from .updater import update_manager


LOGGER = logging.getLogger("yisheng.desktop")
HOST = "127.0.0.1"
APP_TITLE = "译声 · 本地同声传译"
ACTIVATE_EVENT_NAME = r"Local\Yisheng_Interpreter_Activate"
QUIT_EVENT_NAME = r"Local\Yisheng_Interpreter_Quit"
BACKEND_START_TIMEOUT_SECONDS = 120.0


def prefer_foreground_apps() -> bool:
    """Run YiSheng below normal priority so a game keeps scheduler priority."""
    if os.name != "nt":
        return False
    try:
        kernel32 = ctypes.windll.kernel32
        get_current_process = kernel32.GetCurrentProcess
        get_current_process.restype = ctypes.c_void_p
        set_priority_class = kernel32.SetPriorityClass
        set_priority_class.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        set_priority_class.restype = ctypes.c_int
        return bool(set_priority_class(get_current_process(), 0x00004000))
    except (AttributeError, OSError, TypeError):
        return False


def find_free_port(host: str = HOST) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((host, 0))
        return int(probe.getsockname()[1])


def wait_for_health(
    url: str,
    timeout: float = BACKEND_START_TIMEOUT_SECONDS,
    is_running: Callable[[], bool] | None = None,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_running is not None and not is_running():
            return False
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=0.8) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if response.status == 200 and payload.get("ok") is True:
                    return True
        except (OSError, ValueError, urllib.error.URLError):
            time.sleep(0.1)
    return False


class LocalBackend:
    """Owns the local FastAPI server for the lifetime of the desktop window."""

    def __init__(self, port: int | None = None) -> None:
        self.port = port or find_free_port()
        self.url = f"http://{HOST}:{self.port}"
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._startup_error: BaseException | None = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and self._server and self._server.started)

    def start(self, timeout: float = BACKEND_START_TIMEOUT_SECONDS) -> None:
        if self.running:
            return
        config = uvicorn.Config(
            "app.main:app",
            host=HOST,
            port=self.port,
            log_level="warning",
            access_log=False,
            # The branded YishengBackend.exe is the embedded pythonw runtime
            # and deliberately has no console/stdout. Keep all diagnostics in
            # Yisheng's rotating desktop.log instead of Uvicorn's console setup.
            log_config=None,
        )
        self._server = uvicorn.Server(config)
        self._startup_error = None

        def run_server() -> None:
            try:
                self._server.run()
            except BaseException as exc:
                self._startup_error = exc
                LOGGER.exception("Local backend thread failed during startup")

        self._thread = threading.Thread(
            target=run_server,
            name="yisheng-local-backend",
            daemon=True,
        )
        started_at = time.monotonic()
        LOGGER.info("Starting local backend; cold-start timeout is %.0f seconds", timeout)
        self._thread.start()
        if not wait_for_health(
            self.url,
            timeout,
            is_running=lambda: bool(self._thread and self._thread.is_alive()),
        ):
            startup_error = self._startup_error
            thread_alive = bool(self._thread and self._thread.is_alive())
            self.stop()
            if startup_error is not None:
                raise RuntimeError(f"本地同传后端启动失败：{startup_error}") from startup_error
            if not thread_alive:
                raise RuntimeError("本地同传后端启动进程提前结束。")
            raise RuntimeError(f"本地同传后端首次启动超过 {timeout:.0f} 秒，请重新启动应用。")
        LOGGER.info("Local backend ready after %.1f seconds", time.monotonic() - started_at)

    def stop(self, timeout: float = 5.0) -> None:
        if self._server:
            self._server.should_exit = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                LOGGER.warning("Local backend thread did not stop within %.1f seconds", timeout)
        self._server = None
        self._thread = None


class WindowsAppControl:
    """Receives restore and quit requests from the Windows launcher/tray."""

    WAIT_OBJECT_0 = 0
    WAIT_TIMEOUT = 258

    def __init__(self, on_activate: Any, on_quit: Any) -> None:
        self._on_activate = on_activate
        self._on_quit = on_quit
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._kernel32: Any | None = None
        self._activate_handle: int | None = None
        self._quit_handle: int | None = None

    def start(self) -> None:
        if os.name != "nt" or self._thread is not None:
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateEventW.restype = ctypes.c_void_p
        kernel32.SetEvent.argtypes = [ctypes.c_void_p]
        kernel32.SetEvent.restype = ctypes.c_bool
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_bool
        kernel32.WaitForMultipleObjects.argtypes = [
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_bool,
            ctypes.c_ulong,
        ]
        kernel32.WaitForMultipleObjects.restype = ctypes.c_ulong

        activate = kernel32.CreateEventW(None, False, False, ACTIVATE_EVENT_NAME)
        quit_handle = kernel32.CreateEventW(None, False, False, QUIT_EVENT_NAME)
        if not activate or not quit_handle:
            if activate:
                kernel32.CloseHandle(activate)
            if quit_handle:
                kernel32.CloseHandle(quit_handle)
            raise OSError(ctypes.get_last_error(), "无法建立译声窗口控制通道。")

        self._kernel32 = kernel32
        self._activate_handle = int(activate)
        self._quit_handle = int(quit_handle)
        self._thread = threading.Thread(
            target=self._listen,
            name="yisheng-window-control",
            daemon=True,
        )
        self._thread.start()
        LOGGER.info("Windows launcher control channel ready")

    def _listen(self) -> None:
        if self._kernel32 is None or self._activate_handle is None or self._quit_handle is None:
            return
        handles = (ctypes.c_void_p * 2)(self._activate_handle, self._quit_handle)
        while not self._stop.is_set():
            result = int(self._kernel32.WaitForMultipleObjects(2, handles, False, 250))
            if self._stop.is_set():
                break
            try:
                if result == self.WAIT_OBJECT_0:
                    LOGGER.info("Restore request received from launcher/tray")
                    self._on_activate()
                elif result == self.WAIT_OBJECT_0 + 1:
                    LOGGER.info("Exit request received from launcher tray")
                    self._on_quit()
                    break
                elif result != self.WAIT_TIMEOUT:
                    LOGGER.warning("Windows control wait returned unexpected value: %s", result)
                    break
            except Exception:
                LOGGER.exception("Windows launcher control request failed")

    def stop(self) -> None:
        self._stop.set()
        if self._kernel32 is not None and self._activate_handle is not None:
            self._kernel32.SetEvent(ctypes.c_void_p(self._activate_handle))
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self._kernel32 is not None:
            for handle in (self._activate_handle, self._quit_handle):
                if handle is not None:
                    self._kernel32.CloseHandle(ctypes.c_void_p(handle))
        self._thread = None
        self._activate_handle = None
        self._quit_handle = None


class DesktopBridge:
    """Small, explicit bridge for interactions that need Windows UI."""

    MAX_EXPORT_CHARS = 2_000_000
    OVERLAY_HISTORY_LIMIT = 4

    def __init__(self) -> None:
        # Keep native objects private. pywebview exposes public JS API members
        # recursively, and a public Window reference contains circular handles.
        self._window: Any | None = None
        self._overlay_window: Any | None = None
        self._native_overlay: Any | None = None
        self._latest_subtitle: dict[str, str] = {"original": "", "translation": "", "meta": ""}
        self._overlay_history: list[dict[str, str]] = []
        self._overlay_locked = False
        self._overlay_positioned = False
        self._ui_language = "zh"

    def get_app_info(self) -> dict[str, Any]:
        hardware = detect_hardware()
        return {
            "desktop": True,
            "version": __version__,
            "name": APP_NAME,
            "developer": DEVELOPER,
            "copyright": COPYRIGHT,
            "repository": OFFICIAL_REPOSITORY,
            "platform": hardware.os,
            "gpu": hardware.gpu,
        }

    def get_overlay_snapshot(self) -> dict[str, str]:
        return dict(self._latest_subtitle)

    def get_overlay_state(self) -> dict[str, Any]:
        return {
            **self._latest_subtitle,
            "history": self._overlay_history_lines(),
            "history_count": len(self._overlay_history),
            "locked": self._overlay_locked,
            "ui_language": self._ui_language,
        }

    def set_ui_language(self, language: str) -> dict[str, Any]:
        self._ui_language = "en" if language == "en" else "zh"
        if self._native_overlay is not None:
            self._native_overlay.set_ui_language(self._ui_language)
        return {"ok": True, "language": self._ui_language}

    def show_overlay(self) -> dict[str, Any]:
        if self._window is None or self._native_overlay is None:
            return {"ok": False, "error": "悬浮字幕窗口尚未准备好。"}
        main_window = self._window
        native_overlay = self._native_overlay

        def transition() -> None:
            try:
                native_overlay.show()
                self._render_overlay()
                LOGGER.info(
                    "Native lyric overlay shown before minimizing main window: %s",
                    native_overlay.debug_state(),
                )
                # Hiding the only pywebview host form can tear down the WinForms
                # message loop on some Windows/WebView2 combinations, leaving the
                # launcher alive with no visible windows. Minimizing preserves the
                # UI loop while the topmost native lyric window remains visible.
                main_window.minimize()

                def audit_overlay() -> None:
                    try:
                        LOGGER.info(
                            "Native lyric overlay one-second audit: %s",
                            native_overlay.debug_state(),
                        )
                    except Exception:
                        LOGGER.exception("Native lyric overlay did not survive the transition")

                threading.Timer(1.0, audit_overlay).start()
            except Exception:
                LOGGER.exception("Could not show overlay window")

        # Let pywebview return the JavaScript promise before hiding its source window.
        threading.Timer(0.08, transition).start()
        return {"ok": True}

    def restore_main(self) -> dict[str, Any]:
        if self._window is None:
            return {"ok": False, "error": "主窗口尚未准备好。"}
        main_window = self._window
        native_overlay = self._native_overlay

        def transition() -> None:
            if native_overlay is not None:
                try:
                    native_overlay.hide()
                except Exception:
                    # The user may have closed the overlay form itself. That
                    # must never prevent the minimized main window returning.
                    LOGGER.info("Overlay was already closed while restoring the main window")
            try:
                main_window.show()
                main_window.restore()
                if os.name == "nt":
                    user32 = ctypes.windll.user32
                    handle = user32.FindWindowW(None, APP_TITLE)
                    if handle:
                        user32.ShowWindow(handle, 9)  # SW_RESTORE
                        user32.SetForegroundWindow(handle)
            except Exception:
                LOGGER.exception("Could not restore main window")

        # Resolve the click first; hiding the page before pywebview returns can deadlock WebView2.
        threading.Timer(0.08, transition).start()
        return {"ok": True}

    def update_overlay(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {"ok": False, "error": "字幕数据无效。"}
        subtitle = {
            "original": str(payload.get("original") or "")[:4000],
            "translation": str(payload.get("translation") or "")[:4000],
            "meta": str(payload.get("meta") or "")[:300],
        }
        replace_latest = bool(payload.get("replace_latest"))
        same_as_latest = bool(
            self._overlay_history
            and self._overlay_history[-1]["original"] == subtitle["original"]
            and self._overlay_history[-1]["translation"] == subtitle["translation"]
        )
        if self._overlay_history and (replace_latest or same_as_latest):
            self._overlay_history[-1] = subtitle
        elif subtitle["original"] or subtitle["translation"]:
            self._overlay_history.append(subtitle)
            del self._overlay_history[:-self.OVERLAY_HISTORY_LIMIT]
        self._latest_subtitle = subtitle
        self._render_overlay()
        return {"ok": True, "history_count": len(self._overlay_history)}

    def clear_overlay(self) -> dict[str, Any]:
        self._latest_subtitle = {"original": "", "translation": "", "meta": ""}
        self._overlay_history.clear()
        self._render_overlay()
        return {"ok": True}

    def _overlay_history_lines(self) -> list[str]:
        lines: list[str] = []
        for subtitle in self._overlay_history:
            text = (subtitle["translation"] or subtitle["original"]).strip()
            if text:
                lines.append(" ".join(text.split())[:600])
        return lines[-self.OVERLAY_HISTORY_LIMIT:]

    def resize_overlay(self, width: int, height: int) -> dict[str, Any]:
        if self._native_overlay is None:
            return {"ok": False, "error": "迷你字幕窗口尚未准备好。"}
        if self._overlay_locked:
            return {"ok": False, "locked": True, "error": "窗口已锁定，请先解除锁定。"}
        try:
            safe_width = max(480, min(1800, int(width)))
            safe_height = max(300, min(700, int(height)))
            self._native_overlay.resize(safe_width, safe_height)
            return {"ok": True, "width": safe_width, "height": safe_height}
        except (TypeError, ValueError, OSError) as exc:
            return {"ok": False, "error": f"调整窗口大小失败：{exc}"}

    def set_overlay_locked(self, locked: bool) -> dict[str, Any]:
        self._overlay_locked = bool(locked)
        if self._native_overlay is not None:
            state = self._native_overlay.debug_state()
            if bool(state.get("locked")) != self._overlay_locked:
                self._native_overlay.set_locked(self._overlay_locked)
        return {"ok": True, "locked": self._overlay_locked}

    def set_overlay_transparency(self, percent: int) -> dict[str, Any]:
        if self._native_overlay is None:
            return {"ok": False, "error": "迷你字幕窗口尚未准备好。"}
        value = max(0, min(100, int(percent)))
        self._native_overlay.set_transparency(value)
        return {"ok": True, "transparency": value}

    def _on_native_lock_changed(self, locked: bool) -> None:
        self._overlay_locked = bool(locked)

    def _render_overlay(self) -> None:
        if self._native_overlay is None:
            return
        try:
            self._native_overlay.update(
                **self._latest_subtitle,
                history=self._overlay_history_lines(),
            )
        except Exception:
            LOGGER.debug("Native overlay is not ready yet", exc_info=True)

    def default_export_name(self) -> str:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        prefix = "YiSheng_Transcript" if self._ui_language == "en" else "译声同传"
        return f"{prefix}_{stamp}.txt"

    def save_transcript(self, content: str) -> dict[str, Any]:
        if not isinstance(content, str) or not content.strip():
            return {"ok": False, "cancelled": False, "error": "没有可导出的内容。"}
        if len(content) > self.MAX_EXPORT_CHARS:
            return {"ok": False, "cancelled": False, "error": "文本过长，无法导出。"}
        if self._window is None:
            return {"ok": False, "cancelled": False, "error": "桌面窗口尚未准备好。"}

        try:
            import webview

            selected = self._window.create_file_dialog(
                webview.FileDialog.SAVE,
                save_filename=self.default_export_name(),
                file_types=(
                    ("Text files (*.txt)", "All files (*.*)")
                    if self._ui_language == "en"
                    else ("文本文件 (*.txt)", "所有文件 (*.*)")
                ),
            )
            if not selected:
                return {"ok": False, "cancelled": True}
            path = Path(selected[0]).expanduser().resolve()
            path.write_text(content, encoding="utf-8-sig")
            return {"ok": True, "cancelled": False, "path": str(path)}
        except Exception as exc:
            LOGGER.exception("Desktop export failed")
            return {"ok": False, "cancelled": False, "error": f"保存失败：{exc}"}

    def install_update(self) -> dict[str, Any]:
        result = update_manager.launch_installer()
        if result.get("ok") and self._window is not None:
            # Give the new installer time to create its window before closing
            # the running app and releasing executable files for replacement.
            window = self._window
            native_overlay = self._native_overlay

            def close_windows() -> None:
                if native_overlay is not None:
                    try:
                        native_overlay.close()
                    except Exception:
                        pass
                window.destroy()

            threading.Timer(1.0, close_windows).start()
        return result


def _show_fatal_error(message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(0, message, APP_TITLE, 0x10)
    except (AttributeError, OSError):
        print(message)


def main() -> int:
    clear_webview_cache_on_start()
    log_dir = ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[RotatingFileHandler(
            log_dir / "desktop.log",
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )],
    )
    if prefer_foreground_apps():
        LOGGER.info("YiSheng process priority set to BelowNormal for game responsiveness")

    try:
        import webview
    except ImportError:
        _show_fatal_error("桌面组件尚未安装，请重新运行 setup.cmd。")
        return 1

    backend = LocalBackend()
    app_control: WindowsAppControl | None = None
    smoke_test = os.getenv("YISHENG_DESKTOP_SMOKE_TEST") == "1"
    visual_overlay_test = os.getenv("YISHENG_OVERLAY_VISUAL_TEST") == "1"
    fatal_error: str | None = None
    try:
        backend.start()
        bridge = DesktopBridge()
        window = webview.create_window(
            APP_TITLE,
            backend.url,
            js_api=bridge,
            width=1280,
            height=820,
            min_size=(900, 620),
            hidden=True,
            resizable=True,
            background_color="#090b12",
            text_select=True,
        )
        if window is None:
            raise RuntimeError("无法创建桌面窗口。")
        bridge._window = window

        def request_app_exit() -> None:
            def close_window() -> None:
                try:
                    window.destroy()
                except Exception:
                    LOGGER.exception("Could not close the desktop window from the tray")

            threading.Timer(0.05, close_window).start()

        app_control = WindowsAppControl(bridge.restore_main, request_app_exit)
        app_control.start()
        loaded = threading.Event()
        startup_state = {"interactive": False, "error": None}
        window.events.loaded += lambda: loaded.set()

        def prepare_window() -> None:
            # The WebView loaded event can fire before the worker reaches this
            # wait on fast or reused profiles. Poll the actual page contract so
            # a missed one-shot event is never mistaken for a startup failure.
            loaded.wait(timeout=1.5)
            deadline = time.monotonic() + 30
            capabilities = None
            while time.monotonic() < deadline:
                try:
                    capability_script = "".join([
                        "({",
                        "microphone: Boolean(navigator.mediaDevices && navigator.mediaDevices.getUserMedia),",
                        "desktopBridge: Boolean(window.pywebview && window.pywebview.api && window.pywebview.api.get_app_info),",
                        "recordButton: Boolean(document.getElementById('recordButton')),",
                        "audioSource: Boolean(document.getElementById('audioSourceSelect')),",
                        "targetLanguage: Boolean(document.getElementById('targetLanguageSelect')),",
                        "languageToggle: Boolean(document.getElementById('languageToggle')),",
                        "about: Boolean(document.getElementById('aboutVersion') && document.getElementById('officialRepository')),",
                        "styles: Array.from(document.styleSheets).some(s => (s.href || '').includes('styles.css')),",
                        "appReady: document.documentElement.dataset.appReady === '1'",
                        "})",
                    ])
                    capabilities = window.evaluate_js(capability_script)
                    startup_state["interactive"] = bool(
                        capabilities
                        and capabilities.get("microphone")
                        and capabilities.get("desktopBridge")
                        and capabilities.get("recordButton")
                        and capabilities.get("audioSource")
                        and capabilities.get("targetLanguage")
                        and capabilities.get("languageToggle")
                        and capabilities.get("about")
                        and capabilities.get("styles")
                        and capabilities.get("appReady")
                    )
                    if startup_state["interactive"]:
                        break
                except Exception:
                    LOGGER.debug("Waiting for desktop interaction layer", exc_info=True)
                time.sleep(0.15)

            LOGGER.info("Desktop interaction capabilities: %s", capabilities)
            if not startup_state["interactive"]:
                startup_state["error"] = "界面资源没有完整加载，请重新启动应用。"
                LOGGER.error(startup_state["error"])
                window.destroy()
                return

            try:
                from .native_overlay import create_native_overlay

                bridge._native_overlay = create_native_overlay(
                    window,
                    bridge.restore_main,
                    bridge._on_native_lock_changed,
                    bridge._ui_language,
                )

                def close_native_overlay() -> None:
                    # Run before the WebView host form is disposed. Otherwise
                    # WinForms can close the overlay form first, leaving its
                    # parameterless message loop alive with no visible window.
                    if bridge._native_overlay is not None:
                        bridge._native_overlay.close()

                def finish_desktop_close() -> None:
                    from System.Windows.Forms import Application

                    Application.Exit()

                window.events.closing += close_native_overlay
                window.events.closed += finish_desktop_close
                LOGGER.info("Windows native desktop lyric overlay ready")
            except Exception as exc:
                startup_state["error"] = f"Windows 桌面歌词窗口初始化失败：{exc}"
                LOGGER.error(startup_state["error"])
                window.destroy()
                return

            if smoke_test:
                language_capabilities = window.evaluate_js(
                    "setUiLanguage('en'); ({"
                    "language: localStorage.getItem('yisheng-ui-language'),"
                    "title: document.title,"
                    "settings: document.getElementById('settingsButton').getAttribute('title'),"
                    "target: document.querySelector('label[for=\"targetLanguageSelect\"]').textContent"
                    "})"
                )
                bridge.set_ui_language("en")
                bridge.update_overlay({
                    "original": "First rolling subtitle",
                    "translation": "第一句保留在最上方",
                    "meta": "Base · CPU · 80 ms",
                })
                bridge.update_overlay({
                    "original": "Second rolling subtitle",
                    "translation": "第二句随新内容向上滚动",
                    "meta": "Base · CPU · 90 ms",
                })
                bridge.update_overlay({
                    "original": "Third rolling subtitle",
                    "translation": "第三句仍然可以继续阅读",
                    "meta": "Base · CPU · 100 ms",
                })
                bridge.update_overlay({
                    "original": "Current subtitle remains highlighted",
                    "translation": "第四句作为当前译文高亮",
                    "meta": "Base · CPU · 120 ms",
                })
                bridge.set_overlay_transparency(100)
                result = bridge.show_overlay()
                if not result.get("ok"):
                    startup_state["error"] = result.get("error") or "迷你字幕窗口打开失败。"
                    LOGGER.error(startup_state["error"])
                    window.destroy()
                    return
                time.sleep(0.35)
                bridge.set_overlay_locked(False)
                resize_result = bridge.resize_overlay(760, 300)
                saved_style = bridge._native_overlay.debug_state()
                bridge._native_overlay.set_text_style(18, 24, "#66CCFF", "#FFCC66")
                bridge._native_overlay.show_style_settings()
                style_capabilities = bridge._native_overlay.debug_state()
                bridge._native_overlay.set_text_style(
                    saved_style["original_font_size"],
                    saved_style["translation_font_size"],
                    saved_style["original_color"],
                    saved_style["translation_color"],
                )
                lock_result = bridge.set_overlay_locked(True)
                blocked_resize = bridge.resize_overlay(800, 240)
                time.sleep(0.25)
                overlay_capabilities = bridge._native_overlay.debug_state()
                LOGGER.info("English UI interaction capabilities: %s", language_capabilities)
                LOGGER.info("Native overlay interaction capabilities: %s", overlay_capabilities)
                overlay_ok = bool(
                    overlay_capabilities
                    and language_capabilities
                    and language_capabilities.get("language") == "en"
                    and language_capabilities.get("title") == "YiSheng · Local Live Interpreter"
                    and language_capabilities.get("settings") == "Settings"
                    and language_capabilities.get("target") == "Translate to"
                    and overlay_capabilities.get("ui_language") == "en"
                    and overlay_capabilities.get("style_button") == "Text style"
                    and overlay_capabilities.get("locked")
                    and overlay_capabilities.get("transparency") == 100
                    and not overlay_capabilities.get("background_visible")
                    and resize_result.get("ok")
                    and lock_result.get("locked")
                    and blocked_resize.get("locked")
                    and style_capabilities.get("style_visible")
                    and style_capabilities.get("original_font_size") == 18
                    and style_capabilities.get("translation_font_size") == 24
                    and style_capabilities.get("original_color") == "#66CCFF"
                    and style_capabilities.get("translation_color") == "#FFCC66"
                    and overlay_capabilities.get("history_visible")
                    and overlay_capabilities.get("history") == ["第一句保留在最上方", "第二句随新内容向上滚动", "第三句仍然可以继续阅读", "第四句作为当前译文高亮"]
                    and not overlay_capabilities.get("style_visible")
                )
                if not overlay_ok:
                    startup_state["error"] = "迷你字幕窗口交互或透明背景测试失败。"
                    LOGGER.error(startup_state["error"])
                    window.destroy()
                    return
                bridge.set_overlay_locked(False)
                bridge.set_overlay_transparency(55)
                LOGGER.info("Desktop smoke test restoring main window")
                bridge.restore_main()
                time.sleep(0.2)
                LOGGER.info("Desktop smoke test destroying main window")
                window.destroy()
                LOGGER.info("Desktop smoke test destroy request completed")
            elif visual_overlay_test:
                bridge.update_overlay({
                    "original": "The first sentence moves to the top",
                    "translation": "第一句移动到最上方，直到第五句到来才消失",
                    "meta": "滚动字幕检查 1/4",
                })
                bridge.update_overlay({
                    "original": "The second sentence remains readable",
                    "translation": "第二句保留在队列中，可以继续阅读",
                    "meta": "滚动字幕检查 2/4",
                })
                bridge.update_overlay({
                    "original": "The third sentence follows naturally",
                    "translation": "第三句自然向上移动，不会突然清空",
                    "meta": "滚动字幕检查 3/4",
                })
                bridge.update_overlay({
                    "original": "The newest sentence stays highlighted at the bottom",
                    "translation": "第四句固定在最下方，并作为当前译文高亮",
                    "meta": "滚动字幕检查 4/4",
                })
                bridge.set_overlay_locked(False)
                bridge.set_overlay_transparency(100)
                bridge.show_overlay()
                threading.Timer(0.6, lambda: bridge.resize_overlay(1420, 520)).start()
                threading.Timer(30.0, bridge.restore_main).start()
            else:
                window.show()

        webview.start(
            func=prepare_window,
            gui="edgechromium",
            debug=False,
            private_mode=False,
            # Automated/visual verification uses an isolated WebView profile so
            # an interrupted test cannot lock or damage the user's real profile.
            storage_path=str(
                ROOT
                / ".models"
                / ("webview-test-profile" if smoke_test or visual_overlay_test else "webview-profile")
            ),
            icon=str(ROOT / "static" / "yisheng.ico") if (ROOT / "static" / "yisheng.ico").exists() else None,
        )
        LOGGER.info("Desktop WebView message loop stopped")
        if startup_state["error"]:
            raise RuntimeError(startup_state["error"])
        return 0
    except Exception as exc:
        LOGGER.exception("Desktop application failed")
        fatal_error = f"译声启动失败：\n{exc}\n\n详细信息已写入 logs\\desktop.log。"
    finally:
        if app_control is not None:
            app_control.stop()
        backend.stop()
    if fatal_error is not None:
        # Stop the backend before showing the blocking dialog. Otherwise a
        # timed-out cold-start worker can keep loading models behind the error.
        _show_fatal_error(fatal_error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
