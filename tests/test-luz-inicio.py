"""Exercise the registry adapter against an in-memory replacement."""
import sys
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, "src")
import Escritorio

values = {}


def query(_key, name):
    try:
        return values[name]
    except KeyError:
        raise FileNotFoundError(name) from None


def delete(key, name):
    query(key, name)
    del values[name]


with TemporaryDirectory() as temporal, patch.multiple(
    Escritorio.winreg,
    OpenKey=lambda *_args: nullcontext(),
    CreateKeyEx=lambda *_args: nullcontext(),
    QueryValueEx=query,
    SetValueEx=lambda _key, name, _zero, kind, value: values.update({name: (value, kind)}),
    DeleteValue=delete,
):
    folder = Path(temporal)
    old, new = folder / "Anterior.exe", folder / "Luz.exe"
    assert not Escritorio.inicio_windows()
    Escritorio.guardar_inicio_windows(Escritorio.comando_inicio_windows(old))
    assert Escritorio.inicio_windows() == Escritorio.comando_inicio_windows(old)
    Escritorio.actualizar_inicio_windows(new)
    assert Escritorio.inicio_windows() == Escritorio.comando_inicio_windows(new)
    Escritorio.guardar_inicio_windows("")
    assert not Escritorio.inicio_windows()
    Escritorio.actualizar_inicio_windows(new)
    assert not values

print("Inicio con Windows verificado con un registro en memoria")

# The tray and Windows hotkeys are shared across configuration directories.
with TemporaryDirectory(prefix="luz-desktop-lock-") as folder, patch.dict(
    "os.environ", {"LOCALAPPDATA": folder}
):
    primary = Escritorio.desktop_lock()
    secondary = Escritorio.desktop_lock()
    assert primary.tryLock(0)
    try:
        assert not secondary.tryLock(0)
    finally:
        primary.unlock()
    assert secondary.tryLock(0)
    secondary.unlock()
