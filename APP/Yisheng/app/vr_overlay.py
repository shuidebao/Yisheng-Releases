"""Opt-in SteamVR subtitles. Only the child process imports OpenVR/.NET."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time


DEFAULTS = {"size": 1.0, "distance": 1.5, "vertical": -0.35,
            "opacity": 0.8, "original": True}
EMPTY = {"original": "", "translation": "", "meta": ""}
START_TIMEOUT_SECONDS = 12
RESPONSE_TIMEOUT_SECONDS = 5


def settings(payload):
    if not isinstance(payload, dict):
        raise ValueError("invalid_settings")
    result = dict(DEFAULTS)
    for key, low, high in (("size", 0.6, 1.6), ("distance", 0.8, 3.0),
                           ("vertical", -0.8, 0.3), ("opacity", 0.25, 1.0)):
        value = payload.get(key, result[key])
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise ValueError("invalid_settings")
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError("invalid_settings")
        result[key] = float(value)
    result["original"] = payload.get("original", True)
    if not isinstance(result["original"], bool):
        raise ValueError("invalid_settings")
    return result


def subtitle(payload):
    return {key: str(payload.get(key) or "")[:limit]
            for key, limit in (("original", 4000), ("translation", 4000), ("meta", 300))}


class VROverlay:
    """One owned child, one in-flight request, latest subtitle wins."""

    def __init__(self, command=None):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._process = None
        self._helpers = ()
        # The packaged desktop uses pythonw/YishengBackend.exe. Use console
        # Python with CREATE_NO_WINDOW so the child still has working pipes.
        console_python = Path(sys.executable).with_name("python.exe")
        executable = str(console_python) if console_python.is_file() else sys.executable
        self._command = command or [executable, "-u", "-m", "app.vr_overlay", "--worker"]
        self._settings = dict(DEFAULTS)
        self._subtitle = dict(EMPTY)
        self._state = "off"
        self._error = ""
        self._display = "empty"
        self._preview_until = 0.0
        self._preview = dict(EMPTY)

    def snapshot(self):
        with self._lock:
            return {"ok": not bool(self._error), "state": self._state,
                    "error": self._error, "settings": dict(self._settings),
                    "display": self._display}

    def configure(self, payload):
        value = settings(payload)
        with self._lock:
            self._settings = value
        return self.snapshot()

    def update(self, payload):
        with self._lock:
            self._subtitle = subtitle(payload)
            self._preview_until = 0.0

    def preview(self, language="zh"):
        with self._lock:
            ready = self._state == "ready" and not self._stop.is_set()
            if ready:
                self._preview = {"original": "SteamVR subtitle display test",
                                 "translation": "Private subtitle display test" if language == "en" else "译声 VR 字幕显示测试",
                                 "meta": ""}
                self._preview_until = time.monotonic() + 5.0
        result = self.snapshot()
        if not ready:
            result.update(ok=False, error="not_ready")
        return result

    def start(self, payload):
        value = settings(payload)
        with self._lock:
            if (self._thread is None or not self._thread.is_alive()) and self._process is None:
                self._settings = value
                self._stop.clear()
                self._state, self._error = "starting", ""
                self._display, self._preview_until = "empty", 0.0
                self._thread = threading.Thread(target=self._run, name="YishengVR", daemon=True)
                self._thread.start()
        return self.snapshot()

    def stop(self):
        with self._lock:
            self._stop.set()
            self._preview_until = 0.0
            thread = self._thread
            if thread and thread.is_alive():
                self._state = "stopping"
            elif self._process is not None:
                self._state = "stopping"
                thread = self._thread = threading.Thread(
                    target=self._retry_cleanup, name="YishengVRCleanup", daemon=True)
                thread.start()
            else:
                self._state, self._error = "off", ""
        if thread and thread is not threading.current_thread():
            thread.join(timeout=4)
        return self.snapshot()

    @staticmethod
    def _finish_process(process, helpers):
        """Return true only after the owned child has definitely exited."""
        try:
            if process.poll() is None:
                try:
                    process.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1.5)
        except (OSError, subprocess.TimeoutExpired):
            return False
        finally:
            for helper in helpers:
                if helper is not None and helper.ident is not None:
                    helper.join(timeout=0.5)
        return process.poll() is not None

    def _publish_exit(self, process, helpers, failure):
        try:
            finished = process is None or self._finish_process(process, helpers)
        except Exception:
            # Do not discard an owned process when OS cleanup unexpectedly fails.
            finished = False
        with self._lock:
            self._process = None if finished else process
            self._helpers = () if finished else helpers
            self._error = ("" if self._stop.is_set() else failure) if finished else "cleanup_failed"
            self._state = "error" if self._error else "off"
            self._display = "empty"

    def _retry_cleanup(self):
        with self._lock:
            process, helpers = self._process, self._helpers
        self._publish_exit(process, helpers, "")

    def _run(self):
        process = None
        failure = ""
        io_finished = threading.Event()
        writer_failed = threading.Event()
        reader = writer = None
        try:
            process = subprocess.Popen(
                self._command, cwd=str(Path(__file__).resolve().parent.parent),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8", bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            with self._lock:
                self._process = process
            replies = queue.Queue(maxsize=2)
            outgoing = queue.Queue(maxsize=1)

            def read_replies():
                try:
                    while True:
                        line = process.stdout.readline(4096)
                        replies.put(line, timeout=1)
                        if not line:
                            break
                except (ValueError, OSError, queue.Full):
                    pass
                finally:
                    process.stdout.close()

            def write_requests():
                # A stopped native process may no longer read its pipe. Keep
                # blocking writes off the supervisor so its deadline/stop still
                # works. This thread alone owns stdin, including flush/close.
                try:
                    while not io_finished.is_set():
                        try:
                            message = outgoing.get(timeout=0.1)
                        except queue.Empty:
                            continue
                        if io_finished.is_set():
                            break
                        process.stdin.write(message)
                        process.stdin.flush()
                except (OSError, ValueError):
                    writer_failed.set()
                finally:
                    try:
                        process.stdin.close()
                    except (OSError, ValueError):
                        pass

            reader = threading.Thread(target=read_replies, name="YishengVRResponse", daemon=True)
            writer = threading.Thread(target=write_requests, name="YishengVRRequest", daemon=True)
            reader.start()
            writer.start()
            with self._lock:
                self._helpers = (writer, reader)
            first = True
            previous_request = None
            while not self._stop.is_set():
                with self._lock:
                    preview = time.monotonic() < self._preview_until
                    request = {"settings": dict(self._settings),
                               "subtitle": dict(self._preview if preview else self._subtitle)}
                # Initial request contains no subtitle while native imports load.
                if first:
                    request["subtitle"] = dict(EMPTY)
                    preview = False
                message = {"tick": True} if request == previous_request else request
                # The deadline includes pipe writes as well as native work.
                deadline = time.monotonic() + (START_TIMEOUT_SECONDS if first else RESPONSE_TIMEOUT_SECONDS)
                outgoing.put_nowait(json.dumps(message, ensure_ascii=True) + "\n")
                previous_request = request
                reply = None
                while not self._stop.is_set():
                    if writer_failed.is_set():
                        raise RuntimeError("worker_exit")
                    try:
                        reply = replies.get(timeout=0.1)
                        break
                    except queue.Empty:
                        if time.monotonic() >= deadline:
                            raise RuntimeError("timeout")
                if self._stop.is_set():
                    break
                if not reply:
                    raise RuntimeError("worker_exit")
                result = json.loads(reply)
                if not isinstance(result, dict):
                    raise RuntimeError("runtime_error")
                if result.get("error"):
                    raise RuntimeError(result["error"])
                if result.get("ok") is not True:
                    raise RuntimeError("runtime_error")
                with self._lock:
                    if not self._stop.is_set():
                        self._state = "ready"
                        visible = bool(request["subtitle"]["translation"] or
                                       (request["settings"]["original"] and request["subtitle"]["original"]))
                        self._display = ("preview" if preview else "subtitle") if visible else "empty"
                first = False
                self._stop.wait(0.1)
        except Exception as exc:
            # Never log subtitle text or expose arbitrary native exception data.
            code = str(exc)
            failure = code if code in ERROR_CODES else "runtime_error"
        finally:
            io_finished.set()
            # Writer-owned EOF requests orderly teardown; the supervisor can
            # still kill only its own child if either the pipe or native code hangs.
            self._publish_exit(process, (writer, reader), failure)


ERROR_CODES = {"missing_dependency", "windows_only", "no_runtime", "no_headset",
               "runtime_quit", "runtime_error", "timeout", "worker_exit", "cleanup_failed"}


class SteamVRDisplay:
    def __init__(self):
        self.vr = self.system = self.overlay = self.handle = None
        self._initialized = False
        self._last = None
        self._pixels = None

    def open(self):
        if os.name != "nt":
            raise RuntimeError("windows_only")
        try:
            import openvr
        except ImportError:
            raise RuntimeError("missing_dependency") from None
        self.vr = openvr
        if not openvr.isRuntimeInstalled():
            raise RuntimeError("no_runtime")
        if not openvr.isHmdPresent():
            raise RuntimeError("no_headset")
        # InitInternal permits cleanup even if obtaining IVRSystem subsequently fails.
        openvr.initInternal2(openvr.VRApplication_Overlay, None)
        self._initialized = True
        self.system = openvr.VRSystem()
        self.overlay = openvr.VROverlay()
        self.handle = self.overlay.createOverlay(f"yisheng.subtitles.{os.getpid()}", "YiSheng Subtitles")
        self.overlay.setOverlayInputMethod(self.handle, openvr.VROverlayInputMethod_None)

    def tick(self, text, options):
        import ctypes

        vr = self.vr
        event = vr.VREvent_t()
        for _ in range(64):
            if not self.system.pollNextEvent(event):
                break
            if event.eventType == vr.VREvent_Quit:
                self.system.acknowledgeQuit_Exiting()
                raise RuntimeError("runtime_quit")
        # Bound event draining so rendering and shutdown cannot be starved.
        for _ in range(64):
            available, event = self.overlay.pollNextOverlayEvent(self.handle, event)
            if not available:
                break
            if event.eventType == vr.VREvent_ImageFailed:
                # Raw image upload can fail asynchronously after setOverlayRaw
                # returned. Do not keep claiming the cached sentence is visible.
                raise RuntimeError("runtime_error")
            if event.eventType == vr.VREvent_Quit:
                self.system.acknowledgeQuit_Exiting()
                raise RuntimeError("runtime_quit")
        if not self.system.isTrackedDeviceConnected(vr.k_unTrackedDeviceIndex_Hmd):
            raise RuntimeError("no_headset")
        current = (text, options)
        if current == self._last:
            return
        if not text["translation"] and not (options["original"] and text["original"]):
            self.overlay.hideOverlay(self.handle)
            self._last = current
            return
        pixels, width, height = render_text(text, options)
        self._pixels = ctypes.create_string_buffer(pixels)
        self.overlay.setOverlayRaw(self.handle, self._pixels, width, height, 4)
        transform = vr.HmdMatrix34_t()
        for i in range(3):
            transform.m[i][i] = 1
        # Keep angular size/vertical position stable as virtual distance changes.
        transform.m[1][3] = options["vertical"] * options["distance"]
        transform.m[2][3] = -options["distance"]
        self.overlay.setOverlayTransformTrackedDeviceRelative(
            self.handle, vr.k_unTrackedDeviceIndex_Hmd, transform)
        self.overlay.setOverlayWidthInMeters(self.handle, options["size"] * options["distance"] * 0.7)
        self.overlay.setOverlayAlpha(self.handle, options["opacity"])
        self.overlay.showOverlay(self.handle)
        self._last = current

    def close(self):
        try:
            if self.overlay is not None and self.handle is not None:
                self.overlay.destroyOverlay(self.handle)
        finally:
            if self._initialized:
                self.vr.shutdown()
                self._initialized = False


def render_text(text, options):
    """Rasterize in memory with Windows font fallback; no screenshots/files/audio."""
    import ctypes
    import clr
    clr.AddReference("System.Drawing")
    from System.Drawing import (Bitmap, Color, Font, FontStyle, Graphics, GraphicsUnit,
                                Rectangle, RectangleF, SolidBrush, StringFormat,
                                StringAlignment, StringTrimming, StringFormatFlags)
    from System.Drawing.Imaging import PixelFormat, ImageLockMode
    from System.Drawing.Text import TextRenderingHint

    width, height = 1024, 320
    bitmap = Bitmap(width, height, PixelFormat.Format32bppArgb)
    resources = [bitmap]
    try:
        graphics = Graphics.FromImage(bitmap)
        resources.append(graphics)
        graphics.Clear(Color.FromArgb(210, 12, 17, 26))
        graphics.TextRenderingHint = TextRenderingHint.AntiAliasGridFit
        fmt = StringFormat()
        resources.append(fmt)
        fmt.Alignment = StringAlignment.Center
        fmt.LineAlignment = StringAlignment.Center
        fmt.Trimming = StringTrimming.EllipsisCharacter
        fmt.FormatFlags = StringFormatFlags.LineLimit
        show_original = options["original"] and bool(text["original"])
        regions = [(text["translation"], RectangleF(24, 90 if show_original else 16, 976,
                    214 if show_original else 288), 40, True, Color.White)]
        if show_original:
            regions.append((text["original"], RectangleF(24, 12, 976, 72), 26, False,
                            Color.FromArgb(196, 210, 226)))
        for content, rect, size, bold, color in regions:
            # Maintain a readable floor; visibly ellipsize unusually long text.
            while True:
                font = Font("Microsoft YaHei UI", float(size),
                            FontStyle.Bold if bold else FontStyle.Regular, GraphicsUnit.Pixel)
                measured = graphics.MeasureString(content, font, int(rect.Width), fmt)
                if measured.Height <= rect.Height or size <= 22:
                    break
                font.Dispose()
                size -= 2
            resources.append(font)
            brush = SolidBrush(color)
            resources.append(brush)
            fmt.LineAlignment = StringAlignment.Center if measured.Height <= rect.Height else StringAlignment.Near
            graphics.SetClip(rect)
            try:
                graphics.DrawString(content, font, brush, rect, fmt)
            finally:
                graphics.ResetClip()
        graphics.Flush()
        locked = bitmap.LockBits(Rectangle(0, 0, width, height), ImageLockMode.ReadOnly,
                                 PixelFormat.Format32bppArgb)
        try:
            # GDI+ stores BGRA; OpenVR raw image input expects RGBA.
            rows = [ctypes.string_at(locked.Scan0.ToInt64() + row * locked.Stride, width * 4)
                    for row in range(height)]
            pixels = bytearray(b"".join(rows))
            pixels[0::4], pixels[2::4] = pixels[2::4], pixels[0::4]
            return bytes(pixels), width, height
        finally:
            bitmap.UnlockBits(locked)
    finally:
        for resource in reversed(resources):
            resource.Dispose()


def worker():
    display = SteamVRDisplay()
    try:
        opened = False
        options, text = dict(DEFAULTS), dict(EMPTY)
        for line in sys.stdin:
            request = json.loads(line)
            if not request.get("tick"):
                options = settings(request["settings"])
                text = subtitle(request["subtitle"])
            if not opened:
                display.open()
                opened = True
            display.tick(text, options)
            print(json.dumps({"ok": True}), flush=True)
    except Exception as exc:
        code = str(exc)
        print(json.dumps({"error": code if code in ERROR_CODES else "runtime_error"}), flush=True)
    finally:
        display.close()


if __name__ == "__main__" and "--worker" in sys.argv:
    worker()
