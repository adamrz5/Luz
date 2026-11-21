import ctypes
import sys
from ctypes import wintypes
from unittest.mock import Mock, patch

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu

sys.path.insert(0, "src")
from Escritorio import DEFAULT_SHORTCUTS, LEGACY_SHORTCUTS, GlobalShortcuts, ShortcutRecorder, migrate_shortcuts, shortcut_parts
from Idioma import set_language, tr

app = QApplication([])
recorder = ShortcutRecorder("Ctrl+Alt+L")
callback = Mock()
hotkeys = GlobalShortcuts((callback,))
hotkeys.register = Mock(return_value=True)
hotkeys.unregister = Mock()
assert hotkeys.configure(("Ctrl+Alt+Shift+Z",)) == []
message = wintypes.MSG(message=0x0312, wParam=0x4C00)
with patch.object(QApplication, "focusWidget", return_value=recorder):
    hotkeys.paused = True
    recorder.start_recording()
    assert hotkeys.nativeEventFilter(b"windows_dispatcher_MSG", ctypes.addressof(message)) == (True, 0)
    assert recorder.sequence == "Ctrl+Alt+Shift+Z" and not recorder.recording
    callback.assert_not_called()
    # Preferences may be open while the user controls the light.
    hotkeys.nativeEventFilter(b"windows_dispatcher_MSG", ctypes.addressof(message))
    callback.assert_called_once()
    callback.reset_mock()
    hotkeys.paused = False
    hotkeys.nativeEventFilter(b"windows_dispatcher_MSG", ctypes.addressof(message))
    callback.assert_called_once()

recorder.start_recording()
QTest.keyClick(recorder, Qt.Key.Key_1, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.KeypadModifier)
assert recorder.sequence == "Ctrl+Num1"
assert shortcut_parts("Ctrl+Num1") == (0x4002, 0x61)
assert shortcut_parts("Ctrl+1") == (0x4002, 0x31)
assert migrate_shortcuts(LEGACY_SHORTCUTS) == DEFAULT_SHORTCUTS[:len(LEGACY_SHORTCUTS)]
assert migrate_shortcuts((LEGACY_SHORTCUTS[0], "Alt+Ctrl+F5", "", "Ctrl+Z")) == (
    LEGACY_SHORTCUTS[0], "Alt+Ctrl+F5", "", "Ctrl+Z"
)
assert DEFAULT_SHORTCUTS[:4] == tuple(f"Ctrl+Alt+F{index}" for index in range(5, 9))
recorder.start_recording()
QTest.keyClick(recorder, Qt.Key.Key_F5, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
assert recorder.sequence == "Ctrl+Alt+F5"
assert shortcut_parts(recorder.sequence) == (0x4003, 0x74)
assert DEFAULT_SHORTCUTS[4:6] == ("Ctrl+Alt+8", "Ctrl+Alt+9")
old_brightness = DEFAULT_SHORTCUTS[:4] + ("Ctrl+Alt+Num8", "Ctrl+Alt+Num2") + DEFAULT_SHORTCUTS[6:]
assert migrate_shortcuts(old_brightness) == DEFAULT_SHORTCUTS
custom = ("Ctrl+Alt+8",) + old_brightness[1:]
assert migrate_shortcuts(custom)[4] == "Ctrl+Alt+Num8"
hotkeys.clear()

set_language("en")
assert tr("Este modelo tiene blanco fijo.") == "This model has fixed white."
assert tr("La versión del perfil no es compatible.") == "The profile version is not supported."
print("Atajos registrados, teclado numérico y mensajes de error verificados.")

# Exercise the real dispatch policy with a fake Windows registrar.
actions = [Mock() for _ in range(8)]
bindings = GlobalShortcuts(actions, repeat_from=4)
bindings.register = Mock(return_value=True)
bindings.unregister = Mock()
assert DEFAULT_SHORTCUTS[6:] == ("Ctrl+Alt+F9", "Ctrl+Alt+F10")
old_temperature = DEFAULT_SHORTCUTS[:6] + ("Ctrl+Alt+Num6", "Ctrl+Alt+Num4")
assert migrate_shortcuts(old_temperature, schema=1) == DEFAULT_SHORTCUTS
assert migrate_shortcuts(old_temperature, schema=2) == old_temperature
assert migrate_shortcuts((*old_temperature[:6], "", old_temperature[7]), schema=1)[6:] == ("", "Ctrl+Alt+Num4")
assert bindings.configure(DEFAULT_SHORTCUTS) == []
assert [call.args[2:] for call in bindings.register.call_args_list] == [
    *((0x4003, vk) for vk in range(0x74, 0x78)),
    (3, 0x38), (3, 0x39), (3, 0x78), (3, 0x79),
]
for index, callback in enumerate(actions):
    event = wintypes.MSG(message=0x0312, wParam=0x4C00 + index)
    assert bindings.nativeEventFilter(b"windows_dispatcher_MSG", ctypes.addressof(event)) == (True, 0)
    callback.assert_called_once_with()
assert bindings.configure(old_temperature) == []
assert [call.args[-1] for call in bindings.register.call_args_list[-2:]] == [0x66, 0x64]
bindings.clear()

# Win32 refuses a chord already owned by anyone, even with different repeat flags.
owned = {}
external = set()
registration_failures = set()
moving = GlobalShortcuts([Mock() for _ in range(3)], repeat_from=2)


def register(_, identifier, modifiers, key):
    chord = (modifiers & ~0x4000, key)
    if (chord in external or chord in [(mods & ~0x4000, vk) for mods, vk in owned.values()]
            or (modifiers, key) in registration_failures):
        return False
    assert identifier not in owned
    owned[identifier] = (modifiers, key)
    return True


def unregister(_, identifier):
    del owned[identifier]
    return True


def active_shortcuts():
    assert owned.keys() == moving.registered.keys() == moving.slots.keys()
    return {moving.slots[identifier]: chord for identifier, chord in owned.items()}


moving.register, moving.unregister = register, unregister
moving.registration_error = lambda: 1409
first, second, third = DEFAULT_SHORTCUTS[:3]
assert moving.configure((first, second, "")) == []
assert moving.configure((second, first, "")) == []
assert moving.available(first, ("",)), "Un atajo propio se puede mover a una fila libre"
assert active_shortcuts() == {0: shortcut_parts(second), 1: shortcut_parts(first)}
assert moving.configure(("", first, second)) == []
assert active_shortcuts() == {1: shortcut_parts(first), 2: (3, 0x75)}
saved = owned.copy(), moving.slots.copy(), moving.registered.copy()
external.add((3, 0x76))
assert moving.configure((second, "", third)) == [third]
assert (owned, moving.slots, moving.registered) == saved
registration_failures.add((3, 0x74))
assert moving.configure((second, "", first)) == [first]
assert (owned, moving.slots, moving.registered) == saved
assert moving.configure(("", "", "")) == []
assert moving.configure((first, "", third)) == [third]
assert active_shortcuts() == {}, "Un intento rechazado dejó un atajo nuevo activo"
assert moving.statuses[0] == ("unchanged", 0)

startup = GlobalShortcuts(actions[:3])
startup.register, startup.unregister = register, unregister
startup.registration_error = moving.registration_error
assert startup.configure((first, "", third)) == [third]
assert list(startup.registered.values()) == [first]
assert list(owned.values()) == [(0x4003, 0x74)]
startup.clear()
assert not owned

# Keep real Qt ownership while supplying modal results without a nested event loop.
choose = Mock(return_value=None)


class TestMenu(QMenu):
    def exec(self, _position):
        return choose(self)


with patch("Escritorio.QMenu", TestMenu):
    for _ in range(3):
        recorder.show_options(QPoint())
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not recorder.findChildren(QMenu), "ShortcutRecorder retained a dismissed menu"
    assert recorder.sequence == "Ctrl+Alt+F5"

    choose.side_effect = lambda menu: menu.actions()[0]
    recorder.show_options(QPoint())
    assert recorder.sequence == ""
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not recorder.findChildren(QMenu), "ShortcutRecorder retained a selected menu"

    choose.side_effect = RuntimeError("menu error")
    try:
        recorder.show_options(QPoint())
    except RuntimeError as error:
        assert str(error) == "menu error"
    else:
        raise AssertionError("Expected menu error")
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not recorder.findChildren(QMenu), "ShortcutRecorder retained a menu after an exception"


# Closing to the tray from Preferences must release the shortcut pause.
import runpy
from PySide6.QtWidgets import QDialogButtonBox

ui = runpy.run_path("src/Bombilla.pyw")
window = ui["Window"]()
window.install_desktop(ui["preferences"](), enable=False)
window.hotkeys = bindings
window.show()
window.show_section(2)
app.processEvents()
assert bindings.paused and window.section_dialog is not None
window.hide()
app.processEvents()
assert not bindings.paused, "Preferencias silenció los atajos al ocultar Luz"
window.show()
app.processEvents()
assert bindings.paused
window.section_dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Cancel).click()
assert not bindings.paused
window.hotkeys = None
window.close()
