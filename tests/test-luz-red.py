import json
import socket
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from construct import ChecksumError

sys.path.insert(0, "src")
import BombillaLocal as local

response = bytes.fromhex("21310020000000001234567800000001") + bytes(range(16))
fake = Mock()
fake.recvfrom.side_effect = [
    (b"bad packet", ("192.168.1.10", 54321)),
    (response, ("192.168.1.11", 54321)),
    (response, ("192.168.1.11", 54321)),
    socket.timeout(),
]
with patch.object(local.socket, "socket") as open_socket, patch.object(
    local, "powershell", return_value="192.168.1.11 AA-BB-CC-DD-EE-FF",
), patch.object(local, "_broadcasts", return_value=["192.168.1.255"]), patch.object(local, "saved_profiles", return_value=[]):
    open_socket.return_value.__enter__.return_value = fake
    records = local.descubrir_bombillas()
    assert [(item.ip, item.mac, item.device_id) for item in records] == [
        ("192.168.1.11", "AABBCCDDEEFF", "12345678")
    ]
    assert fake.sendto.call_count == 3
    assert not hasattr(records[0], "token")

def wrapped(cause):
    try:
        raise cause
    except Exception as error:
        try:
            raise local.DeviceException("detalle sensible") from error
        except local.DeviceException as wrapper:
            return wrapper

messages = [local.mensaje_error_conexion(error) for error in (
    local.BombillaNoEncontrada(), local.IdentidadIncorrecta(),
    wrapped(ChecksumError("detalle sensible")), wrapped(socket.timeout("detalle sensible")),
)]
assert len(set(messages)) == 4 and all("detalle sensible" not in message for message in messages)
assert [local.codigo_error_conexion(error) for error in (
    local.BombillaNoEncontrada(), local.IdentidadIncorrecta(),
    wrapped(ChecksumError("detalle sensible")), wrapped(socket.timeout("detalle sensible")),
)] == ["not-found", "identity", "authentication", "timeout"]
assert local.mensaje_error_conexion(ValueError("otro error")) is None

bulb = local.Bulb()
bulb.ip, bulb.mac, bulb.model = "192.168.1.10", "AABBCCDDEEFF", local.MODEL
with patch.object(local, "LocalYeelight") as device, patch.object(local, "_descubrir_saludos",
    return_value=[("192.168.1.11", "12345678")],
), patch.object(local, "powershell") as neighbors, patch.object(local, "_guardar_ip_recuperada") as save:
    first, candidate = Mock(), Mock()
    first.info.side_effect = local.BombillaNoEncontrada()
    candidate.info.return_value = SimpleNamespace(mac_address=bulb.mac, model=bulb.model)
    device.side_effect = [first, candidate]
    assert bulb.verified("a" * 32) is candidate
    assert bulb.ip == "192.168.1.11"
    neighbors.assert_not_called()
    save.assert_called_once_with(bulb, "192.168.1.10")

with TemporaryDirectory() as folder:
    profiles = Path(folder) / "bombilla.json"
    original = {
        "active": "001122334455",
        "devices": [
            {"mac": bulb.mac, "model": bulb.model, "ip": "192.168.1.10", "token": "cifrado"},
            {"mac": "001122334455", "ip": "192.168.1.12", "token": "otro cifrado"},
        ],
    }
    profiles.write_text(json.dumps(original), encoding="utf-8")
    with patch.object(local, "PROFILE_FILE", profiles):
        local._guardar_ip_recuperada(bulb, "192.168.1.10")
        stored = json.loads(profiles.read_text(encoding="utf-8"))
        assert stored["active"] == original["active"]
        assert stored["devices"][1] == original["devices"][1]
        assert stored["devices"][0] == dict(original["devices"][0], ip=bulb.ip)

print("Descubrimiento, autenticación, causas de error y recuperación verificados")

# Explicit verification must not silently accept another endpoint.
with patch.object(local, "LocalYeelight", side_effect=local.BombillaNoEncontrada("synthetic")), patch.object(
    local, "_descubrir_saludos", side_effect=AssertionError("unexpected rediscovery")
):
    try:
        bulb.control("a7" * 16, "status", recover=False)
    except local.BombillaNoEncontrada:
        pass
    else:
        raise AssertionError("Explicit endpoint failure was not propagated")

# Multiple untrusted hellos must not produce one authentication attempt each.
responders = [(f"192.0.2.{index}", "device") for index in range(1, 41)]
bulb._connection = None
with patch.object(local, "LocalYeelight", side_effect=local.BombillaNoEncontrada()) as attempts, patch.object(
    local, "_descubrir_saludos", return_value=responders
), patch.object(local, "powershell", return_value=""):
    try:
        bulb.verified("a7" * 16)
    except local.BombillaNoEncontrada:
        pass
    else:
        raise AssertionError("Unexpected recovered device")
    assert attempts.call_count <= 5

# A corrupt nested file must be reported as invalid, without escaping the UI
# with a RecursionError. Oversized files must not be parsed.
from Escenas import load_scenes
with TemporaryDirectory() as folder:
    corrupt = Path(folder) / "invalid.json"
    for reader, valid, limit in (
        (load_scenes, "[null, null, null]", 64 * 1024),
        (lambda _path: local.read_profiles(), "{}", 1024 * 1024),
    ):
        with patch.object(local, "PROFILE_FILE", corrupt):
            for text in ("[" * 1500 + "]" * 1500, " " * (limit + 1) + valid):
                corrupt.write_text(text, encoding="utf-8")
                try:
                    reader(corrupt)
                except ValueError:
                    pass
                else:
                    raise AssertionError("Invalid state accepted")

with patch.object(local.subprocess, "run", return_value=SimpleNamespace(stdout="ok")) as runner:
    assert local.powershell("Get-Date") == "ok"
    executable = Path(runner.call_args.args[0][0])
    assert executable.is_absolute() and executable.name.lower() == "powershell.exe"
    assert executable.parent.name == "v1.0"

# Discovery consumes a bounded number of untrusted responses and closes its socket.
sample = bytes(16)
with patch.object(local, "_saludos", return_value=((f"device-{i}", sample) for i in range(200))):
    assert len(local._descubrir_saludos()) == 128
