from __future__ import annotations

import threading
import time
import webbrowser

import uvicorn


HOST = "127.0.0.1"
PORT = 8765


def _open_browser() -> None:
    time.sleep(1.1)
    webbrowser.open(f"http://{HOST}:{PORT}")


def main() -> None:
    threading.Thread(target=_open_browser, daemon=True).start()
    print("\n译声已启动：http://127.0.0.1:8765")
    print("关闭此窗口或按 Ctrl+C 即可停止。\n")
    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()

