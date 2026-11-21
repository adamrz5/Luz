import runpy,sys,tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QInputDialog, QMenu, QMessageBox
sys.path.insert(0,"src")
import BombillaLocal, Escenas
with patch.object(BombillaLocal,"load_token",return_value=""):
    gui=runpy.run_path("src/Bombilla.pyw")
app=QApplication([])
app.setStyle("Fusion")
app.setStyleSheet(gui["STYLE"])
app.setWindowIcon(gui["app_icon"]())
with tempfile.TemporaryDirectory(prefix="luz-tests-") as temp:
    Escenas.SCENE_FILE=Path(temp)/"escenas.json"
    w=gui["Window"]()
    assert not w.heartbeat.isActive(), "La ventana oculta no debe sondear la red"
    w.update_connection(True,"Conectada")
    w.schedule=Mock()
    w.token = "a7" * 16
    w.show()
    QTest.qWait(80)
    assert w.heartbeat.isActive()
    w.resize(870, 660)
    assert (w.width(), w.height()) == (870, 660)
    QTest.qWait(30)
    origin = QPoint(0, 0)
    color_geometry = (w.colors.hue.mapToGlobal(origin), w.colors.degrees.width(),
                      w.effects_label.mapToGlobal(origin))
    for _ in range(3):
        w.show_mode(1)
        QTest.qWait(15)
        assert color_geometry == (w.temperature.mapToGlobal(origin), w.kelvin_value.width(),
                                  w.effects_label.mapToGlobal(origin))
        w.show_mode(0)
        QTest.qWait(15)
    w.show_mode(1)
    p=w.temperature
    QTest.mouseClick(p,Qt.MouseButton.LeftButton,pos=QPoint(10,p.height()//2))
    assert 1700<=p.value()<1800
    assert w.kelvin_value.value()==p.value()
    w.schedule.assert_called_with("white",p.value())
    QTest.mousePress(p, Qt.MouseButton.LeftButton, pos=QPoint(10, p.height() // 2))
    QTest.mouseRelease(p, Qt.MouseButton.LeftButton, pos=QPoint(p.width() - 1, p.height() // 2))
    assert p.value() == p.maximum()
    assert w.kelvin_value.value() == p.maximum()
    w.schedule.assert_called_with("white", p.maximum())
    w.amber.click()
    assert w.pages.currentIndex()==0
    w.schedule.assert_called_with("color",(255,121,0))
    labels = []
    def choose_edit():
        menu = app.activePopupWidget()
        if isinstance(menu, QMenu):
            actions = [action for action in menu.actions() if not action.isSeparator()]
            labels.extend(action.text() for action in actions)
            actions[0].trigger()
            menu.close()
    QTimer.singleShot(150, choose_edit)
    w.scenes[0].customContextMenuRequested.emit(QPoint(10, 10))
    assert labels == ["Editar escena", "Renombrar", "Vaciar"]
    assert w.editing_scene == 0
    assert not w.power.isEnabled() and w.brightness.isEnabled() and w.brightness_value.isEnabled()
    w.brightness.setValue(57)
    before=w.schedule.call_count
    w.show_mode(0)
    plane=w.colors.hue
    QTest.mousePress(plane,Qt.MouseButton.LeftButton,pos=QPoint(30,22))
    QTest.mouseMove(plane,QPoint(150,22))
    QTest.mouseRelease(plane,Qt.MouseButton.LeftButton,pos=QPoint(150,22))
    assert w.editing_scene==0
    assert w.schedule.call_count==before
    QTest.mouseClick(plane,Qt.MouseButton.LeftButton,pos=QPoint(180,22))
    assert w.editing_scene == 0
    assert w.schedule.call_count == before
    w.brightness_value.setValue(42)
    assert w.lamp.level == w.brightness.value() == 42
    w.save_scene_edit()
    assert w.editing_scene is None
    edited=Escenas.load_scenes()[0]
    assert edited.mode=="color" and edited.brightness==42 and edited.name=="Lectura"
    w.schedule.assert_called_with("scene",edited.command())
    with patch.object(QInputDialog,"getText",return_value=("Jugar",True)):
        w.rename_scene(0)
    assert Escenas.load_scenes()[0].name=="Jugar"
    def answer_vaciar(text):
        modal = app.activeModalWidget()
        if isinstance(modal, QMessageBox):
            next(button for button in modal.buttons() if button.text() == text).click()
    QTimer.singleShot(150, lambda: answer_vaciar("Cancelar"))
    w.clear_scene(1)
    assert Escenas.load_scenes()[1].name == "Cine"
    before = w.schedule.call_count
    QTimer.singleShot(150, lambda: answer_vaciar("Vaciar"))
    w.clear_scene(1)
    restored = Escenas.load_scenes()
    assert len(restored)==3 and restored[1] == Escenas.WHITE_SCENE
    assert w.schedule.call_count == before
    assert w.scenes[1].text().startswith("Blanco")
    w.activate_scene(1)
    w.schedule.assert_called_with("scene", ("white", 4000, 100))
    w.begin_scene_edit(1)
    w.brightness.setValue(23)
    w.cancel_scene_edit()
    assert Escenas.load_scenes()[1] == Escenas.WHITE_SCENE
    legacy = Path(temp) / "legacy.json"
    legacy.write_text("[null, null, null]", encoding="utf-8")
    assert Escenas.load_scenes(legacy) == [Escenas.WHITE_SCENE] * 3
    if not w.isMaximized(): w.showMaximized()
    QTest.qWait(100)
    assert w.editor_card.width()>0 and w.flow.isVisible()
    w.toggle_fullscreen()
    QTest.qWait(100)
    assert w.isFullScreen() and w.power.isVisible() and w.timer.isVisible()
    assert w.light.width()+w.editor_card.width()<=1300
    w.show_mode(1)
    assert w.temperature.height() == 44
    if w.stacked_lights:
        assert w.light.geometry().bottom() < w.editor_card.geometry().top()
        assert w.light.geometry().left() == w.editor_card.geometry().left()
    else:
        assert w.light.geometry().top() == w.editor_card.geometry().top()
        assert w.light.geometry().bottom() == w.editor_card.geometry().bottom()
    assert w.scenes_card.geometry().left() == w.light.geometry().left()
    assert w.scenes_card.geometry().right() == w.editor_card.geometry().right()
    assert w.kelvin_value.mapToGlobal(QPoint(0,0)).y() < w.temperature.mapToGlobal(QPoint(0,0)).y()
    w.grab().save("tests/resultados/luz-blanco-pantalla-completa.png")
    w.escape()
    QTest.qWait(100)
    assert not w.isFullScreen() and w.isMaximized()
    w.bulb.model = "yeelink.light.ct2"
    w.update_device()
    QTest.qWait(30)
    assert w.pages.currentIndex() == 1 and w.temperature.minimum() == 2700
    assert w.white_presets[0].isHidden() and w.amber.isHidden()
    w.bulb.model = "yeelink.light.mono1"
    w.update_device()
    assert w.pages.currentIndex() == 2 and w.flow.isHidden()
    w.close()
print("Blanco, ambar, arrastre, guardado, renombrado, confirmacion de vaciado, migracion y pantalla completa verificados")
