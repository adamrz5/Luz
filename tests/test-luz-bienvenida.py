"""First-run connection guidance uses the existing verification flow."""
import runpy
import sys
from concurrent.futures import Future
from unittest.mock import Mock, patch

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QLineEdit, QPushButton

sys.path.insert(0, "src")
from Idioma import set_language, tr

app = QApplication([])
ui = runpy.run_path("src/Bombilla.pyw")
for language in ("es", "en"):
    set_language(language)
    window = ui["Window"]()
    window.install_desktop(ui["preferences"](), enable=False)
    window.show()
    window.start_first_run()
    app.processEvents()
    assert window.sections.currentIndex() == 1
    dialog = window.section_dialog
    window.start_first_run()
    assert window.section_dialog is dialog, "The guide was created twice"
    texts = [item.text() for item in dialog.findChildren(QLabel)]
    assert tr("Bienvenido a Luz") in texts
    assert tr("1. Encuentra tu bombilla") in texts
    assert tr("2. Consigue el token") in texts
    assert tr("3. Detalles opcionales") in texts
    if language == "en":
        assert "Bienvenido a Luz" not in texts
    buttons = dialog.findChild(QDialogButtonBox)
    save = buttons.button(QDialogButtonBox.StandardButton.Save)
    save.click()
    assert window.section_dialog is dialog
    assert not window.token
    address = dialog.findChild(QLineEdit, "bulbIp")
    secret = dialog.findChild(QLineEdit, "bulbToken")
    assert secret.echoMode() == QLineEdit.EchoMode.Password
    clipboard = Mock()
    clipboard.text.return_value = "NAME: Demo\nIP: 192.0.2.20\nTOKEN: " + "a7" * 16
    with patch.object(QApplication, "clipboard", return_value=clipboard):
        next(button for button in dialog.findChildren(QPushButton) if button.text() == tr("Pegar IP y token")).click()
    assert address.text() == "192.0.2.20" and secret.text() == "a7" * 16
    assert dialog.findChild(QLineEdit, "xiaomiName").text() == "Demo"
    clipboard.clear.assert_called_once()
    with patch.object(window, "submit") as submit:
        save.click()
        assert submit.call_args.args[0] == "settings"
        assert submit.call_args.args[1][:2] == (address.text(), secret.text())
    window.connection_result("Introduce el token de la bombilla.")
    assert window.section_dialog is dialog and save.isEnabled()
    assert address.text() == "192.0.2.20" and secret.text() == "a7" * 16
    assert buttons.button(QDialogButtonBox.StandardButton.Cancel).text() == tr("Configurar más tarde")
    buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
    assert window.section_dialog is None and window.sections.currentIndex() == 0
    window.token = "a7" * 16
    window.start_first_run()
    assert window.section_dialog is None
    window.close()

window = ui["Window"]()
window.install_desktop(ui["preferences"](), enable=False)
window.start_first_run()
dialog = window.section_dialog
dialog.findChild(QLineEdit, "bulbIp").setText("192.0.2.20")
dialog.findChild(QLineEdit, "bulbToken").setText("a7" * 16)
with patch.object(window, "submit") as submit:
    dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).click()
candidate = ui["Bulb"]()
candidate.ip, candidate.mac = "192.0.2.20", "020000000001"
from BombillaLocal import LightStatus
future = Future()
future.set_result((LightStatus(True, 50, 4000, None, None, False, 0), (candidate, "a7" * 16)))
window.future, window.in_flight = future, ("settings", submit.call_args.args[1])
window.finish()
assert window.token and window.online and window.section_dialog is None
assert window.sections.currentIndex() == 0
window.start_first_run()
assert window.section_dialog is None
window.close()

window = ui["Window"]()
window.install_desktop(ui["preferences"](), enable=False)
window.show_section(2)
preferences_dialog = window.section_dialog
window.start_first_run()
assert window.sections.currentIndex() == 2 and window.section_dialog is preferences_dialog, "First-run callback discarded an open Preferences form"
preferences_dialog.reject()
window.show_section(3)
window.start_first_run()
assert window.sections.currentIndex() == 3 and window.section_dialog is None
window.show_section(0)
window.closing = True
window.start_first_run()
assert window.section_dialog is None, "The guide appeared during shutdown"
window.closing = False
window.start_first_run()
dialog = window.section_dialog
dialog.findChild(QLineEdit, "bulbIp").setText("192.0.2.20")
dialog.findChild(QLineEdit, "bulbToken").setText("a7" * 16)
with patch.object(window, "submit"):
    dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).click()
window.navigation.button(0).click()
assert window.section_dialog is dialog, "Navigation cancelled an active verification"
assert window.navigation.button(1).isChecked(), "Navigation selection no longer matches the active page"
window.escape()
assert window.section_dialog is dialog, "Escape cancelled an active verification"
window.connection_result("Introduce el token de la bombilla.")
dialog.reject()
QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
before = len(window.findChildren(QDialog))
for _ in range(3):
    with patch.object(QDialog, "exec", return_value=0):
        window.token_help()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
assert len(window.findChildren(QDialog)) == before, "Closed QR help dialogs accumulated in memory"

window.close()

# The real entry point schedules the guide only for a visible startup.
for hidden in (False, True):
    application = Mock()
    application.exec.return_value = 0
    factory = Mock()
    timer = Mock()
    lock = Mock()
    lock.tryLock.return_value = True
    settings = Mock()
    settings.value.return_value = "es"
    with patch.dict(ui["main"].__globals__, {
        "QApplication": Mock(return_value=application), "Window": factory,
        "QTimer": timer, "QLockFile": Mock(return_value=lock),
        "desktop_lock": Mock(return_value=lock), "app_icon": Mock(),
        "preferences": Mock(return_value=settings),
    }), patch.object(sys, "argv", ["Luz.exe", "--oculto" if hidden else "--sin-bandeja"]):
        assert ui["main"]() == 0
    if hidden:
        timer.singleShot.assert_not_called()
        factory.return_value.show.assert_not_called()
    else:
        timer.singleShot.assert_called_once_with(0, factory.return_value.start_first_run)

print("Primera conexión: guía bilingüe, validación, reintento, cancelación y perfil existente comprobados")

# Guidance remains available when a configured user buys another bulb.
for language in ("es", "en"):
    set_language(language)
    window = ui["Window"]()
    window.install_desktop(ui["preferences"](), enable=False)
    window.token = "ab" * 16
    window.show_section(1)
    form = window.section_dialog
    texts = [item.text() for item in form.findChildren(QLabel)]
    assert tr("1. Encuentra tu bombilla") in texts
    assert tr("2. Consigue el token") in texts
    assert tr("Añade tu bombilla a Luz") in texts
    assert any(button.text() == tr("Obtener token por QR") for button in form.findChildren(QPushButton))
    form.reject()
    assert window.token == "ab" * 16
    window.close()

# Dismissing Connection erases the draft immediately and releases its widgets.
window = ui["Window"]()
window.install_desktop(ui["preferences"](), enable=False)
def draft_and_reject(dialog):
    dialog.findChild(QLineEdit, "bulbToken").setText("a7" * 16)
    dialog.reject()
    return 0

for _ in range(3):
    with patch.object(QDialog, "exec", draft_and_reject):
        window.settings(True)
    secret = window.findChild(QLineEdit, "bulbToken")
    assert secret is not None and not secret.text(), "A closed modal retained the drafted token"
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert window.findChild(QLineEdit, "bulbToken") is None
    window.show_section(1)
    form = window.section_dialog
    secret = form.findChild(QLineEdit, "bulbToken")
    secret.setText("a7" * 16)
    form.reject()
    assert not secret.text(), "The dismissed embedded form retained the drafted token"
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert window.findChild(QLineEdit, "bulbToken") is None
window.close()

# Help is available again for configured users, in either language.
from PySide6.QtCore import QTimer
for language in ("es", "en"):
    set_language(language)
    window = ui["Window"]()
    window.install_desktop(ui["preferences"](), enable=False)
    window.token = "ab" * 16
    window.show_section(3)
    actions = window.section_layouts[3].itemAt(0).widget().findChildren(QPushButton)
    assert [item.text() for item in actions[:2]] == [tr("Atajos"), tr("Ayuda")]
    seen = []
    def inspect_help():
        guide = app.activeModalWidget()
        seen.append(guide.windowTitle())
        texts = [item.text() for item in guide.findChildren(QLabel)]
        assert tr("Volver a configurar una bombilla") in texts
        assert not window.configuring
        next(item for item in guide.findChildren(QPushButton) if item.text() == tr("Abrir Conexión")).click()
    QTimer.singleShot(0, inspect_help)
    window.setup_help()
    app.processEvents()
    assert seen == [tr("Ayuda")]
    assert window.sections.currentIndex() == 1
    assert window.token == "ab" * 16
    window.section_dialog.reject()
    window.close()

from PySide6.QtCore import QRect
from PySide6.QtGui import QScreen
for language in ("es", "en"):
    set_language(language)
    window = ui["Window"]()
    window.install_desktop(ui["preferences"](), enable=False)
    window.show_section(3)
    checks = []
    def inspect_small_help():
        guide = app.activeModalWidget()
        checks.append(guide.width() <= 400)
        guide.reject()
    QTimer.singleShot(0, inspect_small_help)
    with patch.object(QScreen, "availableGeometry", return_value=QRect(0, 0, 400, 400)):
        window.setup_help()
    assert checks == [True], "Help exceeds the available screen width"
    window.future = Future()
    checks = []
    def inspect_busy_help():
        guide = app.activeModalWidget()
        next(item for item in guide.findChildren(QPushButton) if item.text() == tr("Abrir Conexión")).click()
        checks.append(guide.isVisible() and window.sections.currentIndex() == 3)
        guide.reject()
    QTimer.singleShot(0, inspect_busy_help)
    window.setup_help()
    window.future = None
    assert checks == [True], "Busy Connection discarded the guide"
    window.close()
