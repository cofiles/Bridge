"""Desktop VPN conflict hints and system-tray controls."""
import os
import sys
import threading
import time
import psutil


def vpn_conflicts():
    warnings = []
    # Interface names are hints, never proof: Apple services also create utun devices.
    for name, state in psutil.net_if_stats().items():
        lowered = name.lower()
        if state.isup and (lowered.startswith(('tun','tap','utun','wg')) or any(x in lowered for x in ('wireguard','wintun','openvpn','tailscale','zerotier','warp','vpn'))):
            warnings.append(name)
    candidates={'openvpn','openvpn.exe','wireguard','wireguard.exe','tailscaled','tailscaled.exe','sing-box','sing-box.exe','xray','xray.exe'}
    for process in psutil.process_iter(['pid','ppid','name']):
        try:
            info=process.info
            if (info.get('name') or '').lower() in candidates and info.get('ppid')!=os.getpid():
                warnings.append(info['name'])
        except (psutil.NoSuchProcess,psutil.AccessDenied):
            pass
    return {'warnings': sorted(set(warnings)), 'kind':'possible_vpn'}


class Tray:
    def __init__(self, api, window, image_path):
        import pystray
        from PIL import Image
        self.api, self.window = api, window
        self.Menu, self.Item = pystray.Menu, pystray.MenuItem
        self.icon = pystray.Icon('Bridge', Image.open(image_path), 'Bridge', self.Menu(self.Item('Bridge', self.show)))
        self.stopped = False
        self.signature = None
        self.refresh()

    def show(self, *args):
        self.window.show()
        self.window.restore()

    def launch(self, name):
        def work():
            if self.api.preflight()['warnings']:
                # Confirmation happens in the app before any new system network changes.
                self.show()
                self.window.evaluate_js('window.bridgeTrayConflict && window.bridgeTrayConflict()')
                return
            self.api.cancel()
            deadline=time.monotonic()+12
            while self.api.snapshot()['connecting'] and time.monotonic()<deadline:
                time.sleep(.1)
            if self.api.snapshot()['connecting']:
                self.show()
                return
            self.api.disconnect()
            result=self.api.connect(name)
            if result.get('error'):
                self.show()
        threading.Thread(target=work,daemon=True).start()

    def disconnect(self, *args):
        threading.Thread(target=self.api.disconnect,daemon=True).start()

    def quit(self, *args):
        def close():
            self.api._force_quit = True
            self.api._close_window()
            self.stop()
            self.window.destroy()
        threading.Thread(target=close,daemon=True).start()

    def refresh(self):
        state=self.api.snapshot()
        names=self.api.servers()['names']
        language=self.api.language()['name']
        private=self.api.preferences()['presentation']
        signature=(tuple(names),state['active'],state['connecting'],state['reconnecting'],state.get('server'),language,private)
        if signature==self.signature:
            return
        self.signature=signature
        en=language=='en'
        label=('Connected' if en else 'Подключено') if state['active'] else ('Connecting…' if en else 'Подключаем…') if state['connecting'] or state['reconnecting'] else ('Disconnected' if en else 'Отключено')
        def action(name):
            def callback(icon,item): self.launch(name)
            return callback
        def checked(name):
            return lambda item:state.get('server')==name
        nodes=[self.Item((f'Server {i+1}' if en else f'Сервер {i+1}') if private else name, action(name), checked=checked(name)) for i,name in enumerate(names)]
        self.icon.menu=self.Menu(
            self.Item(label, lambda icon,item:None, enabled=False),
            self.Item('Open Bridge' if en else 'Открыть Bridge', self.show, default=True),
            self.Item('Auto select and connect' if en else 'Автовыбор и подключение', action('__auto__'), enabled=bool(names)),
            self.Item('Servers' if en else 'Серверы', self.Menu(*nodes) if nodes else self.Menu(self.Item('—',lambda icon,item:None,enabled=False))),
            self.Item('Disconnect' if en else 'Отключить', self.disconnect, enabled=state['active'] or state['connecting'] or state['reconnecting']),
            self.Menu.SEPARATOR,
            self.Item('Quit Bridge' if en else 'Выйти из Bridge',self.quit))
        self.icon.title='Bridge · '+label
        self.icon.update_menu()

    def start(self):
        if sys.platform=='darwin':
            self.icon.run_detached()
        else:
            threading.Thread(target=self.icon.run,daemon=True).start()
        def monitor():
            while not self.stopped and not self.api._closed:
                try:
                    if sys.platform=="darwin":
                        from PyObjCTools import AppHelper
                        AppHelper.callAfter(self.refresh)
                    else:
                        self.refresh()
                except Exception:
                    pass
                time.sleep(1)
        threading.Thread(target=monitor,daemon=True).start()

    def stop(self):
        self.stopped=True
        self.icon.stop()
