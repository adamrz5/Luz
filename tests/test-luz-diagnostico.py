import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

sys.path.insert(0, "src")
from Diagnostico import Diagnostico

with TemporaryDirectory(prefix="luz-tests-") as temp:
    monitor = Diagnostico(Path(temp))
    token_prueba = "0123456789abcdef" * 2
    monitor.registrar("error", token_prueba)
    monitor.registrar("check", "ok")
    settings = Mock()
    settings.value.return_value = token_prueba
    bulb = Mock(ip="192.0.2.134", mac="020000A1B2C3", model="yeelink.light.color5")
    target = Path(temp) / "export.txt"
    monitor.exportar(target, bulb, settings)
    for path in Path(temp).glob("*"):
        assert token_prueba not in path.read_text(encoding="utf-8")
    output = target.read_text(encoding="utf-8")
    assert "192.0." not in output and "02:00:00" not in output
    assert "192.0.2.134" not in output and bulb.mac not in output
    assert "check: ok" in output
print("Diagnóstico: redacción, registro y exportación comprobados")

with TemporaryDirectory(prefix="luz-tests-") as temp:
    root = Path(temp)
    lock = root / "Luz" / "escritorio.lock"
    lock.parent.mkdir()
    lock.write_text("held", encoding="utf-8")
    with patch.dict("os.environ", {"LOCALAPPDATA": temp}):
        try:
            Diagnostico(root).exportar(lock, bulb, None)
        except ValueError:
            pass
        else:
            raise AssertionError("Diagnostic export overwrote the desktop lock")
    assert lock.read_text(encoding="utf-8") == "held"
