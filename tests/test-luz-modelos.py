import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, "src")
import BombillaLocal as local
from Escenas import DEFAULT_SCENES, load_scenes, save_scenes

rgb = local.capabilities("yeelink.light.color5")
tunable = local.capabilities("yeelink.light.ct_bulb")
fixed = local.capabilities("yeelink.light.mono1")
assert rgb.rgb and rgb.effects
assert tunable.tunable_white and tunable.minimum == 2700 and not tunable.rgb
assert not fixed.tunable_white and not fixed.rgb

for model in ("philips.light.bulb", "yeelink.light.ceiling1", "yeelink.light.color99"):
    try:
        local.capabilities(model)
    except ValueError:
        pass
    else:
        raise AssertionError(model)

device = Mock()
device.get_properties.side_effect = lambda keys: [
    {"power":"on", "bright":"35", "color_mode":"3", "hue":"202", "sat":"71"}.get(key, "")
    for key in keys
]
assert local.read_status(device, rgb).hsv == (202, 71, 35)
assert local.read_status(device, fixed).color_temp is None
assert device.get_properties.call_args.args[0] == ["power", "bright", "color_mode"]

with tempfile.TemporaryDirectory(prefix="luz-tests-") as folder, patch.object(
    local, "PROFILE_FILE", Path(folder) / "bombilla.json"
):
    with patch.object(local, "LocalDevice") as discovery:
        discovery.return_value.info.return_value = SimpleNamespace(
            model="yeelink.light.ct_bulb", mac_address="aa:bb:cc:dd:ee:ff"
        )
        bulb = local.Bulb.identify("192.168.1.120", "a"*32)
    local.save_profile(bulb, "a"*32, room="Dormitorio", xiaomi_name="Original Xiaomi")
    assert local.Bulb(bulb.mac).xiaomi_name == "Original Xiaomi"
    assert local.Bulb(bulb.mac).room == "Dormitorio"
    assert local.load_token() == "a"*32
    saved = local.load_profile()
    assert saved["version"] == 2 and "a"*32 not in local.PROFILE_FILE.read_text()
    tampered = dict(saved, mac="001122334455")
    local.PROFILE_FILE.write_text(json.dumps(tampered), encoding="utf-8")
    try:
        local.load_token()
    except OSError:
        pass
    else:
        raise AssertionError("Se pudo leer el token de un perfil con otra MAC")
    for invalid in (None, dict(saved, ip="invalid")):
        local.PROFILE_FILE.write_text(json.dumps(invalid), encoding="utf-8")
        try:
            local.load_token()
        except ValueError:
            pass
        else:
            raise AssertionError("Se recuperó un token pese a un perfil activo inválido.")
    local.PROFILE_FILE.write_text(json.dumps(saved), encoding="utf-8")
    restored = local.Bulb()
    assert (restored.mac, restored.model, restored.ip) == (
        "AABBCCDDEEFF", "yeelink.light.ct_bulb", "192.168.1.120"
    )
    with patch.object(restored, "verified", return_value=device) as verified:
        try:
            restored.control("a"*32, "color", (1,2,3))
        except local.UnsupportedControl:
            verified.assert_not_called()
        else:
            raise AssertionError("El modelo de blanco aceptó RGB")
        device.get_properties.side_effect = lambda keys: [
            {"power": "on", "bright": "30", "color_mode": "2", "ct": "2700"}.get(key, "")
            for key in keys
        ]
        restored.control("a"*32, "scene", ("white", 2000, 30))
        device.set_color_temp.assert_called_with(2700)
        device.set_brightness.assert_called_with(30)

wrong = SimpleNamespace(model=restored.model, mac_address="001122334455")
right = SimpleNamespace(model=restored.model, mac_address=restored.mac)
with patch.object(local, "LocalYeelight") as connect, patch.object(
    local, "_descubrir_saludos", return_value=[]
), patch.object(
    local, "powershell", return_value="192.168.1.121"
):
    old, recovered = Mock(), Mock()
    old.info.return_value, recovered.info.return_value = wrong, right
    connect.side_effect = [old, recovered]
    assert restored.verified("a"*32) is recovered
    assert restored.ip == "192.168.1.121"

with patch.object(local, "LocalYeelight") as connect, patch.object(
    local, "_descubrir_saludos", return_value=[]
), patch.object(
    local, "powershell", side_effect=subprocess.TimeoutExpired("powershell.exe", 10)
):
    connect.return_value.info.side_effect = local.DeviceException("offline")
    restored._connection = None
    try:
        restored.verified("a"*32)
    except ValueError as error:
        assert "Sin conexión" in str(error)
    else:
        raise AssertionError("La consulta vecinal fallida se trató como una conexión válida.")

with tempfile.TemporaryDirectory(prefix="luz-tests-") as folder, patch.object(
    local, "PROFILE_FILE", Path(folder) / "bombilla.json"
), patch.object(local, "TOKEN_FILE", Path(folder) / "token.dpapi"):
    local.TOKEN_FILE.write_bytes(b"not base64!")
    try:
        local.load_token()
    except ValueError:
        pass
    else:
        raise AssertionError("Se aceptó un archivo antiguo que no era base64.")
    backup = Path(folder) / "escenas.json"
    save_scenes(DEFAULT_SCENES, backup)
    try:
        save_scenes(DEFAULT_SCENES[:2], backup)
    except ValueError:
        assert load_scenes(backup) == DEFAULT_SCENES
    else:
        raise AssertionError("Se sobreescribieron las escenas con una lista incompleta.")

device.get_properties.side_effect = None
device.get_properties.return_value = None
try:
    local.read_status(device, rgb)
except local.DeviceException:
    pass
else:
    raise AssertionError("Se aceptó una respuesta de estado nula.")
device.get_properties.side_effect = TypeError("un resultado nulo no se puede extender")
try:
    local.read_status(device, rgb)
except local.DeviceException:
    pass
else:
    raise AssertionError("El error de python-miio debía convertirse a DeviceException.")
device.get_properties.side_effect = None
device.get_properties.return_value = ["on", float("inf"), "2", "-10000"]
state = local.read_status(device, tunable)
assert state.color_temp is None and state.brightness == 1

raw = "0123456789abcdef" * 2
block = f"NAME: Bombilla\r\nIP: 192.168.1.40\r\nTOKEN: {raw}\r\nMODEL: yeelink.light.color5"
assert local.parse_extractor_clipboard(block) == ("192.168.1.40", raw)
assert local.parse_extractor_clipboard(raw) == (None, raw)
for invalid in (block+"\n"+block, block.replace("192.168.1.40", "999.168.1.40")):
    try:
        local.parse_extractor_clipboard(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("Entrada de portapapeles inválida aceptada")
print("Catálogo, estado normalizado, perfil cifrado y límites de hardware verificados")


for preset, steps in local.FLOW_PRESETS.items():
    bulb = local.Bulb()
    bulb.model = local.MODEL
    active = local.LightStatus(True, 100, None, None, None, True, 0)
    inactive = local.LightStatus(True, 100, None, None, None, False, 0)
    with patch.object(bulb, "verified", return_value=device), patch.object(
            local, "read_status", side_effect=[active, inactive]):
        bulb.control("a"*32, "flow", preset)
        expected = ",".join(str(part) for duration, rgb, brightness in steps
                            for part in (duration, 1, rgb, brightness))
        device.send.assert_called_with("start_cf", [0, 0, expected])
        bulb.control("a"*32, "flow", False)
        device.send.assert_called_with("stop_cf")

bulb = local.Bulb()
bulb.model = local.MODEL
with patch.object(bulb, "verified", return_value=device):
    def properties(keys):
        return [values.get(key) for key in keys]

    device.get_properties.side_effect = properties
    values = dict(power="on", flowing="1", delayoff="4")
    assert bulb.control(raw, "flow", True).color_flowing is True
    assert bulb.control(raw, "timer", 5).delay_off == 4
    for action, value, readback in (
        ("flow", True, {"flowing": "0"}), ("flow", False, {"flowing": "1"}),
        ("flow", False, {"flowing": None}), ("flow", True, {"flowing": "2"}),
        ("timer", 5, {"delayoff": "0"}), ("timer", 5, {"delayoff": "30"}),
        ("timer", 0, {"delayoff": "4"}), ("timer", 0, {"delayoff": None}),
        ("timer", 0, {"delayoff": "-1"}),
    ):
        values = dict(power="on", **readback)
        try:
            bulb.control(raw, action, value)
        except local.CambioNoAplicado:
            pass
        else:
            raise AssertionError(f"Unexpected confirmation of {action}={value} con {readback}")
    values = dict(power="on", flowing="0", delayoff="0")
    assert bulb.control(raw, "flow", False).color_flowing is False
    assert bulb.control(raw, "timer", 0).delay_off == 0

valid = "a7" * 16
for pasted in (
    f"TOKEN: inválido\nTOKEN: {valid}",
    f"IP:\nIP: 127.0.0.1\nTOKEN: {valid}",
    f"TOKEN: {valid}\n\x00",
    "x" * 17000 + f"\nTOKEN: {valid}",
):
    try:
        local.parse_extractor_clipboard(pasted)
    except ValueError:
        pass
    else:
        raise AssertionError("El pegado aceptó una entrada ambigua o demasiado larga")
