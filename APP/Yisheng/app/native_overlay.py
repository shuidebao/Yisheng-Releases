from __future__ import annotations

import ctypes
import json
import logging
import math
import queue
import threading
from typing import Any, Callable

from .config import MODEL_ROOT


LOGGER = logging.getLogger("yisheng.native_overlay")
CHROMA_RGB = (1, 2, 3)
STYLE_PATH = MODEL_ROOT / "overlay-style.json"
DEFAULT_STYLE = {
    "original_size": 20,
    "translation_size": 28,
    "original_color": "#FFFFFF",
    "translation_color": "#C7FF61",
}


def _load_style() -> dict[str, Any]:
    style = dict(DEFAULT_STYLE)
    try:
        payload = json.loads(STYLE_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            style.update(payload)
    except (OSError, ValueError, TypeError):
        pass
    style["original_size"] = max(12, min(40, int(style.get("original_size", 20))))
    style["translation_size"] = max(16, min(56, int(style.get("translation_size", 28))))
    for key in ("original_color", "translation_color"):
        value = str(style.get(key) or DEFAULT_STYLE[key]).upper()
        style[key] = value if len(value) == 7 and value.startswith("#") else DEFAULT_STYLE[key]
    return style


class NativeLyricOverlay:
    """Windows-native desktop lyric overlay hosted by the pywebview UI thread."""

    MIN_WIDTH = 480
    MIN_HEIGHT = 130
    MAX_WIDTH = 1800
    MAX_HEIGHT = 700

    def __init__(
        self,
        main_bounds: tuple[int, int, int, int],
        on_restore: Callable[[], Any],
        on_lock_changed: Callable[[bool], Any],
    ) -> None:
        import clr

        clr.AddReference("System.Drawing")
        clr.AddReference("System.Windows.Forms")
        from System.Drawing import Color, ContentAlignment, Font, FontStyle, Point, Size
        from System.Windows.Forms import (
            AnchorStyles,
            AutoScaleMode,
            Button,
            DockStyle,
            FlatStyle,
            Form,
            FormBorderStyle,
            FormStartPosition,
            Label,
            MouseButtons,
            Panel,
            TrackBar,
            TickStyle,
            Timer,
        )

        self._Color = Color
        self._Font = Font
        self._FontStyle = FontStyle
        self._Point = Point
        self._Size = Size
        self._AnchorStyles = AnchorStyles
        self._MouseButtons = MouseButtons
        self._on_restore_callback = on_restore
        self._on_lock_changed = on_lock_changed
        self._main_bounds = main_bounds
        self._ui_thread: Any | None = None
        self._ui_thread_id = int(threading.get_ident())
        self._command_queue: queue.Queue[
            tuple[Callable[[], None], threading.Event, list[BaseException]]
        ] = queue.Queue()
        self._visible = False
        self._locked = False
        self._transparency = 100
        self._original = "等待原声…"
        self._translation = "开始同传后，中文翻译会显示在这里"
        self._meta = "拖动顶部移动 · 右下角调整大小"
        self._style = _load_style()
        self._original_font_size = int(self._style["original_size"])
        self._translation_font_size = int(self._style["translation_size"])
        self._original_color = self._color_from_hex(str(self._style["original_color"]))
        self._translation_color = self._color_from_hex(str(self._style["translation_color"]))
        self._closing = False

        key = Color.FromArgb(255, *CHROMA_RGB)

        self.background = Form()
        self.background.Text = "译声字幕背景"
        self.background.FormBorderStyle = getattr(FormBorderStyle, "None")
        self.background.StartPosition = FormStartPosition.Manual
        self.background.ShowInTaskbar = False
        self.background.TopMost = True
        self.background.BackColor = Color.Black
        self.background.Opacity = 0.45
        self.background.Size = Size(920, 250)

        self.form = Form()
        self.form.Text = "译声 · 桌面字幕"
        self.form.FormBorderStyle = getattr(FormBorderStyle, "None")
        self.form.StartPosition = FormStartPosition.Manual
        self.form.ShowInTaskbar = False
        self.form.TopMost = True
        self.form.AllowTransparency = True
        self.form.BackColor = key
        self.form.TransparencyKey = key
        self.form.AutoScaleMode = AutoScaleMode.Dpi
        self.form.Size = Size(920, 250)
        self.form.MinimumSize = Size(self.MIN_WIDTH, self.MIN_HEIGHT)

        self.toolbar = Panel()
        self.toolbar.Height = 50
        self.toolbar.Dock = DockStyle.Top
        self.toolbar.BackColor = Color.FromArgb(52, 55, 61)
        self.form.Controls.Add(self.toolbar)

        self.title_label = Label()
        self.title_label.Text = "译声 · 桌面字幕"
        self.title_label.ForeColor = Color.WhiteSmoke
        self.title_label.BackColor = Color.Transparent
        self.title_label.Font = Font("Microsoft YaHei UI", 9.0, FontStyle.Bold)
        self.title_label.AutoSize = True
        self.title_label.Location = Point(14, 16)
        self.toolbar.Controls.Add(self.title_label)

        self.style_button = Button()
        self.style_button.Text = "字幕样式"
        self.style_button.FlatStyle = FlatStyle.Flat
        self.style_button.BackColor = Color.FromArgb(75, 78, 85)
        self.style_button.ForeColor = Color.White
        self.style_button.Size = Size(82, 32)
        self.style_button.Location = Point(654, 9)
        self.toolbar.Controls.Add(self.style_button)

        self.transparency_label = Label()
        self.transparency_label.Text = "背景透明度"
        self.transparency_label.ForeColor = Color.Gainsboro
        self.transparency_label.AutoSize = True
        self.transparency_label.Anchor = AnchorStyles.Top | AnchorStyles.Right
        self.transparency_label.Location = Point(470, 17)
        self.toolbar.Controls.Add(self.transparency_label)

        self.transparency_slider = TrackBar()
        self.transparency_slider.Minimum = 0
        self.transparency_slider.Maximum = 100
        self.transparency_slider.Value = 100
        self.transparency_slider.TickStyle = getattr(TickStyle, "None")
        self.transparency_slider.AutoSize = False
        self.transparency_slider.Size = Size(140, 30)
        self.transparency_slider.Anchor = AnchorStyles.Top | AnchorStyles.Right
        self.transparency_slider.Location = Point(558, 10)
        self.toolbar.Controls.Add(self.transparency_slider)

        self.value_label = Label()
        self.value_label.Text = "100%"
        self.value_label.ForeColor = Color.WhiteSmoke
        self.value_label.AutoSize = True
        self.value_label.Anchor = AnchorStyles.Top | AnchorStyles.Right
        self.value_label.Location = Point(700, 17)
        self.toolbar.Controls.Add(self.value_label)

        self.lock_button = Button()
        self.lock_button.Text = "锁定窗口"
        self.lock_button.FlatStyle = FlatStyle.Flat
        self.lock_button.BackColor = Color.FromArgb(75, 78, 85)
        self.lock_button.ForeColor = Color.White
        self.lock_button.Size = Size(82, 32)
        self.lock_button.Anchor = AnchorStyles.Top | AnchorStyles.Right
        self.lock_button.Location = Point(746, 9)
        self.toolbar.Controls.Add(self.lock_button)

        self.restore_button = Button()
        self.restore_button.Text = "返回主界面"
        self.restore_button.FlatStyle = FlatStyle.Flat
        self.restore_button.BackColor = Color.FromArgb(199, 255, 97)
        self.restore_button.ForeColor = Color.FromArgb(15, 20, 10)
        self.restore_button.Size = Size(82, 32)
        self.restore_button.Anchor = AnchorStyles.Top | AnchorStyles.Right
        self.restore_button.Location = Point(832, 9)
        self.toolbar.Controls.Add(self.restore_button)

        self.unlock_button = Button()
        self.unlock_button.Text = "解除锁定"
        self.unlock_button.FlatStyle = FlatStyle.Flat
        self.unlock_button.BackColor = Color.FromArgb(199, 255, 97)
        self.unlock_button.ForeColor = Color.FromArgb(15, 20, 10)
        self.unlock_button.Size = Size(76, 30)
        self.unlock_button.Anchor = AnchorStyles.Top | AnchorStyles.Right
        self.unlock_button.Location = Point(834, 8)
        self.unlock_button.Visible = False
        self.form.Controls.Add(self.unlock_button)
        self.unlock_button.BringToFront()

        self.resize_grip = Label()
        self.resize_grip.Text = "◢"
        self.resize_grip.TextAlign = ContentAlignment.MiddleCenter
        self.resize_grip.ForeColor = Color.FromArgb(199, 255, 97)
        self.resize_grip.BackColor = Color.FromArgb(55, 58, 64)
        self.resize_grip.Size = Size(28, 28)
        self.resize_grip.Anchor = AnchorStyles.Bottom | AnchorStyles.Right
        self.resize_grip.Location = Point(892, 222)
        self.form.Controls.Add(self.resize_grip)
        self.resize_grip.BringToFront()

        self._build_style_form()

        self.form.Paint += self._paint
        self.form.Move += self._sync_background
        self.form.Resize += self._on_resize
        self.form.VisibleChanged += self._on_visible_changed
        self.form.FormClosed += self._on_closed
        self.toolbar.MouseDown += self._drag_window
        self.title_label.MouseDown += self._drag_window
        self.resize_grip.MouseDown += self._resize_window
        self.transparency_slider.ValueChanged += self._on_transparency_changed
        self.style_button.Click += lambda *_: self._show_style_form()
        self.lock_button.Click += lambda *_: self.set_locked(True)
        self.unlock_button.Click += lambda *_: self.set_locked(False)
        self.restore_button.Click += lambda *_: self._on_restore_callback()

        # Python.NET Control.Invoke can silently discard Python delegates on
        # some WebView2/WinForms combinations. A native WinForms timer drains a
        # Python queue on this form's own UI thread instead.
        self._command_timer = Timer()
        self._command_timer.Interval = 15
        self._command_timer.Tick += self._drain_commands
        self._command_timer.Start()

        self.form.CreateControl()
        self.background.CreateControl()
        self._make_background_click_through()
        self._center_on_main()
        self._layout_toolbar()

    def _invoke(self, action: Callable[[], None]) -> None:
        if self.form.IsDisposed:
            return
        if int(threading.get_ident()) == self._ui_thread_id:
            action()
            return
        completed = threading.Event()
        failures: list[BaseException] = []
        self._command_queue.put((action, completed, failures))
        if not completed.wait(timeout=10):
            raise RuntimeError("桌面字幕窗口没有响应。")
        if failures:
            raise failures[0]

    def _drain_commands(self, *_: Any) -> None:
        while True:
            try:
                action, completed, failures = self._command_queue.get_nowait()
            except queue.Empty:
                break
            try:
                action()
            except BaseException as exc:
                failures.append(exc)
                LOGGER.exception("Native desktop lyric command failed")
            finally:
                completed.set()

    def _color_from_hex(self, value: str) -> Any:
        try:
            normalized = value.strip().lstrip("#")
            if len(normalized) != 6:
                raise ValueError("invalid color")
            return self._Color.FromArgb(
                int(normalized[0:2], 16),
                int(normalized[2:4], 16),
                int(normalized[4:6], 16),
            )
        except (TypeError, ValueError):
            return self._Color.White

    @staticmethod
    def _color_hex(color: Any) -> str:
        return f"#{int(color.R):02X}{int(color.G):02X}{int(color.B):02X}"

    def _save_style(self) -> None:
        payload = {
            "original_size": self._original_font_size,
            "translation_size": self._translation_font_size,
            "original_color": self._color_hex(self._original_color),
            "translation_color": self._color_hex(self._translation_color),
        }
        try:
            STYLE_PATH.parent.mkdir(parents=True, exist_ok=True)
            STYLE_PATH.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            LOGGER.warning("Could not save desktop lyric style", exc_info=True)

    def _set_color_button(self, button: Any, color: Any) -> None:
        button.BackColor = color
        luminance = int(color.R) * 299 + int(color.G) * 587 + int(color.B) * 114
        button.ForeColor = self._Color.Black if luminance > 145000 else self._Color.White

    def _build_style_form(self) -> None:
        from System.Drawing import Color, Font, FontStyle, Point, Size
        from System.Windows.Forms import (
            Button,
            ColorDialog,
            FlatStyle,
            Form,
            FormBorderStyle,
            FormStartPosition,
            Label,
            TrackBar,
            TickStyle,
        )

        self.style_form = Form()
        self.style_form.Text = "译声 · 字幕样式"
        self.style_form.FormBorderStyle = FormBorderStyle.FixedToolWindow
        self.style_form.StartPosition = FormStartPosition.Manual
        self.style_form.ShowInTaskbar = False
        self.style_form.TopMost = True
        self.style_form.ClientSize = Size(500, 275)
        self.style_form.BackColor = Color.FromArgb(31, 34, 42)
        self.style_form.ForeColor = Color.White

        heading = Label()
        heading.Text = "分别设置原声识别字幕与中文翻译字幕"
        heading.AutoSize = True
        heading.Font = Font("Microsoft YaHei UI", 10.0, FontStyle.Bold)
        heading.Location = Point(18, 14)
        self.style_form.Controls.Add(heading)

        original_name = Label()
        original_name.Text = "原声识别"
        original_name.AutoSize = True
        original_name.Location = Point(18, 61)
        self.style_form.Controls.Add(original_name)

        self.original_size_slider = TrackBar()
        self.original_size_slider.Minimum = 12
        self.original_size_slider.Maximum = 40
        self.original_size_slider.Value = self._original_font_size
        self.original_size_slider.TickStyle = getattr(TickStyle, "None")
        self.original_size_slider.AutoSize = False
        self.original_size_slider.Size = Size(225, 30)
        self.original_size_slider.Location = Point(103, 54)
        self.style_form.Controls.Add(self.original_size_slider)

        self.original_size_value = Label()
        self.original_size_value.Text = f"{self._original_font_size}px"
        self.original_size_value.AutoSize = True
        self.original_size_value.Location = Point(334, 61)
        self.style_form.Controls.Add(self.original_size_value)

        self.original_color_button = Button()
        self.original_color_button.Text = "文字颜色"
        self.original_color_button.FlatStyle = FlatStyle.Flat
        self.original_color_button.Size = Size(96, 32)
        self.original_color_button.Location = Point(390, 50)
        self._set_color_button(self.original_color_button, self._original_color)
        self.style_form.Controls.Add(self.original_color_button)

        translation_name = Label()
        translation_name.Text = "中文翻译"
        translation_name.AutoSize = True
        translation_name.Location = Point(18, 117)
        self.style_form.Controls.Add(translation_name)

        self.translation_size_slider = TrackBar()
        self.translation_size_slider.Minimum = 16
        self.translation_size_slider.Maximum = 56
        self.translation_size_slider.Value = self._translation_font_size
        self.translation_size_slider.TickStyle = getattr(TickStyle, "None")
        self.translation_size_slider.AutoSize = False
        self.translation_size_slider.Size = Size(225, 30)
        self.translation_size_slider.Location = Point(103, 110)
        self.style_form.Controls.Add(self.translation_size_slider)

        self.translation_size_value = Label()
        self.translation_size_value.Text = f"{self._translation_font_size}px"
        self.translation_size_value.AutoSize = True
        self.translation_size_value.Location = Point(334, 117)
        self.style_form.Controls.Add(self.translation_size_value)

        self.translation_color_button = Button()
        self.translation_color_button.Text = "文字颜色"
        self.translation_color_button.FlatStyle = FlatStyle.Flat
        self.translation_color_button.Size = Size(96, 32)
        self.translation_color_button.Location = Point(390, 106)
        self._set_color_button(self.translation_color_button, self._translation_color)
        self.style_form.Controls.Add(self.translation_color_button)

        background_name = Label()
        background_name.Text = "背景透明"
        background_name.AutoSize = True
        background_name.Location = Point(18, 173)
        self.style_form.Controls.Add(background_name)

        self.style_transparency_slider = TrackBar()
        self.style_transparency_slider.Minimum = 0
        self.style_transparency_slider.Maximum = 100
        self.style_transparency_slider.Value = self._transparency
        self.style_transparency_slider.TickStyle = getattr(TickStyle, "None")
        self.style_transparency_slider.AutoSize = False
        self.style_transparency_slider.Size = Size(225, 30)
        self.style_transparency_slider.Location = Point(103, 166)
        self.style_form.Controls.Add(self.style_transparency_slider)

        self.style_transparency_value = Label()
        self.style_transparency_value.Text = f"{self._transparency}%"
        self.style_transparency_value.AutoSize = True
        self.style_transparency_value.Location = Point(334, 173)
        self.style_form.Controls.Add(self.style_transparency_value)

        reset_button = Button()
        reset_button.Text = "恢复默认"
        reset_button.FlatStyle = FlatStyle.Flat
        reset_button.BackColor = Color.FromArgb(75, 78, 85)
        reset_button.ForeColor = Color.White
        reset_button.Size = Size(96, 34)
        reset_button.Location = Point(282, 222)
        self.style_form.Controls.Add(reset_button)

        close_button = Button()
        close_button.Text = "完成"
        close_button.FlatStyle = FlatStyle.Flat
        close_button.BackColor = Color.FromArgb(199, 255, 97)
        close_button.ForeColor = Color.FromArgb(15, 20, 10)
        close_button.Size = Size(96, 34)
        close_button.Location = Point(390, 222)
        self.style_form.Controls.Add(close_button)

        self._color_dialog = ColorDialog()
        self._color_dialog.FullOpen = True
        self.original_size_slider.ValueChanged += self._on_original_size_changed
        self.translation_size_slider.ValueChanged += self._on_translation_size_changed
        self.style_transparency_slider.ValueChanged += self._on_style_transparency_changed
        self.original_color_button.Click += lambda *_: self._choose_color("original")
        self.translation_color_button.Click += lambda *_: self._choose_color("translation")
        reset_button.Click += lambda *_: self._reset_style()
        close_button.Click += lambda *_: self.style_form.Hide()
        self.style_form.FormClosing += self._on_style_form_closing

    def _show_style_form(self) -> None:
        if self._locked:
            return
        self.style_form.Left = self.form.Left + max(0, (self.form.Width - self.style_form.Width) // 2)
        self.style_form.Top = self.form.Top + 56
        self.style_form.Show()
        self.style_form.Activate()
        self.style_form.BringToFront()

    def _on_style_form_closing(self, _sender: Any, event: Any) -> None:
        if not self._closing:
            event.Cancel = True
            self.style_form.Hide()

    def _on_original_size_changed(self, *_: Any) -> None:
        self._original_font_size = int(self.original_size_slider.Value)
        self.original_size_value.Text = f"{self._original_font_size}px"
        self._save_style()
        self.form.Invalidate()

    def _on_translation_size_changed(self, *_: Any) -> None:
        self._translation_font_size = int(self.translation_size_slider.Value)
        self.translation_size_value.Text = f"{self._translation_font_size}px"
        self._save_style()
        self.form.Invalidate()

    def _on_style_transparency_changed(self, *_: Any) -> None:
        self.set_transparency(int(self.style_transparency_slider.Value))

    def _choose_color(self, target: str) -> None:
        from System.Windows.Forms import DialogResult

        current = self._original_color if target == "original" else self._translation_color
        self._color_dialog.Color = current
        if self._color_dialog.ShowDialog(self.style_form) != DialogResult.OK:
            return
        selected = self._color_dialog.Color
        if target == "original":
            self._original_color = selected
            self._set_color_button(self.original_color_button, selected)
        else:
            self._translation_color = selected
            self._set_color_button(self.translation_color_button, selected)
        self._save_style()
        self.form.Invalidate()

    def _reset_style(self) -> None:
        self._original_color = self._color_from_hex(str(DEFAULT_STYLE["original_color"]))
        self._translation_color = self._color_from_hex(str(DEFAULT_STYLE["translation_color"]))
        self.original_size_slider.Value = int(DEFAULT_STYLE["original_size"])
        self.translation_size_slider.Value = int(DEFAULT_STYLE["translation_size"])
        self._set_color_button(self.original_color_button, self._original_color)
        self._set_color_button(self.translation_color_button, self._translation_color)
        self._save_style()
        self.form.Invalidate()

    def _layout_toolbar(self) -> None:
        width = max(self.MIN_WIDTH, int(self.form.ClientSize.Width))
        right = width - 8
        self.restore_button.Location = self._Point(right - 82, 9)
        right -= 86
        self.lock_button.Location = self._Point(right - 82, 9)
        right -= 86
        self.style_button.Location = self._Point(right - 82, 9)
        right -= 90
        show_inline_transparency = width >= 720
        self.transparency_label.Visible = show_inline_transparency
        self.transparency_slider.Visible = show_inline_transparency
        self.value_label.Visible = show_inline_transparency
        if show_inline_transparency:
            self.value_label.Location = self._Point(right - 42, 17)
            right -= 46
            self.transparency_slider.Location = self._Point(right - 140, 10)
            right -= 144
            self.transparency_label.Location = self._Point(right - 82, 17)
        self.unlock_button.Location = self._Point(width - self.unlock_button.Width - 10, 8)

    @staticmethod
    def _fitted_text_size(
        text: str,
        preferred: float,
        minimum: float,
        width: float,
        height: float,
    ) -> float:
        if not text:
            return preferred
        cjk = any("\u2e80" <= char <= "\u9fff" or "\u3040" <= char <= "\u30ff" for char in text)
        width_factor = 1.0 if cjk else 0.58
        lines = text.splitlines() or [text]
        size = float(preferred)
        while size > minimum:
            per_line = max(1, int(max(1.0, width) / max(1.0, size * width_factor)))
            wrapped_lines = sum(max(1, math.ceil(len(line) / per_line)) for line in lines)
            if wrapped_lines * size * 1.35 <= max(1.0, height):
                break
            size -= 1.0
        return max(float(minimum), size)

    def _read_state(self) -> dict[str, Any]:
        handle = int(self.form.Handle.ToInt64())
        return {
            "visible": self._visible,
            "locked": self._locked,
            "transparency": self._transparency,
            "width": int(self.form.Width),
            "height": int(self.form.Height),
            "background_visible": bool(self.background.Visible),
            "toolbar_visible": bool(self.toolbar.Visible),
            "unlock_visible": bool(self.unlock_button.Visible),
            "style_visible": bool(self.style_form.Visible),
            "original_font_size": self._original_font_size,
            "translation_font_size": self._translation_font_size,
            "original_color": self._color_hex(self._original_color),
            "translation_color": self._color_hex(self._translation_color),
            "handle": handle,
            "handle_exists": bool(ctypes.windll.user32.IsWindow(handle)),
            "thread_alive": bool(self._ui_thread and self._ui_thread.IsAlive),
        }

    def _center_on_main(self) -> None:
        main_left, main_top, main_width, _main_height = self._main_bounds
        left = main_left + max(0, (main_width - self.form.Width) // 2)
        top = main_top + 70
        self.form.Location = self._Point(left, top)
        self._sync_background()

    def _make_background_click_through(self) -> None:
        handle = int(self.background.Handle.ToInt64())
        get_style = ctypes.windll.user32.GetWindowLongW
        set_style = ctypes.windll.user32.SetWindowLongW
        style = get_style(handle, -20)
        set_style(handle, -20, style | 0x20 | 0x80 | 0x08000000)

    def _sync_background(self, *_: Any) -> None:
        if self.background.IsDisposed:
            return
        self.background.Bounds = self.form.Bounds
        if self._visible and self._transparency < 100:
            self.background.Show()
            self.form.BringToFront()

    def _on_resize(self, *_: Any) -> None:
        self.resize_grip.Location = self._Point(
            self.form.ClientSize.Width - self.resize_grip.Width,
            self.form.ClientSize.Height - self.resize_grip.Height,
        )
        self._layout_toolbar()
        self._sync_background()
        self.form.Invalidate()

    def _drag_window(self, sender: Any, event: Any) -> None:
        if self._locked or event.Button != self._MouseButtons.Left:
            return
        ctypes.windll.user32.ReleaseCapture()
        ctypes.windll.user32.SendMessageW(int(self.form.Handle.ToInt64()), 0xA1, 2, 0)

    def _resize_window(self, sender: Any, event: Any) -> None:
        if self._locked or event.Button != self._MouseButtons.Left:
            return
        ctypes.windll.user32.ReleaseCapture()
        ctypes.windll.user32.SendMessageW(int(self.form.Handle.ToInt64()), 0xA1, 17, 0)

    def _on_transparency_changed(self, *_: Any) -> None:
        self.set_transparency(int(self.transparency_slider.Value))

    def _paint(self, sender: Any, event: Any) -> None:
        from System.Drawing import RectangleF, SolidBrush, StringAlignment, StringFormat
        from System.Drawing.Text import TextRenderingHint

        graphics = event.Graphics
        graphics.TextRenderingHint = TextRenderingHint.AntiAliasGridFit
        width = max(1, self.form.ClientSize.Width)
        height = max(1, self.form.ClientSize.Height)
        top = 0 if self._locked else self.toolbar.Height
        content_height = max(80, height - top)
        meta_size = max(8.0, min(11.0, content_height * 0.05))
        original_rect = RectangleF(20.0, top + content_height * 0.05, width - 40.0, content_height * 0.29)
        translation_rect = RectangleF(20.0, top + content_height * 0.32, width - 40.0, content_height * 0.48)
        meta_rect = RectangleF(20.0, top + content_height * 0.82, width - 40.0, content_height * 0.14)
        original_size = self._fitted_text_size(
            self._original,
            float(self._original_font_size),
            12.0,
            original_rect.Width,
            original_rect.Height,
        )
        translation_size = self._fitted_text_size(
            self._translation,
            float(self._translation_font_size),
            16.0,
            translation_rect.Width,
            translation_rect.Height,
        )
        alignment = StringFormat()
        alignment.Alignment = StringAlignment.Center
        alignment.LineAlignment = StringAlignment.Center
        original_luminance = int(self._original_color.R) * 299 + int(self._original_color.G) * 587 + int(self._original_color.B) * 114
        translation_luminance = int(self._translation_color.R) * 299 + int(self._translation_color.G) * 587 + int(self._translation_color.B) * 114
        original_shadow = SolidBrush(
            self._Color.FromArgb(245, 255, 255, 255)
            if original_luminance < 90000
            else self._Color.FromArgb(245, 0, 0, 0)
        )
        translation_shadow = SolidBrush(
            self._Color.FromArgb(245, 255, 255, 255)
            if translation_luminance < 90000
            else self._Color.FromArgb(245, 0, 0, 0)
        )
        meta_shadow = SolidBrush(self._Color.FromArgb(245, 0, 0, 0))
        original_brush = SolidBrush(self._original_color)
        translation_brush = SolidBrush(self._translation_color)
        muted = SolidBrush(self._Color.FromArgb(220, 220, 220))
        original_font = self._Font("Microsoft YaHei UI", original_size, self._FontStyle.Bold)
        translation_font = self._Font("Microsoft YaHei UI", translation_size, self._FontStyle.Bold)
        meta_font = self._Font("Microsoft YaHei UI", meta_size, self._FontStyle.Regular)
        try:
            for rect, text, font, brush, shadow in (
                (original_rect, self._original, original_font, original_brush, original_shadow),
                (translation_rect, self._translation, translation_font, translation_brush, translation_shadow),
            ):
                shadow_rect = RectangleF(rect.X + 2.0, rect.Y + 2.0, rect.Width, rect.Height)
                graphics.DrawString(text, font, shadow, shadow_rect, alignment)
                graphics.DrawString(text, font, brush, rect, alignment)
            graphics.DrawString(self._meta, meta_font, meta_shadow, RectangleF(meta_rect.X + 1, meta_rect.Y + 1, meta_rect.Width, meta_rect.Height), alignment)
            graphics.DrawString(self._meta, meta_font, muted, meta_rect, alignment)
        finally:
            for resource in (
                alignment,
                original_shadow,
                translation_shadow,
                meta_shadow,
                original_brush,
                translation_brush,
                muted,
                original_font,
                translation_font,
                meta_font,
            ):
                resource.Dispose()

    def _on_closed(self, *_: Any) -> None:
        LOGGER.info("Native desktop lyric form closed")
        try:
            self.background.Close()
        except Exception:
            pass
        if not self._closing:
            # Closing the mini subtitle is equivalent to "return to main".
            # Otherwise the pywebview host remains minimized and the whole app
            # appears to have vanished while its processes keep running.
            threading.Timer(0.05, self._on_restore_callback).start()

    def _on_visible_changed(self, *_: Any) -> None:
        LOGGER.info(
            "Native desktop lyric visibility changed: visible=%s handle=%s bounds=%sx%s@%s,%s",
            bool(self.form.Visible),
            int(self.form.Handle.ToInt64()),
            int(self.form.Width),
            int(self.form.Height),
            int(self.form.Left),
            int(self.form.Top),
        )

    def show(self) -> None:
        def action() -> None:
            self._visible = True
            self._sync_background()
            if self._transparency < 100:
                self.background.Show()
            self.form.Show()
            self.form.BringToFront()
            self.form.Invalidate()

        self._invoke(action)

    def hide(self) -> None:
        def action() -> None:
            self._visible = False
            self.style_form.Hide()
            self.form.Hide()
            self.background.Hide()

        self._invoke(action)

    def close(self) -> None:
        def action() -> None:
            from System.Windows.Forms import Application

            self._command_timer.Stop()
            self._closing = True
            if not self.style_form.IsDisposed:
                self.style_form.Close()
            if not self.form.IsDisposed:
                self.form.Close()
            if not self.background.IsDisposed:
                self.background.Close()
            Application.ExitThread()

        self._invoke(action)

    def update(self, original: str, translation: str, meta: str) -> None:
        def action() -> None:
            self._original = original or "等待原声…"
            self._translation = translation or "开始同传后，中文翻译会显示在这里"
            self._meta = meta or "拖动顶部移动 · 右下角调整大小"
            self.form.Invalidate()

        self._invoke(action)

    def set_transparency(self, percent: int) -> None:
        def action() -> None:
            self._transparency = max(0, min(100, int(percent)))
            if self.transparency_slider.Value != self._transparency:
                self.transparency_slider.Value = self._transparency
            self.value_label.Text = f"{self._transparency}%"
            if self.style_transparency_slider.Value != self._transparency:
                self.style_transparency_slider.Value = self._transparency
            self.style_transparency_value.Text = f"{self._transparency}%"
            if self._transparency >= 100:
                self.background.Hide()
            else:
                self.background.Opacity = max(0.05, (100 - self._transparency) / 100.0)
                if self._visible:
                    self.background.Show()
                    self.form.BringToFront()

        self._invoke(action)

    def set_locked(self, locked: bool) -> None:
        def action() -> None:
            self._locked = bool(locked)
            self.toolbar.Visible = not self._locked
            self.resize_grip.Visible = not self._locked
            self.unlock_button.Visible = self._locked
            self.transparency_slider.Enabled = not self._locked
            if self._locked:
                self.style_form.Hide()
            self._on_lock_changed(self._locked)
            self.form.Invalidate()

        self._invoke(action)

    def resize(self, width: int, height: int) -> tuple[int, int]:
        safe_width = max(self.MIN_WIDTH, min(self.MAX_WIDTH, int(width)))
        safe_height = max(self.MIN_HEIGHT, min(self.MAX_HEIGHT, int(height)))

        def action() -> None:
            if not self._locked:
                self.form.Size = self._Size(safe_width, safe_height)

        self._invoke(action)
        return safe_width, safe_height

    def show_style_settings(self) -> None:
        self._invoke(lambda: self.style_button.PerformClick())

    def set_text_style(
        self,
        original_size: int,
        translation_size: int,
        original_color: str,
        translation_color: str,
    ) -> None:
        def action() -> None:
            safe_original = max(12, min(40, int(original_size)))
            safe_translation = max(16, min(56, int(translation_size)))
            self._original_font_size = safe_original
            self._translation_font_size = safe_translation
            if self.original_size_slider.Value != safe_original:
                self.original_size_slider.Value = safe_original
            if self.translation_size_slider.Value != safe_translation:
                self.translation_size_slider.Value = safe_translation
            self._original_color = self._color_from_hex(original_color)
            self._translation_color = self._color_from_hex(translation_color)
            self._set_color_button(self.original_color_button, self._original_color)
            self._set_color_button(self.translation_color_button, self._translation_color)
            self._save_style()
            self.form.Invalidate()

        self._invoke(action)

    def debug_state(self) -> dict[str, Any]:
        if self.form.IsDisposed:
            return {"visible": False, "disposed": True}
        states: list[dict[str, Any]] = []
        self._invoke(lambda: states.append(self._read_state()))
        return states[0] if states else {"visible": False, "error": "state_unavailable"}


def create_native_overlay(
    main_window: Any,
    on_restore: Callable[[], Any],
    on_lock_changed: Callable[[bool], Any],
) -> NativeLyricOverlay:
    from System import Action
    from System.Threading import ApartmentState, Thread, ThreadStart
    from System.Windows.Forms import Application
    from webview.platforms.winforms import BrowserView

    main_form = BrowserView.instances.get(main_window.uid)
    if main_form is None:
        raise RuntimeError("Windows 主窗口尚未创建。")

    main_bounds: list[tuple[int, int, int, int]] = []

    def read_main_bounds() -> None:
        main_bounds.append((
            int(main_form.Left),
            int(main_form.Top),
            int(main_form.Width),
            int(main_form.Height),
        ))

    if main_form.InvokeRequired:
        main_form.Invoke(Action(read_main_bounds))
    else:
        read_main_bounds()
    if not main_bounds:
        raise RuntimeError("无法读取主窗口位置。")

    created: list[NativeLyricOverlay] = []
    failures: list[BaseException] = []
    ready = threading.Event()

    def run_overlay_loop() -> None:
        try:
            overlay = NativeLyricOverlay(main_bounds[0], on_restore, on_lock_changed)
            created.append(overlay)
            ready.set()
            LOGGER.info("Native desktop lyric message loop started")
            Application.Run()
            LOGGER.info("Native desktop lyric message loop stopped")
        except BaseException as exc:
            failures.append(exc)
            ready.set()
            LOGGER.exception("Native desktop lyric UI thread failed")

    ui_thread = Thread(ThreadStart(run_overlay_loop))
    ui_thread.Name = "YishengNativeLyricOverlay"
    ui_thread.IsBackground = True
    ui_thread.SetApartmentState(ApartmentState.STA)
    ui_thread.Start()
    if not ready.wait(timeout=10):
        raise RuntimeError("桌面歌词窗口线程启动超时。")
    if failures:
        raise RuntimeError(str(failures[0]))
    if not created:
        raise RuntimeError("无法创建桌面歌词窗口。")
    created[0]._ui_thread = ui_thread
    return created[0]
