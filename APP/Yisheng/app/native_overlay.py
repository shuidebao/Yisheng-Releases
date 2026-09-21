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
    "original_color": "#CBD5E1",
    "translation_color": "#F5F8FF",
}
DEFAULT_TRANSPARENCY = 28


def subtitle_layout(width: int, height: int, locked: bool) -> dict[str, tuple[float, float, float, float]]:
    """Logical client rectangles shared by painting and layout regression tests."""
    padding = 28.0 if width >= 640 else 22.0
    top = 54.0 if locked else 88.0
    available = max(150.0, height - top - 28.0)
    original_height = max(40.0, available * 0.25)
    translation_top = top + 22.0 + original_height + 26.0
    text_width = max(1.0, width - padding * 2)
    return {
        "original_label": (padding, top, text_width, 18.0),
        "original": (padding, top + 22.0, text_width, original_height),
        "translation_label": (padding, translation_top, text_width, 18.0),
        "translation": (padding, translation_top + 22.0, text_width,
                        max(40.0, height - translation_top - 68.0)),
        "meta": (padding, height - 36.0, text_width - 24.0, 20.0),
    }

OVERLAY_TEXT = {
    "zh": {
        "waiting": "等待原声…", "translation_waiting": "开始同传后，翻译会显示在这里",
        "drag_help": "拖动顶部移动 · 右下角调整大小", "background_title": "译声字幕背景",
        "window_title": "译声 · 桌面字幕", "style": "字幕样式", "transparency": "背景透明度",
        "lock": "锁定窗口", "restore": "返回主界面", "unlock": "解除锁定",
        "style_title": "译声 · 字幕样式", "style_heading": "分别设置原声识别字幕与翻译字幕",
        "original": "原声识别", "translation": "翻译字幕", "text_color": "文字颜色",
        "background": "背景透明", "reset": "恢复默认", "done": "完成",
        "mini_title": "译声", "mini_detail": "迷你字幕", "short_lock": "锁定",
        "short_restore": "主界面", "style_note": "清晰阅读，轻盈呈现。改动会即时生效。",
    },
    "en": {
        "waiting": "Waiting for speech…", "translation_waiting": "The translation will appear here",
        "drag_help": "Drag the top bar to move · Resize from the bottom-right",
        "background_title": "YiSheng subtitle background", "window_title": "YiSheng · Desktop subtitles",
        "style": "Text style", "transparency": "Background", "lock": "Lock window",
        "restore": "Main window", "unlock": "Unlock", "style_title": "YiSheng · Subtitle style",
        "style_heading": "Customize recognized and translated subtitles", "original": "Recognized",
        "translation": "Translation", "text_color": "Text color", "background": "Transparency",
        "reset": "Reset", "done": "Done",
        "mini_title": "YiSheng", "mini_detail": "MINI", "short_lock": "Lock",
        "short_restore": "Main", "style_note": "Make it yours. Changes appear instantly.",
    },
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
    MIN_HEIGHT = 300
    MAX_WIDTH = 1800
    MAX_HEIGHT = 700

    def _text(self, key: str) -> str:
        return OVERLAY_TEXT[self._ui_language][key]

    def __init__(
        self,
        main_bounds: tuple[int, int, int, int],
        on_restore: Callable[[], Any],
        on_lock_changed: Callable[[bool], Any],
        language: str = "zh",
    ) -> None:
        import clr

        clr.AddReference("System.Drawing")
        clr.AddReference("System.Windows.Forms")
        from System.Drawing import Color, ContentAlignment, Font, FontStyle, Point, Size
        from System.Windows.Forms import (
            AnchorStyles,
            AutoScaleMode,
            Button,
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
        self._application_context: Any | None = None
        self._ui_thread_id = int(threading.get_ident())
        self._command_queue: queue.Queue[
            tuple[Callable[[], None], threading.Event, list[BaseException]]
        ] = queue.Queue()
        self._visible = False
        self._locked = False
        self._transparency = DEFAULT_TRANSPARENCY
        self._ui_language = "en" if language == "en" else "zh"
        self._has_content = False
        self._original = self._text("waiting")
        self._translation = self._text("translation_waiting")
        self._meta = self._text("drag_help")
        self._style = _load_style()
        self._original_font_size = int(self._style["original_size"])
        self._translation_font_size = int(self._style["translation_size"])
        self._original_color = self._color_from_hex(str(self._style["original_color"]))
        self._translation_color = self._color_from_hex(str(self._style["translation_color"]))
        self._closing = False

        key = Color.FromArgb(255, *CHROMA_RGB)

        self.background = Form()
        self.background.Text = self._text("background_title")
        self.background.FormBorderStyle = getattr(FormBorderStyle, "None")
        self.background.StartPosition = FormStartPosition.Manual
        self.background.ShowInTaskbar = False
        self.background.TopMost = True
        self.background.BackColor = Color.FromArgb(17, 23, 34)
        self.background.Opacity = (100 - self._transparency) / 100.0
        self.background.Size = Size(920, 360)

        self.form = Form()
        self.form.Text = self._text("window_title")
        self.form.FormBorderStyle = getattr(FormBorderStyle, "None")
        self.form.StartPosition = FormStartPosition.Manual
        self.form.ShowInTaskbar = False
        self.form.TopMost = True
        self.form.AllowTransparency = True
        self.form.BackColor = key
        self.form.TransparencyKey = key
        self.form.AutoScaleMode = AutoScaleMode.Dpi
        self.form.Size = Size(920, 360)
        self.form.MinimumSize = Size(self.MIN_WIDTH, self.MIN_HEIGHT)

        self.toolbar = Panel()
        self.toolbar.Size = Size(892, 60)
        self.toolbar.Location = Point(14, 12)
        self.toolbar.BackColor = Color.FromArgb(30, 39, 54)
        self.form.Controls.Add(self.toolbar)

        self.title_label = Label()
        self.title_label.Text = self._text("mini_title")
        self.title_label.ForeColor = Color.WhiteSmoke
        self.title_label.BackColor = Color.Transparent
        self.title_label.Font = Font("Microsoft YaHei UI", 11.5, FontStyle.Bold)
        self.title_label.AutoSize = True
        self.title_label.Location = Point(20, 10)
        self.toolbar.Controls.Add(self.title_label)

        self.detail_label = Label()
        self.detail_label.Text = self._text("mini_detail")
        self.detail_label.ForeColor = Color.FromArgb(157, 177, 199)
        self.detail_label.BackColor = Color.Transparent
        self.detail_label.Font = Font("Microsoft YaHei UI", 8.5)
        self.detail_label.AutoSize = True
        self.detail_label.Location = Point(21, 34)
        self.toolbar.Controls.Add(self.detail_label)

        self.style_button = Button()
        self.style_button.Text = self._text("style")
        self.style_button.FlatStyle = FlatStyle.Flat
        self.style_button.BackColor = Color.FromArgb(75, 78, 85)
        self.style_button.ForeColor = Color.White
        self.style_button.Size = Size(82, 32)
        self.style_button.Location = Point(654, 9)
        self.toolbar.Controls.Add(self.style_button)

        self.transparency_label = Label()
        self.transparency_label.Text = self._text("transparency")
        self.transparency_label.ForeColor = Color.Gainsboro
        self.transparency_label.AutoSize = True
        self.transparency_label.Anchor = AnchorStyles.Top | AnchorStyles.Right
        self.transparency_label.Location = Point(470, 17)
        self.toolbar.Controls.Add(self.transparency_label)

        self.transparency_slider = TrackBar()
        self.transparency_slider.Minimum = 0
        self.transparency_slider.Maximum = 100
        self.transparency_slider.Value = self._transparency
        self.transparency_slider.TickStyle = getattr(TickStyle, "None")
        self.transparency_slider.AutoSize = False
        self.transparency_slider.Size = Size(140, 30)
        self.transparency_slider.Anchor = AnchorStyles.Top | AnchorStyles.Right
        self.transparency_slider.Location = Point(558, 10)
        self.toolbar.Controls.Add(self.transparency_slider)

        self.value_label = Label()
        self.value_label.Text = f"{self._transparency}%"
        self.value_label.ForeColor = Color.WhiteSmoke
        self.value_label.AutoSize = True
        self.value_label.Anchor = AnchorStyles.Top | AnchorStyles.Right
        self.value_label.Location = Point(700, 17)
        self.toolbar.Controls.Add(self.value_label)

        self.lock_button = Button()
        self.lock_button.Text = self._text("lock")
        self.lock_button.FlatStyle = FlatStyle.Flat
        self.lock_button.BackColor = Color.FromArgb(75, 78, 85)
        self.lock_button.ForeColor = Color.White
        self.lock_button.Size = Size(82, 32)
        self.lock_button.Anchor = AnchorStyles.Top | AnchorStyles.Right
        self.lock_button.Location = Point(746, 9)
        self.toolbar.Controls.Add(self.lock_button)

        self.restore_button = Button()
        self.restore_button.Text = self._text("restore")
        self.restore_button.FlatStyle = FlatStyle.Flat
        self.restore_button.BackColor = Color.FromArgb(199, 255, 97)
        self.restore_button.ForeColor = Color.FromArgb(15, 20, 10)
        self.restore_button.Size = Size(82, 32)
        self.restore_button.Anchor = AnchorStyles.Top | AnchorStyles.Right
        self.restore_button.Location = Point(832, 9)
        self.toolbar.Controls.Add(self.restore_button)

        self.unlock_button = Button()
        self.unlock_button.Text = self._text("unlock")
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
        self.resize_grip.Text = "⋰"
        self.resize_grip.TextAlign = ContentAlignment.MiddleCenter
        self.resize_grip.ForeColor = Color.FromArgb(168, 190, 216)
        self.resize_grip.BackColor = Color.FromArgb(30, 39, 54)
        self.resize_grip.Size = Size(28, 28)
        self.resize_grip.Anchor = AnchorStyles.Bottom | AnchorStyles.Right
        self.resize_grip.Location = Point(892, 332)
        self.form.Controls.Add(self.resize_grip)
        self.resize_grip.BringToFront()

        from System.Windows.Forms import Cursors, ToolTip
        self._tooltips = ToolTip()
        for button in (self.style_button, self.lock_button, self.restore_button, self.unlock_button):
            self._theme_button(button, prominent=button in (self.restore_button, self.unlock_button))
        for label in (self.transparency_label, self.value_label):
            label.Font = Font("Microsoft YaHei UI", 9.0)
            label.BackColor = Color.Transparent
        self.transparency_slider.BackColor = self.toolbar.BackColor
        self.resize_grip.Cursor = Cursors.SizeNWSE
        self.resize_grip.Font = Font("Segoe UI", 15.0)
        self.unlock_button.Size = Size(108, 36)
        self.toolbar.Cursor = Cursors.SizeAll
        self.title_label.Cursor = Cursors.SizeAll
        self.detail_label.Cursor = Cursors.SizeAll
        self.toolbar.Paint += self._paint_toolbar
        self.background.Paint += self._paint_background

        self._build_style_form()

        self.form.Paint += self._paint
        self.form.Move += self._sync_background
        self.form.Resize += self._on_resize
        self.form.VisibleChanged += self._on_visible_changed
        self.form.FormClosed += self._on_closed
        self.toolbar.MouseDown += self._drag_window
        self.title_label.MouseDown += self._drag_window
        self.detail_label.MouseDown += self._drag_window
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
        self._on_resize()

    @staticmethod
    def _rounded_path(width: float, height: float, radius: float, inset: float = 0.0) -> Any:
        from System.Drawing import RectangleF
        from System.Drawing.Drawing2D import GraphicsPath
        path = GraphicsPath()
        diameter = min(radius * 2, width - inset * 2, height - inset * 2)
        for x, y, angle in ((inset, inset, 180), (width - diameter - inset, inset, 270),
                            (width - diameter - inset, height - diameter - inset, 0),
                            (inset, height - diameter - inset, 90)):
            path.AddArc(RectangleF(float(x), float(y), float(diameter), float(diameter)), float(angle), 90.0)
        path.CloseFigure()
        return path

    def _round_control(self, control: Any, radius: float) -> None:
        from System.Drawing import Region
        path = self._rounded_path(float(control.Width), float(control.Height), radius)
        try:
            old_region = control.Region
            control.Region = Region(path)
            if old_region is not None:
                old_region.Dispose()
        finally:
            path.Dispose()

    def _round_windows(self) -> None:
        self._round_control(self.form, 28.0)
        self._round_control(self.background, 28.0)
        self._round_control(self.toolbar, 21.0)
        self._round_control(self.resize_grip, 12.0)

    def _theme_button(self, button: Any, prominent: bool = False) -> None:
        from System.Windows.Forms import Cursors
        button.UseVisualStyleBackColor = False
        button.FlatAppearance.BorderSize = 0
        button.BackColor = self._Color.FromArgb(214, 233, 255) if prominent else self._Color.FromArgb(53, 66, 84)
        button.ForeColor = self._Color.FromArgb(27, 45, 67) if prominent else self._Color.FromArgb(240, 245, 252)
        button.FlatAppearance.MouseOverBackColor = self._Color.FromArgb(235, 245, 255) if prominent else self._Color.FromArgb(70, 87, 110)
        button.FlatAppearance.MouseDownBackColor = self._Color.FromArgb(170, 207, 244) if prominent else self._Color.FromArgb(40, 51, 70)
        button.Font = self._Font("Microsoft YaHei UI", 10.0, self._FontStyle.Regular)
        button.Cursor = Cursors.Hand
        self._round_control(button, 18.0)

    def _paint_glass(self, control: Any, event: Any, radius: float, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> None:
        from System.Drawing import Rectangle, Pen
        from System.Drawing.Drawing2D import LinearGradientBrush, LinearGradientMode, SmoothingMode
        graphics = event.Graphics
        graphics.SmoothingMode = SmoothingMode.AntiAlias
        bounds = Rectangle(0, 0, max(1, control.Width), max(1, control.Height))
        fill = LinearGradientBrush(bounds, self._Color.FromArgb(*top), self._Color.FromArgb(*bottom), LinearGradientMode.Vertical)
        rim = Pen(self._Color.FromArgb(68, 196, 219, 248), 1.0)
        path = self._rounded_path(float(control.Width), float(control.Height), radius, 0.75)
        try:
            graphics.FillPath(fill, path)
            graphics.DrawPath(rim, path)
        finally:
            fill.Dispose()
            rim.Dispose()
            path.Dispose()

    def _paint_toolbar(self, sender: Any, event: Any) -> None:
        self._paint_glass(sender, event, 21.0, (44, 57, 77), (27, 35, 49))

    def _paint_background(self, sender: Any, event: Any) -> None:
        self._paint_glass(sender, event, 28.0, (37, 49, 67), (13, 19, 29))

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
        self.style_form.Text = self._text("style_title")
        self.style_form.FormBorderStyle = getattr(FormBorderStyle, "None")
        self.style_form.StartPosition = FormStartPosition.Manual
        self.style_form.ShowInTaskbar = False
        self.style_form.TopMost = True
        self.style_form.ClientSize = Size(560, 374)
        self.style_form.BackColor = Color.FromArgb(24, 32, 45)
        self.style_form.ForeColor = Color.White
        self.style_form.Font = Font("Microsoft YaHei UI", 10.0)

        self.style_heading = Label()
        self.style_heading.Text = self._text("style")
        self.style_heading.AutoSize = True
        self.style_heading.Font = Font("Microsoft YaHei UI", 15.0, FontStyle.Bold)
        self.style_heading.Location = Point(24, 22)
        self.style_heading.BackColor = Color.Transparent
        self.style_form.Controls.Add(self.style_heading)

        self.style_note = Label()
        self.style_note.Text = self._text("style_note")
        self.style_note.AutoSize = True
        self.style_note.Font = Font("Microsoft YaHei UI", 9.5)
        self.style_note.ForeColor = Color.FromArgb(165, 184, 208)
        self.style_note.Location = Point(26, 60)
        self.style_note.BackColor = Color.Transparent
        self.style_form.Controls.Add(self.style_note)

        self.original_name = Label()
        self.original_name.Text = self._text("original")
        self.original_name.AutoSize = True
        self.original_name.Location = Point(18, 61)
        self.style_form.Controls.Add(self.original_name)

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
        self.original_size_value.Text = f"{self._original_font_size} pt"
        self.original_size_value.AutoSize = True
        self.original_size_value.Location = Point(334, 61)
        self.style_form.Controls.Add(self.original_size_value)

        self.original_color_button = Button()
        self.original_color_button.Text = self._text("text_color")
        self.original_color_button.FlatStyle = FlatStyle.Flat
        self.original_color_button.Size = Size(96, 32)
        self.original_color_button.Location = Point(390, 50)
        self._set_color_button(self.original_color_button, self._original_color)
        self.style_form.Controls.Add(self.original_color_button)

        self.translation_name = Label()
        self.translation_name.Text = self._text("translation")
        self.translation_name.AutoSize = True
        self.translation_name.Location = Point(18, 117)
        self.style_form.Controls.Add(self.translation_name)

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
        self.translation_size_value.Text = f"{self._translation_font_size} pt"
        self.translation_size_value.AutoSize = True
        self.translation_size_value.Location = Point(334, 117)
        self.style_form.Controls.Add(self.translation_size_value)

        self.translation_color_button = Button()
        self.translation_color_button.Text = self._text("text_color")
        self.translation_color_button.FlatStyle = FlatStyle.Flat
        self.translation_color_button.Size = Size(96, 32)
        self.translation_color_button.Location = Point(390, 106)
        self._set_color_button(self.translation_color_button, self._translation_color)
        self.style_form.Controls.Add(self.translation_color_button)

        self.background_name = Label()
        self.background_name.Text = self._text("background")
        self.background_name.AutoSize = True
        self.background_name.Location = Point(18, 173)
        self.style_form.Controls.Add(self.background_name)

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

        self.reset_button = Button()
        self.reset_button.Text = self._text("reset")
        self.reset_button.FlatStyle = FlatStyle.Flat
        self.reset_button.BackColor = Color.FromArgb(75, 78, 85)
        self.reset_button.ForeColor = Color.White
        self.reset_button.Size = Size(96, 34)
        self.reset_button.Location = Point(282, 222)
        self.style_form.Controls.Add(self.reset_button)

        self.close_style_button = Button()
        self.close_style_button.Text = self._text("done")
        self.close_style_button.FlatStyle = FlatStyle.Flat
        self.close_style_button.BackColor = Color.FromArgb(199, 255, 97)
        self.close_style_button.ForeColor = Color.FromArgb(15, 20, 10)
        self.close_style_button.Size = Size(96, 34)
        self.close_style_button.Location = Point(390, 222)
        self.style_form.Controls.Add(self.close_style_button)

        # Spacious, aligned native controls: keyboard and color dialogs remain
        # standard WinForms behavior, without introducing another WebView.
        for label, slider, value, button, y in (
            (self.original_name, self.original_size_slider, self.original_size_value, self.original_color_button, 110),
            (self.translation_name, self.translation_size_slider, self.translation_size_value, self.translation_color_button, 182),
            (self.background_name, self.style_transparency_slider, self.style_transparency_value, None, 254),
        ):
            label.Location = Point(26, y)
            value.Location = Point(367, y)
            value.ForeColor = Color.FromArgb(173, 201, 232)
            slider.Location = Point(140, y - 7)
            slider.Size = Size(220, 34)
            slider.BackColor = self.style_form.BackColor
            if button is not None:
                button.Location = Point(430, y - 10)
                button.Size = Size(104, 40)
                self._theme_button(button)
                self._set_color_button(button, self._original_color if button == self.original_color_button else self._translation_color)
            for control in (label, value):
                control.BackColor = Color.Transparent
        self.original_size_value.Text = f"{self._original_font_size} pt"
        self.translation_size_value.Text = f"{self._translation_font_size} pt"
        self.reset_button.Location = Point(290, 313)
        self.reset_button.Size = Size(120, 42)
        self.close_style_button.Location = Point(422, 313)
        self.close_style_button.Size = Size(112, 42)
        self._theme_button(self.reset_button)
        self._theme_button(self.close_style_button, prominent=True)
        self._round_control(self.style_form, 24.0)
        self.style_form.KeyPreview = True
        self.style_form.KeyDown += self._on_style_key
        self.style_form.Paint += self._paint_style_form
        self.style_heading.MouseDown += self._drag_style_window
        self.style_note.MouseDown += self._drag_style_window
        self.style_form.MouseDown += self._drag_style_window
        self.style_form.AcceptButton = self.close_style_button
        self.style_form.CancelButton = self.close_style_button

        self._color_dialog = ColorDialog()
        self._color_dialog.FullOpen = True
        self.original_size_slider.ValueChanged += self._on_original_size_changed
        self.translation_size_slider.ValueChanged += self._on_translation_size_changed
        self.style_transparency_slider.ValueChanged += self._on_style_transparency_changed
        self.original_color_button.Click += lambda *_: self._choose_color("original")
        self.translation_color_button.Click += lambda *_: self._choose_color("translation")
        self.reset_button.Click += lambda *_: self._reset_style()
        self.close_style_button.Click += lambda *_: self.style_form.Hide()
        self.style_form.FormClosing += self._on_style_form_closing

    def _show_style_form(self) -> None:
        if self._locked:
            return
        from System.Windows.Forms import Screen
        area = Screen.FromControl(self.form).WorkingArea
        left = self.form.Left + max(0, (self.form.Width - self.style_form.Width) // 2)
        top = self.form.Top + 56
        self.style_form.Left = max(area.Left, min(left, area.Right - self.style_form.Width))
        self.style_form.Top = max(area.Top, min(top, area.Bottom - self.style_form.Height))
        self.style_form.Show()
        self.style_form.Activate()
        self.style_form.BringToFront()

    def _on_style_key(self, _sender: Any, event: Any) -> None:
        from System.Windows.Forms import Keys
        if event.KeyCode == Keys.Escape:
            self.style_form.Hide()
            event.Handled = True

    def _drag_style_window(self, _sender: Any, event: Any) -> None:
        if event.Button == self._MouseButtons.Left:
            ctypes.windll.user32.ReleaseCapture()
            ctypes.windll.user32.SendMessageW(int(self.style_form.Handle.ToInt64()), 0xA1, 2, 0)

    def _paint_style_form(self, sender: Any, event: Any) -> None:
        from System.Drawing import Pen
        self._paint_glass(sender, event, 24.0, (32, 43, 59), (19, 27, 39))
        pen = Pen(self._Color.FromArgb(34, 173, 196, 224), 1.0)
        try:
            for y in (94, 164, 236, 300):
                event.Graphics.DrawLine(pen, 26, y, 534, y)
        finally:
            pen.Dispose()

    def _on_style_form_closing(self, _sender: Any, event: Any) -> None:
        if not self._closing:
            event.Cancel = True
            self.style_form.Hide()

    def _on_original_size_changed(self, *_: Any) -> None:
        self._original_font_size = int(self.original_size_slider.Value)
        self.original_size_value.Text = f"{self._original_font_size} pt"
        self._save_style()
        self.form.Invalidate()

    def _on_translation_size_changed(self, *_: Any) -> None:
        self._translation_font_size = int(self.translation_size_slider.Value)
        self.translation_size_value.Text = f"{self._translation_font_size} pt"
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
        self.toolbar.Size = self._Size(width - 28, 60)
        right = self.toolbar.Width - 10
        for button, button_width in ((self.restore_button, 104), (self.lock_button, 88), (self.style_button, 104)):
            button.Size = self._Size(button_width, 44)
            button.Location = self._Point(right - button_width, 8)
            self._round_control(button, 18.0)
            right -= button_width + 8
        self.title_label.AutoSize = False
        self.title_label.Size = self._Size(max(70, min(160, right - 30)), 26)
        self.lock_button.Text = self._text("short_lock")
        self.restore_button.Text = self._text("short_restore")
        show_inline_transparency = width >= 880
        self.transparency_label.Visible = show_inline_transparency
        self.transparency_slider.Visible = show_inline_transparency
        self.value_label.Visible = show_inline_transparency
        if show_inline_transparency:
            self.value_label.Location = self._Point(right - 42, 21)
            right -= 46
            self.transparency_slider.Size = self._Size(120, 30)
            self.transparency_slider.Location = self._Point(right - 120, 17)
            right -= 128
            self.transparency_label.Location = self._Point(right - 88, 21)
        self.unlock_button.Location = self._Point(width - self.unlock_button.Width - 16, 12)
        self._round_control(self.unlock_button, 18.0)
        self._round_control(self.toolbar, 21.0)
        for button, key in ((self.style_button, "style"), (self.lock_button, "lock"),
                            (self.restore_button, "restore"), (self.unlock_button, "unlock")):
            button.AccessibleName = self._text(key)
            self._tooltips.SetToolTip(button, self._text(key))

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
        # Hangul syllables and Jamo need the same conservative full-width
        # estimate as Han/Kana, otherwise long Korean subtitles get clipped.
        # Compatibility Jamo (3130-318F) is covered by the existing CJK range.
        cjk = any(
            "\u2e80" <= char <= "\u9fff"
            or "\u3040" <= char <= "\u30ff"
            or "\u1100" <= char <= "\u11ff"  # Hangul Jamo
            or "\ua960" <= char <= "\ua97f"  # Jamo Extended-A
            or "\uac00" <= char <= "\ud7ff"  # Syllables and Jamo Extended-B
            for char in text
        )
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
            "ui_language": self._ui_language,
            "window_title": str(self.form.Text),
            "style_button": str(self.style_button.Text),
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
            "original": self._original,
            "translation": self._translation,
            "has_content": self._has_content,
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
            self.form.ClientSize.Width - self.resize_grip.Width - 10,
            self.form.ClientSize.Height - self.resize_grip.Height - 10,
        )
        self._layout_toolbar()
        self._sync_background()
        self._round_windows()
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

    def _reading_font(self, graphics: Any, text: str, preferred: float, minimum: float, rect: Any, bold: bool) -> Any:
        from System.Drawing import SizeF
        # The existing saved font sizes are points, not pixels. Measure actual
        # glyph wrapping (including Korean and English words) in client pixels.
        size = float(preferred)
        style = self._FontStyle.Bold if bold else self._FontStyle.Regular
        while True:
            font = self._Font("Microsoft YaHei UI", size, style)
            try:
                measured = graphics.MeasureString(text, font, SizeF(float(rect.Width), 100000.0))
            except Exception:
                font.Dispose()
                raise
            if measured.Height <= rect.Height or size <= minimum:
                return font
            font.Dispose()
            size = max(minimum, size - 1.0)

    def _paint(self, sender: Any, event: Any) -> None:
        from System.Drawing import RectangleF, SolidBrush, StringAlignment, StringFormat
        from System.Drawing.Text import TextRenderingHint

        graphics = event.Graphics
        graphics.TextRenderingHint = TextRenderingHint.AntiAliasGridFit
        width = max(1, self.form.ClientSize.Width)
        height = max(1, self.form.ClientSize.Height)
        layout = subtitle_layout(width, height, self._locked)
        original_rect = RectangleF(*layout["original"])
        translation_rect = RectangleF(*layout["translation"])
        meta_rect = RectangleF(*layout["meta"])
        alignment = StringFormat()
        alignment.Alignment = StringAlignment.Near
        alignment.LineAlignment = StringAlignment.Center
        original_luminance = (
            int(self._original_color.R) * 299
            + int(self._original_color.G) * 587
            + int(self._original_color.B) * 114
        )
        translation_luminance = (
            int(self._translation_color.R) * 299
            + int(self._translation_color.G) * 587
            + int(self._translation_color.B) * 114
        )
        shadow_alpha = 245 if self._transparency >= 75 else 85
        original_shadow = SolidBrush(
            self._Color.FromArgb(shadow_alpha, 255, 255, 255)
            if original_luminance < 90000
            else self._Color.FromArgb(shadow_alpha, 0, 0, 0)
        )
        translation_shadow = SolidBrush(
            self._Color.FromArgb(shadow_alpha, 255, 255, 255)
            if translation_luminance < 90000
            else self._Color.FromArgb(shadow_alpha, 0, 0, 0)
        )
        meta_shadow = SolidBrush(self._Color.FromArgb(shadow_alpha, 0, 0, 0))
        original_brush = SolidBrush(self._original_color)
        translation_brush = SolidBrush(self._translation_color)
        muted = SolidBrush(self._Color.FromArgb(176, 195, 217))
        original_font = self._reading_font(graphics, self._original, float(self._original_font_size), 12.0, original_rect, False)
        meta_font = self._Font(
            "Microsoft YaHei UI",
            10.0,
            self._FontStyle.Regular,
        )
        label_font = self._Font("Microsoft YaHei UI", 9.0, self._FontStyle.Regular)

        def draw_text(rect: Any, text: str, font: Any, brush: Any, shadow: Any) -> None:
            shadow_rect = RectangleF(
                rect.X + 1.0,
                rect.Y + 1.0,
                rect.Width,
                rect.Height,
            )
            graphics.DrawString(text, font, shadow, shadow_rect, alignment)
            graphics.DrawString(text, font, brush, rect, alignment)

        try:
            for key, label in (("original_label", "original"), ("translation_label", "translation")):
                draw_text(RectangleF(*layout[key]), self._text(label), label_font, muted, meta_shadow)
            draw_text(
                original_rect,
                self._original,
                original_font,
                original_brush,
                original_shadow,
            )
            translation_font = self._reading_font(graphics, self._translation, float(self._translation_font_size), 16.0, translation_rect, True)
            try:
                draw_text(
                    translation_rect,
                    self._translation,
                    translation_font,
                    translation_brush,
                    translation_shadow,
                )
            finally:
                translation_font.Dispose()
            graphics.DrawString(
                self._meta,
                meta_font,
                meta_shadow,
                RectangleF(
                    meta_rect.X + 1,
                    meta_rect.Y + 1,
                    meta_rect.Width,
                    meta_rect.Height,
                ),
                alignment,
            )
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
                meta_font,
                label_font,
            ):
                resource.Dispose()

    def _on_closed(self, *_: Any) -> None:
        LOGGER.info("Native desktop lyric form closed")
        try:
            self.background.Close()
        except Exception:
            pass
        if self._closing:
            # FormClosed runs on the overlay's own WinForms thread. Ending the
            # thread here is reliable even when the main WebView is closing at
            # the same time and avoids leaving a background process behind.
            if self._application_context is not None:
                self._application_context.ExitThread()
            return
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
            self._command_timer.Stop()
            self._closing = True
            if not self.style_form.IsDisposed:
                self.style_form.Close()
            if not self.form.IsDisposed:
                self.form.Close()
            if not self.background.IsDisposed:
                self.background.Close()
            if self._application_context is not None:
                self._application_context.ExitThread()

        self._invoke(action)

    def update(
        self,
        original: str,
        translation: str,
        meta: str,
    ) -> None:
        def action() -> None:
            self._has_content = bool(original or translation)
            self._original = original or self._text("waiting")
            self._translation = translation or self._text("translation_waiting")
            self._meta = meta or self._text("drag_help")
            self.form.Invalidate()

        self._invoke(action)

    def set_ui_language(self, language: str) -> None:
        locale = "en" if language == "en" else "zh"

        def action() -> None:
            self._ui_language = locale
            self.background.Text = self._text("background_title")
            self.form.Text = self._text("window_title")
            self.title_label.Text = self._text("mini_title")
            self.detail_label.Text = self._text("mini_detail")
            self.style_button.Text = self._text("style")
            self.transparency_label.Text = self._text("transparency")
            self.lock_button.Text = self._text("lock")
            self.restore_button.Text = self._text("restore")
            self.unlock_button.Text = self._text("unlock")
            self.style_form.Text = self._text("style_title")
            self.style_heading.Text = self._text("style")
            self.style_note.Text = self._text("style_note")
            self.original_name.Text = self._text("original")
            self.translation_name.Text = self._text("translation")
            self.original_color_button.Text = self._text("text_color")
            self.translation_color_button.Text = self._text("text_color")
            self.background_name.Text = self._text("background")
            self.reset_button.Text = self._text("reset")
            self.close_style_button.Text = self._text("done")
            self._layout_toolbar()
            if not self._has_content:
                self._original = self._text("waiting")
                self._translation = self._text("translation_waiting")
                self._meta = self._text("drag_help")
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
            self.form.Invalidate()

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
    language: str = "zh",
) -> NativeLyricOverlay:
    from System import Action
    from System.Threading import ApartmentState, Thread, ThreadStart
    from System.Windows.Forms import Application, ApplicationContext
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
            overlay = NativeLyricOverlay(main_bounds[0], on_restore, on_lock_changed, language)
            overlay._application_context = ApplicationContext()
            created.append(overlay)
            ready.set()
            LOGGER.info("Native desktop lyric message loop started")
            Application.Run(overlay._application_context)
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
