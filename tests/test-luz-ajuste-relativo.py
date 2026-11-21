import runpy
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtCore import QPoint, QSettings, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QDialogButtonBox

sys.path.insert(0, "src")
import BombillaLocal as local
from Escritorio import DEFAULT_SHORTCUTS, GlobalShortcuts

with patch.object(local, "load_token", return_value=""):
    ui = runpy.run_path("src/Bombilla.pyw")
app = QApplication([])
window = ui["Window"]()
window.show()
window.update_connection(True, "Conectada")
# Clicking the track must select that position instead of page-stepping.
with patch.object(window, "submit"):
    QTest.mouseClick(window.brightness, Qt.MouseButton.LeftButton,
                     pos=QPoint(window.brightness.width()-1, window.brightness.height()//2))
    assert window.brightness.value() == 100
    window.pending.clear()
    window.pending_shortcuts.clear()
    window.send_timer.stop()
initial = local.LightStatus(False, 25, 2700, None, None, False, 0)
window.render_status(initial)
window.brightness.setSliderDown(True)
window.brightness.setValue(60)
window.send_timer.stop()
window.pending.clear()
window.pending_shortcuts.clear()
window.render_status(initial)  # A response to an older request arrives mid-drag.
assert window.brightness.value() == window.brightness_value.value() == window.lamp.level == 60
assert window.lamp.lit
window.brightness.setValue(80)
with patch.object(window, "submit") as send:
    window.brightness.setSliderDown(False)
    send.assert_called_once_with("brightness", 80, shortcut=None)
    assert not window.send_timer.isActive()
window.brightness_value.setFocus()
app.processEvents()
window.render_status(initial)
assert window.brightness.value() == window.brightness_value.value() == window.lamp.level == 25
window.set_number(window.brightness, 85)
window.ajustar_relativo("brightness", 1)
window.ajustar_relativo("brightness", 1)
assert window.brightness.value() == 100
assert window.lamp.level == 100 and window.pending == {"brightness": 100}
window.ajustar_relativo("brightness", -1)
assert window.brightness.value() == 90
window.bulb.model = "yeelink.light.mono1"
window.update_device()
window.ajustar_relativo("white", 1)
assert list(window.pending) == ["brightness"]
window.pending.clear()
window.send_timer.stop()
window.bulb.model = local.MODEL
window.update_device()
window.set_number(window.temperature, 6400)
window.ajustar_relativo("white", 1)
assert window.kelvin_value.value() == 6500
assert window.pending == {"white": 6500}
window.pending.clear()
window.send_timer.stop()
window.desktop = Mock()
window.desktop.value.return_value = 5
window.set_number(window.brightness, 5)
window.ajustar_relativo("brightness", -1)
assert window.brightness.value() == 1
window.ajustar_relativo("brightness", -1)
assert window.pending == {"brightness": 1}
window.pending.clear()
window.send_timer.stop()

other = Mock(mac="AA2233445566", name="Otra bombilla")
other.features = local.capabilities(local.MODEL)
window.habitacion_ajustes = (window.bulb, other)
window.bulb.model = "yeelink.light.mono1"
window.update_device()
window.ajustar_relativo("white", 1)
key, value = next(iter(window.pending.items()))
with patch.dict(window.call.__func__.__globals__, {"load_token": Mock(return_value="")}) as scope:
    window.call(key, value)
    scope["load_token"].assert_called_once_with(other.mac)
other.relative_target.assert_called_once_with("", "white", (250,), recover=False)
window.pending.clear()
window.send_timer.stop()
window.habitacion_ajustes = ()

bulb = local.Bulb()
bulb.model = local.MODEL
device = Mock()
state = SimpleNamespace(brightness=96, color_temp=6400, is_on=True)
with patch.object(bulb, "verified", return_value=device), patch.object(local, "read_status", side_effect=[state, SimpleNamespace(is_on=True,brightness=95), state, SimpleNamespace(is_on=True,color_temp=6500)]):
    bulb.ajustar_relativo("", "brightness", (10, -5))
    device.set_brightness.assert_called_once_with(95)
    bulb.ajustar_relativo("", "white", (250,))
    device.set_color_temp.assert_called_once_with(6500)

with TemporaryDirectory(prefix="luz-tests-") as temp:
    preferences = QSettings(str(Path(temp) / "preferencias.ini"), QSettings.Format.IniFormat)
    window.install_desktop(preferences, enable=False)
    def guardar_paso():
        panel = app.activeModalWidget()
        control = next((item for item in panel.findChildren(QComboBox) if item.findData(15) >= 0), None)
        if control is None:
            panel.reject()
            return
        control.setCurrentIndex(control.findData(15))
        panel.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).click()

    QTimer.singleShot(50, guardar_paso)
    window.desktop_settings()
    assert preferences.value("brightness_step", type=int) == 15
    assert window.paso_brillo() == 15

hotkeys = GlobalShortcuts((Mock(),) * 8, repeat_from=4)
hotkeys.register = Mock(return_value=True)
assert not hotkeys.configure(DEFAULT_SHORTCUTS)
assert all(call.args[2] & 0x4000 for call in hotkeys.register.call_args_list[:4])
assert all(not call.args[2] & 0x4000 for call in hotkeys.register.call_args_list[4:])
window.hide()
window.set_number(window.brightness, 100)
window.ajustar_relativo("brightness", 1)
window.ajustar_relativo("brightness", -1)
assert window.pending == {"relative_brightness": (15, -15)}
with patch.object(window.bulb, "ajustar_relativo", return_value=state) as relative:
    assert window.call("relative_brightness", (15, -15)) == (state, None)
    relative.assert_called_once_with(window.token, "brightness", (15, -15))
print("Ajustes relativos, vista previa, cola y límites verificados")

# A group operation records remaining members after its deadline.
window.bulb.model = local.MODEL
window.bulb.mac = "020000000042"
first = Mock(mac="020000000001", name="Primera")
next_bulb = Mock(mac="020000000002", name="Segunda")
first.name, next_bulb.name = "Primera", "Segunda"
with patch.dict(window.call.__func__.__globals__, {"load_token": Mock(return_value="fake"),
                                                   "monotonic": Mock(side_effect=[0, 1, 20])}):
    (_status, completed, failures), _ = window.call("group", ((first, next_bulb), "color", (5, 6, 7)))
assert completed == 1 and [(item.bulb.name, item.state) for item in failures] == [("Primera", "applied"), ("Segunda", "timeout")]
first.control.assert_called_once_with("fake", "color", (5, 6, 7), recover=False)
next_bulb.control.assert_not_called()
window.close()

# A light that recovers must be reachable by hotkey after a transient outage.
window = ui["Window"]()
window.token = "a7" * 16
window.online = False
window.ajustar_relativo("brightness", -1)
assert window.pending == {"relative_brightness": (-10,)}
window.close()
