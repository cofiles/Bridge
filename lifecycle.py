import threading
import socket

class Cancelled(Exception):
    pass

class Attempt:
    def __init__(self):
        self.event = threading.Event()
        self.stage = "starting"
        self.client = None

    def check(self):
        if self.event.is_set():
            raise Cancelled()

    def progress(self, stage):
        self.check()
        self.stage = stage


    def cancel(self):
        self.event.set()
        client = self.client
        if client and client.sock:
            try:
                client.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
