"""Regression checks for the palette and keyboard-facing controls."""
import runpy
import sys
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, "src")
from Tema import colors_for

app = QApplication([])
for light in (False, True):
    system = colors_for(light, contrast=True)
    assert system["edge"] == system["text"]
    assert system["accentText"] == system["text"]
    assert system["preview"] == system["canvas"]
    roles = colors_for(light)
    assert roles["preview"] != roles["canvas"]

ui = runpy.run_path("src/Bombilla.pyw")
window = ui["Window"]()
window.install_desktop(ui["preferences"](), enable=False)
window.show()
window.update_connection(True, "Synthetic")
hue = window.colors.hue
assert hue.accessibleName() and hue.accessibleDescription()
accessible_hue = QAccessible.queryAccessibleInterface(hue)
assert accessible_hue.role() == QAccessible.Role.Slider
assert accessible_hue.valueInterface().currentValue() == hue.value()
assert window.lamp.accessibleName() and window.lamp.accessibleDescription()
for key, target in ((Qt.Key.Key_End, hue.maximum()), (Qt.Key.Key_Home, hue.minimum())):
    QTest.keyClick(hue, key)
    assert hue.value() == target
QTest.keyClick(hue, Qt.Key.Key_PageUp)
assert hue.value() > hue.minimum()
QTest.keyClick(hue, Qt.Key.Key_PageDown)
assert hue.value() == hue.minimum()
scene = window.scenes[0]
scene.setFocus()
app.processEvents()
with patch.object(window, "scene_menu") as menu:
    QTest.keyClick(scene, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    menu.assert_called_once_with(0, scene.rect().center())
window.close()
print("Paleta del sistema, nombres y navegación del tono verificados")

# Selected text and items use the operating system's selection colors.
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QLineEdit, QListWidget
from Tema import theme_style

app.setStyleSheet(theme_style(False, contrast=True))
combo = ui["MenuCombo"]()
combo.addItems(["A", "B"])
for widget in (QLineEdit("Selection"), QListWidget(), combo.view()):
    widget.ensurePolished()
    palette = widget.palette()
    assert palette.color(QPalette.ColorRole.Highlight).name() == system["accent"]
    assert palette.color(QPalette.ColorRole.HighlightedText).name() == system["ink"]
