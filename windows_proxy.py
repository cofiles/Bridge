"""Windows per-user HTTP/HTTPS proxy, with reversible WinINet settings."""
import ctypes as c
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


class Value(c.Union):
    _fields_ = [('number', w.DWORD), ('pointer', c.c_void_p), ('time', w.FILETIME)]


class Option(c.Structure):
    _fields_ = [('option', w.DWORD), ('value', Value)]


class Options(c.Structure):
    _fields_ = [('size', w.DWORD), ('connection', w.LPWSTR), ('count', w.DWORD),
                ('error', w.DWORD), ('options', c.POINTER(Option))]


class WinInet:
    def __init__(self):
        self.dll = c.WinDLL('wininet', use_last_error=True)
        self.kernel = c.WinDLL('kernel32', use_last_error=True)
        self.dll.InternetQueryOptionW.argtypes = [w.HANDLE, w.DWORD, c.c_void_p, c.POINTER(w.DWORD)]
        self.dll.InternetSetOptionW.argtypes = [w.HANDLE, w.DWORD, c.c_void_p, w.DWORD]
        self.kernel.GlobalFree.argtypes = [c.c_void_p]
        self.kernel.GlobalFree.restype = c.c_void_p
        self.kernel.CreateMutexW.argtypes = [c.c_void_p, w.BOOL, w.LPCWSTR]
        self.kernel.CreateMutexW.restype = w.HANDLE
        self.kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
        self.kernel.ReleaseMutex.argtypes = [w.HANDLE]
        self.kernel.CloseHandle.argtypes = [w.HANDLE]
        self.kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        self.kernel.OpenProcess.restype = w.HANDLE

    def read(self):
        options = (Option * 4)()
        for item, code in zip(options, (10, 2, 3, 4)):
            item.option = code
        data = Options(c.sizeof(Options), None, 4, 0, options)
        size = w.DWORD(c.sizeof(data))
        if not self.dll.InternetQueryOptionW(None, 75, c.byref(data), c.byref(size)):
            options[0].option = 1
            if not self.dll.InternetQueryOptionW(None, 75, c.byref(data), c.byref(size)):
                raise c.WinError(c.get_last_error())
        try:
            return [options[0].value.number] + [c.wstring_at(o.value.pointer) if o.value.pointer else '' for o in options[1:]]
        finally:
            for item in options[1:]:
                if item.value.pointer:
                    self.kernel.GlobalFree(item.value.pointer)

    def write(self, values):
        options = (Option * 4)()
        strings = [c.create_unicode_buffer(v) for v in values[1:]]
        options[0].option = 1
        options[0].value.number = values[0]
        for item, code, text in zip(options[1:], (2, 3, 4), strings):
            item.option = code
            item.value.pointer = c.cast(text, c.c_void_p).value
        data = Options(c.sizeof(Options), None, 4, 0, options)
        if not self.dll.InternetSetOptionW(None, 75, c.byref(data), c.sizeof(data)):
            raise c.WinError(c.get_last_error())
        for flag in (39, 37):
            if not self.dll.InternetSetOptionW(None, flag, None, 0):
                raise c.WinError(c.get_last_error())


def backup_path():
    return Path(os.environ['LOCALAPPDATA']) / 'Bridge' / 'windows-proxy.json'


class WindowsProxy:
    def __init__(self):
        self.api = WinInet()
        self.path = backup_path()
        self.mutex = self.api.kernel.CreateMutexW(None, False, 'Local\\BridgeSystemProxy')
        if not self.mutex:
            raise c.WinError(c.get_last_error())
        if c.get_last_error() == 183:
            self.api.kernel.CloseHandle(self.mutex)
            self.mutex = None
            raise OSError('Another Bridge instance is managing the Windows proxy.')

    def restore(self):
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding='utf-8'))
        # Preserve a user's manual changes made while Bridge was connected.
        if self.api.read() == data['applied']:
            self.api.write(data['previous'])
        self.path.unlink()

    def enable(self, port):
        self.restore()
        previous = self.api.read()
        applied = [3, f'http=127.0.0.1:{port};https=127.0.0.1:{port}', '<local>;localhost;127.*;[::1]', '']
        self.path.parent.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'previous':previous, 'applied':applied, 'token':token}), encoding='utf-8')
        os.replace(temporary, self.path)
        try:
            self.api.write(applied)
            if self.api.read() != applied:
                raise OSError('Windows did not apply the proxy settings.')
            command = [sys.executable]
            if not getattr(sys, 'frozen', False):
                command.append(str(Path(__file__).with_name('app.py')))
            command += ['--proxy-watch', str(os.getpid()), token]
            env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT='1')
            subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        except BaseException:
            self.api.write(previous)
            self.path.unlink(missing_ok=True)
            raise

    def close(self):
        if not self.mutex:
            return
        try:
            self.restore()
        finally:
            if self.mutex:
                self.api.kernel.CloseHandle(self.mutex)
                self.mutex = None


def watch(parent_pid, token):
    """Restore settings if the UI is killed; leave normally restored sessions alone."""
    api = WinInet()
    parent = api.kernel.OpenProcess(0x100000, False, parent_pid)
    path = backup_path()
    try:
        while path.exists():
            if json.loads(path.read_text(encoding='utf-8'))['token'] != token:
                return
            if not parent or api.kernel.WaitForSingleObject(parent, 1000) == 0:
                proxy = WindowsProxy()
                try:
                    if path.exists() and json.loads(path.read_text(encoding='utf-8'))['token'] == token:
                        proxy.restore()
                finally:
                    # Only release ownership: a different session must not be restored here.
                    proxy.api.kernel.CloseHandle(proxy.mutex)
                return
    except (OSError, ValueError):
        # Backup remains for recovery on the next application launch.
        pass
    finally:
        if parent:
            api.kernel.CloseHandle(parent)
