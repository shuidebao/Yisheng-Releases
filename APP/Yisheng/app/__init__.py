"""译声 - 本地同声传译应用元数据。"""

from pathlib import Path


_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"
__version__ = _VERSION_FILE.read_text(encoding="utf-8").strip()
if not __version__:
    raise RuntimeError("VERSION 文件不能为空。")

APP_NAME = "译声 YiSheng"
DEVELOPER = "Huyuanhao"
COPYRIGHT = "Copyright © 2026 Huyuanhao"
OFFICIAL_REPOSITORY = "https://github.com/shuidebao/Yisheng-Releases"
