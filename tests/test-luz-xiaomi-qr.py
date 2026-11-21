"""Cloud QR flow is tested with synthetic responses, never an account."""
import base64
import json
import logging
import runpy
import sys
from queue import Queue
from threading import Event
from unittest.mock import Mock, patch

from requests import Response
from requests.adapters import BaseAdapter
from requests.structures import CaseInsensitiveDict

sys.path.insert(0, "src")
from XiaomiCloud import CloudError, CloudSession, Cancelled, compatible_devices, scan

token = "ab" * 16
device = dict(name="Demo", localip="192.0.2.20", token=token, model="yeelink.light.color5", mac="02:00:00:00:00:01")
bulbs = compatible_devices([device, device, dict(device, model="roborock.vacuum.a1"), dict(device, token="invalid"), dict(device, localip="0.0.0.0")])
assert len(bulbs) == 1 and bulbs[0].ip == "192.0.2.20"
assert token not in repr(bulbs[0])

cancel = Event()
session = CloudSession(cancel)
with patch("requests.Session.request") as send:
    for url in ("http://account.xiaomi.com/", "https://evil.invalid/", "https://account.xiaomi.com:8443/", "https://account.xiaomi.com.evil.invalid/"):
        try:
            session.get(url)
        except CloudError:
            pass
        else:
            raise AssertionError("Untrusted cloud URL accepted")
    send.assert_not_called()
    cancel.set()
    try:
        session.get("https://account.xiaomi.com/")
    except Cancelled:
        pass
    else:
        raise AssertionError("A cancelled request was sent")
    send.assert_not_called()
cancel.clear()
response = Mock(status_code=200, is_redirect=False, headers={})
response.iter_content.return_value = [b"ok"]
with patch("requests.Session.request", return_value=response) as send:
    result = session.get("https://account.xiaomi.com/", timeout=30)
    assert result._content == b"ok"
    assert send.call_args.kwargs["timeout"] == (3, 3)
    assert send.call_args.kwargs["verify"] is True
    response.close.assert_called_once()
response = Mock(status_code=302, is_redirect=True, headers={"Location": "https://evil.invalid/"})
with patch("requests.Session.request", return_value=response) as send:
    try:
        session.get("https://account.xiaomi.com/")
    except CloudError:
        pass
    else:
        raise AssertionError("Untrusted redirect accepted")
    assert send.call_count == 1
response = Mock(status_code=200, is_redirect=False, headers={})
response.iter_content.return_value = [b"x" * (2 * 1024 * 1024 + 1)]
with patch("requests.Session.request", return_value=response):
    try:
        session.get("https://account.xiaomi.com/")
    except CloudError:
        pass
    else:
        raise AssertionError("An oversized cloud response was accepted")
    response.close.assert_called_once()

# Keep Requests' real send path while replacing only the HTTP transport.
class SyntheticAdapter(BaseAdapter):
    def __init__(self, responses):
        self.responses = iter(responses)
        self.urls = []

    def send(self, request, **kwargs):
        self.urls.append(request.url)
        assert kwargs["verify"] and kwargs["stream"]
        reply = next(self.responses)
        reply.url, reply.request = request.url, request
        return reply

    def close(self):
        pass


def synthetic_response(status, headers=None):
    reply = Response()
    reply.status_code = status
    reply.headers = CaseInsensitiveDict(headers or {})
    reply.raw = Mock(_original_response=None)
    return reply


for destination in ("/ok", "https://evil.invalid/"):
    redirect = synthetic_response(302, {"Location": destination})
    redirect.raw.stream.side_effect = AssertionError("Redirect body was read")
    ok = synthetic_response(200)
    ok.raw.stream.return_value = iter((b"ok",))
    adapter = SyntheticAdapter((redirect, ok))
    with CloudSession(cancel) as real_session:
        real_session.mount("https://", adapter)
        try:
            result = real_session.get("https://account.xiaomi.com/start", params={"p": "1"})
        except CloudError:
            assert destination == "https://evil.invalid/" and len(adapter.urls) == 1
        else:
            assert destination == "/ok" and result.content == b"ok"
            assert adapter.urls == ["https://account.xiaomi.com/start?p=1", "https://account.xiaomi.com/ok"]
    redirect.raw.stream.assert_not_called()
    redirect.raw.close.assert_called_once()

image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aRZkAAAAASUVORK5CYII=")
client = Mock()
client._qr_image_url = "https://account.xiaomi.com/qr"
client._long_polling_url = "https://account.xiaomi.com/poll"
client._timeout = 2
client.login_step_1.return_value = True
client.login_step_4.return_value = True
client.to_json.side_effect = json.loads
client._session.get.side_effect = [
    Mock(content=image),
    Mock(text=json.dumps(dict(userId="synthetic", ssecurity="secret-session", cUserId="test", passToken="test", location="https://sts.api.io.mi.com/sts"))),
]
client.get_homes.return_value = {"result": {"homelist": [{"id": 12}]}}
client.get_dev_cnt.return_value = {"result": {"share": {"share_family": []}}}
client.get_devices.return_value = {"result": {"device_info": [device]}}
events = Queue()
scan(events, cancel, "de", connector_factory=lambda: client)
messages = []
while not events.empty():
    messages.append(events.get_nowait())
assert messages[0] == ("qr", image)
assert messages[-1][0] == "devices" and messages[-1][1][0].token == token
client._session.close.assert_called_once()
client._session.cookies.clear.assert_called_once()
assert client._ssecurity is None and client._serviceToken is None and client.userId is None
events = Queue()
cancel.set()
factory = Mock()
scan(events, cancel, "de", connector_factory=factory)
factory.assert_not_called()
assert events.empty()
cancel.clear()
events = Queue()
client = Mock()
client.login_step_1.side_effect = RuntimeError("secret-session-value")
scan(events, cancel, "de", connector_factory=lambda: client)
event, message = events.get_nowait()
assert event == "error" and "secret-session-value" not in message
client._session.close.assert_called_once()

# Importing the reused CLI must not parse Luz arguments or replace logging.
logger_class = logging.getLoggerClass()
with patch.object(sys, "argv", ["Luz.exe", "--oculto"]), patch("colorama.init") as init:
    module = runpy.run_path("tools/xiaomi-tokens/token_extractor.py")
assert logging.getLoggerClass() is logger_class
init.assert_not_called()
assert not module["args"].non_interactive
print("QR Xiaomi: destinos HTTPS, cancelación, filtrado, sesión temporal e importación sin efectos comprobados")
