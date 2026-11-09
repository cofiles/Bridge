import sys
import threading
import time
from pathlib import Path
import os
import tempfile
import hashlib
from activity_store import ActivityStore
from urllib.error import HTTPError


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
        self._monitor = threading.Thread(target=self._monitor_usage, daemon=True)
        self._monitor.start()

    def _monitor_usage(self):
        while not self._closed:
            with self._lock:
                if self._connection and self._connection.running():
                    self._fresh = self._sample()
                interval = 5 if self._store.get("settings", {}).get("power_saving") else 1
            time.sleep(interval)

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
            if self._closed or self._connection:
                return {"error": "Отключите мост перед сменой подписки."}
            self._nodes = nodes
            self._metadata = metadata
        return {"names": list(nodes), "skipped": skipped}

    def connect(self, name):
        with self._lock:
            if self._closed or self._connection or name not in self._nodes:
                return {"error": "Выберите сервер из подписки."}
            try:
                self._connection = self._connect(self._nodes[name])
            except (ProxyError, ValueError) as error:
                return {"error": str(error)}
            except OSError:
                return {"error": "Не удалось запустить мост."}
            self._seconds, self._bytes = 0, 0
            self._previous_sample = None
            self._rates = {"upload": 0, "download": 0}
            self._session = self._store.begin(name, time.time())
            return self._snapshot()

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
        return {"active": bool(self._connection), "seconds": self._seconds, "bytes": self._bytes,
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
        defaults = {"presentation":False,"power_saving":False,"scale":100,"pinned":[]}
        with self._lock:
            current = {**defaults, **self._store.get("settings",{})}
            if updates is not None:
                if not isinstance(updates,dict) or set(updates)-set(defaults):
                    return {"error":"Invalid preferences."}
                if "scale" in updates and updates["scale"] not in (100,115,130,150):
                    return {"error":"Invalid scale."}
                for key in ("presentation","power_saving"):
                    if key in updates and type(updates[key]) is not bool:
                        return {"error":"Invalid preference."}
                if "pinned" in updates and (not isinstance(updates["pinned"],list) or any(x not in ("presentation","power_saving","scale","language","palette") for x in updates["pinned"])):
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
        with self._lock:
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
        with self._lock:
            self._closed = True
            self._stop()
