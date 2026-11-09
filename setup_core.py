"""Install the matching, checksum-verified Xray executable."""
import hashlib
import io
import os
import platform
import ssl
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import certifi

ROOT = Path(__file__).resolve().parent
VERSION = "v26.10.31"
HASHES = {
    "macos-64": "37c60b63c77ef5edcfb46a0d70349f7d96e0c132e6a356ead4fd20aeeacc5c75",
    "macos-arm64-v8a": "0a05dca3bd311b0bc5a89c7ce56350cab1e829e131e4b2bcd48eb304fac07e9a",
    "windows-64": "2e04a9995a6f2ad1b28c0bb25c708ecb2695e43a1c9c7889c4b6ac2b48cf7a6a",
    "windows-arm64-v8a": "db062e8a177facacc8ae53d4c9c0df4132b13fc3a89acda6f21d92d36633077e",
}


def install():
    system = {"Darwin": "macos", "Windows": "windows"}[platform.system()]
    arch = {"arm64": "arm64-v8a", "aarch64": "arm64-v8a", "amd64": "64", "x86_64": "64"}[platform.machine().lower()]
    target = f"{system}-{arch}"
    url = f"https://github.com/XTLS/Xray-core/releases/download/{VERSION}/Xray-{target}.zip"
    with urllib.request.urlopen(url, timeout=90, context=ssl.create_default_context(cafile=certifi.where())) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != HASHES[target]:
        raise RuntimeError("Контрольная сумма архива Xray не совпала.")
    binary = ROOT / "bin" / ("xray.exe" if os.name == "nt" else "xray")
    binary.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        payload = archive.read(binary.name)
    with tempfile.NamedTemporaryFile(dir=binary.parent, delete=False) as output:
        output.write(payload)
    os.chmod(output.name, 0o755)
    os.replace(output.name, binary)
    print(binary)


if __name__ == "__main__":
    install()
