"""Create an explicit source-only archive for GitHub."""
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parent
files = [
    "quality.py", "instance.py", "desktop_integration.py", "lifecycle.py", "activity_store.py", "README.md", "requirements.txt", ".gitignore", "app.py", "controller.py",
    "windows_proxy.py", "bridge.py", "connection.py", "mac_proxy.m", "build.py", "setup_core.py",
    "prepare_android.py", "make_icons.py", "package_source.py",
    "android/settings.gradle", "android/build.gradle", "android/gradle.properties",
    "android/app/build.gradle", "android/app/src/main/AndroidManifest.xml",
]
for folder in ("tests", "docs", ".github", "android/app/src/main/java", "android/app/src/main/python",
               "android/app/src/main/res"):
    files.extend(str(p.relative_to(root)) for p in (root / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
files.extend("assets/" + name for name in ("bridge.html","bridge-icon.png","bridge.ico","bridge.icns"))
(root / "dist").mkdir(exist_ok=True)
with zipfile.ZipFile(root / "dist/Bridge-source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
    for name in sorted(set(files)):
        archive.write(root / name, "Bridge/" + name)
print(f"Packaged {len(set(files))} source files.")
