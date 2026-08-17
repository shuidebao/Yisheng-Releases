from __future__ import annotations

import argparse
import sys

from .translation import OfflineTranslator
from .whisper_models import ensure_whisper_model


def main() -> int:
    parser = argparse.ArgumentParser(description="下载译声所需的免费离线模型")
    parser.add_argument("--whisper", default="base", choices=["tiny", "base", "small", "medium"])
    parser.add_argument("--source", default="en", help="要安装的翻译源语言代码，例如 en / ja / ko")
    parser.add_argument("--translation-only", action="store_true")
    args = parser.parse_args()

    try:
        if not args.translation_only:
            print(f"[1/2] 下载 Faster-Whisper {args.whisper} 模型…")
            ensure_whisper_model(args.whisper)
            print("      语音模型准备完成。")

        print(f"[2/2] 安装 {args.source} → zh 离线翻译模型…")
        installed = OfflineTranslator().install_pair(args.source, "zh")
        print("      翻译模型准备完成：" + (", ".join(installed) or "已存在"))
        return 0
    except Exception as exc:
        print(f"模型安装失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
