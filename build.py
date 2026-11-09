import os
import subprocess
import sys
from pathlib import Path

from bridge import BINARY

root = Path(__file__).resolve().parent
if not BINARY.is_file():
    from setup_core import install
    install()
extra = []
if sys.platform == "darwin":
    import platform
    helper = root / "bin" / "bridge-proxy"
    subprocess.run(["xcrun", "clang", "-arch", platform.machine(), "-fobjc-arc", "-framework", "Foundation",
                    "-framework", "SystemConfiguration", "-framework", "Security",
                    str(root / "mac_proxy.m"), "-o", str(helper)], check=True)
    extra = ["--add-binary", f"{helper}{os.pathsep}bin"]

subprocess.run([
    sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--name", "Bridge",
    "--icon", str(root / "assets" / ("bridge.ico" if os.name == "nt" else "bridge.icns")),
    "--workpath", str(root / "build" / sys.platform),
    "--onefile" if os.name == "nt" else "--onedir", "--add-data", f"assets/bridge.html{os.pathsep}assets",
    "--add-binary", f"{BINARY}{os.pathsep}bin", *extra, "app.py",
], cwd=root, check=True)
