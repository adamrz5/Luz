"""Win32 failures must leave the active registration intact."""
import sys
from unittest.mock import Mock
sys.path.insert(0, "src")
from Escritorio import GlobalShortcuts
keys = GlobalShortcuts((Mock(),))
keys.register = Mock(return_value=True)
keys.unregister = Mock()
keys.registration_error = Mock(return_value=1409)
assert keys.configure(("Ctrl+Alt+F5",)) == []
saved = keys.registered.copy()
keys.register.return_value = False
assert keys.configure(("Ctrl+Alt+F9",)) == ["Ctrl+Alt+F9"]
assert keys.registered == saved
assert keys.statuses[0] == ("occupied", 1409)
keys.unregister.assert_not_called()
keys.register.return_value = True
assert keys.configure(("Ctrl+Alt+F9",)) == []
assert list(keys.registered.values()) == ["Ctrl+Alt+F9"]
assert keys.statuses[0] == ("registered", 0)
keys.clear()

keys.registration_error.return_value = 5
keys.register.return_value = False
assert keys.configure(("Ctrl+Shift+F10",)) == ["Ctrl+Shift+F10"]
assert keys.statuses[0] == ("invalid", 5)
assert keys.configure(("",)) == [] and keys.statuses[0] == ("unassigned", 0)

# A temporary probe is released and never replaces an active or drafted binding.
keys.register.return_value = True
keys.unregister.reset_mock()
assert keys.available("Ctrl+Shift+F9", ("Ctrl+Alt+F9",))
keys.unregister.assert_called_once_with(None, 0x5FFF)
assert not keys.available("Ctrl+Shift+F9", ("Shift+Ctrl+F9",))

import ctypes
from unittest.mock import patch
from Escritorio import altgr_conflict
fake_layout = Mock()
fake_layout.GetKeyboardLayout.return_value = 1
fake_layout.MapVirtualKeyExW.return_value = 9
with patch.object(ctypes.windll, "user32", fake_layout):
    fake_layout.ToUnicodeEx.return_value = 1
    assert altgr_conflict("Ctrl+Alt+8")
    assert not altgr_conflict("Ctrl+Shift+F9")
    fake_layout.ToUnicodeEx.return_value = 0
    assert not altgr_conflict("Ctrl+Alt+8")
