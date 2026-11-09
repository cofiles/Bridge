import os
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and len(sys.argv) == 4 and sys.argv[1] == "--proxy-watch":
    from windows_proxy import watch
    watch(int(sys.argv[2]), sys.argv[3])
    raise SystemExit(0)

import webview
import threading
import time
import json
import psutil

from controller import Bridge


class DesktopBridge(Bridge):
    def _platform_monitor(self):
        while not self._closed:
            addresses = psutil.net_if_addrs()
            network = sorted((name, address.address) for name, values in addresses.items()
                             if not name.lower().startswith(("lo","utun","tun","bridge"))
                             for address in values if address.family.name in ("AF_INET","AF_INET6"))
            battery = psutil.sensors_battery()
            low = battery is not None and not battery.power_plugged and battery.percent <= 20
            self.environment(str(network), low)
            time.sleep(3)

    def _system_notice(self, message):
        if sys.platform == "darwin":
            script = "display notification " + json.dumps(message) + ' with title "Bridge"'
            command = ["/usr/bin/osascript","-e",script]
        else:
            # The notification body is serialized as data, never interpolated as PowerShell code.
            import base64
            encoded = base64.b64encode(message.encode("utf-8")).decode("ascii")
            script = ("Add-Type -AssemblyName System.Windows.Forms; "
                      "$n=New-Object System.Windows.Forms.NotifyIcon; "
                      "$n.Icon=[System.Drawing.SystemIcons]::Information; $n.Visible=$true; "
                      "$m=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + encoded + "')); "
                      "$n.ShowBalloonTip(10000,'Bridge',$m,0); Start-Sleep 11; $n.Dispose()")
            command = ["powershell.exe","-NoProfile","-NonInteractive","-Command",script]
        subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))

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
    if sys.platform == "win32":
        from windows_proxy import WindowsProxy
        try:
            recovery = WindowsProxy()
            recovery.close()
        except OSError:
            pass  # Active instance or recovery failure; connect reports the error.
    api = DesktopBridge(settings)
    window = webview.create_window("Bridge", html=(root / "assets/bridge.html").read_text(encoding="utf-8"),
                                   js_api=api, width=474, height=628, min_size=(360, 500),
                                   background_color="#f7f8f3")
    api._notify = api._system_notice
    threading.Thread(target=api._platform_monitor,daemon=True).start()
    def close_window():
        if api.preferences().get("close_behavior") == "background":
            window.minimize()
            return False
        api._close_window()
    window.events.closing += close_window
    webview.start()
