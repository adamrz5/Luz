from concurrent.futures import Future
import runpy
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from construct import ChecksumError
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLabel, QLineEdit, QListWidget, QPushButton

sys.path.insert(0, "src")
import BombillaLocal
from Idioma import set_language

with patch.object(BombillaLocal, "load_token", return_value=""):
    ui = runpy.run_path("src/Bombilla.pyw")
app = QApplication([])
window = ui["Window"]()
window.show()
ip = QLineEdit("192.168.1.1")
with TemporaryDirectory(prefix="luz-tests-") as carpeta:
    window.diagnostico = ui["Diagnostico"](Path(carpeta))
    with patch.dict(window.buscar_bombillas.__func__.__globals__, {
        "descubrir_bombillas": lambda: (SimpleNamespace(ip="192.168.1.80", model=None, mac=None),),
    }):
        def elegir():
            dialog = app.activeModalWidget()
            lista = dialog.findChild(QListWidget)
            if not lista.count():
                dialog.reject()
                return
            lista.setCurrentRow(0)
            next(button for button in dialog.findChildren(QPushButton)
                 if button.text() == "Usar esta IP").click()

        QTimer.singleShot(250, elegir)
        window.buscar_bombillas(window, ip)
        assert ip.text() == "192.168.1.80"
        assert not window.token

    causas = (
        BombillaLocal.BombillaNoEncontrada(),
        BombillaLocal.IdentidadIncorrecta(),
        TimeoutError("detalle privado"),
        ChecksumError("detalle privado"),
    )
    for idioma in ("es", "en"):
        set_language(idioma)
        for error in causas:
            future = Future()
            future.set_exception(error)
            window.in_flight = ("check", None)
            window.future = future
            window.finish()
            mensaje = BombillaLocal.mensaje_error_conexion(error)
            assert mensaje and window.note.text() == ui["tr"](mensaje)
            assert "detalle privado" not in window.note.text()
            if idioma == "en":
                assert window.note.text() != mensaje
    set_language("es")
    assert window.brightness_value.width() < 72
    window.show_section(1)
    app.processEvents()
    dialog = window.section_dialog
    feedback = dialog.findChild(QLabel, "connectionFeedback")
    assert feedback is not None
    save = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save)
    address = dialog.findChild(QLineEdit, "bulbIp")
    secret = dialog.findChild(QLineEdit, "bulbToken")
    save.click()
    assert "IPv4" in feedback.text() and dialog.focusWidget() is address, feedback.text()
    address.setText("192.0.2.20")
    save.click()
    assert "token" in feedback.text() and dialog.focusWidget() is secret, feedback.text()
    secret.setText("a7" * 16)
    with patch.object(window, "submit") as submit:
        save.click()
        submit.assert_called_once()
    assert window.section_dialog is dialog and not save.isEnabled()
    for index, error in enumerate(causas):
        if index:
            with patch.object(window, "submit"):
                save.click()
        future = Future()
        future.set_exception(error)
        window.in_flight = ("settings", submit.call_args.args[1])
        window.future = future
        window.finish()
        assert window.section_dialog is dialog and save.isEnabled()
        assert feedback.text() == BombillaLocal.mensaje_error_conexion(error)
        assert address.text() == "192.0.2.20" and secret.text() == "a7" * 16
    dialog.reject()
window.close()
print("Búsqueda: resultados del trabajador y selección de IP sin autenticación comprobadas")
