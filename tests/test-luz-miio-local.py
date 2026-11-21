"""Exercise encrypted miIO traffic on a dynamically assigned loopback port."""
import socket
import struct
import sys
import time
from datetime import datetime, timedelta
from threading import Event, Thread
from unittest.mock import patch

from construct import ConstructError
from miio import DeviceException
from miio.protocol import Message

sys.path.insert(0, "src")
import BombillaLocal as local

IP, MAC, TOKEN = "127.0.0.1", "02:00:00:00:00:42", "a7" * 16
DEVICE = bytes((0, 0, 0, 42))
info = {"mac": MAC, "model": local.MODEL}
properties = {"power": "on", "bright": "37", "color_mode": "2", "ct": "2700"}
stop = Event()
errors = []
mode = "normal"


def serve(channel):
    try:
        while not stop.is_set():
            try:
                packet, peer = channel.recvfrom(4096)
            except (TimeoutError, ConnectionResetError):
                continue
            behavior = mode
            if behavior == "absent":
                continue
            if packet == local.SALUDO:
                hello = struct.pack("!HHI4sI", 0x2131, 32, 0, DEVICE, int(time.time())) + bytes(16)
                channel.sendto(hello, peer)
                continue
            try:
                request = Message.parse(packet, token=bytes.fromhex(TOKEN)).data.value
            except (ConstructError, ValueError):
                continue
            if behavior == "drop_reply":
                continue
            if behavior == "slow" and stop.wait(.025):
                return
            command = request["method"]
            if command == "miIO.info":
                output = {k: v for k, v in info.items() if k != behavior}
            elif command == "get_prop":
                output = [properties.get(key, "") for key in request["params"]]
            elif command == "set_bright":
                if behavior != "ignore":
                    properties["bright"] = str(request["params"][0])
                output = ["ok"]
            else:
                raise AssertionError(command)
            if behavior == "drop_set" and command == "set_bright":
                continue
            payload = {"id": request["id"] - (behavior == "stale"), "result": output}
            header = {"unknown": 0, "device_id": bytes(4) if behavior == "wrong-device" else DEVICE,
                      "ts": datetime.utcnow() - timedelta(seconds=10 if behavior == "old-time" else 0)}
            response = Message.build({"header": {"value": header}, "data": {"value": payload}, "checksum": 0},
                                     token=bytes.fromhex(TOKEN))
            if behavior in {"other-port", "other-address"}:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as other:
                    other.bind(("127.0.0.2" if behavior == "other-address" else IP, 0))
                    other.sendto(response, peer)
            else:
                if behavior == "checksum":
                    response = response[:16] + bytes(16) + response[32:]
                if behavior == "malformed":
                    response = response[:9]
                if behavior == "wrong-length":
                    response = response[:2] + bytes(2) + response[4:]
                if behavior == "oversize":
                    response += bytes(4096)
                channel.sendto(response, peer)
    except Exception as error:
        errors.append(error)


with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
    channel.bind((IP, 0))
    channel.settimeout(.05)
    port = channel.getsockname()[1]
    server = Thread(target=serve, args=(channel,), daemon=True)
    server.start()
    original = local.ProtocoloLuz.__init__

    def init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.port = port

    try:
        with patch.object(local, "PUERTO_MIIO", port), patch.object(local.ProtocoloLuz, "__init__", init), patch.object(
            local.DispositivoLocal, "timeout", .18
        ), patch.object(local, "_descubrir_saludos", return_value=()), patch.object(local, "powershell", return_value=""):
            with patch.object(local, "load_profile", return_value=dict(
                ip=IP, mac="020000000099", model=local.MODEL, device_id="00000099"
            )):
                bulb = local.Bulb.identify(IP, TOKEN)
            assert bulb.device_id is None
            assert bulb.mac == local.normalized_mac(MAC)
            assert bulb.control(TOKEN, "status").brightness == 37
            assert bulb.ajustar_relativo(TOKEN, "brightness", [10]).brightness == 47
            mode = "slow"
            assert bulb.control(TOKEN, "status").color_temp == 2700
            assert bulb.control(TOKEN, "brightness", 61).brightness == 61
            mode = "ignore"
            try:
                bulb.control(TOKEN, "brightness", 73)
            except local.CambioNoAplicado as error:
                assert error.status.brightness == 61
            else:
                raise AssertionError("La bombilla acepto el comando sin aplicar el brillo")
            mode = "drop_set"
            deadline = local.COMMAND_DEADLINE.set(time.monotonic() + .15)
            try:
                try:
                    bulb.control(TOKEN, "brightness", 52, recover=False)
                except (ValueError, DeviceException, TimeoutError):
                    pass
                else:
                    raise AssertionError("A lost command response was reported as success")
            finally:
                local.COMMAND_DEADLINE.reset(deadline)
            mode = "normal"
            assert bulb.control(TOKEN, "status").brightness == 52
            for mode in (
                "other-port", "other-address", "checksum", "malformed", "wrong-length", "oversize",
                "wrong-device", "stale", "old-time", "mac", "model", "absent", "normal",
            ):
                try:
                    bulb.verified("c8" * 16 if mode == "normal" else TOKEN)
                except (ValueError, DeviceException):
                    pass
                else:
                    raise AssertionError(f"Accepted invalid response: {mode}")
            mode = "drop_reply"
            start = time.monotonic()
            deadline = local.COMMAND_DEADLINE.set(start + .07)
            try:
                try:
                    bulb.verified(TOKEN, recover=False)
                except (ValueError, DeviceException, TimeoutError):
                    pass
                else:
                    raise AssertionError("Accepted an unanswered request")
            finally:
                local.COMMAND_DEADLINE.reset(deadline)
            assert time.monotonic() - start < .16
    finally:
        stop.set()
        server.join(timeout=1)
        assert not server.is_alive()
        if errors:
            raise errors[0]

print("UDP miIO local: estado, ajuste, retardo, identidad incompleta, silencio y token incorrecto")
