"""Preferences and Windows keyboard shortcuts for the desktop controls."""
import ctypes
import os
import re
from time import monotonic
import winreg
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import QAbstractNativeEventFilter, QEvent, QLockFile, QSettings, Qt
from PySide6.QtWidgets import QApplication, QMenu, QPushButton

from BombillaLocal import STATE_DIR
from Idioma import tr

LEGACY_SHORTCUTS = (
    "Ctrl+Alt+Shift+L", "Ctrl+Alt+Shift+1", "Ctrl+Alt+Shift+2", "Ctrl+Alt+Shift+3",
    "Ctrl+Alt+Num8", "Ctrl+Alt+Num2",
)
DEFAULT_SHORTCUTS = (
    *(f"Ctrl+Alt+F{number}" for number in range(5, 9)),
    "Ctrl+Alt+8", "Ctrl+Alt+9", "Ctrl+Alt+F9", "Ctrl+Alt+F10",
)
AJUSTES_RELATIVOS = (
    ("Subir brillo", "brightness", 1),
    ("Bajar brillo", "brightness", -1),
    ("Subir temperatura", "white", 1),
    ("Bajar temperatura", "white", -1),
)
PASOS_BRILLO = (5, 10, 15)
PASO_TEMPERATURA = 250


def desktop_lock():
    directory = Path(os.environ["LOCALAPPDATA"]) / "Luz"
    directory.mkdir(parents=True, exist_ok=True)
    return QLockFile(str(directory / "escritorio.lock"))


def preferences():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return QSettings(str(STATE_DIR / "preferencias.ini"), QSettings.Format.IniFormat)


def shortcut_parts(sequence):
    fields = [part.strip().upper() for part in sequence.split("+")]
    flags = {"ALT": 1, "CTRL": 2, "SHIFT": 4}
    key = fields[-1]
    if (len(fields) < 2 or len(set(fields[:-1])) != len(fields)-1
            or not all(item in flags for item in fields[:-1])
            or not re.fullmatch(r"[A-Z0-9]|NUM[0-9]|F(?:[1-9]|1[01])", key)
            or not set(fields[:-1]).intersection({"ALT","CTRL"})):
        raise ValueError("Usa Ctrl o Alt con una letra, número o F1–F11")
    if key.startswith("NUM"):
        virtual_key = 0x60 + int(key[-1])
    elif len(key) > 1:
        virtual_key = 0x6F + int(key[1:])
    else:
        virtual_key = ord(key)
    return 0x4000 | sum(flags[item] for item in fields[:-1]), virtual_key


def migrate_shortcuts(saved, *, schema=0):
    if schema >= 2:
        return saved
    migrate_temperature = saved[6:] == ("Ctrl+Alt+Num6", "Ctrl+Alt+Num4")
    old_defaults = (LEGACY_SHORTCUTS if schema < 1 else (None,) * 6)
    if migrate_temperature:
        old_defaults += saved[6:]
    occupied = set()
    for index, key in enumerate(saved):
        old = old_defaults[index] if index < len(old_defaults) else None
        if key and key != old:
            try:
                occupied.add(shortcut_parts(key))
            except ValueError:
                continue
    return tuple(new if key == old and shortcut_parts(new) not in occupied else key
                 for key, old, new in zip(saved, old_defaults, DEFAULT_SHORTCUTS)) + saved[len(old_defaults):]


class ShortcutRecorder(QPushButton):
    def __init__(self, sequence):
        super().__init__()
        self.sequence = sequence
        self.recording = False
        self.setMinimumWidth(190)
        self.setToolTip(tr("Clic para grabar. Clic derecho para desactivar."))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_options)
        self.clicked.connect(self.start_recording)
        self.finish_recording()

    def start_recording(self):
        self.recording = True
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.setText(tr("Pulsa la combinación…"))

    def finish_recording(self):
        self.recording = False
        self.setText(self.sequence or tr("Sin atajo"))

    def show_options(self, position):
        menu = QMenu(self)
        try:
            clear = menu.addAction(tr("Desactivar atajo"))
            clear.setEnabled(bool(self.sequence))
            if menu.exec(self.mapToGlobal(position)) is clear:
                self.sequence = ""
                self.finish_recording()
        finally:
            menu.deleteLater()

    def event(self, event):
        if self.recording and event.type() == QEvent.Type.ShortcutOverride:
            event.accept()
            return True
        return super().event(event)

    def focusOutEvent(self, event):
        self.finish_recording()
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if not self.recording:
            return super().keyPressEvent(event)
        event.accept()
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.finish_recording()
            return
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift, Qt.Key.Key_Meta):
            return
        mods = event.modifiers()
        function_key = Qt.Key.Key_F1 <= key <= Qt.Key.Key_F11
        if (mods & Qt.KeyboardModifier.MetaModifier or
                not (function_key or ord("A") <= key <= ord("Z") or ord("0") <= key <= ord("9"))):
            self.setText(tr("Usa Ctrl o Alt con una letra, número o F1–F11"))
            return
        parts = [name for name, flag in (
            ("Ctrl", Qt.KeyboardModifier.ControlModifier),
            ("Alt", Qt.KeyboardModifier.AltModifier),
            ("Shift", Qt.KeyboardModifier.ShiftModifier),
        ) if mods & flag]
        if function_key:
            key_name = f"F{key - Qt.Key.Key_F1 + 1}"
        elif ord("0") <= key <= ord("9") and mods & Qt.KeyboardModifier.KeypadModifier:
            key_name = f"Num{chr(key)}"
        else:
            key_name = chr(key)
        sequence = "+".join([*parts, key_name])
        try:
            shortcut_parts(sequence)
        except ValueError:
            self.setText(tr("Usa Ctrl o Alt con una letra, número o F1–F11"))
            return
        self.sequence = sequence
        self.finish_recording()


def altgr_conflict(sequence):
    try:
        modifiers, key = shortcut_parts(sequence)
    except ValueError:
        return False
    if modifiers & 7 != 3 or not 0x30 <= key <= 0x5A:
        return False
    user = ctypes.windll.user32
    user.GetKeyboardLayout.restype = wintypes.HKL
    layout = user.GetKeyboardLayout(0)
    state = (ctypes.c_ubyte * 256)()
    for code in (0x11, 0x12, 0xA2, 0xA5):
        state[code] = 0x80
    output = ctypes.create_unicode_buffer(8)
    scan = user.MapVirtualKeyExW(key, 0, wintypes.HKL(layout))
    return user.ToUnicodeEx(key, scan, state, output, len(output), 4, wintypes.HKL(layout)) != 0


class GlobalShortcuts(QAbstractNativeEventFilter):
    def __init__(self, callbacks, repeat_from=None):
        super().__init__()
        self.callbacks = callbacks
        self.repeat_from = repeat_from
        self._configured = False
        self.registered = {}
        self.slots = {}
        self.statuses = {}
        self.last_activations = {}
        self.paused = False
        user = ctypes.WinDLL("user32", use_last_error=True)
        self.register = user.RegisterHotKey
        self.register.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        self.unregister = user.UnregisterHotKey
        self.unregister.argtypes = [wintypes.HWND, ctypes.c_int]
        self.registration_error = ctypes.get_last_error

    def available(self, sequence, others):
        modifiers, key = shortcut_parts(sequence)
        if any(shortcut_parts(other) == (modifiers, key) for other in others if other):
            return False
        if any(shortcut_parts(active) == (modifiers, key) for active in self.registered.values()):
            return True
        identifier = 0x5FFF
        if not self.register(None, identifier, modifiers, key):
            return False
        self.unregister(None, identifier)
        return True

    def _native_modifiers(self, modifiers, index):
        return modifiers & ~0x4000 if self.repeat_from is not None and index >= self.repeat_from else modifiers

    def configure(self, sequences):
        # Only startup can keep a partial set of registrations.
        startup = not self._configured
        self._configured = True
        failures, next_keys, next_slots = [], {}, {}
        self.statuses = {}
        old_chords = {shortcut_parts(sequence): identifier for identifier, sequence in self.registered.items()}
        seen, added, mode_changes, released, reconfigured = set(), set(), {}, {}, set()

        def reject(index, sequence, code):
            self.statuses[index] = ("occupied" if code == 1409 else "invalid", code)
            failures.append(sequence)

        for index, sequence in enumerate(sequences):
            if not sequence:
                self.statuses[index] = ("unassigned", 0)
                continue
            try:
                chord = shortcut_parts(sequence)
            except ValueError:
                reject(index, sequence, 87)
                continue
            if chord in seen:
                reject(index, sequence, 1409)
                continue
            seen.add(chord)
            modifiers, key = chord
            native = self._native_modifiers(modifiers, index)
            identifier = old_chords.get(chord)
            if identifier is not None:
                previous = self._native_modifiers(modifiers, self.slots[identifier])
                if native != previous:
                    mode_changes[identifier] = (previous, native, key)
            else:
                identifier = 0x4C00 + index
                while identifier in self.registered or identifier in next_keys:
                    identifier += len(self.callbacks)
                ctypes.set_last_error(0)
                if not self.register(None, identifier, native, key):
                    reject(index, sequence, self.registration_error())
                    continue
                added.add(identifier)
            next_keys[identifier], next_slots[identifier] = sequence, index
            self.statuses[index] = ("registered", 0)

        # Keep old registrations until all unrelated new chords have been acquired.
        if not failures:
            for identifier, (previous, native, key) in mode_changes.items():
                index = next_slots[identifier]
                ctypes.set_last_error(0)
                if not self.unregister(None, identifier):
                    reject(index, next_keys[identifier], self.registration_error())
                    break
                released[identifier] = (previous, key)
                ctypes.set_last_error(0)
                if not self.register(None, identifier, native, key):
                    reject(index, next_keys[identifier], self.registration_error())
                    break
                reconfigured.add(identifier)

        if failures and not startup:
            for identifier in added:
                self.unregister(None, identifier)
            for identifier, index in next_slots.items():
                if self.statuses[index][0] == "registered" and self.slots.get(identifier) != index:
                    self.statuses[index] = ("unchanged", 0)
            for identifier, (previous, key) in released.items():
                if identifier in reconfigured:
                    self.unregister(None, identifier)
                ctypes.set_last_error(0)
                if not self.register(None, identifier, previous, key):
                    index = self.slots.pop(identifier)
                    del self.registered[identifier]
                    code = self.registration_error()
                    self.statuses[index] = ("occupied" if code == 1409 else "invalid", code)
            return failures
        for identifier in self.registered.keys() - next_keys.keys():
            self.unregister(None, identifier)
        self.registered, self.slots = next_keys, next_slots
        return failures

    def clear(self):
        for identifier in self.registered:
            self.unregister(None, identifier)
        self.registered.clear()
        self.slots.clear()

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) in (b"windows_dispatcher_MSG", b"windows_generic_MSG"):
            event = wintypes.MSG.from_address(int(message))
            if event.message == 0x0312 and event.wParam in self.registered:  # WM_HOTKEY
                recorder = QApplication.focusWidget()
                if self.paused and isinstance(recorder, ShortcutRecorder) and recorder.recording:
                    recorder.sequence = self.registered[event.wParam]
                    recorder.finish_recording()
                else:
                    index = self.slots[event.wParam]
                    self.last_activations[index] = monotonic()
                    self.callbacks[index]()
                return True, 0
        return False, 0

CLAVE_INICIO = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALOR_INICIO = "Luz"


def inicio_windows():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE_INICIO) as clave:
            comando, tipo = winreg.QueryValueEx(clave, VALOR_INICIO)
    except FileNotFoundError:
        return ""
    return comando if tipo == winreg.REG_SZ and isinstance(comando, str) else ""


def guardar_inicio_windows(comando):
    if len(comando) > 260:
        raise OSError("Startup command exceeds the Windows limit")
    if comando:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, CLAVE_INICIO, 0, winreg.KEY_SET_VALUE) as clave:
            winreg.SetValueEx(clave, VALOR_INICIO, 0, winreg.REG_SZ, comando)
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE_INICIO, 0, winreg.KEY_SET_VALUE) as clave:
                winreg.DeleteValue(clave, VALOR_INICIO)
        except FileNotFoundError:
            pass


def comando_inicio_windows(ejecutable):
    return f'"{Path(ejecutable).resolve()}" --oculto'


def actualizar_inicio_windows(ejecutable):
    actual = inicio_windows()
    propio = re.fullmatch(r'"([^"]+)" --oculto', actual)
    nuevo = comando_inicio_windows(ejecutable)
    if propio and actual != nuevo and not Path(propio[1]).is_file():
        guardar_inicio_windows(nuevo)
