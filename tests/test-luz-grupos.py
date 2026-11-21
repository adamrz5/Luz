"""A group retry must never repeat a completed command or recompute a sent step."""
import runpy
import sys
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication

sys.path.insert(0, "src")
import BombillaLocal as local

app = QApplication([])
ui = runpy.run_path("src/Bombilla.pyw")
w = ui["Window"]()
good, lost, incompatible = (Mock(mac=mac) for mac in ("020000000001","020000000002","020000000003"))
for bulb in (good, lost, incompatible):
    bulb.name, bulb.model = bulb.mac, local.MODEL
    bulb.features = local.capabilities(local.MODEL)
incompatible.features = local.capabilities("yeelink.light.mono1")
lost.relative_target.return_value = 4200
good.relative_target.return_value = 4000
lost.control.side_effect = [local.DeviceException(), Mock()]
with patch.dict(w.call.__func__.__globals__, {"load_token": Mock(return_value="synthetic")}):
    report, _ = w.call("room_white", ((good, lost, incompatible), (250,), 0))
    assert [item.state for item in report[2]] == ["applied", "failed", "incompatible"]
    retry, _ = w.call("retry_group", report[2])
    assert [item.state for item in retry[2]] == ["applied", "applied", "incompatible"]
    assert [call.args[2] for call in lost.control.call_args_list] == [4200, 4200]
    assert lost.relative_target.call_count == good.control.call_count == 1
    incompatible.control.assert_not_called()

# Repeated failed/retried batches keep the absolute target and never repeat a success.
for _ in range(50):
    good.control.reset_mock()
    lost.control.reset_mock(side_effect=True)
    lost.control.side_effect = [local.DeviceException(), Mock()]
    with patch.dict(w.call.__func__.__globals__, {"load_token": Mock(return_value="synthetic")}):
        one, _ = w.call("room_white", ((good, lost, incompatible), (250,), 0))
        two, _ = w.call("retry_group", one[2])
    assert two[1] == 2
    assert good.control.call_count == 1
    assert [call.args[2] for call in lost.control.call_args_list] == [4200, 4200]

w.close()

# A disconnected active bulb must not block a room adjustment for the others.
w = ui["Window"]()
w.token = "a7" * 16
w.habitacion_ajustes = (lost, good)
for command, shortcut in (("brightness", 4), ("white", 6)):
    w.dispatch_shortcut(shortcut, lambda: w.ajustar_relativo(command, 1))
    assert w.shortcut_results[shortcut] == "Pendiente", "Offline room adjustment was dropped"
    with patch.object(w, "submit") as submit:
        w.pump()
        action, (bulbs, steps, value) = submit.call_args.args
        assert action == f"room_{command}" and bulbs == (lost, good) and len(steps) == 1
        assert submit.call_args.kwargs["shortcut"] == shortcut
w.close()

# A group can confirm the active light has recovered, even when its controls were offline.
from concurrent.futures import Future
from threading import Event
state = local.LightStatus(True, 53, 2700, None, None, False, 0)
w = ui["Window"]()
for active in (None, state):
    w.future = Future()
    w.in_flight = ("room_brightness", None)
    w.future.set_result(((active, 1, ()), None))
    w.finish()
    assert w.online == (active is not None)
    if active is not None:
        assert w.power.isEnabled() and w.connection_states[w.bulb.mac][1] == ""
w.close()

# Exiting while a member is busy prevents later members from even loading credentials.
w = ui["Window"]()
started, release = Event(), Event()
def block_member(*args, **kwargs):
    started.set()
    assert release.wait(3)
    return state
good.control.side_effect = block_member
lost.control.reset_mock()
credentials = Mock(return_value="synthetic")
with patch.dict(w.call.__func__.__globals__, {"load_token": credentials}):
    w.submit("group", ((good, lost), "color", (1, 2, 3)))
    future = w.future
    try:
        assert started.wait(3)
        w.close()
    finally:
        release.set()
    future.result(timeout=3)
credentials.assert_called_once_with(good.mac)
lost.control.assert_not_called()
