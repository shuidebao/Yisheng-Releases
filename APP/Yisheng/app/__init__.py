"""译声 - 本地同声传译应用元数据。"""

from pathlib import Path

from .inference_runtime import configure_inference_runtime


# Initialize the process-local wait policy before any desktop/backend imports
# can initialize the bundled OpenMP runtime. No model is loaded here.
configure_inference_runtime()


_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"
__version__ = _VERSION_FILE.read_text(encoding="utf-8").strip()
if not __version__:
    raise RuntimeError("VERSION 文件不能为空。")

APP_NAME = "译声 YiSheng"
DEVELOPER = "Huyuanhao"
COPYRIGHT = "Copyright © 2026 Huyuanhao"
OFFICIAL_REPOSITORY = "https://github.com/shuidebao/Yisheng-Releases"
