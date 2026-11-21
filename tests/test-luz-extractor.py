"""Verify the vendored extractor without importing it or opening the cloud."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

root = Path("tools/xiaomi-tokens")
module = ast.parse((root / "token_extractor.py").read_text(encoding="utf-8"))
server = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "start_image_server")
server_factory = Mock()
scope = {
    "HTTPServer": server_factory, "BaseHTTPRequestHandler": object,
    "_LOGGER": Mock(), "socket": SimpleNamespace(gethostname=lambda: "synthetic"),
    "threading": SimpleNamespace(Thread=Mock()), "args": SimpleNamespace(host="0.0.0.0"),
}
exec(compile(ast.Module(body=[server], type_ignores=[]), str(root), "exec"), scope)
scope["start_image_server"](b"synthetic")
assert server_factory.call_args.args[0] == ("127.0.0.1", 31415)
for launcher in (root / "run.sh", root / "run_docker.sh"):
    script = launcher.read_text(encoding="utf-8")
    assert "/releases/latest" not in script
    assert "curl " not in script
print("Extractor: QR local y lanzadores sin descarga automática")

# A failed first QR poll must report failure without reading an unbound response.
import requests
qr = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "QrCodeXiaomiCloudConnector")
poll = next(node for node in qr.body if isinstance(node, ast.FunctionDef) and node.name == "login_step_3")
scope = {"requests": requests, "_LOGGER": Mock(), "time": SimpleNamespace(time=Mock(side_effect=[0, 11]), monotonic=Mock(side_effect=[0, 0, 11]))}
exec(compile(ast.Module(body=[poll], type_ignores=[]), str(root), "exec"), scope)
client = SimpleNamespace(_long_polling_url="https://example.invalid", _timeout=10, _session=SimpleNamespace(get=Mock(side_effect=requests.exceptions.Timeout)))
assert scope["login_step_3"](client) is False
client._session.get = Mock(side_effect=requests.exceptions.ConnectionError)
scope["time"] = SimpleNamespace(time=lambda: 0, monotonic=lambda: 0)
assert scope["login_step_3"](client) is False
client._session.get = Mock(return_value=SimpleNamespace(status_code=500))
assert scope["login_step_3"](client) is False
client._session.get.assert_called_once()

# STS can set the service cookie on a redirect instead of the final response.
finish = next(node for node in qr.body if isinstance(node, ast.FunctionDef) and node.name == "login_step_4")
scope = {"_LOGGER": Mock()}
exec(compile(ast.Module(body=[finish], type_ignores=[]), str(root), "exec"), scope)
client = SimpleNamespace(_location="https://sts.api.io.mi.com/sts", _session=Mock())
client._session.get.return_value.status_code = 200
client._session.get.return_value.cookies.get.return_value = None
client._session.cookies.get.return_value = "synthetic-service-cookie"
assert scope["login_step_4"](client) is True and client._serviceToken == "synthetic-service-cookie"
client._session.cookies.get.return_value = None
assert scope["login_step_4"](client) is False

for node in ast.walk(module):
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("get", "post") and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "_session"):
        assert any(key.arg == "timeout" for key in node.keywords), f"Unbounded cloud request at line {node.lineno}"
