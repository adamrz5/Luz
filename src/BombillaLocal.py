"""Authenticated local control for supported Xiaomi bulb models."""
import base64
import ctypes
import json
import logging
import os
import re
import socket
import subprocess
import sys
import time
from contextlib import closing
from contextvars import ContextVar
from ctypes import wintypes
from dataclasses import dataclass
from datetime import timedelta
from ipaddress import IPv4Address, IPv4Network
from itertools import count
from pathlib import Path
from secrets import randbelow
from tempfile import NamedTemporaryFile

from construct import ChecksumError, ConstructError
from ifaddr import get_adapters
from miio import Device, DeviceException, Yeelight
from miio.exceptions import PayloadDecodeException, RecoverableError
from miio.miioprotocol import MiIOProtocol
from miio.protocol import Message

from Idioma import tr

# The pinned library formats raw protocol payloads and checksums in debug messages.
logging.getLogger("miio.miioprotocol").disabled = True
logging.getLogger("miio.protocol").disabled = True

SALUDO = bytes.fromhex("21310020" + "ff" * 28)
PUERTO_MIIO = 54321

MODEL = "yeelink.light.color5"
APP_DIR = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
PROJECT_DIR = APP_DIR.parent
state_override = os.environ.get("LUZ_STATE_DIR")
if state_override is not None:
    STATE_DIR = Path(state_override)
    if not STATE_DIR.is_absolute():
        raise ValueError("LUZ_STATE_DIR must be an absolute directory path")
    STATE_DIR = STATE_DIR.resolve()
else:
    STATE_DIR = (PROJECT_DIR / "config" if APP_DIR.name.lower() in {"app", "src"}
                 and (PROJECT_DIR / "src" / "BombillaLocal.py").is_file()
                 else Path(os.environ["LOCALAPPDATA"]) / "Luz")
TOKEN_FILE = STATE_DIR / "bombilla-token.dpapi"
IP_FILE = STATE_DIR / "bombilla-ip.txt"
PROFILE_FILE = STATE_DIR / "bombilla.json"

# Firmware families from the specs bundled with the pinned python-miio.
RGB_MODELS = frozenset("color color1 color2 color3 color4 color5 color7 colorc".split())
WHITE_MODELS = frozenset("ct_bulb ct2 mono1 mono5 monob".split())

FLOW_PRESETS = {
    "Ciclo de color": ((2400, 16733559, 40), (2400, 6669567, 40), (2400, 11832831, 40)),
    "Océano": ((2800, 0x195DFF, 42), (3200, 0x27D4CA, 47), (2800, 0x493BDB, 36)),
    "Atardecer": ((4000, 0xFF520C, 38), (4000, 0xFFAA50, 52), (4000, 0xD32955, 33)),
    "Respiración": ((3300, 0x7765FF, 55), (3300, 0x7765FF, 12)),
}



@dataclass(frozen=True)
class Capabilities:
    rgb: bool
    minimum: int
    maximum: int
    effects: bool

    @property
    def tunable_white(self):
        return self.maximum > self.minimum


def capabilities(model):
    if not isinstance(model, str):
        raise ValueError("La bombilla no devolvió un modelo miIO válido.")
    family = model.removeprefix("yeelink.light.")
    if not model.startswith("yeelink.light.") or family not in RGB_MODELS | WHITE_MODELS:
        raise ValueError(tr("Modelo sin control local compatible: {model}").format(model=model))
    if family in ("mono1", "mono5", "monob"):
        return Capabilities(False, 2700, 2700, False)
    minimum = 2700 if family in ("color2", "colorc", "ct_bulb", "ct2") else 1700
    return Capabilities(family in RGB_MODELS, minimum, 6500, model == MODEL)


def normalized_mac(value):
    mac = re.sub(r"[:-]", "", value.upper()) if isinstance(value, str) else ""
    if not re.fullmatch(r"[0-9A-F]{12}", mac):
        raise ValueError("La bombilla no devolvió una MAC válida.")
    return mac


PROFILE_JSON_LIMIT = 1024 * 1024
INVALID_PROFILE = "El archivo de bombillas no es válido."


def read_bounded_json(path, limit, invalid):
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ValueError(invalid)
    try:
        return json.loads(data.decode("utf-8"))
    except (ValueError, RecursionError):
        raise ValueError(invalid) from None


def read_profiles():
    try:
        data = read_bounded_json(PROFILE_FILE, PROFILE_JSON_LIMIT, INVALID_PROFILE)
    except FileNotFoundError:
        return None
    if not isinstance(data, dict):
        raise ValueError(INVALID_PROFILE)
    return data


def profile_entries(stored):
    if stored is None:
        return []
    if not isinstance(stored, dict):
        raise ValueError("El archivo de bombillas no es válido.")
    if "devices" not in stored:
        return [stored]
    devices = stored["devices"]
    if not isinstance(devices, list) or any(not isinstance(item, dict) for item in devices):
        raise ValueError("La lista de bombillas no es válida.")
    return devices


def saved_profiles():
    return profile_entries(read_profiles())


def load_profile(mac=None):
    stored = read_profiles()
    entries = profile_entries(stored)
    if mac:
        selected = next((item for item in entries if item.get("mac") == mac), None)
        if selected is None:
            raise ValueError("La bombilla seleccionada ya no está guardada.")
        return selected
    if isinstance(stored, dict) and "devices" in stored:
        active = next((item for item in entries if item.get("mac") == stored.get("active")), None)
        if active is None:
            raise ValueError("No se encontró la bombilla activa en el archivo de perfiles.")
        return active
    return entries[0] if entries else None


def profiles_for_display():
    profiles = []
    for item in saved_profiles():
        if not all(isinstance(item.get(key), str) for key in ("mac", "model")):
            continue
        name = next((item[key] for key in ("name", "xiaomi_name")
                     if isinstance(item.get(key), str) and item[key]), item["model"])
        profiles.append((item["mac"], name))
    return profiles


def profile_address(profile):
    try:
        ip = str(IPv4Address(profile["ip"]))
        mac = normalized_mac(profile["mac"])
        model = profile["model"]
        capabilities(model)
    except (KeyError, ValueError, TypeError) as error:
        raise ValueError("El perfil de la bombilla seleccionada no es válido.") from error
    return ip, mac, model


def profile_context(mac, model):
    capabilities(model)
    return f"Luz/miIO/v2/{normalized_mac(mac)}/{model}".encode("ascii")


def valid_token(token):
    return isinstance(token, str) and re.fullmatch(r"[0-9a-fA-F]{32}", token) is not None


def save_profile(bulb, token, name=None, room=None, xiaomi_name=None):
    if not valid_token(token):
        raise ValueError("El token debe tener 32 caracteres hexadecimales.")
    context = profile_context(bulb.mac, bulb.model)
    profiles = saved_profiles()
    previous = next((item for item in profiles if item.get("mac") == bulb.mac), {})
    entry = dict(version=2, ip=bulb.ip, mac=bulb.mac, model=bulb.model,
                 name=previous.get("name", "") if name is None else name,
                 room=previous.get("room", "") if room is None else room,
                 xiaomi_name=previous.get("xiaomi_name", "") if xiaomi_name is None else xiaomi_name,
                 token=base64.b64encode(dpapi(token.encode("ascii"), entropy=context)).decode("ascii"))
    if bulb.device_id is not None:
        entry["device_id"] = bulb.device_id
    contents = dict(active=bulb.mac, devices=[item for item in profiles if item.get("mac") != bulb.mac] + [entry])
    _escribir_perfiles(contents)


def _escribir_perfiles(contents):
    encoded = json.dumps(contents)
    if len(encoded) > PROFILE_JSON_LIMIT:
        raise ValueError(INVALID_PROFILE)
    PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(dir=PROFILE_FILE.parent, prefix=".bombilla-", suffix=".tmp",
                                mode="w", encoding="utf-8", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
        temporary.replace(PROFILE_FILE)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _guardar_ip_recuperada(bulb, previous_ip):
    stored = read_profiles()
    profile = next((item for item in profile_entries(stored)
                    if (item.get("mac"), item.get("model"), item.get("ip"))
                    == (bulb.mac, bulb.model, previous_ip)), None)
    if profile is not None:
        if profile["ip"] != bulb.ip or (bulb.device_id is not None and profile.get("device_id") != bulb.device_id):
            profile["ip"] = bulb.ip
            if bulb.device_id is not None:
                profile["device_id"] = bulb.device_id
            _escribir_perfiles(stored)


@dataclass(frozen=True)
class LightStatus:
    is_on: bool
    brightness: int
    color_temp: int | None
    rgb: tuple[int, int, int] | None
    hsv: tuple[int, int, int] | None
    color_flowing: bool
    delay_off: int


def read_status(device, features, *, require_effect=None):
    keys = ["power", "bright", "color_mode"]
    if features.tunable_white:
        keys.append("ct")
    if features.rgb:
        keys.extend(("rgb", "hue", "sat"))
    if features.effects:
        keys.extend(("flowing", "delayoff"))
    try:
        properties = device.get_properties(keys)
    except TypeError as error:
        raise DeviceException("La bombilla devolvió un estado inválido.") from error
    if not isinstance(properties, (list, tuple)):
        raise DeviceException("La bombilla devolvió un estado inválido.")
    data = dict(zip(keys, properties))
    if data.get("power") not in ("on", "off"):
        raise DeviceException("La bombilla no devolvió su estado de encendido.")

    def number(key, fallback=0):
        try:
            return int(data.get(key))
        except (ValueError, TypeError, OverflowError):
            return fallback

    brightness = min(100, max(1, number("bright", 1)))
    mode = number("color_mode")
    rgb = hsv = None
    temperature = None
    if features.rgb and mode == 1:
        value = number("rgb", -1)
        if 0 <= value <= 0xFFFFFF:
            rgb = (value >> 16, (value >> 8) & 255, value & 255)
    elif features.rgb and mode == 3:
        hsv = (number("hue") % 360, min(100, max(0, number("sat"))), brightness)
    elif features.tunable_white:
        value = number("ct")
        if features.minimum <= value <= features.maximum:
            temperature = value
    flowing, delay_off = number("flowing", -1), number("delayoff", -1)
    status = LightStatus(data["power"] == "on", brightness, temperature, rgb, hsv,
                         flowing > 0, max(0, delay_off))
    if ((require_effect == "flow" and flowing not in (0, 1))
            or (require_effect == "timer" and delay_off < 0)):
        raise CambioNoAplicado(status)
    return status


class UnsupportedControl(ValueError):
    pass


class CambioNoAplicado(DeviceException):
    def __init__(self, status):
        super().__init__("La bombilla no confirmó el cambio. Vuelve a intentarlo.")
        self.status = status


def confirmar_cambio(status, **expected):
    if any(getattr(status, name) != value for name, value in expected.items()):
        raise CambioNoAplicado(status)
    return status


class BombillaNoEncontrada(ValueError, DeviceException):
    pass


class IdentidadIncorrecta(ValueError, DeviceException):
    pass


class TokenProbable(DeviceException):
    pass


class RespuestaNoValida(DeviceException):
    pass


MENSAJES_CONEXION = {
    "probable-token": "Token rechazado (probable). Comprueba el token y vuelve a comprobar.",
    "invalid-response": "Respuesta no válida. Comprueba de nuevo la conexión.",
    "identity": "La MAC o el modelo no coinciden. Comprueba la IP: podría ser otra bombilla.",
    "authentication": "La bombilla no autenticó la respuesta. Vuelve a obtener su token en Conexión → Obtener token por QR.",
    "timeout": "La bombilla no respondió a tiempo. Reintenta y comprueba que el firewall de Windows permite el tráfico UDP de Luz.",
    "not-found": "No se encontró la bombilla. Comprueba la corriente y que el PC y la bombilla estén en la misma red Wi-Fi. Usa Buscar bombillas o reserva la IP en el router.",
}


def codigo_error_conexion(error):
    actual = error
    while actual is not None:
        if isinstance(actual, TokenProbable):
            return "probable-token"
        if isinstance(actual, RespuestaNoValida):
            return "invalid-response"
        if isinstance(actual, IdentidadIncorrecta):
            return "identity"
        if isinstance(actual, (ChecksumError, PayloadDecodeException)):
            return "authentication"
        if isinstance(actual, TimeoutError):
            return "timeout"
        if isinstance(actual, BombillaNoEncontrada):
            return "not-found"
        actual = actual.__cause__
    return None


def mensaje_error_conexion(error):
    if isinstance(error, CambioNoAplicado):
        return str(error)
    if isinstance(error, RespuestaNoValida) and str(error) == "Hay varias IP posibles. Comprueba la dirección manualmente.":
        return str(error)
    return MENSAJES_CONEXION.get(codigo_error_conexion(error))


def _broadcasts():
    targets = {"255.255.255.255"}
    for adapter in get_adapters():
        for address in adapter.ips:
            if address.is_IPv4 and not IPv4Address(address.ip).is_loopback and address.network_prefix < 31:
                network = IPv4Network((address.ip, address.network_prefix), strict=False)
                targets.add(str(network.broadcast_address))
    return sorted(targets)


def _saludos(addr=None, timeout=5):
    deadline = time.monotonic() + timeout
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
        if addr is None:
            channel.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        last_error, sent = None, False
        for target in (addr,) if addr is not None else _broadcasts():
            try:
                for _ in range(3):
                    channel.sendto(SALUDO, (target, PUERTO_MIIO))
                    sent = True
            except OSError as error:
                last_error = error
        if not sent and last_error is not None:
            raise last_error
        while (remaining := deadline - time.monotonic()) > 0:
            channel.settimeout(remaining)
            try:
                data, (ip, port) = channel.recvfrom(1024)
            except socket.timeout:
                return
            if (port == PUERTO_MIIO and (addr is None or addr == ip)
                    and len(data) == 32 and data[:4] == SALUDO[:4] and data[8:12] != b"\xff" * 4):
                yield ip, data[:16]


def _descubrir_saludos():
    with_saludo = {}
    with closing(_saludos()) as replies:
        for ip, header in replies:
            with_saludo[ip] = header
            if len(with_saludo) == 128:
                break
    return [(ip, header[8:12].hex()) for ip, header in with_saludo.items()]


@dataclass(frozen=True)
class BombillaDescubierta:
    ip: str
    device_id: str
    mac: str | None
    model: str | None


def descubrir_bombillas():
    saludos = _descubrir_saludos()
    if not saludos:
        return ()
    macs, models = {}, {}
    try:
        neighbors = powershell(
            "Get-NetNeighbor -AddressFamily IPv4 | ForEach-Object {"
            " '{0} {1}' -f $_.IPAddress,$_.LinkLayerAddress }",
            timeout=2,
        )
        for line in neighbors.splitlines():
            fields = line.split()
            if len(fields) == 2 and re.fullmatch(r"(?:[0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2}", fields[1]):
                macs[fields[0]] = normalized_mac(fields[1])
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        models = {mac: model for item in saved_profiles()
                  if isinstance(mac := item.get("mac"), str) and isinstance(model := item.get("model"), str)}
    except (OSError, ValueError):
        pass
    return tuple(BombillaDescubierta(ip, device_id, macs.get(ip), models.get(macs.get(ip)))
                 for ip, device_id in saludos)


REQUEST_IDS = count(randbelow(2**30) + 1)
COMMAND_DEADLINE = ContextVar("miio_command_deadline", default=None)


class ProtocoloLuz(MiIOProtocol):
    def _create_request(self, command, parameters, extra_parameters=None):
        identifier = next(REQUEST_IDS)
        if identifier >= 2**31:
            raise RespuestaNoValida("miIO request ID exhausted")
        request = super()._create_request(command, parameters, extra_parameters)
        request["id"] = identifier
        return request

    def remaining_timeout(self):
        deadline = COMMAND_DEADLINE.get()
        if deadline is None:
            return self._timeout
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("miIO command deadline")
        return min(self._timeout, remaining)

    def send(self, command, parameters=None, retry_count=3, *, extra_parameters=None):
        for attempt in range(retry_count + 1):
            if not self.lazy_discover or not self._discovered:
                self.send_handshake()
            request = self._create_request(command, parameters, extra_parameters)
            header = {"device_id": self._device_id, "ts": self._device_ts + timedelta(seconds=1)}
            packet = Message.build({"header": {"value": header}, "data": {"value": request},
                                    "checksum": 0}, token=self.token)
            try:
                # Connected UDP filters datagrams from ports and addresses other than the peer.
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
                    channel.settimeout(self.remaining_timeout())
                    channel.connect((self.ip, self.port))
                    channel.send(packet)
                    channel.settimeout(self.remaining_timeout())
                    response = channel.recv(4097)
            except OSError as error:
                self._discovered = False
                if attempt == retry_count:
                    raise DeviceException("No response from the device") from error
                continue
            if not 32 < len(response) <= 4096 or int.from_bytes(response[2:4], "big") != len(response):
                raise RespuestaNoValida("Invalid miIO response size")
            try:
                reply = Message.parse(response, token=self.token)
                payload = reply.data.value
            except ChecksumError as error:
                raise DeviceException("miIO checksum error") from error
            except (ConstructError, PayloadDecodeException, ValueError, OverflowError, RecursionError) as error:
                raise RespuestaNoValida("Invalid miIO response") from error
            if (not isinstance(payload, dict) or type(payload.get("id")) is not int
                    or payload["id"] != request["id"] or reply.header.value.device_id != self._device_id):
                raise RespuestaNoValida("miIO response identity mismatch")
            if reply.header.value.ts < self._device_ts:
                self._discovered = False
                raise RespuestaNoValida("miIO timestamp rollback")
            self._device_ts = reply.header.value.ts
            if "error" in payload:
                if not isinstance(payload["error"], dict):
                    raise DeviceException("Invalid miIO error response")
                try:
                    self._handle_error(payload["error"])
                except RecoverableError as error:
                    if attempt == retry_count:
                        raise DeviceException("Unable to recover failed command") from error
                    continue
            return payload.get("result", payload)
        raise DeviceException("No response from the device")

    def send_handshake(self, *, retry_count=1):
        for _ in range(retry_count + 1):
            replies = _saludos(self.ip, self.remaining_timeout())
            try:
                response = next(replies, None)
            finally:
                replies.close()
            if response:
                message = Message.parse(response[1] + bytes(16))
                device_id = message.header.value.device_id
                expected = getattr(self, "expected_device_id", None)
                if expected is not None and expected != device_id.hex():
                    raise IdentidadIncorrecta("miIO device ID mismatch")
                self._device_id = device_id
                self._device_ts = message.header.value.ts
                self._discovered = True
                return message
        raise BombillaNoEncontrada("Sin conexión con la bombilla.")


class DispositivoLocal:
    timeout = 2
    retry_count = 1

    def __init__(self, ip, token, *, model=None):
        super().__init__(ip, token, model=model)
        self._protocol = ProtocoloLuz(ip, token, timeout=self.timeout)


class LocalDevice(DispositivoLocal, Device):
    _supported_models = [f"yeelink.light.{family}" for family in sorted(RGB_MODELS | WHITE_MODELS)]


class LocalYeelight(DispositivoLocal, Yeelight):
    pass


def powershell(script, timeout=10):
    directory = ctypes.create_unicode_buffer(32768)
    length = ctypes.windll.kernel32.GetSystemDirectoryW(directory, len(directory))
    if not 0 < length < len(directory):
        raise OSError("Windows system directory unavailable")
    executable = Path(directory.value) / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    return subprocess.run(
        [str(executable), "-NoProfile", "-NonInteractive", "-Command", "$ErrorActionPreference='Stop'; " + script],
        capture_output=True, text=True, check=True, timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW,
    ).stdout.strip()


class DataBlob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.c_void_p)]


def dpapi(data, decrypt=False, entropy=None):
    buffer = ctypes.create_string_buffer(data)
    source = DataBlob(len(data), ctypes.cast(buffer, ctypes.c_void_p))
    result = DataBlob()
    scope = None
    if entropy is not None:
        entropy_buffer = ctypes.create_string_buffer(entropy)
        scope = DataBlob(len(entropy), ctypes.cast(entropy_buffer, ctypes.c_void_p))
    library = ctypes.WinDLL("crypt32", use_last_error=True)
    operation = library.CryptUnprotectData if decrypt else library.CryptProtectData
    operation.argtypes = [
        ctypes.POINTER(DataBlob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DataBlob),
    ]
    operation.restype = wintypes.BOOL
    try:
        if not operation(ctypes.byref(source), None, ctypes.byref(scope) if scope is not None else None,
                         None, None, 1, ctypes.byref(result)):
            raise ctypes.WinError(ctypes.get_last_error())
        return ctypes.string_at(result.data, result.size)
    finally:
        ctypes.memset(buffer, 0, len(data))
        if result.data:
            ctypes.memset(result.data, 0, result.size)
            local_free = ctypes.windll.kernel32.LocalFree
            local_free.argtypes = [ctypes.c_void_p]
            local_free.restype = ctypes.c_void_p
            local_free(result.data)


def save_token(token):
    if not valid_token(token):
        raise ValueError("El token debe tener 32 caracteres hexadecimales.")
    encrypted = base64.b64encode(dpapi(token.encode("ascii")))
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(dir=TOKEN_FILE.parent, prefix=".token-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encrypted)
        temporary.replace(TOKEN_FILE)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_token(mac=None):
    profile = load_profile(mac)
    if profile is not None:
        if not isinstance(profile, dict) or not isinstance(profile.get("token"), str):
            raise ValueError("El perfil de la bombilla no contiene un token válido.")
        version = profile.get("version", 1)
        if type(version) is not int or version not in (1, 2):
            raise ValueError("La versión del perfil no es compatible.")
        _, mac, model = profile_address(profile)
        entropy = profile_context(mac, model) if version == 2 else None
        token = dpapi(base64.b64decode(profile["token"], validate=True), decrypt=True, entropy=entropy).decode("ascii")
        if not valid_token(token):
            raise ValueError("El perfil de la bombilla no contiene un token válido.")
        return token
    try:
        encrypted = TOKEN_FILE.read_bytes()
    except FileNotFoundError:
        return ""
    token = dpapi(base64.b64decode(encrypted.strip(), validate=True), decrypt=True).decode("ascii")
    if not valid_token(token):
        raise ValueError("El archivo antiguo no contiene un token válido.")
    return token


def parse_extractor_clipboard(text):
    """Read a single extractor device or a raw token without executing pasted text."""
    invalid = "Copia solo el bloque de una bombilla o un token de 32 caracteres."
    if len(text) > 16384 or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", text):
        raise ValueError(invalid)
    text = text.strip()
    if re.fullmatch(r"[0-9a-fA-F]{32}", text):
        return None, text
    tokens = re.findall(r"(?im)^[ \t]*TOKEN[ \t]*:[ \t]*([^\r\n]*)", text)
    ips = re.findall(r"(?im)^[ \t]*IP[ \t]*:[ \t]*([^\r\n]*)", text)
    if len(tokens) != 1 or not valid_token(tokens[0].strip()) or len(ips) > 1:
        raise ValueError(invalid)
    try:
        address = str(IPv4Address(ips[0].strip())) if ips else None
    except ValueError:
        raise ValueError("La IP copiada no es válida. Copia el token y escribe la IP en Conexión.") from None
    return address, tokens[0].strip()


class Bulb:
    def __init__(self, mac=None):
        self.ip, self.mac, self.model = "", "", MODEL
        self.name = ""
        self.xiaomi_name = ""
        self.room = ""
        self._connection = None
        self.device_id = None
        try:
            self.ip = str(IPv4Address(IP_FILE.read_text(encoding="ascii").strip()))
        except (OSError, ValueError):
            pass
        try:
            profile = load_profile(mac)
            if isinstance(profile, dict):
                self.ip, self.mac, self.model = profile_address(profile)
                device_id = profile.get("device_id")
                if isinstance(device_id, str) and re.fullmatch(r"[0-9a-f]{8}", device_id):
                    self.device_id = device_id
                self.name = profile.get("name", "") if isinstance(profile.get("name"), str) else ""
                self.room = profile.get("room", "") if isinstance(profile.get("room"), str) else ""
                xiaomi_name = profile.get("xiaomi_name")
                self.xiaomi_name = xiaomi_name if isinstance(xiaomi_name, str) else ""
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            if mac:
                raise ValueError("El perfil de la bombilla seleccionada no es válido.") from error

    @property
    def features(self):
        return capabilities(self.model)

    @classmethod
    def identify(cls, ip, token):
        if not valid_token(token):
            raise ValueError("Introduce un token miIO de 32 caracteres.")
        bulb = cls()
        bulb.device_id = None
        bulb.ip = str(IPv4Address(ip))
        info = LocalDevice(bulb.ip, token).info()
        capabilities(info.model)
        bulb.mac, bulb.model = normalized_mac(info.mac_address), info.model
        return bulb

    def verified(self, token, *, recover=True):
        if not valid_token(token):
            raise ValueError("Introduce un token miIO de 32 caracteres.")

        if not self.ip:
            raise BombillaNoEncontrada()

        def connect(ip):
            key = (ip, token, self.model)
            if self._connection is None or self._connection[0] != key:
                device = LocalYeelight(ip, token, model=self.model)
            else:
                device = self._connection[1]
            protocol = getattr(device, "_protocol", None)
            if isinstance(protocol, ProtocoloLuz):
                protocol.expected_device_id = self.device_id
            try:
                try:
                    info = device.info(skip_cache=True)
                except DeviceException as error:
                    if codigo_error_conexion(error) != "authentication":
                        raise
                    info = device.info(skip_cache=True)
            except (BombillaNoEncontrada, IdentidadIncorrecta, RespuestaNoValida):
                raise
            except DeviceException as error:
                if isinstance(protocol, ProtocoloLuz) and len(protocol._device_id) == 4 and codigo_error_conexion(error) in {"timeout", "authentication"}:
                    raise TokenProbable("miIO authentication or response timeout") from error
                raise
            except (AttributeError, TypeError) as error:
                raise RespuestaNoValida("Invalid miIO device info") from error
            try:
                observed_mac = normalized_mac(info.mac_address)
                matches = info.model == self.model and (not self.mac or observed_mac == self.mac)
            except (AttributeError, ValueError):
                matches = False
            if not matches:
                raise IdentidadIncorrecta("La bombilla no coincide con la MAC y el modelo guardados.")
            learned = protocol._device_id.hex() if isinstance(protocol, ProtocoloLuz) else None
            return key, device, learned, observed_mac

        def adopt(ip, verified):
            key, device, learned, self.mac = verified
            previous_ip, previous_id = self.ip, self.device_id
            self.device_id = learned or previous_id
            self._connection = key, device
            self.ip = ip
            if previous_ip != ip or previous_id != self.device_id:
                try:
                    _guardar_ip_recuperada(self, previous_ip)
                except (OSError, ValueError):
                    pass
            return device

        try:
            return adopt(self.ip, connect(self.ip))
        except (OSError, ValueError, DeviceException) as error:
            initial_error = error
        self._connection = None
        if not recover or not self.mac:
            raise initial_error

        tried = {self.ip}
        def try_candidates(candidates, limit):
            match = None
            for candidate in candidates:
                try:
                    ip = str(IPv4Address(candidate))
                except ValueError:
                    continue
                if ip in tried:
                    continue
                if not limit:
                    if match:
                        raise RespuestaNoValida("Hay varias IP posibles. Comprueba la dirección manualmente.")
                    break
                tried.add(ip)
                limit -= 1
                try:
                    verified = connect(ip)
                except (ValueError, DeviceException, OSError):
                    continue
                if match:
                    raise RespuestaNoValida("Hay varias IP posibles. Comprueba la dirección manualmente.")
                match = ip, verified
            return adopt(*match) if match else None

        try:
            discovered = _descubrir_saludos()
        except OSError:
            discovered = ()
        device = try_candidates((ip for ip, identifier in discovered if self.device_id is None or self.device_id == identifier), 3)
        if device is not None:
            return device

        mac = "-".join(self.mac[i:i+2] for i in range(0, 12, 2))
        try:
            neighbors = powershell(
                "Get-NetNeighbor -AddressFamily IPv4 | "
                f"Where-Object LinkLayerAddress -eq '{mac}' | "
                "Select-Object -ExpandProperty IPAddress -Unique"
            )
        except (OSError, subprocess.SubprocessError):
            neighbors = ""
        device = try_candidates(neighbors.splitlines(), 1)
        if device is not None:
            return device
        if isinstance(initial_error, ValueError) or mensaje_error_conexion(initial_error):
            raise initial_error
        raise BombillaNoEncontrada("Sin conexión con la bombilla.") from initial_error

    def relative_target(self, token, action, pasos, *, recover=True):
        device = self.verified(token, recover=recover)
        return self.relative_value(action, pasos, read_status(device, self.features))

    def relative_value(self, action, pasos, status):
        features = self.features
        if action == "brightness":
            value, minimum, maximum = status.brightness, 1, 100
        else:
            value, minimum, maximum = status.color_temp or 4000, features.minimum, features.maximum
        for paso in pasos:
            value = min(maximum, max(minimum, value + paso))
        return value

    def ajustar_relativo(self, token, action, pasos, *, recover=True):
        features = self.features
        if action == "white" and not features.tunable_white:
            return None
        device = self.verified(token, recover=recover)
        status = read_status(device, features)
        value = self.relative_value(action, pasos, status)
        if not status.is_on:
            device.on()
        if action == "brightness":
            device.set_brightness(value)
        else:
            device.set_color_temp(value)
        key = "brightness" if action == "brightness" else "color_temp"
        return confirmar_cambio(read_status(device, features), is_on=True, **{key: value})

    def control(self, token, action, value=None, *, recover=True):
        features = self.features
        color = action == "color" or (action == "scene" and value[0] == "color")
        white = action == "white" or (action == "scene" and value[0] == "white")
        if color and not features.rgb:
            raise UnsupportedControl("Este modelo no admite colores RGB.")
        if action == "white" and not features.tunable_white:
            raise UnsupportedControl("Este modelo tiene blanco fijo.")
        if action in ("flow", "timer") and not features.effects:
            raise UnsupportedControl("El efecto no está validado para este modelo.")
        if white and features.tunable_white:
            level = value[1] if action == "scene" else value
            level = min(features.maximum, max(features.minimum, level))
        if action == "flow" and value:
            preset = "Ciclo de color" if value is True else value
            if not isinstance(preset, str) or preset not in FLOW_PRESETS:
                raise UnsupportedControl("Efecto desconocido.")
            expression = ",".join(str(part) for duration, rgb, brightness in FLOW_PRESETS[preset]
                                  for part in (duration, 1, rgb, brightness))
        device = self.verified(token, recover=recover)
        if action in ("brightness", "white", "color") and not read_status(device, features).is_on:
            device.on()
        expected = {}
        if action == "power":
            (device.on if value else device.off)()
            expected = dict(is_on=bool(value))
        elif action == "brightness":
            device.set_brightness(value)
            expected = dict(is_on=True, brightness=value)
        elif action == "white":
            device.set_color_temp(level)
            expected = dict(is_on=True, color_temp=level)
        elif action == "color":
            device.set_rgb(value)
            expected = dict(is_on=True, rgb=tuple(value))
        elif action == "scene":
            device.on()
            if color:
                device.set_rgb(value[1])
            elif features.tunable_white:
                device.set_color_temp(level)
            device.set_brightness(value[2])
            expected = dict(is_on=True, brightness=value[2])
            if color:
                expected["rgb"] = tuple(value[1])
            elif features.tunable_white:
                expected["color_temp"] = level
        elif action == "flow":
            if value:
                device.on()
                device.send("start_cf", [0, 0, expression])
            else:
                device.send("stop_cf")
            return confirmar_cambio(read_status(device, features, require_effect="flow"),
                                    color_flowing=bool(value))
        elif action == "timer":
            if value:
                device.send("cron_add", [0, value])
            else:
                device.send("cron_del", [0])
            status = read_status(device, features, require_effect="timer")
            # delayoff reports remaining whole minutes and may round down.
            if value:
                if not max(1, value - 1) <= status.delay_off <= value:
                    raise CambioNoAplicado(status)
                return status
            return confirmar_cambio(status, delay_off=0)
        return confirmar_cambio(read_status(device, features), **expected)
