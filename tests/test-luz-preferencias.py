"""Preference saves use an isolated state and register no Windows hotkeys."""
import runpy
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication, QDialogButtonBox

sys.path.insert(0, "src")
import BombillaLocal as local

app = QApplication([])
with TemporaryDirectory(prefix="luz-tests-") as folder:
    state = Path(folder)
    with patch.multiple(local, STATE_DIR=state, IP_FILE=state/"ip", PROFILE_FILE=state/"profiles",
                        TOKEN_FILE=state/"token"):
        ui = runpy.run_path("src/Bombilla.pyw")
        recorder = ui["ShortcutRecorder"]
        window = ui["Window"]()
        settings = QSettings(str(state/"prefs.ini"), QSettings.Format.IniFormat)
        settings.setValue("hotkey/0", "Ctrl+Alt+Shift+L")
        window.install_desktop(settings, enable=False)
        assert window.shortcut_values()[0] == "Ctrl+Alt+F5"
        seen = []

        def save():
            dialog = app.activeModalWidget()
            try:
                entries = dialog.findChildren(recorder)
                seen.append((len(entries), dialog.height()))
                entries[0].sequence = "Ctrl+Alt+Shift+L"
                dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).click()
            finally:
                if dialog.isVisible():
                    dialog.reject()

        QTimer.singleShot(100, save)
        window.desktop_settings()
        assert seen and seen[0][0] == 8 and seen[0][1] < 600
        assert settings.value("hotkey_schema", type=int) == 2
        assert window.shortcut_values()[0] == "Ctrl+Alt+Shift+L"
        window.close()

print("Preferencias: ocho atajos en el diseño compacto y guardado sin remigración")

from concurrent.futures import Future
from PySide6.QtWidgets import QComboBox, QLabel
from Idioma import set_language

with TemporaryDirectory(prefix="luz-tests-") as folder:
    state = Path(folder)
    with patch.multiple(local, STATE_DIR=state, IP_FILE=state/"ip", PROFILE_FILE=state/"profiles",
                        TOKEN_FILE=state/"token"), patch("Escritorio.STATE_DIR", state):
        for old_language, new_language in (("es", "en"), ("en", "es")):
            set_language(old_language)
            window = ui["Window"]()
            settings = QSettings(str(state / "prefs.ini"), QSettings.Format.IniFormat)
            settings.setValue("language", old_language)
            window.install_desktop(settings, enable=False)
            window.show_section(2)
            dialog = window.section_dialog
            language = dialog.findChildren(QComboBox)[0]
            notice_text = ("Luz se reiniciará para aplicar el idioma" if old_language == "es"
                           else "Luz will restart to apply the language")
            notices = [item for item in dialog.findChildren(QLabel) if item.text() == notice_text]
            assert len(notices) == 1
            notice = notices[0]
            assert notice.objectName() == "muted" and notice.wordWrap()
            assert notice.isHidden()
            with patch.object(window, "restart", return_value=True, create=True) as restart:
                language.setCurrentIndex(language.findData(new_language))
                assert not notice.isHidden()
                restart.assert_not_called()
                assert settings.value("language") == old_language
                language.setCurrentIndex(language.findData(old_language))
                assert notice.isHidden()
                language.setCurrentIndex(language.findData(new_language))
                assert not notice.isHidden()
                window.future = Future()
                dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).click()
                assert settings.value("language") == old_language
                restart.assert_not_called()
                assert window.section_dialog is dialog
                window.future = None
                dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).click()
                restart.assert_called_once()
                assert settings.value("language") == new_language
            window.close()
        set_language("es")

        # A failed launch keeps the current process alive; a successful launch releases it.
        window = ui["Window"]()
        for frozen in (False, True):
            for succeeded in (False, True):
                with patch.object(sys, "frozen", frozen, create=True), \
                     patch.object(sys, "argv", ["Luz", "--oculto", "--sin-bandeja"]), \
                     patch.object(ui["QProcess"], "startDetached", return_value=(succeeded, 123)) as launch, \
                     patch.object(window, "quit_desktop") as quit_app:
                    assert window.restart() is succeeded
                    args = launch.call_args.args
                    assert args[0] == sys.executable
                    expected = [] if frozen else [str(Path("src/Bombilla.pyw").resolve())]
                    assert args[1] == expected + ["--restart", "--sin-bandeja"]
                    assert quit_app.call_count == int(succeeded)
        window.close()
        print("Language: both directions restart after saving, busy commands protected, launch failure preserves process")
