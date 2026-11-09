import sys
import threading
import time
from pathlib import Path
import os
import tempfile
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
            nodes, skipped = load_subscription(url.strip())
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
            return self._snapshot()

    def _sample(self):
        self._seconds = int(time.monotonic() - self._connection.started)
        count = self._connection.traffic()
        if count is not None:
            self._bytes = count
        return count is not None

    def _snapshot(self):
        return {"active": bool(self._connection), "seconds": self._seconds, "bytes": self._bytes,
                "port": self._connection.port if self._connection else PORT, "mac": sys.platform == "darwin"}

    def _stop(self):
        try:
            if self._connection:
                self._connection.close()
        except ProxyError as error:
            return str(error)
        finally:
            self._connection = None

    def snapshot(self):
        with self._lock:
            if self._connection and not self._connection.running():
                message = self._stop() or "Соединение прервано."
                return {**self._snapshot(), "error": message}
            fresh = self._sample() if self._connection else True
            return {**self._snapshot(), "fresh": fresh}

    def disconnect(self):
        with self._lock:
            if self._connection:
                self._sample()
            message = self._stop()
            return {**self._snapshot(), "error": message}

    def _close_window(self):
        with self._lock:
            self._closed = True
            self._stop()
