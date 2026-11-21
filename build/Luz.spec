# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, copy_metadata
import argparse
from importlib.util import find_spec
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--portatil", action="store_true")
portatil = parser.parse_args().portatil
project = Path(SPECPATH).parent
metadata = [
    (str(project / "LICENSE"), "licenses/Luz"),
    (str(project / "tools/xiaomi-tokens/LICENSE"), "licenses/xiaomi-cloud-tokens-extractor"),
]
for package in ("python-miio", "PySide6_Essentials", "PyInstaller"):
    metadata.extend(copy_metadata(package))

a = Analysis(
    ['../src/Bombilla.pyw'],
    pathex=[str(project / "tools/xiaomi-tokens")],
    binaries=[],
    datas=collect_data_files('miio') + metadata,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6.QtNetwork"],
    noarchive=False,
    optimize=0,
)
# Python 3.11 bundles an older VC runtime. Match the PySide6 runtime at startup
# so Windows does not reuse an older DLL when it imports QtCore.
qt_dir = Path(find_spec("PySide6").origin).parent
runtime = {"vcruntime140.dll", "vcruntime140_1.dll"}
a.binaries = [
    (name, str(qt_dir / name.lower()), kind)
    if name.lower() in runtime else (name, path, kind)
    for name, path, kind in a.binaries
    # Qt uses the system ICU ABI. Other tools on PATH can ship incompatible ICU.
    if not Path(name).name.lower().startswith(("icuuc", "icudt", "icuin"))
]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries if portatil else [],
    a.datas if portatil else [],
    exclude_binaries=not portatil,
    name="Luz-portatil" if portatil else "Luz",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(Path(SPECPATH) / "luz-qt.ico"),
    disable_windowed_traceback=True,
)
if not portatil:
    app = COLLECT(exe, a.binaries, a.datas, name="app", strip=False, upx=False)
