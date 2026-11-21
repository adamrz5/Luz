"""Run the local test battery with a fresh data folder per test."""
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]

# We deliberately exclude tests that change a physical bulb or launch the
# installed application. Network access inside the Python tests is loopback only.
SUITES = (
    "aislamiento", "miio-local", "ajuste-relativo", "atajos", "busqueda", "bienvenida", "xiaomi-qr", "xiaomi-qr-gui",
    "diagnostico", "diseno", "accesibilidad", "escritorio", "escenas", "inicio", "extractor",
    "modelos", "preferencias", "red", "senuelo", "fuzz", "replay", "recuperacion", "grupos", "atajos-estado",
    "distribucion",
)
BOOTSTRAP = """
import ipaddress, runpy, sys

def local_only(event, args):
    if event in ('socket.connect', 'socket.sendto', 'socket.bind'):
        address = args[1]
        if not isinstance(address, tuple) or not ipaddress.ip_address(address[0]).is_loopback:
            raise AssertionError('Non-loopback socket blocked by the test runner')

sys.addaudithook(local_only)
runpy.run_path(sys.argv[1], run_name='__main__')
"""


def main():
    failures = []
    selected = sys.argv[1:] or SUITES
    for suite in selected:
        if suite not in SUITES:
            raise SystemExit(f"Unknown safe suite: {suite}")
        test = ROOT / "tests" / f"test-luz-{suite}.py"
        with TemporaryDirectory(prefix="luz-tests-") as state:
            env = os.environ | {"LUZ_STATE_DIR": state, "QT_QPA_PLATFORM": "offscreen",
                                "PYTHONIOENCODING": "utf-8"}
            env.pop("PYTHONOPTIMIZE", None)
            try:
                result = subprocess.run([sys.executable, "-B", "-c", BOOTSTRAP, str(test)],
                                        cwd=ROOT, env=env, timeout=25)
                if result.returncode:
                    failures.append(suite)
            except subprocess.TimeoutExpired:
                failures.append(suite)
    print(f"Safe suites: {len(selected) - len(failures)}/{len(selected)}")
    if failures:
        print("Failed:", ", ".join(failures))
    return bool(failures)


if __name__ == "__main__":
    sys.exit(main())
