import json
import os
import socket
import subprocess
import time
import tempfile
import http.client
from pathlib import Path
from controller import Bridge
from connection import Connection
from bridge import configuration, stop, validate_config
import bridge
from lifecycle import Attempt

api = None
service = None

class Tunnel(Connection):
    def __init__(self, outbound, attempt=None):
        attempt = attempt or Attempt()
        attempt.progress("creating_tunnel")
        self.helper = None
        with socket.socket() as listener:
            listener.bind(("127.0.0.1",0))
            self.port = listener.getsockname()[1]
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.metrics_port = sock.getsockname()[1]
        config = configuration(outbound, port=self.port, metrics_port=self.metrics_port)
        config["inbounds"][0]["tag"] = "test"
        config["inbounds"] += [{"tag": "bridge", "protocol": "tun", "settings": {"name": "bridge0", "mtu": 1500}}]
        validate_config(config,attempt,binary=str(service.getApplicationInfo().nativeLibraryDir)+"/libxray.so")
        attempt.progress("creating_tunnel")
        self.device = service.openTunnel()
        if self.device is None:
            raise ValueError("Android не создал VPN-интерфейс.")
        fd = self.device.getFd()
        self.errors = tempfile.TemporaryFile()
        try:
            self.core = subprocess.Popen(
                [str(service.getApplicationInfo().nativeLibraryDir) + "/libxray.so", "run", "-config", "stdin:"],
                stdin=subprocess.PIPE, stdout=self.errors, stderr=self.errors,
                pass_fds=(fd,), env={**os.environ, "XRAY_TUN_FD": str(fd)})
            with self.core.stdin as output:
                output.write(json.dumps(config).encode())
            self.started = time.monotonic()
            attempt.progress("starting_core")
            for _ in range(60):
                attempt.check()
                if self.core.poll() is not None:
                    self.errors.seek(0)
                    diagnostic = self.errors.read(65536).decode("utf-8", errors="replace")
                    reason = "VPN_CORE_EXIT"
                    for pattern, code in (("interface information", "VPN_INTERFACE_PERMISSION"),
                                          ("bad file descriptor", "VPN_TUN_FD"),
                                          ("permission denied", "VPN_PERMISSION"),
                                          ("address already in use", "VPN_PORT_BUSY"),
                                          ("unknown config id", "VPN_TUN_UNSUPPORTED")):
                        if pattern in diagnostic.lower():
                            reason = code
                            break
                    raise ValueError(f"Не удалось запустить ядро VPN. [{reason}; exit={self.core.returncode}]")
                # Readiness is independent of whether the TUN has emitted traffic counters.
                probe = http.client.HTTPConnection("127.0.0.1", self.metrics_port, timeout=.2)
                try:
                    probe.request("GET", "/debug/vars")
                    if probe.getresponse().status == 200:
                        attempt.core_ready = True
                        return
                except (OSError, http.client.HTTPException):
                    pass
                finally:
                    probe.close()
                time.sleep(.1)
            raise ValueError("Ядро VPN не отвечает.")
        except BaseException:
            if hasattr(self, "core"):
                stop(self.core)
            self.device.close()
            self.errors.close()
            raise

    def close(self):
        try:
            stop(self.core)
        finally:
            self.device.close()
            self.errors.close()

def init(directory, native_directory=None):
    global api
    if native_directory:
        bridge.BINARY = Path(str(native_directory)) / "libxray.so"
    if api is None:
        api = Bridge(directory, connect=Tunnel)

def connect(vpn, name, candidates="null"):
    global service
    service = vpn
    api._notify = lambda message: service.alert(message)
    return json.dumps(api.connect(name,candidates=json.loads(candidates)))

def call(method, args):
    if method not in ("load", "palette", "snapshot", "disconnect", "servers", "language", "preferences", "favorite", "undo", "report", "reset", "cancel", "speed_test", "environment"):
        return json.dumps({"error":"Недоступное действие."})
    return json.dumps(getattr(api, method)(*json.loads(args)))
