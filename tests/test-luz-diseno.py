"""Layout and accessibility checks for the help page."""
import runpy
import sys

from PySide6.QtWidgets import QApplication, QFrame, QPushButton

sys.path.insert(0, "src")
ui = runpy.run_path("src/Bombilla.pyw")
app = QApplication([])
window = ui["Window"]()
window.install_desktop(ui["preferences"](), enable=False)
window.show()
window.show_section(3)
app.processEvents()
layout = window.section_layouts[3]
panel = layout.itemAt(0).widget()
rows = panel.findChildren(QPushButton)
rules = [frame for frame in panel.findChildren(QFrame) if frame.objectName() == "rule"]
assert len(rows) == 4
assert len(rules) == 3, f"Se esperaban 3 separadores y hay {len(rules)}"
for above, rule, below in zip(rows, rules, rows[1:]):
    assert above.geometry().bottom() < rule.y() < below.y()
    assert rule.height() == 1 and rule.width() == above.width()
    assert above.height() >= 44
window.close()
print("Ayuda: tres separadores de 1 px entre las cuatro acciones")

# Repainting an unchanged preview must not rebuild its gradients.
from dataclasses import replace
from unittest.mock import Mock, patch

from BombillaLocal import LightStatus
window = ui["Window"]()
window.install_desktop(ui["preferences"](), enable=False)
window.show()
app.processEvents()
assert not window.heartbeat.isActive()
scope = window.lamp.paintEvent.__func__.__globals__
def unexpected_gradient(*args):
    raise AssertionError("gradient in paintEvent")

window.lamp.grab()
window.colors.hue.grab()
with patch.dict(scope, {"QLinearGradient": unexpected_gradient}):
    assert not window.lamp.grab().isNull()
    assert not window.colors.hue.grab().isNull()
window.token = "a7" * 16
window.hide()
assert window.heartbeat.isActive() and window.heartbeat.interval() == 60000
window.show()
assert window.heartbeat.isActive() and window.heartbeat.interval() == 60000
window.close()

# Power previews immediately and dispatches without the slider debounce.
window = ui["Window"]()
window.show()
window.update_connection(True, "Conectada")
status = LightStatus(True, 50, 2700, None, None, False, 0)
window.render_status(status)
with patch.object(window, "submit") as submit:
    window.power.click()
    submit.assert_called_once_with("power", False, shortcut=None)
    assert not window.send_timer.isActive()
    assert not window.power.isChecked() and not window.lamp.lit
    assert window.power.text() == "Encender" and window.power_on

    # An older reply must leave the newest pending click visible.
    window.in_flight = ("power", False)
    window.future = Mock()
    window.power.click()
    assert list(window.pending.items()) == [("power", True)]
    window.in_flight = None
    window.future = None
    window.render_status(replace(status, is_on=False))
    assert window.power.isChecked() and window.lamp.lit
    window.pending.clear()
    window.render_status(replace(status, is_on=False))
    assert not window.power.isChecked() and not window.lamp.lit
window.close()

# Background checks are read-only and user commands can recover an offline light.
window = ui["Window"]()
window.token = "a7" * 16
window.hide()
window.start_heartbeat()
assert window.heartbeat.isActive() and window.heartbeat.interval() == 60000
window.online = False
with patch.object(window, "submit") as send:
    window.refresh()
    send.assert_called_once_with("status")
window.future = Mock()
window.in_flight = ("status", None)
window.dispatch_shortcut(0, window.tray_toggle)
assert window.pending == {"desktop_power": None}
assert window.shortcut_results[0] == "Pendiente"
window.future = None
window.in_flight = None
window.pending.clear()
window.pending_shortcuts.clear()
window.send_timer.stop()
window.dispatch_shortcut(1, lambda: window.desktop_scene(0))
assert window.pending == {"scene": window.scene_slots[0].command()}
assert window.shortcut_results[1] == "Pendiente"
window.pending.clear()
window.pending_shortcuts.clear()
window.send_timer.stop()
from concurrent.futures import Future
window.current_shortcut = None
window.in_flight_shortcut = 1
window.in_flight = ("scene", window.scene_slots[0].command())
window.future = Future()
window.future.set_result((status, None))
window.finish()
assert window.shortcut_results[1] == "Aplicado"
assert 1 in window.shortcut_times
window.close()

# Quiet probes preserve UI feedback and skip repainting an unchanged state.
window = ui["Window"]()
window.token = "a7" * 16
window.update_connection(True, "Conectada")
window.render_status(status)
window.note.setText("Mensaje de una acción")
window.in_flight = ("status", None)
window.in_flight_shortcut = None
window.in_flight_silent = True
window.future = Future()
window.future.set_result((status, None))
with patch.object(window, "render_status") as render:
    window.finish()
    render.assert_not_called()
assert window.note.text() == "Mensaje de una acción"
window.in_flight = ("status", None)
window.in_flight_silent = True
window.future = Future()
from BombillaLocal import BombillaNoEncontrada
window.future.set_exception(BombillaNoEncontrada())
window.finish()
assert not window.online and window.note.text() == "Mensaje de una acción"
window.in_flight = ("status", None)
window.in_flight_silent = True
window.future = Future()
window.future.set_result((status, None))
window.finish()
assert window.online and window.note.text() == "Mensaje de una acción"
window.close()

# The preview supports the same power action by click and keyboard.
window = ui["Window"]()
window.show()
window.update_connection(True, "Conectada")
window.render_status(status)
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
with patch.object(window, "toggle") as toggle:
    QTest.mouseClick(window.lamp, Qt.MouseButton.LeftButton)
    toggle.assert_called_once()
    window.lamp.setFocus()
    QTest.keyClick(window.lamp, Qt.Key.Key_Space)
    assert toggle.call_count == 2
window.begin_scene_edit(0)
assert not window.lamp.isEnabled()
window.cancel_scene_edit()
window.close()

# A command rejected by readback leaves the connection online and shows actual state.
window = ui["Window"]()
window.online = True
window.in_flight = ("brightness", 73)
window.in_flight_shortcut = 4
window.future = Future()
from BombillaLocal import CambioNoAplicado
window.future.set_exception(CambioNoAplicado(status))
window.finish()
assert window.online
assert window.brightness.value() == status.brightness
assert window.shortcut_results[4] == "El cambio no se aplicó"
assert "confirm" in window.note.text()
window.close()

# Switching directly between forms must not briefly open the lights page.
window = ui["Window"]()
window.install_desktop(ui["preferences"](), enable=False)
window.show_section(1)
visited = []
window.sections.currentChanged.connect(visited.append)
window.show_section(2)
assert visited == [2], f"Unexpected intermediate pages: {visited}"
window.close()

# A valid long bulb label must not force the form outside a small window.
with patch.dict(ui["Window"].__init__.__globals__, {
    "profiles_for_display": lambda: [("020000000001", "W" * 48)],
}):
    window = ui["Window"]()
    window.install_desktop(ui["preferences"](), enable=False)
    window.bulb.mac = "020000000001"
    window.bulb.ip = "192.0.2.20"
    window.bulb.name = "W" * 48
    window.token = "a7" * 16
    window.resize(870, 660)
    window.show()
    app.processEvents()
    window.navigation.button(1).click()
    app.processEvents()
    connection = window.sections.widget(1)
    scroll = connection.verticalScrollBar()
    assert scroll.maximum() > 0, "The small window must allow scrolling"
    scroll.setValue(min(90, scroll.maximum()))
    window.navigation.button(2).click()
    window.navigation.button(1).click()
    app.processEvents()
    form = window.section_dialog
    welcome = next(item for item in form.findChildren(ui["QLabel"], "section")
                   if item.text() == "Añade tu bombilla a Luz")
    viewport = connection.viewport()
    heading_bounds = welcome.rect().translated(welcome.mapTo(viewport, welcome.rect().topLeft()))
    assert viewport.rect().contains(heading_bounds), "The welcome heading is clipped on reentry"
    for width, height in ((870, 660), (1140, 750), (870, 660)):
        window.resize(width, height)
        app.processEvents()
        for group in form.findChildren(QFrame, "group"):
            for item in group.findChildren(ui["QWidget"], options=ui["Qt"].FindChildOption.FindDirectChildrenOnly):
                if item.isHidden():
                    continue
                assert group.rect().contains(item.geometry()), f"{item.metaObject().className()} extends beyond its group"
                if isinstance(item, (ui["QLineEdit"], ui["QComboBox"])):
                    assert item.height() >= item.minimumSizeHint().height(), "The connection field is clipped"
                if isinstance(item, ui["QLabel"]) and item.wordWrap():
                    assert item.height() >= item.heightForWidth(item.width()), f"Connection text is clipped at {width}: {item.text()} is {item.height()} high, needs {item.heightForWidth(item.width())}"
    headings = form.findChildren(ui["QLabel"], "section")
    assert headings and all(item.font().pointSizeF() > app.font().pointSizeF() for item in headings), "Form headings never received the theme font"
    for item in form.findChildren(ui["QLabel"]):
        if item.wordWrap() and item.text() and not item.isHidden():
            assert item.geometry().right() < item.parentWidget().width(), "Connection text extends beyond its panel"
    assert window.sections.widget(1).horizontalScrollBar().maximum() == 0
    window.close()

# Embedded form corners must match the workspace in both themes.
window = ui["Window"]()
settings = ui["preferences"]()
window.install_desktop(settings, enable=False)
window.show()
for theme in ("light", "dark"):
    settings.setValue("theme", theme)
    window.apply_theme()
    window.show_section(2)
    app.processEvents()
    corner = window.section_dialog.grab().toImage().pixelColor(0, 0)
    assert corner == app.palette().window().color(), "Contrasting square corners around embedded groups"
    window.show_section(0)
window.close()

# Repeatedly opening transient dialogs and menus must not accumulate hidden widgets.
window = ui["Window"]()
window.install_desktop(ui["preferences"](), enable=False)
window.group_results = ()

def dismiss_popup():
    popup = app.activePopupWidget() or app.activeModalWidget()
    if popup:
        popup.close()

dialogs = (window.configure_timer, window.compatibility_catalog, window.show_group_results, window.desktop_settings, window.setup_help)
menus = (window.flow_menu, window.backup_menu, window.lights_menu)
for widget_type, operations in ((ui["QDialog"], dialogs), (ui["QMenu"], menus)):
    baseline = len(window.findChildren(widget_type))
    for _ in range(3):
        for operation in operations:
            ui["QTimer"].singleShot(0, dismiss_popup)
            operation()
            app.sendPostedEvents(None, ui["QEvent"].Type.DeferredDelete)
            assert len(window.findChildren(widget_type)) == baseline, f"{operation.__name__} retained a widget"
window.close()

# A later scene supersedes the earlier pending shortcut, including after a repeat.
window = ui["Window"]()
window.token = "a7" * 16
window.dispatch_shortcut(1, lambda: window.desktop_scene(0))
window.dispatch_shortcut(2, lambda: window.desktop_scene(1))
window.dispatch_shortcut(2, lambda: window.desktop_scene(1))
assert window.shortcut_results[1] == "Sustituido por un cambio posterior"
assert window.shortcut_results[2] == "Pendiente"
with patch.object(window, "submit") as submit:
    window.pump()
    submit.assert_called_once_with("scene", window.scene_slots[1].command(), shortcut=2)
window.close()

# Lights cards and scenes stay within the viewport at both layout widths.
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QFont, QScreen

app.setFont(QFont("Segoe UI", 9))
window = ui["Window"]()
window.install_desktop(ui["preferences"](), enable=False)
window.show()
window.update_connection(True, "Conectada")
view = window.sections.widget(0)
for width in (870, 1140, 870):
    window.resize(width, 660)
    app.processEvents()
    assert view.horizontalScrollBar().maximum() == 0, f"Lights clip at {width} px"
    for card in (window.light, window.editor_card, window.scenes_card):
        left = card.mapTo(view.viewport(), QPoint()).x()
        assert 0 <= left and left + card.width() <= view.viewport().width()
window.close()

# A 1920 x 1080 desktop at 200% scaling leaves about 960 x 516 logical px.
work_area = QRect(0, 0, 960, 516)
with patch.object(QScreen, "availableGeometry", return_value=work_area):
    window = ui["Window"]()
    window.show()
    app.processEvents()
    assert window.width() <= work_area.width() - 12
    assert window.height() <= work_area.height() - 24
    assert window.minimumHeight() <= work_area.height() - 24
    window.close()

# Discrete toggles keep their position relative to commands that can turn the light on.
window = ui["Window"]()
window.token = "synthetic"
window.update_connection(True, "Conectada")
toggle = ("desktop_power", None)
scene = ("scene", window.scene_slots[0].command())
for commands in ((toggle,) * 2, (toggle,) * 3,
                 (scene, toggle, scene, toggle), (("brightness", 30), toggle, ("brightness", 60), toggle),
                 (("power", False), toggle, ("power", True), toggle)):
    window.future = Future()
    for action, value in commands:
        if action == "desktop_power":
            window.tray_toggle()
        else:
            window.schedule(action, value)
    window.future = None
    with patch.object(window, "submit") as send:
        while window.pending:
            window.pump()
        assert [call.args for call in send.call_args_list] == list(commands)
window.close()

# No desktop action may be queued against either profile while verification is running.
for success in (True, False):
    window = ui["Window"]()
    window.token = "synthetic"
    original = window.bulb
    candidate = Mock(mac="020000000002", ip="192.0.2.2", room="", xiaomi_name="", model=original.model)
    candidate.name, candidate.features = "Otra", original.features
    verification = Future()
    with patch.object(window.executor, "submit", return_value=verification) as worker:
        window.select_light(candidate)
        window.dispatch_shortcut(0, window.tray_toggle)
        window.desktop_scene(0)
        window.ajustar_relativo("brightness", 1)
        assert not window.pending
        assert window.shortcut_results[0] == "Acción no disponible ahora"
        if success:
            verification.set_result((status, (candidate, "new-synthetic")))
        else:
            verification.set_exception(ValueError("failed"))
        window.finish()
        assert window.bulb is (candidate if success else original)
        assert worker.call_count == 1
    window.close()

# A rendered action stays authoritative when an earlier absolute request moves behind a tray toggle.
for initial in (False, True):
    for trigger in ("power", "lamp", "keyboard"):
        window = ui["Window"]()
        window.token = "synthetic"
        window.update_connection(True, "Conectada")
        old_status = replace(status, is_on=initial)
        window.render_status(old_status)
        window.future = Future()
        window.in_flight = ("status", None)
        window.power.click()
        window.tray_toggle()
        assert window.power.text() == ("Encender" if initial else "Apagar")
        if trigger != "power":
            window.render_status(old_status)
            assert window.power.isChecked() == window.lamp.lit == (not initial)
        if trigger == "power":
            window.power.click()
        elif trigger == "lamp":
            QTest.mouseClick(window.lamp, Qt.MouseButton.LeftButton)
        else:
            QTest.keyClick(window.lamp, Qt.Key.Key_Space)
        assert window.power.isChecked() == window.lamp.lit == initial
        assert window.power.text() == ("Apagar" if initial else "Encender")
        window.future = None
        with patch.object(window, "submit") as send:
            while window.pending:
                window.pump()
        assert [call.args for call in send.call_args_list] == [
            ("power", not initial), ("desktop_power", None), ("power", initial)]
        window.close()
