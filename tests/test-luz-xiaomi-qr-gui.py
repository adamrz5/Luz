"""Native QR controls and Connection import use only synthetic credentials."""
import runpy
import sys
from concurrent.futures import Future
from queue import Empty, Queue
from threading import Event
from unittest.mock import patch

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QPushButton

sys.path.insert(0, "src")
ui = runpy.run_path("src/Bombilla.pyw")
assert "TokenXiaomi" not in sys.modules and "token_extractor" not in sys.modules
from TokenXiaomi import TokenDialog
from XiaomiCloud import CloudBulb
from Idioma import set_language, tr

app = QApplication([])
image = QPixmap(32, 32)
image.fill()
buffer = QBuffer()
buffer.open(QIODevice.OpenModeFlag.WriteOnly)
image.save(buffer, "PNG")
png = bytes(buffer.data())
bulb = CloudBulb("Demo", "192.0.2.20", "yeelink.light.color5", "020000000001", "ab" * 16)
# The producer publishes after get_nowait observes Empty, then completes.
race_parent = QDialog()
race = TokenDialog(race_parent, ui["MenuCombo"]())
for terminal in (("devices", (bulb,)), ("error", "Synthetic error")):
    race.future = Future()

    class FinishingQueue(Queue):
        def get_nowait(self):
            if not race.future.done():
                self.put(terminal)
                race.future.set_result(None)
                raise Empty
            return super().get_nowait()

    race.events = FinishingQueue()
    race.timer.start()
    race.poll()
    assert race.timer.isActive(), "Timer stopped with a queued terminal event"
    race.poll()
    assert not race.timer.isActive()
    if terminal[0] == "devices":
        assert race.devices == (bulb,)
    else:
        assert race.status.text() == terminal[1]
race.future = Future()
race.future.set_result(None)
race.events = Queue()
race.events.put(("qr", b"invalid image"))
race.events.put(("devices", (bulb,)))
race.timer.start()
race.poll()
assert race.cancelled.is_set() and not race.timer.isActive() and race.events.empty()
assert race.status.text() == tr("La imagen QR de Xiaomi no es válida.")
race.reject()

for language in ("es", "en"):
    set_language(language)
    window = ui["Window"]()
    window.install_desktop(ui["preferences"](), enable=False)
    dialog = TokenDialog(window, ui["MenuCombo"]())
    assert dialog.future is None and dialog.executor is None and not dialog.timer.isActive()
    approved = Event()

    def fake_scan(events, cancelled, region):
        assert region == "de"
        events.put(("qr", png))
        approved.wait(1)
        if not cancelled.is_set():
            events.put(("scanning", region))
            events.put(("devices", (bulb,)))

    with patch("TokenXiaomi.scan", fake_scan):
        dialog.show()
        dialog.start()
        QTest.qWait(150)
        assert dialog.qr.pixmap() and not dialog.qr.pixmap().isNull()
        assert not dialog.generate.isEnabled() and not dialog.region.isEnabled()
        approved.set()
        QTest.qWait(150)
        assert dialog.list.count() == 1 and bulb.token not in dialog.list.item(0).text()
        assert dialog.use.isEnabled() and not dialog.timer.isActive()
        dialog.choose()
    assert dialog.selected == bulb and dialog.cancelled.is_set()
    assert not dialog.devices and not dialog.timer.isActive()

    waiting = TokenDialog(window, ui["MenuCombo"]())

    def wait_for_cancel(events, cancelled, region):
        events.put(("qr", png))
        cancelled.wait(1)

    with patch("TokenXiaomi.scan", wait_for_cancel):
        waiting.start()
        waiting.reject()
        QTest.qWait(100)
        assert waiting.cancelled.is_set() and waiting.future.done()
        assert not waiting.timer.isActive() and waiting.selected is None

    window.start_first_run()

    def choose(fake_dialog):
        fake_dialog.selected = bulb
        return QDialog.DialogCode.Accepted

    with patch.object(TokenDialog, "exec", choose):
        next(button for button in window.section_dialog.findChildren(QPushButton)
             if button.text() == tr("Obtener token por QR")).click()
    form = window.section_dialog
    assert form.findChild(QLineEdit, "bulbIp").text() == bulb.ip
    secret = form.findChild(QLineEdit, "bulbToken")
    assert secret.text() == bulb.token and secret.echoMode() == QLineEdit.EchoMode.Password
    assert form.findChild(QLineEdit, "xiaomiName").text() == bulb.name
    assert not window.token, "Cloud selection bypassed local Verify and save"
    form.reject()
    window.close()

# Refreshing an existing bulb's token must preserve its local label.
from BombillaLocal import Bulb, save_profile
existing = Bulb()
existing.ip, existing.mac, existing.model = bulb.ip, bulb.mac, bulb.model
save_profile(existing, bulb.token, "Saved label", "Kitchen", "Previous mobile name")
with patch.dict(ui["Window"].__init__.__globals__, {"load_token": lambda: ""}):
    window = ui["Window"]()
window.install_desktop(ui["preferences"](), enable=False)
window.start_first_run()
form = window.section_dialog
form.findChild(QLineEdit, "bulbName").setText("Unsaved custom label")
with patch.object(TokenDialog, "exec", choose):
    next(button for button in form.findChildren(QPushButton) if button.text() == tr("Obtener token por QR")).click()
assert form.findChild(QLineEdit, "bulbName").text() == "Unsaved custom label"
assert form.findChild(QLineEdit, "bulbToken").text() == bulb.token
assert form.findChild(QLineEdit, "xiaomiName").text() == bulb.name
form.reject()
window.close()
print("QR nativo: carga diferida, imagen, selección bilingüe, limpieza e importación sin guardar comprobados")
