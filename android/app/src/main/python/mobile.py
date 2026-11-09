import json
import os
import socket
import subprocess
import time
from pathlib import Path
from controller import Bridge
from connection import Connection
from bridge import configuration, stop

api = None
service = None

class Tunnel(Connection):
    def __init__(self, outbound):
        self.helper = None
        self.port = 0
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.metrics_port = sock.getsockname()[1]
        config = configuration(outbound, metrics_port=self.metrics_port)
        config["inbounds"] = [{"tag": "bridge", "protocol": "tun", "settings": {"mtu": 1500}}]
        self.device = service.openTunnel()
        if self.device is None:
            raise ValueError("Android не создал VPN-интерфейс.")
        fd = self.device.getFd()
        try:
            self.core = subprocess.Popen(
                [str(service.getApplicationInfo().nativeLibraryDir) + "/libxray.so", "run", "-config", "stdin:"],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                pass_fds=(fd,), env={**os.environ, "XRAY_TUN_FD": str(fd)})
            with self.core.stdin as output:
                output.write(json.dumps(config).encode())
            self.started = time.monotonic()
            for _ in range(60):
                if self.core.poll() is not None:
                    raise ValueError("Не удалось запустить ядро VPN.")
                if self.traffic() is not None:
                    return
                time.sleep(.1)
            raise ValueError("Ядро VPN не отвечает.")
        except BaseException:
            if hasattr(self, "core"):
                stop(self.core)
            self.device.close()
            raise

    def close(self):
        try:
            stop(self.core)
        finally:
            self.device.close()

def init(directory):
    global api
    if api is None:
        api = Bridge(directory, connect=Tunnel)

def connect(vpn, name):
    global service
    service = vpn
    return json.dumps(api.connect(name))

def call(method, args):
    if method not in ("load", "palette", "snapshot", "disconnect", "servers"):
        return json.dumps({"error":"Недоступное действие."})
    return json.dumps(getattr(api, method)(*json.loads(args)))
