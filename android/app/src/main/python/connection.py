import http.client
import json
import socket
import time
import subprocess
import sys
import threading
from lifecycle import Attempt

from bridge import BINARY, PORT, start, stop


class ProxyError(Exception):
    pass


class Connection:
    def __init__(self, outbound, attempt=None):
        attempt = attempt or Attempt()
        attempt.progress("starting_core")
        self.port = PORT
        with socket.socket() as metrics:
            metrics.bind(("127.0.0.1", 0))
            self.metrics_port = metrics.getsockname()[1]
            if sys.platform == "darwin":
                with socket.socket() as probe:
                    probe.bind(("127.0.0.1", 0))
                    self.port = probe.getsockname()[1]
        self.core = start(outbound, self.port, self.metrics_port, attempt)
        self.helper = None
        if sys.platform == "darwin":
            try:
                self.helper = subprocess.Popen(
                    [str(BINARY.with_name("bridge-proxy")), str(self.port)],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                )
                attempt.progress("configuring_system")
                ready = threading.Event()
                response = []
                def read_ready():
                    response.append(self.helper.stdout.readline().strip())
                    ready.set()
                threading.Thread(target=read_ready, daemon=True).start()
                while not ready.wait(.1):
                    if attempt.event.is_set():
                        self.helper.stdin.close()
                    attempt.check()
                attempt.check()
                if response[0] != b"READY":
                    self.close()
                    raise ProxyError("macOS не включила системный прокси. Проверьте активное подключение и разрешите изменение настроек сети.")
            except BaseException:
                if self.helper and not self.helper.stdin.closed:
                    self.helper.stdin.close()
                stop(self.core)
                raise

        self.started = time.monotonic()

    def counters(self):
        client = http.client.HTTPConnection("127.0.0.1", self.metrics_port, timeout=0.5)
        try:
            client.request("GET", "/debug/vars")
            response = client.getresponse()
            if response.status != 200:
                return None
            inbounds = json.load(response)["stats"]["inbound"]
            selected = [inbounds[tag] for tag in ("bridge","test") if tag in inbounds]
            return {"upload": sum(int(v["uplink"]) for v in selected),
                    "download": sum(int(v["downlink"]) for v in selected)}
        except (OSError, http.client.HTTPException, ValueError, TypeError, KeyError):
            return None
        finally:
            client.close()

    def traffic(self):
        values = self.counters()
        return sum(values.values()) if values is not None else None

    def running(self):
        return self.core.poll() is None and (self.helper is None or self.helper.poll() is None)

    def close(self):
        try:
            if self.helper:
                self.helper.stdin.close()
                code = self.helper.wait()
                self.helper.stdout.close()
                if code == 4 or code < 0:
                    raise ProxyError("Проверьте настройки прокси активной сети в macOS: восстановление прервалось.")
        finally:
            stop(self.core)
