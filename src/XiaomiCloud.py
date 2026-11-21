"""On-demand adapter for the MIT-licensed bundled Xiaomi token extractor."""
import importlib.util
import time
from dataclasses import dataclass, field
from ipaddress import IPv4Address
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

from BombillaLocal import capabilities, normalized_mac, valid_token

REGIONS = ("de", "cn", "us", "ru", "tw", "sg", "in", "i2")
MAX_RESPONSE = 2 * 1024 * 1024


class CloudError(ValueError):
    pass


class Cancelled(Exception):
    pass


def check_url(url):
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.port not in (None, 443) or parsed.username or parsed.password
            or not any(host == domain or host.endswith("." + domain) for domain in ("xiaomi.com", "mi.com"))):
        raise CloudError("No se pudo completar la conexión segura con Xiaomi.")


class CloudSession(requests.Session):
    def __init__(self, cancelled):
        super().__init__()
        self.cancelled = cancelled

    def resolve_redirects(self, *args, **kwargs):
        # Requests otherwise reads redirect bodies while computing Response.next.
        return iter(())

    def request(self, method, url, **kwargs):
        for _ in range(4):
            if self.cancelled.is_set():
                raise Cancelled()
            check_url(url)
            kwargs.update(timeout=(3, 3), verify=True, stream=True, allow_redirects=False)
            response = super().request(method, url, **kwargs)
            try:
                if response.is_redirect:
                    if method.upper() != "GET":
                        raise CloudError("No se pudo completar la conexión segura con Xiaomi.")
                    url = urljoin(url, response.headers.get("Location", ""))
                    kwargs.pop("params", None)
                    continue
                response.raise_for_status()
                contents = bytearray()
                for part in response.iter_content(65536):
                    if self.cancelled.is_set():
                        raise Cancelled()
                    if len(contents) + len(part) > MAX_RESPONSE:
                        raise CloudError("La respuesta de Xiaomi no es válida.")
                    contents.extend(part)
                response._content = bytes(contents)
                response._content_consumed = True
                return response
            finally:
                response.close()
        raise CloudError("No se pudo completar la conexión segura con Xiaomi.")


@dataclass(frozen=True)
class CloudBulb:
    name: str
    ip: str
    model: str
    mac: str
    token: str = field(repr=False)


def compatible_devices(devices):
    result, seen = [], set()
    if not isinstance(devices, list):
        return ()
    for device in devices[:512]:
        if not isinstance(device, dict):
            continue
        try:
            model, token = device.get("model"), device.get("token")
            capabilities(model)
            ip = IPv4Address(device.get("localip"))
            mac = normalized_mac(device.get("mac"))
            if not valid_token(token) or ip.is_unspecified or ip.is_multicast or ip.is_loopback or ip.is_global:
                continue
            if mac in seen:
                continue
            name = device.get("name")
            name = " ".join(name.split())[:128] if isinstance(name, str) else model
            result.append(CloudBulb(name or model, str(ip), model, mac, token))
            seen.add(mac)
        except (TypeError, ValueError):
            continue
    return tuple(result)


def connector():
    try:
        import token_extractor
    except ModuleNotFoundError as error:
        if error.name != "token_extractor":
            raise
        path = Path(__file__).resolve().parents[1] / "tools/xiaomi-tokens/token_extractor.py"
        spec = importlib.util.spec_from_file_location("token_extractor", path)
        token_extractor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(token_extractor)
    token_extractor._LOGGER.disabled = True
    return token_extractor.QrCodeXiaomiCloudConnector()


def scan(events, cancelled, region, *, connector_factory=None):
    """No widget access, saved account sessions or local web servers."""
    client = None
    try:
        if region not in REGIONS:
            raise CloudError("Elige la misma región que utilizas en Xiaomi Home.")
        if cancelled.is_set():
            return
        client = (connector_factory or connector)()
        if connector_factory is None:
            client._session.close()
            client._session = CloudSession(cancelled)
        if not client.login_step_1():
            raise CloudError("No se pudo generar el QR de Xiaomi. Inténtalo de nuevo.")
        response = client._session.get(client._qr_image_url)
        events.put(("qr", response.content))
        lifetime = client._timeout
        if not isinstance(lifetime, (int, float)) or lifetime <= 0:
            raise CloudError("La respuesta de Xiaomi no es válida.")
        # Some Xiaomi endpoints report expiry in milliseconds.
        lifetime = lifetime / 1000 if lifetime > 3600 else lifetime
        deadline = time.monotonic() + min(lifetime, 300)
        while time.monotonic() < deadline:
            if cancelled.is_set():
                raise Cancelled()
            try:
                response = client._session.get(client._long_polling_url)
            except requests.Timeout:
                continue
            data = client.to_json(response.text)
            if not isinstance(data, dict) or not all(data.get(key) for key in ("userId", "ssecurity", "location")):
                raise CloudError("El QR ha caducado o no se ha autorizado. Genera otro QR.")
            client.userId, client._ssecurity = data["userId"], data["ssecurity"]
            client._cUserId, client._pass_token = data.get("cUserId"), data.get("passToken")
            client._location = data["location"]
            break
        else:
            raise CloudError("El QR ha caducado o no se ha autorizado. Genera otro QR.")
        if cancelled.is_set():
            raise Cancelled()
        if not client.login_step_4():
            raise CloudError("Xiaomi no autorizó la sesión. Genera otro QR.")
        events.put(("scanning", region))
        homes = client.get_homes(region)
        homes = homes.get("result", {}).get("homelist", []) if isinstance(homes, dict) else []
        shared = client.get_dev_cnt(region)
        shared = shared.get("result", {}).get("share", {}).get("share_family", []) if isinstance(shared, dict) else []
        targets = [(home["id"], client.userId) for home in homes if isinstance(home, dict) and "id" in home]
        targets += [(home["home_id"], home["home_owner"]) for home in shared
                    if isinstance(home, dict) and "home_id" in home and "home_owner" in home]
        devices = {}
        for home_id, owner in targets[:64]:
            if cancelled.is_set():
                raise Cancelled()
            reply = client.get_devices(region, home_id, owner)
            entries = reply.get("result", {}).get("device_info", []) if isinstance(reply, dict) else []
            if isinstance(entries, list):
                for bulb in compatible_devices(entries):
                    devices.setdefault(bulb.mac, bulb)
                    if len(devices) >= 256:
                        break
            if len(devices) >= 256:
                break
        if not cancelled.is_set():
            events.put(("devices", tuple(devices.values())))
    except Cancelled:
        pass
    except CloudError as error:
        if not cancelled.is_set():
            events.put(("error", str(error)))
    except Exception:
        if not cancelled.is_set():
            events.put(("error", "No se pudo conectar con Xiaomi. Comprueba Internet y vuelve a intentarlo."))
    finally:
        if client is not None:
            client._session.cookies.clear()
            client._session.close()
            client.userId = client._ssecurity = client._serviceToken = client._pass_token = client._cUserId = None
            client._location = None
            client._qr_image_url = client._long_polling_url = client._login_url = None
