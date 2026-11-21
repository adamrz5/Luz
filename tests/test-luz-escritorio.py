import ctypes
import runpy
import sys
import tempfile
import time
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QDialogButtonBox, QFileDialog, QLineEdit, QInputDialog, QMessageBox, QPushButton, QSystemTrayIcon

sys.path.insert(0, "src")
import BombillaLocal as local
import Diagnostico
import Escenas
from Escritorio import DEFAULT_SHORTCUTS, GlobalShortcuts, ShortcutRecorder, shortcut_parts
from Idioma import set_language, tr

original_configure = GlobalShortcuts.configure
app = QApplication([])
with patch.object(local, "load_token", return_value=""):
    ui = runpy.run_path("src/Bombilla.pyw")
app.setWindowIcon(ui["app_icon"]())
app.setStyle("Fusion")
assert shortcut_parts("Ctrl+Alt+Shift+L") == (0x4007, ord("L"))
for invalid in ("A", "Ctrl+Ctrl+A", "Ctrl+F12"):
    try:
        shortcut_parts(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(invalid)

recorder = ShortcutRecorder(DEFAULT_SHORTCUTS[0])
recorder.show()
QTest.keyClick(recorder, Qt.Key.Key_Backspace)
assert recorder.sequence == DEFAULT_SHORTCUTS[0]
recorder.click()
QTest.keyClick(recorder, Qt.Key.Key_Backspace)
assert recorder.sequence == DEFAULT_SHORTCUTS[0] and recorder.recording
mods = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
QTest.keyClick(recorder, Qt.Key.Key_K, mods)
assert recorder.sequence == "Ctrl+Alt+K" and not recorder.recording
recorder.click()
QTest.keyClick(recorder, Qt.Key.Key_Escape)
assert recorder.sequence == "Ctrl+Alt+K" and not recorder.recording
recorder.close()

with tempfile.TemporaryDirectory(prefix="luz-tests-") as temp:
    folder = Path(temp)
    cfg = QSettings(str(folder / "prefs.ini"), QSettings.Format.IniFormat)
    cfg.setValue("language", "en")
    cfg.setValue("theme", "light")
    cfg.setValue("tray", True)
    # One uncommon binding for the Win32 integration test.
    for i in range(4):
        cfg.setValue(f"hotkey/{i}", "")
    cfg.setValue("hotkey/0", "Ctrl+Alt+Shift+Z")
    cfg.sync()
    cfg = QSettings(str(folder / "prefs.ini"), QSettings.Format.IniFormat)
    set_language(cfg.value("language", "es", type=str))
    assert tr("Temperatura") == "Temperature"

    with patch.object(Escenas, "SCENE_FILE", folder / "scenes.json"), patch.object(
        local, "PROFILE_FILE", folder / "devices.json"
    ), patch.object(Diagnostico, "PROFILE_FILE", folder / "devices.json"), patch.object(
        Diagnostico, "SCENE_FILE", folder / "scenes.json"
    ), patch.dict(
        "os.environ", {"LOCALAPPDATA": temp}
    ):
        w = ui["Window"]()
        w.diagnostico = ui["Diagnostico"](folder)
        with patch.object(GlobalShortcuts, "configure", autospec=True) as configure:
            def register_in_memory(hotkeys, sequences):
                hotkeys.register = Mock(return_value=True)
                hotkeys.unregister = Mock()
                return original_configure(hotkeys, sequences)

            configure.side_effect = register_in_memory
            w.install_desktop(cfg)
        assert app.property("luzAccent") == "#007aff" and w.network.text() == "Connection"
        w.show()
        assert not w.heartbeat.isActive()
        QTest.qWait(80)
        assert w.colors.hex.height() >= 25 and all(field.height() >= 25 for field in w.colors.rgb)
        assert w.colors.degrees.alignment() & Qt.AlignmentFlag.AlignHCenter
        assert all(field.alignment() & Qt.AlignmentFlag.AlignHCenter for field in w.colors.rgb)
        assert not hasattr(w.colors, "saturation") and not hasattr(w.colors, "intensity")

        if QSystemTrayIcon.isSystemTrayAvailable():
            assert w.tray is not None
            w.token = "a"*32
            w.online = True
            w.power_on = True
            w.update_tray()
            assert w.tray_power.text() == "Turn off" and len(w.tray_scenes.actions()) == 3
            with patch.object(w, "schedule") as send:
                w.tray_power.trigger()
                send.assert_called_once_with("desktop_power", None)
            w.power_on = False
            w.update_tray()
            assert w.tray_power.text() == "Turn on"
            w.close()
            assert not w.isVisible() and not w.heartbeat.isActive() and not w.closing
            with patch.object(w, "refresh"):
                w.restore_window()
            assert w.isVisible() and w.heartbeat.isActive()

        assert w.hotkeys is not None and 0x4C00 in w.hotkeys.registered
        callbacks = Mock()
        w.hotkeys.callbacks = (callbacks,)
        assert ctypes.windll.user32.PostThreadMessageW(ctypes.windll.kernel32.GetCurrentThreadId(), 0x0312, 0x4C00, 0)
        QTest.qWait(150)
        callbacks.assert_called_once()

        w.update_connection(True, "Conectada")
        with patch.object(w, "schedule"):
            w.begin_scene_edit(0)
            w.brightness_value.setValue(37)
            w.save_scene_edit()
        assert Escenas.load_scenes()[0].brightness == 37
        red = Escenas.Scene("Roja 🎨", "color", (255, 0, 0), 60)
        backup = folder / "backup.json"
        backup.write_bytes(b"original JSON")
        chosen_backup = folder / "backup.copy"
        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(chosen_backup),"JSON")):
            w.export_scenes()
        assert backup.read_bytes() == b"original JSON"
        assert Escenas.load_scenes(chosen_backup)[0].brightness == 37

        diagnostic = folder / "diagnostic.txt"
        diagnostic.write_bytes(b"original text")
        chosen_diagnostic = folder / "diagnostic.copy"
        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(chosen_diagnostic), "Text")), patch.object(
            QMessageBox, "information"
        ):
            w.exportar_diagnostico()
        assert diagnostic.read_bytes() == b"original text"
        assert chosen_diagnostic.read_text(encoding="utf-8").startswith("Luz ")

        imported = w.scene_slots.copy()
        imported[0] = red
        Escenas.save_scenes(imported, backup)
        with patch.object(QFileDialog, "getOpenFileName", return_value=(str(backup),"JSON")), patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes
        ):
            w.import_scenes()
        assert Escenas.load_scenes()[0] == red
        assert "token" not in backup.read_text(encoding="utf-8").lower()

        before_import = Escenas.SCENE_FILE.read_bytes()
        backup.write_text(
            r'[{"name":"\ud800","mode":"white","level":4000,"brightness":90},null,null]', encoding="utf-8"
        )
        with patch.object(QFileDialog, "getOpenFileName", return_value=(str(backup), "JSON")), patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes
        ) as confirm, patch.object(QMessageBox, "warning") as warning:
            w.import_scenes()
        confirm.assert_not_called()
        warning.assert_called_once()
        assert Escenas.SCENE_FILE.read_bytes() == before_import and w.scene_slots == imported

        Escenas.save_scenes([red, *imported[1:]], backup)
        with patch.object(QFileDialog, "getOpenFileName", return_value=(str(backup), "JSON")), patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes
        ), patch.dict(w.import_scenes.__func__.__globals__, {"save_scenes": Mock(side_effect=ValueError)}), patch.object(
            QMessageBox, "warning"
        ) as warning:
            w.import_scenes()
        warning.assert_called_once()
        assert Escenas.SCENE_FILE.read_bytes() == before_import and w.scene_slots == imported

        for protected in (local.TOKEN_FILE, local.PROFILE_FILE, local.STATE_DIR / "preferencias.ini",
                          local.STATE_DIR / "Luz.lock", folder / "Luz" / "escritorio.lock"):
            prior = protected.read_bytes() if protected.exists() else None
            with patch.object(QFileDialog, "getSaveFileName", return_value=(str(protected), "JSON")), patch.object(
                QMessageBox, "warning"
            ) as warning:
                w.export_scenes()
            warning.assert_called_once()
            assert (protected.read_bytes() if protected.exists() else None) == prior

        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(Escenas.SCENE_FILE), "JSON")):
            w.export_scenes()
        assert Escenas.SCENE_FILE.read_bytes() == before_import

        first = local.Bulb()
        first.ip, first.mac = "192.168.1.10", "001122334455"
        second = local.Bulb()
        second.ip, second.mac = "192.168.1.11", "AABBCCDDEEFF"
        local.save_profile(first, "1"*32, "Desk")
        local.save_profile(second, "2"*32, "Bedroom")
        assert local.load_token() == "2"*32 and local.load_token(first.mac) == "1"*32
        assert local.Bulb(first.mac).name == "Desk"
        assert set(local.profiles_for_display()) == {(first.mac, "Desk"), (second.mac, "Bedroom")}
        saved = local.PROFILE_FILE.read_text(encoding="utf-8")
        assert "1"*32 not in saved and "2"*32 not in saved
        w.pending.clear()
        w.send_timer.stop()
        w.bulb, w.token = local.Bulb(second.mac), "2"*32
        status = SimpleNamespace(is_on=False, color_flowing=False, delay_off=0,
                                 brightness=25, color_temp=2700, rgb=None, hsv=None)
        def fill_connection():
            dialog = app.activeModalWidget()
            devices = dialog.findChild(QComboBox)
            assert devices.currentData() == second.mac
            devices.setCurrentIndex(devices.findData(first.mac))
            alias = dialog.findChild(QLineEdit, "bulbName")
            address = dialog.findChild(QLineEdit, "bulbIp")
            assert alias.text() == "Desk" and address.text() == first.ip
            alias.setText("Living room")
            clipboard = Mock()
            clipboard.text.return_value = "NAME: Original in Xiaomi\nIP: 192.168.1.25\nTOKEN: " + "1"*32
            controls = {button.text(): button for button in dialog.findChildren(QPushButton)}
            with patch.object(QApplication, "clipboard", return_value=clipboard):
                controls[tr("Pegar IP y token")].click()
            clipboard.clear.assert_called_once()
            assert alias.text() == "Living room"
            assert dialog.findChild(QLineEdit, "xiaomiName").text() == "Original in Xiaomi"
            assert not any(text.startswith(tr("Preferencias")) for text in controls)
            buttons = dialog.findChild(QDialogButtonBox)
            buttons.button(QDialogButtonBox.StandardButton.Save).click()

        with patch.dict(w.call.__func__.__globals__, {"load_token": local.load_token}), patch.object(
            local.Bulb, "control", autospec=True, return_value=status
        ) as control:
            QTimer.singleShot(50, fill_connection)
            w.settings()
            for _ in range(100):
                if not w.future:
                    break
                QTest.qWait(15)
                time.sleep(.01)
            assert not w.future and w.bulb.mac == first.mac and w.bulb.ip == "192.168.1.25", (w.note.text(), w.in_flight, w.connection.text(), control.call_count, w.bulb.mac, w.bulb.ip)
            assert w.bulb.name == "Living room" and w.token == "1"*32
            assert local.load_profile()["name"] == "Living room"
            assert local.load_profile()["xiaomi_name"] == "Original in Xiaomi"
            assert w.device_title.text() == "Living room"
            assert "Original in Xiaomi" in w.model_label.text()
            assert local.load_token(second.mac) == "2"*32
            control.assert_called_once()
            assert control.call_args.args[1:] == ("1"*32, "status")
        previous = w.bulb
        with patch.dict(w.call.__func__.__globals__, {"load_token": local.load_token}), patch.object(
            local.Bulb, "control", side_effect=ValueError("wrong device")
        ):
            w.submit("settings", (second.ip, "", True, "Wrong", second.mac, "", ""))
            for _ in range(100):
                if not w.future:
                    break
                QTest.qWait(15)
                time.sleep(.01)
            assert not w.future and w.bulb is previous
            assert local.load_profile()["mac"] == first.mac
        with patch.dict(w.call.__func__.__globals__, {"load_token": local.load_token}), patch.object(
            local.Bulb, "control", autospec=True, side_effect=[status, local.UnsupportedControl("unsupported")]
        ) as control:
            result, _ = w.call("group", ([local.Bulb(first.mac), local.Bulb(second.mac)], "color", (1, 2, 3)))
            assert result[:2] == (status, 1) and result[2][1].state == "incompatible"
            assert [call.args[1:] for call in control.call_args_list] == [
                ("1"*32, "color", (1, 2, 3)), ("2"*32, "color", (1, 2, 3))
            ]
        with patch.object(QInputDialog, "getText", return_value=("Gaming", True)):
            w.rename_scene(0)
        def set_language_in_preferences():
            dialog = app.activeModalWidget()
            assert any(child.accessibleName() == "Gaming" for child in dialog.findChildren(ShortcutRecorder))
            language = dialog.findChildren(QComboBox)[0]
            assert language.maximumWidth() == 192
            language.setCurrentIndex(language.findData("es"))
            dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).click()
        with patch.object(w.hotkeys, "configure", return_value=["occupied"]) as configure, patch.object(w, "restart", return_value=True):
            QTimer.singleShot(50, set_language_in_preferences)
            w.desktop_settings()
            configure.assert_not_called()
        assert cfg.value("language") == "es"
        w.render_status(SimpleNamespace(is_on=True, color_flowing=False, delay_off=0,
                                        brightness=25, color_temp=None, rgb=None, hsv=(120, 100, 25)))
        assert [field.value() for field in w.colors.rgb] == [0, 255, 0]
        failed = Future()
        failed.set_exception(local.UnsupportedControl("unsupported"))
        w.future, w.in_flight = failed, ("color", (1, 2, 3))
        w.pending["power"] = False
        with patch.object(w, "pump") as pump:
            w.finish()
            pump.assert_called_once()
        assert w.pending == {"power": False}
        w.pending.clear()
        checked = Future()
        checked.set_result((status, None))
        w.future, w.in_flight = checked, ("check", None)
        w.finish()
        assert "Compatibility verified" in w.note.text() and w.bulb.model in w.note.text()

        w.close()
        assert w.closing and not w.hotkeys.registered
        set_language("es")
        cfg.setValue("language", "en")
        reverse = ui["Window"]()
        reverse.install_desktop(cfg, enable=False)
        reverse.tray = Mock()
        reverse.show()
        reverse.close()
        assert reverse.closing
        reverse.tray.hide.assert_called_once()

print("Tray, power, shortcuts, language, theme, backups and encrypted profiles verified")
