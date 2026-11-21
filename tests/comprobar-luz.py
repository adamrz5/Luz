"""Smoke-test the packaged app with an isolated state and a native window."""
import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path
from tempfile import TemporaryDirectory


def has_main_window(pid):
    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = (callback_type, wintypes.LPARAM)
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    owner = wintypes.DWORD()
    title = ctypes.create_unicode_buffer(64)
    found = False

    @callback_type
    def visit(hwnd, _):
        nonlocal found
        if user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner)) and owner.value == pid:
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextW(hwnd, title, len(title))
                found = length == 3 and title.value == "Luz"
        return not found

    user32.EnumWindows(visit, 0)
    return found


def main():
    executable = Path(sys.argv[1] if len(sys.argv) > 1 else "build/ensayo/app/Luz.exe").resolve(strict=True)
    with TemporaryDirectory(prefix="luz-smoke-") as state:
        env = os.environ | {"LUZ_STATE_DIR": state, "QT_QPA_PLATFORM": "windows"}
        process = subprocess.Popen([str(executable), "--sin-bandeja"], env=env)
        try:
            lock = Path(state) / "Luz.lock"
            deadline = time.monotonic() + 15
            while process.poll() is None and time.monotonic() < deadline:
                if lock.is_file() and has_main_window(process.pid):
                    break
                time.sleep(.05)
            else:
                raise RuntimeError("Luz no abrió su ventana en el directorio temporal")
            try:
                status = process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                print("Luz abrió su ventana con el directorio temporal")
            else:
                raise RuntimeError(f"Luz terminó tras abrir su ventana: {status}")
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=6)


if __name__ == "__main__":
    main()
