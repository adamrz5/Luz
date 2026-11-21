"""Recovery must not adopt one of two authenticated candidates."""
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch
sys.path.insert(0, "src")
import BombillaLocal as local

bulb = local.Bulb()
bulb.ip, bulb.mac = "127.0.0.1", "020000000001"
original, a, b = Mock(), Mock(), Mock()
original.info.side_effect = local.BombillaNoEncontrada()
a.info.return_value = b.info.return_value = SimpleNamespace(mac_address=bulb.mac, model=bulb.model)
with patch.object(local, "_descubrir_saludos", return_value=[("127.0.0.2","12345678"),("127.0.0.3","12345678")]), patch.object(
    local, "LocalYeelight", side_effect=[original,a,b]
), patch.object(local, "_guardar_ip_recuperada") as saved:
    try:
        bulb.verified("a7"*16)
    except local.DeviceException:
        assert bulb.ip == "127.0.0.1"
        saved.assert_not_called()
    else:
        raise AssertionError("Adopted an ambiguous address")

# A legacy profile learns only after authentication and stays compatible with DPAPI.
bulb.ip = "127.0.0.2"
local.save_profile(bulb, "a7"*16)
protocol = local.ProtocoloLuz(bulb.ip, "a7"*16)
protocol._device_id = bytes.fromhex("12345678")
candidate = Mock(_protocol=protocol)
candidate.info.return_value = SimpleNamespace(mac_address=bulb.mac, model=bulb.model)
with patch.object(local, "LocalYeelight", return_value=candidate):
    assert bulb.verified("a7"*16, recover=False) is candidate
assert local.load_profile(bulb.mac)["device_id"] == "12345678"
assert local.load_token(bulb.mac) == "a7"*16
