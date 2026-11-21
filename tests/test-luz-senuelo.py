"""Verify that a dynamic synthetic token is not persisted or printed in plaintext."""
import contextlib
import io
import os
import runpy
import secrets
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")
from BombillaLocal import Bulb, DeviceException, load_token, parse_extractor_clipboard, save_profile
from Diagnostico import Diagnostico
from Escritorio import preferences

secret = secrets.token_hex(16)
root = Path(os.environ["LUZ_STATE_DIR"])
bulb = Bulb()
bulb.ip, bulb.mac = "127.0.0.1", "020000000003"
assert parse_extractor_clipboard(f"IP: 127.0.0.1\nTOKEN: {secret}") == (bulb.ip, secret)
save_profile(bulb, secret)
assert load_token(bulb.mac) == secret

monitor = Diagnostico()
monitor.registrar("error", secret)
monitor.registrar("check", "ok")
settings = preferences()
settings.setValue("theme", "light")
settings.sync()
monitor.exportar(root / "test-report.txt", bulb, settings)
assert all(secret.encode() not in p.read_bytes() for p in root.iterdir() if p.is_file())

cli_output = io.StringIO()
with patch.object(Bulb, "control", side_effect=DeviceException(secret)), patch.object(
    sys, "argv", ["Controlar-Bombilla.py"]
), contextlib.redirect_stderr(cli_output):
    try:
        runpy.run_path("src/Controlar-Bombilla.py", run_name="__main__")
    except SystemExit as exit_status:
        assert exit_status.code == 1
    else:
        raise AssertionError("Expected CLI error")
assert secret not in cli_output.getvalue(), "El error de consola filtró el señuelo"
marker = secret.encode("ascii")
for folder in (Path("src/__pycache__"), Path("tests/__pycache__")):
    for artifact in folder.glob("*.pyc"):
        assert marker not in artifact.read_bytes()
for name in ("build/ensayo/app/Luz.exe", "build/ensayo/Luz-instalador.exe"):
    artifact = Path(name)
    if artifact.is_file():
        assert marker not in artifact.read_bytes()
history = subprocess.check_output(["git", "log", "--all", "-p", "--", "src", "tests", "tools"],
                                  timeout=10)
assert marker not in history
print("Señuelo ausente de estado en claro, diagnóstico, consola y artefactos comprobados")
