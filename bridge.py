import base64
import binascii
import json
import gzip
import zlib
import io
import os
import socket
import ssl
import subprocess
import time
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, ProxyHandler, build_opener

import certifi

PORT = 10809
LIMIT = 4 * 1024 * 1024
BINARY = Path(__file__).resolve().parent / "bin" / ("xray.exe" if os.name == "nt" else "xray")


class SecureRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != "https":
            raise ValueError("Подписка перенаправляет на незащищённый адрес.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def profile(line):
    uri = urlsplit(line)
    if uri.scheme not in ("vless", "trojan") or not uri.username or not uri.hostname:
        raise ValueError()
    query = dict(parse_qsl(uri.query))
    transport = query.get("type", "tcp")
    security = query.get("security", "tls" if uri.scheme == "trojan" else "none")
    if transport not in ("tcp", "raw", "ws", "grpc") or security not in ("tls", "reality", "none"):
        raise ValueError()
    if query.get("headerType", "none") != "none":
        raise ValueError()
    stream = {"network": transport, "security": security}
    if security == "reality":
        if not query.get("pbk"):
            raise ValueError()
        stream["realitySettings"] = {"serverName": query.get("sni", uri.hostname),
                                     "password": query["pbk"], "shortId": query.get("sid", ""),
                                     "fingerprint": query.get("fp", "chrome"), "spiderX": query.get("spx", "/")}
    elif security == "tls":
        tls = {"serverName": query.get("sni", uri.hostname)}
        if query.get("fp"):
            tls["fingerprint"] = query["fp"]
        if query.get("alpn"):
            tls["alpn"] = query["alpn"].split(",")
        stream["tlsSettings"] = tls
    if transport == "ws":
        stream["wsSettings"] = {"path": query.get("path", "/"), "host": query.get("host", uri.hostname)}
    elif transport == "grpc":
        stream["grpcSettings"] = {"serviceName": query.get("serviceName", ""), "authority": query.get("authority", ""),
                                  "multiMode": query.get("mode") == "multi"}
    settings = {"address": uri.hostname, "port": uri.port or 443}
    if uri.scheme == "vless":
        settings.update(id=unquote(uri.username), encryption=query.get("encryption", "none"), flow=query.get("flow", ""))
    else:
        settings = {"servers": [{**settings, "password": unquote(uri.netloc.rsplit("@", 1)[0])}]}
    return unquote(uri.fragment) or uri.hostname, {"protocol": uri.scheme, "settings": settings, "streamSettings": stream}


def parse_subscription(data):
    body = data.decode("utf-8-sig").strip()
    if "://" not in body:
        encoded = "".join(body.split())
        try:
            body = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True).decode()
        except (ValueError, binascii.Error):
            raise ValueError("Ожидается список ссылок VLESS или Trojan, текстом или в Base64.") from None
    nodes = {}
    skipped = 0
    for line in body.splitlines():
        if not line.strip():
            continue
        try:
            name, outbound = profile(line.strip())
        except ValueError:
            skipped += 1
            continue
        label = name
        index = 1
        while label in nodes:
            index += 1
            label = f"{name} ({index})"
        nodes[label] = outbound
    if not nodes:
        raise ValueError("В подписке нет поддерживаемых серверов VLESS или Trojan.")
    return nodes, skipped


def subscription_tls_context():
    # Keep platform trust (including managed Windows roots) and the bundled public CAs.
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return context


def load_subscription(url, with_metadata=False, use_system_proxy=True):
    url = url.strip().lstrip("\ufeff").strip()
    if urlsplit(url).scheme != "https" or not urlsplit(url).hostname:
        raise ValueError("Введите HTTPS-ссылку на подписку.")
    handlers = [SecureRedirect(), HTTPSHandler(context=subscription_tls_context())]
    if not use_system_proxy:
        handlers.insert(0, ProxyHandler({}))
    opener = build_opener(*handlers)
    request = Request(url, headers={"User-Agent":"Bridge/1.3.1", "Accept":"text/plain, application/octet-stream;q=0.9, */*;q=0.1", "Accept-Encoding":"gzip"})
    with opener.open(request, timeout=20) as response:
        data = response.read(LIMIT + 1)
        encoding = response.headers.get("Content-Encoding", "").strip().lower()
        content_type = response.headers.get("Content-Type", "").lower()
        metadata = {}
        for item in response.headers.get("subscription-userinfo", "").split(";"):
            key, separator, value = item.strip().partition("=")
            if separator and key in ("upload", "download", "total", "expire"):
                try:
                    metadata[key] = max(0, int(value))
                except ValueError:
                    pass
    if len(data) > LIMIT:
        raise ValueError("Подписка больше 4 МБ.")
    if encoding == "gzip":
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:
                data = compressed.read(LIMIT+1)
        except (OSError, EOFError, zlib.error):
            raise ValueError("Повреждён сжатый ответ подписки. [SUB_GZIP]") from None
    elif encoding not in ("", "identity"):
        raise ValueError("Неизвестное сжатие ответа подписки. [SUB_ENCODING]")
    if len(data) > LIMIT:
        raise ValueError("Подписка больше 4 МБ.")
    if not data.strip():
        raise ValueError("Сервис вернул пустую подписку. [SUB_EMPTY]")
    if "text/html" in content_type or data.lstrip().lower().startswith((b"<!doctype html",b"<html")):
        raise ValueError("Сервис вернул веб-страницу вместо подписки. Проверьте ссылку и доступ к сервису. [SUB_HTML]")
    result = parse_subscription(data)
    return (*result, metadata) if with_metadata else result


def configuration(outbound, port=PORT, metrics_port=None):
    config = {"log": {"loglevel": "none"}, "inbounds": [{"listen": "127.0.0.1", "port": port, "protocol": "http"}],
            "outbounds": [outbound]}
    if metrics_port is not None:
        config["inbounds"][0]["tag"] = "bridge"
        config["stats"] = {}
        config["policy"] = {"system": {"statsInboundUplink": True, "statsInboundDownlink": True}}
        config["metrics"] = {"listen": f"127.0.0.1:{metrics_port}"}
    return config


def stop(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def validate_config(config, attempt=None, binary=None):
    """Ask the installed core to validate before changing the system network."""
    if attempt:
        attempt.progress("validating_config")
    process = subprocess.Popen([str(binary or BINARY), "run", "-test", "-config", "stdin:"],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        payload = json.dumps(config).encode()
        deadline = time.monotonic()+8
        while True:
            if attempt:
                attempt.check()
            try:
                process.communicate(input=payload, timeout=.1)
                break
            except subprocess.TimeoutExpired:
                payload = None
                if time.monotonic()>deadline:
                    raise ValueError("Проверка конфигурации превысила время ожидания.")
        if process.returncode != 0:
            raise ValueError("Ядро отклонило конфигурацию сервера. Обновите подписку или выберите другой сервер.")
    finally:
        stop(process)


def start(outbound, port=PORT, metrics_port=None, attempt=None):
    if not BINARY.is_file():
        raise ValueError("Ядро Xray отсутствует. Выполните python setup_core.py в папке проекта.")
    config = configuration(outbound, port, metrics_port)
    validate_config(config, attempt)
    if attempt:
        attempt.progress("starting_core")
    with socket.socket() as probe:
        if os.name != "nt":
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise ValueError(f"Порт {port} занят. Закройте другой прокси и повторите.") from None
    process = subprocess.Popen([str(BINARY), "run", "-config", "stdin:"], stdin=subprocess.PIPE,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        with process.stdin as stream:
            stream.write(json.dumps(config).encode())
        deadline = time.monotonic() + 5
        while process.poll() is None and time.monotonic() < deadline:
            if attempt:
                attempt.check()
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    return process
            except OSError:
                time.sleep(0.05)
        raise ValueError("Xray не открыл порт. Проверьте параметры выбранного сервера.")
    except BaseException:
        stop(process)
        raise
