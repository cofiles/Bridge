import sys
import threading
import time
from pathlib import Path
import os
import tempfile
import hashlib
from activity_store import ActivityStore
from urllib.error import HTTPError
from lifecycle import Attempt, Cancelled
import socket
import ssl
import http.client
import certifi


from bridge import PORT, load_subscription
from connection import Connection, ProxyError


class Bridge:
    def __init__(self, settings_dir, connect=Connection):
        self._settings = Path(settings_dir) / "palette"
        self._connect = connect
        self._lock = threading.Lock()
        self._connection = None
        self._nodes = {}
        self._seconds = 0
        self._bytes = 0
        self._closed = False
        self._store = ActivityStore(settings_dir)
        self._metadata = {}
        self._session = None
        self._previous_sample = None
        self._fresh = True
        self._rates = {"upload": 0, "download": 0}
        self._undo = None
        self._attempt = None
        self._wanted = None
        self._error = None
        self._retry_at = 0
        self._network = None
        self._low_battery = False
        self._wake = threading.Event()
        self._notified = set()
        self._notify = lambda message: None
        self._monitor = threading.Thread(target=self._monitor_usage, daemon=True)
        self._monitor.start()

    def environment(self, network, low_battery=False):
        with self._lock:
            changed = self._network is not None and network != self._network
            self._network = network
            self._low_battery = bool(low_battery)
            if changed and self._wanted and not self._attempt:
                self._stop()
                self._retry_at = time.monotonic()+2
        self._wake.set()
        return {"ok":True}

    def _monitor_usage(self):
        previous = time.time()
        while not self._closed:
            retry = None
            notifications = []
            with self._lock:
                now = time.monotonic()
                if self._connection:
                    if not self._connection.running() or time.time()-previous > 20:
                        self._stop()
                        self._retry_at = now+2
                    else:
                        self._fresh = self._sample()
                if self._wanted and not self._connection and not self._attempt and now >= self._retry_at:
                    retry = self._wanted
                    self._retry_at = now+15
                for message in self._warnings():
                    if message not in self._notified:
                        self._notified.add(message)
                        notifications.append(message)
                settings = self._store.get("settings", {})
                interval = 5 if settings.get("power_saving") or (settings.get("auto_power",True) and self._low_battery) else 1
                previous = time.time()
            for message in notifications:
                try:
                    self._notify(message)
                except Exception:
                    pass
            if retry:
                self.connect(retry)
            self._wake.wait(interval)
            self._wake.clear()

    def palette(self, name=None):
        choices = ("sage", "ocean", "lilac", "clay", "rose", "sand")
        with self._lock:
            if name is None:
                try:
                    saved = self._settings.read_text(encoding="ascii")
                except (OSError, UnicodeError):
                    saved = ""
                return {"name": saved if saved in choices else choices[0]}
            if name not in choices:
                return {"error": "Неизвестная палитра."}
            try:
                self._settings.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=self._settings.parent, delete=False) as output:
                    output.write(name.encode("ascii"))
                os.replace(output.name, self._settings)
            except OSError:
                return {"error": "Не удалось сохранить палитру."}
            return {"name": name}

    def language(self, name=None):
        path = self._settings.with_name("language")
        with self._lock:
            if name is None:
                try:
                    name = path.read_text(encoding="ascii")
                except (OSError, UnicodeError):
                    name = "ru"
                return {"name": name if name in ("ru", "en") else "ru"}
            if name not in ("ru", "en"):
                return {"error": "Unknown language."}
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
                    output.write(name.encode("ascii"))
                os.replace(output.name, path)
            except OSError:
                return {"error": "Could not save language."}
            return {"name": name}

    def servers(self):
        with self._lock:
            return {"names": list(self._nodes)}

    def load(self, url):
        try:
            nodes, skipped, metadata = load_subscription(url.strip(), with_metadata=True)
        except HTTPError as error:
            return {"error": f"Сервис подписки вернул ошибку HTTP {error.code}."}
        except ValueError as error:
            return {"error": str(error) if str(error).startswith(("Введите", "Ожидается", "В подписке", "Подписка ")) else "Проверьте формат подписки."}
        except OSError:
            return {"error": "Не удалось загрузить подписку. Проверьте адрес и сеть."}
        with self._lock:
            if self._closed or self._connection or self._attempt:
                return {"error": "Отключите мост перед сменой подписки."}
            self._nodes = nodes
            self._metadata = metadata
        return {"names": list(nodes), "skipped": skipped}

    def connect(self, name):
        with self._lock:
            if self._closed or self._connection or self._attempt or name not in self._nodes:
                return {"error":"Select a server or wait for cleanup."}
            attempt = Attempt()
            self._attempt = attempt
            self._wanted = name
            self._error = None
            outbound = self._nodes[name]
        def work():
            connection = None
            try:
                connection = self._connect(outbound, attempt)
                attempt.progress("checking_access")
                self._check_access(connection.port, attempt)
                with self._lock:
                    attempt.check()
                    self._connection = connection
                    connection = None
                    self._seconds = self._bytes = 0
                    self._previous_sample = None
                    self._rates = {"upload":0,"download":0}
                    self._session = self._store.begin(name,time.time())
            except Cancelled:
                pass
            except Exception as error:
                with self._lock:
                    self._error = str(error) if isinstance(error,(ProxyError,ValueError)) else "Connection check failed."
                    self._retry_at = time.monotonic()+15
            finally:
                try:
                    if connection:
                        connection.close()
                finally:
                    with self._lock:
                        self._attempt = None
        threading.Thread(target=work,daemon=True).start()
        return self._snapshot()

    @staticmethod
    def _check_access(port, attempt):
        client = http.client.HTTPConnection("127.0.0.1",port,timeout=3)
        attempt.client = client
        try:
            attempt.check()
            client.request("GET","http://www.gstatic.com/generate_204",headers={"Connection":"close"})
            response = client.getresponse()
            if response.status != 204:
                raise ValueError("Internet access check failed.")
            attempt.check()
        except Exception:
            attempt.check()
            raise
        finally:
            attempt.client = None
            client.close()

    def cancel(self):
        with self._lock:
            self._wanted = None
            if self._attempt:
                self._attempt.cancel()
            return self._snapshot()

    def speed_test(self):
        with self._lock:
            if not self._connection:
                return {"error":"Connect before running a speed test."}
            port = self._connection.port
        limit = 8*1024*1024
        client = http.client.HTTPSConnection("127.0.0.1",port,timeout=5,
                    context=ssl.create_default_context(cafile=certifi.where()))
        client.set_tunnel("speed.cloudflare.com",443)
        received = 0
        started = time.monotonic()
        try:
            client.request("GET",f"/__down?bytes={limit}")
            response = client.getresponse()
            if response.status != 200:
                return {"error":"Speed test service unavailable."}
            while received < limit:
                chunk = response.read(min(65536,limit-received))
                if not chunk:
                    break
                received += len(chunk)
                if time.monotonic()-started > 30:
                    break
            return {"bytes":received,"mbps":received*8/max(.001,time.monotonic()-started)/1e6}
        except (OSError,http.client.HTTPException):
            return {"error":"Speed test failed."}
        finally:
            client.close()

    def _sample(self):
        self._seconds = int(time.monotonic() - self._connection.started)
        counts = self._connection.counters()
        if counts is not None:
            now = time.monotonic()
            if self._previous_sample:
                previous_time, previous_counts = self._previous_sample
                elapsed = max(.001, now - previous_time)
                self._rates = {key: max(0, counts[key]-previous_counts[key])/elapsed for key in counts}
            self._previous_sample = (now, counts)
            self._bytes = sum(counts.values())
            if self._session:
                self._store.sample(self._session, self._bytes, time.time())
        return counts is not None

    def _snapshot(self):
        return {"reconnecting": bool(self._wanted and not self._connection and not self._attempt), "connecting": self._attempt is not None, "stage": self._attempt.stage if self._attempt else "", "error":self._error, "auto_power_active":self._low_battery,
                "active": bool(self._connection), "seconds": self._seconds, "bytes": self._bytes,
                "rates": self._rates, "subscription": self._metadata, "warnings": self._warnings(),
                "port": self._connection.port if self._connection else PORT, "mac": sys.platform == "darwin"}

    def _stop(self):
        try:
            if self._connection:
                try:
                    self._sample()
                finally:
                    self._connection.close()
        except ProxyError as error:
            return str(error)
        finally:
            if self._session:
                self._store.sample(self._session, self._bytes, time.time(), end=True)
                self._session = None
            self._connection = None
            self._rates = {"upload":0, "download":0}

    def snapshot(self):
        with self._lock:
            if self._connection and not self._connection.running():
                message = self._stop() or "Соединение прервано."
                return {**self._snapshot(), "error": message}
            if self._connection:
                self._seconds = int(time.monotonic() - self._connection.started)
                if self._previous_sample is None:
                    self._fresh = self._sample()
            fresh = self._fresh if self._connection else True
            return {**self._snapshot(), "fresh": fresh}

    def disconnect(self):
        self.cancel()
        with self._lock:
            if self._connection:
                self._sample()
            message = self._stop()
            return {**self._snapshot(), "error": message}

    def _warnings(self):
        messages = []
        info = self._metadata
        if info.get("expire") and info["expire"] - time.time() < 3*86400:
            messages.append("Subscription expires within 3 days or has expired.")
        if info.get("total") and (info.get("upload",0)+info.get("download",0))/info["total"] >= .9:
            messages.append("Subscription traffic usage has reached 90%.")
        return messages

    def preferences(self, updates=None):
        defaults = {"auto_power":True,"close_behavior":"stop","presentation":False,"power_saving":False,"scale":100,"pinned":[]}
        with self._lock:
            current = {**defaults, **self._store.get("settings",{})}
            if updates is not None:
                if not isinstance(updates,dict) or set(updates)-set(defaults):
                    return {"error":"Invalid preferences."}
                if "scale" in updates and updates["scale"] not in (100,115,130,150):
                    return {"error":"Invalid scale."}
                if "close_behavior" in updates and updates["close_behavior"] not in ("stop","background"):
                    return {"error":"Invalid close behavior."}
                for key in ("presentation","power_saving","auto_power"):
                    if key in updates and type(updates[key]) is not bool:
                        return {"error":"Invalid preference."}
                if "pinned" in updates and (not isinstance(updates["pinned"],list) or any(x not in ("presentation","power_saving","scale","language","palette","auto_power","close_behavior") for x in updates["pinned"])):
                    return {"error":"Invalid pinned settings."}
                self._undo = ("settings",current,time.monotonic()+15)
                current = {**current,**updates}
                self._store.put("settings",current)
            return current

    def favorite(self, name=None):
        with self._lock:
            values = self._store.get("favorites",[])
            if name is not None:
                if name not in self._nodes:
                    return {"error":"Unknown server."}
                key = hashlib.sha256(str(self._nodes[name]).encode()).hexdigest()
                self._undo = ("favorites",values[:],time.monotonic()+15)
                values = [v for v in values if v != key] if key in values else values+[key]
                self._store.put("favorites",values)
            names = [n for n,node in self._nodes.items() if hashlib.sha256(str(node).encode()).hexdigest() in values]
            return {"names": names}

    def undo(self):
        with self._lock:
            if not self._undo or self._undo[2] < time.monotonic():
                return {"error":"Undo has expired."}
            key,value,_ = self._undo
            self._store.put(key,value)
            self._undo = None
            return {"ok":True}

    def report(self):
        return self._store.report()

    def reset(self):
        self.cancel()
        with self._lock:
            if self._attempt:
                return {"error":"Wait for connection cleanup, then reset."}
            message = self._stop()
            if message:
                return {"error":message}
            self._store.reset()
            for name in ("palette","language"):
                self._settings.with_name(name).unlink(missing_ok=True)
            self._nodes = {}
            self._metadata = {}
            self._bytes = self._seconds = 0
            self._undo = None
            return {"ok":True}

    def _close_window(self):
        self.cancel()
        with self._lock:
            self._closed = True
            self._stop()
