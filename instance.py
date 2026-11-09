"""One desktop instance per user; authenticated loopback activation."""
import json
import os
from pathlib import Path
import secrets
import socket
import threading
import time


class SingleInstance:
    def __init__(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / 'instance.json'
        self.file = (directory / 'instance.lock').open('a+b')
        if self.file.seek(0, 2) == 0:
            self.file.write(b'0')
            self.file.flush()
        self.file.seek(0)
        self.socket = None
        self.callback = None
        self.pending = False
        self.closed = False

    def acquire(self):
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            for _ in range(30):
                try:
                    data = json.loads(self.path.read_text())
                    with socket.create_connection(('127.0.0.1', data['port']), timeout=.3) as client:
                        client.sendall(data['token'].encode('ascii'))
                        if client.recv(2) == b'OK':
                            break
                except (OSError, ValueError, KeyError):
                    time.sleep(.1)
            self.file.close()
            return False
        try:
            self.socket = socket.socket()
            self.socket.bind(('127.0.0.1', 0))
            self.socket.listen(4)
            self.socket.settimeout(.5)
            self.token = secrets.token_hex(32)
            self.path.write_text(json.dumps({'port': self.socket.getsockname()[1], 'token': self.token}))
            self.path.chmod(0o600)
            threading.Thread(target=self._listen, daemon=True).start()
            return True
        except BaseException:
            self.close()
            raise


    def set_callback(self, callback):
        self.callback = callback
        if self.pending:
            self.pending = False
            callback()

    def _listen(self):
        while not self.closed:
            try:
                client, _ = self.socket.accept()
                with client:
                    client.settimeout(1)
                    received = b''
                    while len(received) < len(self.token):
                        part = client.recv(len(self.token)-len(received))
                        if not part:
                            break
                        received += part
                    if secrets.compare_digest(received, self.token.encode('ascii')):
                        self.pending = True
                        if self.callback:
                            self.pending = False
                            self.callback()
                        client.sendall(b'OK')
            except (OSError, RuntimeError):
                pass

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.socket:
            self.socket.close()
            self.path.unlink(missing_ok=True)
        if not self.file.closed:
            self.file.close()
