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
