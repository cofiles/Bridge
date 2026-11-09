import os
import subprocess
import sys
from pathlib import Path

import webview

from controller import Bridge


class DesktopBridge(Bridge):
    def paste(self):
        if sys.platform == "darwin":
            command = ["/usr/bin/pbpaste"]
        else:
            command = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                       "[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); Get-Clipboard -Raw"]
        try:
            result = subprocess.run(command, capture_output=True, timeout=5, check=True,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            text = result.stdout.decode("utf-8").strip()
        except (OSError, UnicodeError, subprocess.SubprocessError):
            return {"error": "Не удалось прочитать буфер обмена."}
        return {"text": text} if text else {"error": "В буфере нет текста."}


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    settings = (Path.home() / "Library/Application Support" if sys.platform == "darwin"
                else Path(os.environ["LOCALAPPDATA"])) / "Bridge"
    api = DesktopBridge(settings)
    window = webview.create_window("Bridge", html=(root / "assets/bridge.html").read_text(encoding="utf-8"),
                                   js_api=api, width=474, height=628, min_size=(360, 500),
                                   background_color="#f7f8f3")
    window.events.closing += api._close_window
    webview.start()
