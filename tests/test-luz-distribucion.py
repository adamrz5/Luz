import ctypes
import os
import runpy
import shutil
import subprocess
import sys
import time
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


class DistributionTests(unittest.TestCase):
    def run_packaged_smoke(self, windows):
        user32 = Mock()
        process = Mock(pid=42)
        process.poll.return_value = None

        def wait(timeout):
            if timeout == 1:
                raise subprocess.TimeoutExpired("Luz.exe", timeout)
            return 0

        process.wait.side_effect = wait

        def enumerate_windows(callback, parameter):
            for handle in windows:
                if not callback(handle, parameter):
                    break
            return True

        def owner(hwnd, pointer):
            pointer._obj.value = windows[hwnd][0]
            return 1

        def title(hwnd, buffer, _length):
            buffer.value = windows[hwnd][2]
            return len(buffer.value)

        def launch(_args, *, env):
            self.assertEqual(env["QT_QPA_PLATFORM"], "windows")
            (Path(env["LUZ_STATE_DIR"]) / "Luz.lock").touch()
            return process

        user32.EnumWindows.side_effect = enumerate_windows
        user32.GetWindowThreadProcessId.side_effect = owner
        user32.IsWindowVisible.side_effect = lambda hwnd: windows[hwnd][1]
        user32.GetWindowTextW.side_effect = title
        with (
            patch.object(ctypes.windll, "user32", user32),
            patch.object(subprocess, "Popen", side_effect=launch),
            patch.object(sys, "argv", ["smoke", sys.executable]),
            patch.object(time, "monotonic", side_effect=[0, 0, 16]),
            patch.object(time, "sleep"),
        ):
            try:
                runpy.run_path(ROOT / "tests/comprobar-luz.py", run_name="__main__")
            finally:
                process.terminate.assert_called_once()

    def test_lock_foreign_window_hidden_window_and_wrong_title_are_not_ready(self):
        with self.assertRaisesRegex(RuntimeError, "ventana"):
            self.run_packaged_smoke({
                101: (41, True, "Luz"),
                102: (42, False, "Luz"),
                103: (42, True, "Other"),
            })

    def test_visible_luz_window_owned_by_the_child_is_ready(self):
        self.run_packaged_smoke({101: (42, True, "Luz")})

    def test_assertions_stay_enabled_in_the_child(self):
        runner = runpy.run_path(ROOT / "tests/ejecutar-seguras.py")
        main = runner["main"]
        run = subprocess.run

        def run_test(*args, **kwargs):
            result = run(*args, **kwargs, capture_output=True)
            self.assertIn(b"AssertionError: distribution regression", result.stderr)
            return result

        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "tests").mkdir()
            (root / "tests/test-luz-aislamiento.py").write_text(
                "assert False, 'distribution regression'\n", encoding="utf-8"
            )
            with (
                patch.dict(main.__globals__, {"ROOT": root}),
                patch.object(sys, "argv", ["runner", "aislamiento"]),
                patch.dict(os.environ, {"PYTHONOPTIMIZE": "1"}),
                patch.object(subprocess, "run", side_effect=run_test),
                redirect_stdout(StringIO()),
            ):
                self.assertTrue(main(), "The failing assert must fail the safe test run")

    def test_powershell_guards_reject_existing_installation_and_mismatched_version(self):
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        self.assertIsNotNone(powershell, "PowerShell is required for the Windows distribution tests")
        with TemporaryDirectory() as folder:
            result = subprocess.run(
                [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                 "-File", str(ROOT / "tests/comprobar-distribucion.ps1"), "-Scratch", folder],
                capture_output=True, timeout=15,
            )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
