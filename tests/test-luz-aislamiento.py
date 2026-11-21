"""Prove that source-mode operations stay within the redirected data root."""
import os
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication

root = Path(os.environ["LUZ_STATE_DIR"]).resolve(strict=True)
sys.path.insert(0, "src")
from BombillaLocal import Bulb, IP_FILE, PROFILE_FILE, STATE_DIR, TOKEN_FILE, load_token, save_profile, save_token
from Diagnostico import Diagnostico
from Escenas import DEFAULT_SCENES, SCENE_FILE, load_scenes, save_scenes
from Escritorio import preferences

app = QApplication([])
assert STATE_DIR == root
assert all(path.parent == root for path in (IP_FILE, PROFILE_FILE, TOKEN_FILE, SCENE_FILE))
fresh = Bulb()
assert fresh.ip == fresh.mac == ""
token = "ab" * 16
IP_FILE.write_text("127.0.0.1", encoding="ascii")
save_token(token)
assert load_token() == token
bulb = Bulb()
assert bulb.ip == "127.0.0.1" and not bulb.mac
device = Mock()
device.info.return_value = SimpleNamespace(mac_address="02:00:00:00:00:01", model=bulb.model)
with patch("BombillaLocal.LocalYeelight", return_value=device):
    assert bulb.verified(token) is device
assert bulb.mac == "020000000001"
save_profile(bulb, token)
assert Bulb().mac == bulb.mac and load_token(bulb.mac) == token
save_scenes(DEFAULT_SCENES)
assert load_scenes() == DEFAULT_SCENES
settings = preferences()
settings.setValue("theme", "dark")
settings.sync()
assert Path(settings.fileName()).parent == root
Diagnostico().registrar("check", "ok")
assert (root / "luz-diagnostico.log").is_file()
lock_path = PROFILE_FILE.with_name("Luz.lock")
lock = QLockFile(str(lock_path))
assert lock.tryLock(0) and lock_path.is_file()
lock.unlock()
# Instantiate the UI without authenticating the synthetic profile during the check.
with patch("BombillaLocal.load_token", return_value=""):
    ui = runpy.run_path("src/Bombilla.pyw")
window = ui["Window"]()
window.install_desktop(settings, enable=False)
window.close()
print("Perfiles, legados, escenas, ajustes, diagnóstico y bloqueo aislados")
