"""Prepare an ARM64 Android build from a clean source checkout."""
import hashlib
import shutil
import ssl
import urllib.request
import zipfile
import io
from pathlib import Path
import certifi

root = Path(__file__).resolve().parent
destination = root / "android/app/src/main"
for name in ("lifecycle.py", "activity_store.py", "bridge.py", "controller.py", "connection.py"):
    shutil.copy2(root / name, destination / "python" / name)
shutil.copy2(root / "assets/bridge-icon.png", destination / "res/drawable/icon.png")
url = "https://github.com/XTLS/Xray-core/releases/download/v26.10.31/Xray-android-arm64-v8a.zip"
with urllib.request.urlopen(url, timeout=120, context=ssl.create_default_context(cafile=certifi.where())) as response:
    data = response.read()
if hashlib.sha256(data).hexdigest() != "ee7878bb47ce28ff5b068e2d173ba1a9fab20ca1aec94191644919ec08ba5f1d":
    raise RuntimeError("Xray checksum mismatch")
target = destination / "jniLibs/arm64-v8a"
target.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(io.BytesIO(data)) as archive:
    (target / "libxray.so").write_bytes(archive.read("xray"))
print("Android sources and Xray are ready.")
