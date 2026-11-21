import re
import sys
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from functools import partial
from ipaddress import IPv4Address
from pathlib import Path
from time import monotonic, strftime

# Load the device stack before PySide6 installs its import hook.
from BombillaLocal import COMMAND_DEADLINE, FLOW_PRESETS, MODEL, PROFILE_FILE, capabilities, Bulb, CambioNoAplicado, UnsupportedControl, codigo_error_conexion, descubrir_bombillas, mensaje_error_conexion, load_token, parse_extractor_clipboard, profiles_for_display, save_profile

from miio import DeviceException

from PySide6.QtCore import QEasingCurve, QEvent, QVariantAnimation, QLockFile, QPointF, QProcess, QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractButton, QApplication, QButtonGroup, QCheckBox, QComboBox, QCompleter, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSlider, QSpinBox, QStackedWidget,
    QStyle, QStyleOptionButton, QStyleOptionSlider, QSystemTrayIcon, QToolButton, QVBoxLayout, QWidget,
)

from Escritorio import (
    AJUSTES_RELATIVOS, DEFAULT_SHORTCUTS, PASOS_BRILLO, PASO_TEMPERATURA,
    GlobalShortcuts, ShortcutRecorder, altgr_conflict, actualizar_inicio_windows, comando_inicio_windows,
    desktop_lock, guardar_inicio_windows, inicio_windows, migrate_shortcuts, preferences, shortcut_parts,
)
from Diagnostico import Diagnostico
from Idioma import EN, current_language, set_language, tr
from Tema import FOCUS_HEIGHT, MOTION_MS, PANEL_RADIUS, STYLE, animations_enabled, apply_fonts, apply_palette, colors_for, high_contrast, theme_style, window_backdrop

from Escenas import DEFAULT_SCENES, WHITE_SCENE, load_scenes, save_scenes

MODELOS_CATALOGO = {
    "color5": ("Xiaomi Mi LED Smart Bulb Essential (Luz blanca y de color)", "MJDPL01YL"),
    "color3": ("Xiaomi Mi LED Smart Bulb (Luz blanca y de color)", "MJDP02YL"),
    "color7": ("Xiaomi Mi Smart LED Bulb (B22)", "MJDPL02YL"),
    "color1": ("Yeelight LED Bulb (Color)", "YLDP02YL / YLDP03YL"),
    "color2": ("Yeelight LED Bulb (Color, 2.ª generación)", "YLDP06YL"),
    "color4": ("Yeelight LED Bulb 1S (Color)", "YLDP13YL / YLDP04YL"),
    "colorc": ("Yeelight GU10 Smart Bulb W1 (Multicolor)", "YLDP004-A"),
    "mono1": ("Yeelight LED Bulb (Blanco fijo)", "YLDP01YL"),
    "mono5": ("Yeelight Smart LED Filament Bulb", "YLDP12YL"),
    "monob": ("Yeelight GU10 Smart Bulb W1 (Blanco fijo)", "YLDP004"),
    "color": ("Yeelight LED Bulb (Color)", ""),
    "ct_bulb": ("Yeelight LED Bulb (Blanco regulable)", ""),
    "ct2": ("Yeelight LED Bulb (Blanco regulable)", ""),
}
FICHAS_CATALOGO = {
    "color5": "https://www.mi.com/es/product/mi-led-smart-bulb-essential-white-and-color/specs/",
    "color3": "https://www.mi.com/in/mi-led-smart-bulb/specs/",
    "color7": "https://github.com/rytilahti/python-miio/issues/1425",
    "mono5": "https://www.yeelight.com/en_US/product/flute",
}
FICHA_CONTROLADOR = "https://yeelight.readthedocs.io/en/stable/devices.html"


class MenuCombo(QComboBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self.palette().text().color(), 1.5))
        x, y = self.width() - 15, self.height() / 2
        arrow = QPainterPath(QPointF(x - 4, y - 2))
        arrow.lineTo(x, y + 2)
        arrow.lineTo(x + 4, y - 2)
        painter.drawPath(arrow)


class ToggleSwitch(QCheckBox):
    def __init__(self, text):
        super().__init__(text)
        self.setMinimumHeight(FOCUS_HEIGHT)

    def hitButton(self, position):
        return self.rect().contains(position)

    def paintEvent(self, event):
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.state &= ~QStyle.StateFlag.State_HasFocus
        painter = QPainter(self)
        self.style().drawControl(QStyle.ControlElement.CE_CheckBox, option, painter, self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        app = QApplication.instance()
        track = QRectF(3, (self.height() - 20) / 2, 32, 20)
        checked = self.isChecked()
        contrast = app.property("luzHighContrast")
        accent = palette.highlight().color() if contrast else QColor(app.property("luzAccent"))
        edge = palette.windowText().color() if contrast else QColor(app.property("luzMuted"))
        painter.setPen(QPen(edge, 1))
        painter.setBrush(accent if checked and self.isEnabled() else palette.window().color())
        painter.drawRoundedRect(track, 10, 10)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(palette.highlightedText().color() if checked and contrast else edge if contrast else Qt.GlobalColor.white)
        painter.drawEllipse(QPointF(track.right() - 10 if checked else track.left() + 10, track.center().y()), 7, 7)
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(edge, 1.5))
            painter.drawRoundedRect(track.adjusted(-2, -2, 2, 2), 12, 12)


def label(text="", role=""):
    result = QLabel(text)
    result.setTextFormat(Qt.TextFormat.PlainText)
    result.setObjectName(role)
    return result


def row(*widgets, spacing=10):
    result = QHBoxLayout()
    result.setSpacing(spacing)
    for widget in widgets:
        if widget is None:
            result.addStretch()
        else:
            result.addWidget(widget)
    return result


def panel():
    box = QFrame()
    box.setObjectName("card")
    layout = QVBoxLayout(box)
    layout.setContentsMargins(21, 19, 21, 19)
    layout.setSpacing(12)
    return box, layout


def button(text, action, role=""):
    result = QPushButton(text)
    result.setCursor(Qt.CursorShape.PointingHandCursor)
    result.setObjectName(role)
    result.setMinimumHeight(FOCUS_HEIGHT)
    result.clicked.connect(action)
    return result


def color_from_hsv(hsv):
    hue, saturation, _ = hsv
    return QColor.fromHsvF(hue / 360, saturation / 100, 1)


def white_preview(kelvin):
    fraction = (kelvin - 1700) / 4800
    return QColor.fromRgbF(1 - .22 * fraction, .58 + .40 * fraction, .31 + .69 * fraction)


def bulb_path():
    path = QPainterPath(QPointF(50, 14))
    path.cubicTo(74, 14, 88, 31, 87, 51)
    path.cubicTo(86, 67, 72, 74, 68, 88)
    path.quadTo(67, 96, 60, 96)
    path.lineTo(40, 96)
    path.quadTo(33, 96, 32, 88)
    path.cubicTo(28, 74, 14, 67, 13, 51)
    path.cubicTo(12, 31, 26, 14, 50, 14)
    path.closeSubpath()
    return path


def app_icon():
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128):
        image = QPixmap(size, size)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(size / 128, size / 128)
        background = QLinearGradient(0, 0, 112, 128)
        background.setColorAt(0, QColor("#303031"))
        background.setColorAt(1, QColor("#171718"))
        painter.setPen(QPen(QColor("#555353"), 2))
        painter.setBrush(background)
        painter.drawRoundedRect(QRectF(2, 2, 124, 124), 28, 28)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        ring = QPen(QColor("#f9f4ed"), 9)
        ring.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(ring)
        painter.drawArc(QRectF(33, 33, 62, 62), 85 * 16, 285 * 16)

        beam = QPainterPath(QPointF(53, 76))
        beam.lineTo(72, 46)
        beam.quadTo(74, 43, 78, 44)
        beam.lineTo(99, 50)
        beam.quadTo(103, 51, 99, 55)
        beam.lineTo(59, 80)
        beam.quadTo(51, 85, 53, 76)
        beam.closeSubpath()
        amber = QLinearGradient(56, 81, 96, 44)
        amber.setColorAt(0, QColor("#eeaa75"))
        amber.setColorAt(1, QColor("#ffe5bb"))
        painter.fillPath(beam, amber)
        painter.end()
        icon.addPixmap(image)
    return icon


def navigation_icon(index, color):
    pixmap = QPixmap(20, 20)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(color, 1.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    if index == 0:
        painter.drawEllipse(QRectF(5, 2, 10, 10))
        painter.drawLine(8, 15, 12, 15)
        painter.drawLine(9, 18, 11, 18)
    elif index == 1:
        for size in (6, 11, 16):
            painter.drawArc(QRectF(10 - size / 2, 14 - size / 2, size, size), 45 * 16, 90 * 16)
        painter.drawPoint(10, 15)
    elif index == 2:
        for y, x in ((5, 7), (10, 13), (15, 9)):
            painter.drawLine(3, y, x - 2, y)
            painter.drawLine(x + 2, y, 17, y)
            painter.drawEllipse(QRectF(x - 2, y - 2, 4, 4))
    else:
        painter.drawEllipse(QRectF(2, 2, 16, 16))
        painter.drawText(QRectF(2, 2, 16, 16), Qt.AlignmentFlag.AlignCenter, "?")
    painter.end()
    return QIcon(pixmap)


def panel_form(parent, title, *, scrollable=False, single_column=False):
    dialog = QDialog(parent)
    dialog.setObjectName("panel")
    dialog.setWindowTitle(title)
    dialog.setMinimumWidth(480)
    body = dialog
    if scrollable:
        body = QWidget()
        scroll = QScrollArea(dialog)
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)
        dialog.resize(680, min(560, parent.screen().availableGeometry().height() - 64))
    heading = label(title, "dialogTitle")
    if single_column:
        form = QVBoxLayout(body)
        form.setSpacing(12)
        form.addWidget(heading)
    else:
        form = QFormLayout(body)
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.addRow(heading)
    form.setContentsMargins(24, 20, 24, 22)
    apply_fonts(QApplication.instance(), dialog)
    return dialog, form


def field_label(form, title, widget):
    caption = label(title, "formLabel")
    caption.setBuddy(widget)
    if isinstance(widget, QComboBox):
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    form.addRow(caption, widget)


class LampView(QAbstractButton):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(168)
        self.color = QColor("#ffe0a4")
        self.level = 55
        self.lit = False
        self.display_color = None
        self.glass = QLinearGradient(22, 20, 82, 92)
        self.bulb_outline = bulb_path()
        self.glass_pen = QPen(QColor(255, 255, 255, 85), 1)
        self.metal = QLinearGradient(33, 0, 67, 0)
        for stop, shade in ((0, "#4a4657"), (.45, "#c5bfce"), (1, "#565163")):
            self.metal.setColorAt(stop, QColor(shade))
        self.base_pen = QPen(QColor("#3d3948"), 1.5)
        self.transition = QVariantAnimation(self)
        self.transition.setDuration(MOTION_MS)
        self.transition.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.transition.valueChanged.connect(self.set_glass)

    def set_glass(self, color):
        if color == self.display_color:
            return
        self.display_color = color
        self.glass.setColorAt(0, color.lighter(143))
        self.glass.setColorAt(.50, color)
        self.glass.setColorAt(1, color.darker(175))
        super().update()

    def update(self, *, animate=True):
        app = QApplication.instance()
        off = QColor(app.property("luzBulbOff") or self.palette().mid().color())
        level = self.level / 100 if self.lit else 0
        color = self.color
        intensity = max(color.redF(), color.greenF(), color.blueF()) * level
        target = QColor.fromRgbF(
            off.redF() * (1 - intensity) + color.redF() * level,
            off.greenF() * (1 - intensity) + color.greenF() * level,
            off.blueF() * (1 - intensity) + color.blueF() * level,
        )
        if not animate or not self.isVisible() or not app.property("luzMotion") or self.display_color is None:
            self.transition.stop()
            self.set_glass(target)
        elif self.transition.endValue() != target:
            self.transition.stop()
            self.transition.setStartValue(self.display_color)
            self.transition.setEndValue(target)
            self.transition.start()

    def hideEvent(self, event):
        self.transition.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.display_color = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        shape = QPainterPath()
        shape.addRoundedRect(bounds, PANEL_RADIUS, PANEL_RADIUS)
        app = QApplication.instance()
        painter.fillPath(shape, QColor(app.property("luzPreview")) if app.property("luzPreview")
                         else self.palette().alternateBase().color())
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(self.palette().highlight().color(), 2))
            painter.drawPath(shape)
        painter.setClipPath(shape)
        center = QPointF(bounds.center().x(), bounds.height() * .47)
        scale = min(2.35, max(.75, min(bounds.height()/185, bounds.width()/255)))
        painter.translate(center.x()-50*scale, center.y()-57*scale)
        painter.scale(scale,scale)
        painter.setPen(self.glass_pen)
        painter.setBrush(self.glass)
        painter.drawPath(self.bulb_outline)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.metal)
        painter.drawRoundedRect(QRectF(34, 96, 32, 21), 6, 6)
        painter.setPen(self.base_pen)
        for y in (101, 106, 111):
            painter.drawLine(QPointF(36, y), QPointF(64, y-2))


class BrightnessSlider(QSlider):
    def __init__(self):
        super().__init__(Qt.Orientation.Horizontal)
        self.drag_offset = 0

    def select_position(self, position):
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        style = self.style()
        control = QStyle.ComplexControl.CC_Slider
        handle = QStyle.SubControl.SC_SliderHandle
        option.sliderPosition = self.minimum()
        start = style.subControlRect(control, option, handle, self).center().x()
        option.sliderPosition = self.maximum()
        end = style.subControlRect(control, option, handle, self).center().x()
        fraction = (position.x() - self.drag_offset - start) / max(1, abs(end - start))
        if end < start:
            fraction = -fraction
        self.setValue(round(self.minimum() + fraction * (self.maximum() - self.minimum())))

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        handle = self.style().subControlRect(QStyle.ComplexControl.CC_Slider, option,
                                            QStyle.SubControl.SC_SliderHandle, self)
        on_handle = handle.contains(event.position().toPoint())
        self.drag_offset = event.position().x() - handle.center().x() if on_handle else 0
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.setSliderDown(True)
        if not on_handle:
            self.select_position(event.position())
        event.accept()

    def mouseMoveEvent(self, event):
        if self.isSliderDown() and event.buttons() & Qt.MouseButton.LeftButton:
            self.select_position(event.position())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.isSliderDown():
            self.select_position(event.position())
            self.setSliderDown(False)
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class SpectrumSlider(QSlider):
    """Compact, keyboard-accessible gradient control shared by hue and white."""
    committed = Signal()
    picked = Signal()

    def __init__(self, stops):
        super().__init__(Qt.Orientation.Horizontal)
        self.stops = stops
        self.gradient = self.make_gradient()
        self.press_position = None
        self.setFixedHeight(FOCUS_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def track(self):
        return QRectF(11, (self.height()-8)/2, max(1, self.width()-22), 8)

    def make_gradient(self):
        track = self.track()
        gradient = QLinearGradient(track.topLeft(), track.topRight())
        for stop, color in self.stops:
            gradient.setColorAt(stop, QColor(color))
        return gradient

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.gradient = self.make_gradient()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = self.track()
        painter.setPen(Qt.PenStyle.NoPen)
        if QApplication.instance().property("luzHighContrast"):
            painter.setBrush(self.palette().windowText())
        else:
            painter.setBrush(self.gradient)
        painter.drawRoundedRect(track, 4, 4)
        fraction = (self.value()-self.minimum())/max(1, self.maximum()-self.minimum())
        dot = QPointF(track.left()+track.width()*fraction, track.center().y())
        painter.setBrush(self.palette().window())
        painter.setPen(QPen(self.palette().windowText().color(), 2))
        painter.drawEllipse(dot, 8, 8)
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(self.palette().windowText().color(), 1))
            painter.drawRoundedRect(track.adjusted(-3,-3,3,3), 13, 13)

    @staticmethod
    def is_click(start, end):
        return (start-end).manhattanLength() < QApplication.startDragDistance()

    def select(self, event):
        track = self.track()
        fraction = (event.position().x()-track.left())/max(1, track.width())
        self.setValue(round(self.minimum()+(self.maximum()-self.minimum())*fraction))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.press_position = event.position()
            self.setFocus()
            self.setSliderDown(True)
            old = self.value()
            self.select(event)
            if old == self.value():
                self.valueChanged.emit(old)
            self.committed.emit()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            if self.press_position is not None and not self.is_click(self.press_position, event.position()):
                self.press_position = None
            self.select(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.select(event)
            self.setSliderDown(False)
            self.committed.emit()
            if self.press_position is not None and self.is_click(self.press_position, event.position()):
                self.picked.emit()
            self.press_position = None


def spectrum_layout(page, caption, exact, slider):
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(9)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    exact.setFixedWidth(88)
    layout.addLayout(row(label(caption, "muted"), None, exact))
    layout.addWidget(slider)
    return layout


class ColorEditor(QWidget):
    changed = Signal(QColor)

    def __init__(self):
        super().__init__()
        self.hue = SpectrumSlider(tuple((step/6, QColor.fromHsvF((step%6)/6, 1, 1))
                                        for step in range(7)))
        self.hue.setRange(0, 359)
        self.tone, self.sat, self.value = 0., 1., 1.
        self.hue.setAccessibleName(tr("Tono"))
        self.hue.setAccessibleDescription(tr("Usa las flechas, Inicio, Fin, Re Pág o Av Pág para ajustar el valor."))
        self.hue.setCursor(Qt.CursorShape.PointingHandCursor)
        self.degrees = self.number(tr("Tono"), 359, "°")
        layout = spectrum_layout(self, tr("Tono"), self.degrees, self.hue)
        codes = QHBoxLayout()
        codes.setSpacing(7)
        self.hex = QLineEdit()
        self.hex.setMaxLength(7)
        self.hex.setAccessibleName(tr("Color hexadecimal"))
        self.hex.setToolTip(tr("Introduce #RRGGBB y pulsa Intro. Ejemplo: #176CE3."))
        self.hex.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hex.setMinimumWidth(84)
        self.rgb = [self.number(channel, 255) for channel in (tr("Rojo"),tr("Verde"),tr("Azul"))]
        for name, widget in zip(("HEX","R","G","B"), (self.hex,*self.rgb)):
            field = QVBoxLayout()
            field.setSpacing(4)
            caption = label(name, "muted")
            caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
            field.addWidget(caption)
            field.addWidget(widget)
            codes.addLayout(field, 1)
        layout.addLayout(codes)
        self.hue.valueChanged.connect(self.set_hue)
        self.degrees.valueChanged.connect(self.set_hue)
        self.hex.editingFinished.connect(self.hex_input)
        for channel in self.rgb:
            channel.valueChanged.connect(self.rgb_input)
        self.set_color(QColor("#7665ff"))

    def number(self, name, maximum, suffix=""):
        widget = QSpinBox()
        widget.setRange(0,maximum)
        widget.setSuffix(suffix)
        widget.setKeyboardTracking(False)
        widget.setAccessibleName(name)
        widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return widget

    def set_color(self, color, send=False, hsv=None):
        hue, sat, value, _ = color.getHsvF()
        if hsv is not None:
            hue, sat, value = hsv
        self.tone = hue if hue >= 0 else self.tone
        self.sat, self.value = sat, value
        degrees = round(self.tone*360)%360
        values = (degrees, degrees, color.red(), color.green(), color.blue())
        for field, number in zip((self.hue, self.degrees, *self.rgb), values):
            previous = field.blockSignals(True)
            field.setValue(number)
            field.blockSignals(previous)
        self.hex.setText(color.name().upper())
        if self.hex.property("invalid"):
            self.hex.setProperty("invalid", False)
            self.hex.style().unpolish(self.hex)
            self.hex.style().polish(self.hex)
        self.hue.update()
        if send:
            self.changed.emit(color)

    def set_hue(self, hue):
        hsv = hue/360, self.sat or 1., self.value or 1.
        self.set_color(QColor.fromHsvF(*hsv), True, hsv)

    def rgb_input(self):
        self.set_color(QColor(*(field.value() for field in self.rgb)),True)

    def hex_input(self):
        entered = self.hex.text().strip().removeprefix("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}",entered):
            self.hex.setProperty("invalid",True)
            self.hex.style().unpolish(self.hex)
            self.hex.style().polish(self.hex)
            return
        color = QColor("#"+entered)
        changed = self.hex.isModified() or [color.red(),color.green(),color.blue()] != [field.value() for field in self.rgb]
        self.set_color(color, changed)


@dataclass(frozen=True)
class GroupEntry:
    bulb: Bulb
    command: str
    value: object
    relative: bool = False
    state: str = "pending"
    detail: str = ""


class Window(QWidget):
    command_finished = Signal()
    shortcut_feedback = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("window")
        self.setWindowTitle("Luz")
        # Leave room for the native title bar and window borders on small desktops.
        available = self.screen().availableGeometry().size() - QSize(16, 48)
        self.setMinimumSize(QSize(870, 660).boundedTo(available))
        self.resize(QSize(1140, 750).boundedTo(available))
        self.bulb = Bulb()
        self.connection_states = {}
        self.diagnostico = Diagnostico()
        self.token = ""
        self.online = self.power_on = self.flowing = False
        self.delay_off = 0
        self.future = None
        self.in_flight = None
        self.closing = False
        self.configuring = False
        self.connection_result = None
        self.desktop = None
        self.hotkeys = None
        self.tray = None
        self.exiting = False
        self.before_toggle = deque()
        self.pending = {}
        self.pending_shortcuts = {}
        self.current_shortcut = None
        self.in_flight_shortcut = None
        self.shortcut_results = {}
        self.shortcut_times = {}
        self.in_flight_silent = False
        self.last_status = None
        self.habitacion_ajustes = ()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.send_timer = QTimer(self, interval=155, singleShot=True)
        self.send_timer.timeout.connect(self.pump)
        self.command_finished.connect(self.finish, Qt.ConnectionType.QueuedConnection)
        self.heartbeat = QTimer(self, interval=60000)
        self.heartbeat.setTimerType(Qt.TimerType.VeryCoarseTimer)
        self.heartbeat.timeout.connect(partial(self.refresh, silent=True))

        shell = QHBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        rail = self.rail = QFrame()
        rail.setObjectName("rail")
        rail.setMinimumWidth(152)
        navigation = QVBoxLayout(rail)
        navigation.setContentsMargins(14, 21, 14, 18)
        navigation.setSpacing(6)
        logo = QLabel()
        logo.setPixmap(self.windowIcon().pixmap(QSize(32, 32)))
        navigation.addLayout(row(logo, label("Luz", "brand"), None, spacing=8))
        navigation.addSpacing(16)
        self.navigation = QButtonGroup(self)
        self.section_names = tuple(map(tr, ("Luces", "Conexión", "Preferencias", "Ayuda")))
        for index, name in enumerate(self.section_names):
            control = button(name, partial(self.show_section, index), "nav")
            control.setCheckable(True)
            control.setMinimumHeight(FOCUS_HEIGHT)
            self.navigation.addButton(control, index)
            navigation.addWidget(control)
        self.navigation.button(0).setChecked(True)
        self.network = self.navigation.button(1)
        navigation.addStretch()

        self.connection = label(tr("Comprobando…"), "connection")
        navigation.addWidget(self.connection)
        shell.addWidget(rail)
        right = QVBoxLayout()
        right.setSpacing(0)
        shell.addLayout(right, 1)
        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(24, 8, 24, 8)
        self.section_title = label(self.section_names[0], "toolbarTitle")
        self.section_title.setWordWrap(True)
        self.light_picker = button(tr("Bombillas guardadas"), self.lights_menu)
        toolbar_layout.addWidget(self.section_title)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.light_picker)
        self.check_button = button(tr("Comprobar de nuevo"), self.check_connection)
        toolbar_layout.addWidget(self.check_button)
        toolbar.setMinimumHeight(56)
        right.addWidget(toolbar)
        self.sections = QStackedWidget()
        right.addWidget(self.sections, 1)
        self.section_dialog = None

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.viewport().setObjectName("canvasViewport")
        workspace = QWidget()
        workspace.setObjectName("workspace")
        span = QHBoxLayout(workspace)
        span.setContentsMargins(0, 0, 0, 0)
        span.setSpacing(0)
        content = QWidget()
        content.setMaximumWidth(1320)
        span.addStretch()
        span.addWidget(content, 100)
        span.addStretch()
        scroll.setWidget(workspace)
        self.sections.addWidget(scroll)
        self.section_layouts = {}
        for index in range(1, len(self.section_names)):
            view = QScrollArea()
            view.setWidgetResizable(True)
            container = QWidget()
            container.setObjectName("workspace")
            if index in (1, 2):
                container.setMaximumWidth(728)
            layout = QVBoxLayout(container)
            layout.setContentsMargins(24, 24, 24, 24)
            layout.addStretch()
            self.section_layouts[index] = layout
            view.setWidget(container)
            self.sections.addWidget(view)
        help_panel, help_layout = panel()
        help_layout.setSpacing(4)
        for index, (text, action) in enumerate((
            ("Atajos", self.shortcut_help),
            ("Ayuda", self.setup_help),
            ("Modelos compatibles", self.compatibility_catalog),
            ("Exportar diagnóstico", self.exportar_diagnostico),
        )):
            if index:
                separator = QFrame()
                separator.setObjectName("rule")
                separator.setFixedHeight(1)
                help_layout.addWidget(separator)
            help_layout.addWidget(button(tr(text), action, "nav"))
        self.section_layouts[3].insertWidget(0, help_panel)
        outer = QVBoxLayout(content)
        outer.setContentsMargins(20, 22, 20, 17)
        outer.setSpacing(16)
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        QShortcut(QKeySequence("Escape"), self, activated=self.escape)

        grid = self.light_grid = QGridLayout()
        grid.setSpacing(16)
        grid.setColumnStretch(0, 11)
        grid.setColumnStretch(1, 10)
        outer.addLayout(grid)
        self.light, main = panel()
        main.setSpacing(8)
        grid.addWidget(self.light, 0, 0)
        self.model_label = label("", "muted")
        self.model_label.setWordWrap(True)
        self.device_title = label("", "title")
        self.device_title.setWordWrap(True)
        main.addWidget(self.device_title)
        main.addWidget(self.model_label)
        self.lamp = LampView()
        self.lamp.setAccessibleName(tr("Encender o apagar"))
        self.lamp.setToolTip(tr("Haz clic en la bombilla para encenderla o apagarla."))
        self.lamp.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.lamp.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lamp.clicked.connect(lambda: self.toggle())
        self.lamp.setAccessibleDescription(tr("El estado de la luz se indica debajo de la vista previa."))
        self.lamp.setMinimumHeight(168)
        self.lamp.setMaximumHeight(390)
        self.lamp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main.addWidget(self.lamp, 1)
        self.power = ToggleSwitch(tr("Encender"))
        self.power.setObjectName("power")
        self.power.clicked.connect(self.toggle)
        self.power.setAccessibleName(tr("Encender o apagar"))
        self.power_readout = label(tr("Estado pendiente"),"status")
        main.addLayout(row(self.power_readout, None, self.power))
        main.addLayout(row(label(tr("Brillo"), "section"), None))
        self.brightness = self.slider(tr("Brillo"), 1, 100)
        self.brightness_value = self.number(tr("Brillo exacto"), 1, 100, " %", width=64)
        self.brightness.setMinimumHeight(FOCUS_HEIGHT)
        self.brightness.setValue(55)
        self.brightness_value.setValue(55)
        main.addLayout(row(self.brightness, self.brightness_value))

        self.scenes_card = QFrame()
        self.scenes_card.setObjectName("shelf")
        scenes_layout = QVBoxLayout(self.scenes_card)
        scenes_layout.setContentsMargins(0, 12, 0, 0)
        scenes_layout.setSpacing(10)
        grid.addWidget(self.scenes_card, 1, 0, 1, 2)
        scenes_layout.addLayout(row(label(tr("Escenas"), "section"), None,
                                    button(tr("Copia de escenas"), self.backup_menu)))
        self.editing_scene = None
        self.scenes_error = ""
        try:
            self.scene_slots = load_scenes()
        except (OSError, ValueError):
            self.scene_slots = DEFAULT_SCENES.copy()
            self.scenes_error = tr("No se pudieron leer las escenas guardadas. Se muestran las iniciales.")
        self.scenes = []
        shortcuts = QHBoxLayout()
        shortcuts.setSpacing(7)
        for index in range(len(self.scene_slots)):
            control = QToolButton()
            control.setObjectName("scene")
            control.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            control.setMinimumSize(FOCUS_HEIGHT, FOCUS_HEIGHT)
            control.clicked.connect(partial(self.activate_scene, index))
            control.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            control.setIconSize(QSize(48, 24))
            control.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            control.customContextMenuRequested.connect(partial(self.scene_menu, index))
            QShortcut(QKeySequence("Shift+F10"), control,
                      activated=lambda slot=index, scene=control: self.scene_menu(slot, scene.rect().center()),
                      context=Qt.ShortcutContext.WidgetShortcut)
            shortcuts.addWidget(control, 1)
            self.scenes.append(control)
        scenes_layout.addLayout(shortcuts)
        self.update_scenes()

        self.editor_card, editor_layout = panel()
        grid.addWidget(self.editor_card, 0, 1)
        editor_layout.addWidget(label(tr("Apariencia"), "section"))
        segments = QFrame()
        segments.setObjectName("segments")
        segment_layout = QHBoxLayout(segments)
        segment_layout.setContentsMargins(4,4,4,4)
        segment_layout.setSpacing(4)
        self.mode_buttons = QButtonGroup(self)
        self.pages = QStackedWidget()
        self.pages.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for index, name in enumerate((tr("Color"),tr("Blanco"))):
            tab = button(name, partial(self.show_mode, index), "segment")
            tab.setCheckable(True)
            self.mode_buttons.addButton(tab, index)
            segment_layout.addWidget(tab, 1)
        self.modes = segments
        editor_layout.addWidget(segments)
        self.colors = ColorEditor()
        self.pages.addWidget(self.colors)
        self.pages.addWidget(self.white_page())
        fixed_white = label(tr("Blanco fijo · ajusta el brillo desde la tarjeta de la bombilla."), "muted")
        fixed_white.setWordWrap(True)
        self.pages.addWidget(fixed_white)
        editor_layout.addWidget(self.pages)
        self.effects_rule = QFrame()
        self.effects_rule.setObjectName("rule")
        self.effects_rule.setFixedHeight(1)
        editor_layout.addWidget(self.effects_rule)
        self.effects_label = label(tr("Efectos"), "section")
        editor_layout.addWidget(self.effects_label)
        self.flow = button(tr("Efectos…"), self.flow_menu)
        self.timer = button(tr("Temporizador…"), self.configure_timer)
        editor_layout.addLayout(row(self.flow, self.timer, None))
        self.edit_bar = QFrame()
        self.edit_bar.setObjectName("segments")
        edit_layout = QVBoxLayout(self.edit_bar)
        edit_layout.setContentsMargins(10, 7, 10, 7)
        self.edit_title = label("", "status")
        self.edit_title.setWordWrap(True)
        edit_layout.addWidget(self.edit_title)
        edit_layout.addLayout(row(None, button(tr("Cancelar"), self.cancel_scene_edit),
                                  button(tr("Guardar escena"), self.save_scene_edit, "primary")))
        editor_layout.addWidget(self.edit_bar)
        self.edit_bar.hide()
        editor_layout.addStretch(1)

        self.note = label(tr("Buscando la bombilla en la red local…"), "status")
        self.note.setWordWrap(True)
        footer = row()
        footer.addWidget(self.note, 1)
        self.group_results = ()
        self.group_details = button(tr("Resultado del grupo"), self.show_group_results)
        self.group_details.hide()
        footer.addWidget(self.group_details)
        outer.addLayout(footer)
        outer.addStretch(1)
        self.controls = [
            self.power, self.lamp, self.colors, self.brightness, self.brightness_value,
            self.temperature, self.kelvin_value, self.flow, self.timer,
            *self.white_presets, self.amber,
        ]
        self.update_device()
        self.colors.changed.connect(self.edit_color)
        self.colors.hue.committed.connect(self.flush_choice)
        self.temperature.committed.connect(self.flush_choice)
        self.brightness.valueChanged.connect(partial(self.edit_number, "brightness", self.brightness_value))
        self.brightness.sliderReleased.connect(partial(self.flush_choice, "brightness"))
        self.brightness_value.valueChanged.connect(partial(self.edit_number, "brightness", self.brightness))
        self.temperature.valueChanged.connect(partial(self.edit_number, "white", self.kelvin_value))
        self.kelvin_value.valueChanged.connect(partial(self.edit_number, "white", self.temperature))
        self.update_connection(False, tr("Comprobando…"))
        try:
            self.token = load_token()
        except (OSError, ValueError):
            self.update_connection(False, tr("Sin configurar"))
            self.note.setText(tr("Windows no pudo abrir el token guardado. Vuelve a introducirlo en Conexión."))
        if self.token:
            self.refresh()
        else:
            self.update_connection(False, tr("Sin configurar"))
            if self.note.text() == tr("Buscando la bombilla en la red local…"):
                self.note.setText(tr("Abre Conexión para guardar el token de la bombilla."))

    def start_first_run(self):
        if not self.closing and not self.token and self.section_dialog is None and self.sections.currentIndex() == 0:
            self.show_section(1, guided=True)

    def show_section(self, index, *, guided=True):
        if self.section_dialog is not None and not self.section_dialog.isEnabled():
            self.navigation.button(self.sections.currentIndex()).setChecked(True)
            self.note.setText(tr("Espera a que termine el cambio en curso."))
            return
        if self.section_dialog is not None:
            if self.sections.currentIndex() == index:
                return
            self.sections.setCurrentIndex(index)
            self.section_dialog.reject()
        self.sections.setCurrentIndex(index)
        self.navigation.button(index).setChecked(True)
        self.navigation.button(index).setFocus(Qt.FocusReason.OtherFocusReason)
        self.section_title.setText(self.section_names[index])
        self.light_picker.setVisible(index == 0)
        self.check_button.setVisible(index == 0)
        if index == 1:
            self.settings(embedded=True, guided=guided)
            if self.section_dialog is None:
                self.show_section(0)
        elif index == 2:
            self.desktop_settings(embedded=True)

    def mount_section(self, index, dialog, cleanup):
        dialog.setObjectName("embeddedPanel")
        dialog.setParent(self.sections.widget(index).widget(), Qt.WindowType.Widget)
        dialog.layout().setContentsMargins(0, 0, 0, 0)
        apply_fonts(QApplication.instance(), dialog)
        self.section_layouts[index].insertWidget(0, dialog)
        self.section_dialog = dialog
        heading = dialog.findChild(QLabel, "dialogTitle")
        if heading and heading.text() == self.section_names[index]:
            heading.hide()

        def finished(_):
            cleanup()
            self.section_dialog = None
            dialog.deleteLater()
            if self.sections.currentIndex() == index:
                self.show_section(0)

        dialog.finished.connect(finished)
        dialog.show()
        self.sections.widget(index).verticalScrollBar().setValue(0)

    def resume_hotkeys(self):
        if self.hotkeys:
            self.hotkeys.paused = False

    def number(self, name, low, high, suffix, *, width=88):
        control = QSpinBox()
        control.setRange(low, high)
        control.setSuffix(suffix)
        control.setKeyboardTracking(False)
        control.setAccessibleName(name)
        control.setAlignment(Qt.AlignmentFlag.AlignCenter)
        control.setFixedWidth(width)
        return control

    def slider(self, name, minimum, maximum):
        control = BrightnessSlider()
        control.setRange(minimum, maximum)
        control.setAccessibleName(name)
        control.setMinimumHeight(28)
        control.setCursor(Qt.CursorShape.PointingHandCursor)
        return control

    def white_page(self):
        page = QWidget()
        self.temperature = SpectrumSlider(((0, "#ffad61"), (.34, "#ffd1a5"),
                                           (.62, "#fff0dd"), (1, "#c6ddff")))
        self.temperature.setRange(1700, 6500)
        self.temperature.setValue(2700)
        self.temperature.setSingleStep(25)
        self.temperature.setAccessibleName(tr("Temperatura de blanco"))
        self.temperature.setAccessibleDescription(tr("Usa las flechas, Inicio, Fin, Re Pág o Av Pág para ajustar el valor."))
        self.kelvin_value = self.number(tr("Temperatura exacta"), 1700, 6500, " K")
        self.kelvin_value.setValue(2700)
        body = spectrum_layout(page, tr("Temperatura"), self.kelvin_value, self.temperature)
        self.amber = button(tr("Ámbar RGB"), self.apply_amber)
        body.addLayout(row(label(tr("Cálido"), "muted"), None, label(tr("Frío"), "muted")))
        self.white_options = (2200, 2700, 4000, 5600)
        self.white_presets = [button(f"{value} K", partial(self.white_preset, value)) for value in self.white_options]
        body.addLayout(row(*self.white_presets, None, self.amber))
        return page

    def show_mode(self, index):
        features = self.bulb.features
        if index == 0 and not features.rgb:
            index = 1
        if index == 1 and not features.tunable_white:
            index = 2
        self.pages.setCurrentIndex(index)
        if index < 2:
            self.mode_buttons.button(index).setChecked(True)

    def update_device(self):
        features = self.bulb.features
        title = self.bulb.name or self.bulb.xiaomi_name or tr("Bombilla Xiaomi")
        self.device_title.setText(title)
        original = self.bulb.xiaomi_name
        model = f"Xiaomi · {self.bulb.model}"
        self.model_label.setText(f"Xiaomi Home · {original}\n{model}" if original and original != title else model)
        self.modes.setVisible(features.rgb)
        self.amber.setVisible(features.rgb)
        for preset, value in zip(self.white_presets, self.white_options):
            preset.setVisible(features.minimum <= value <= features.maximum)
        self.effects_rule.setVisible(features.effects)
        self.effects_label.setVisible(features.effects)
        self.flow.setVisible(features.effects)
        self.timer.setVisible(features.effects)
        for picker in (self.temperature, self.kelvin_value):
            previous = picker.blockSignals(True)
            picker.setRange(features.minimum, features.maximum)
            picker.blockSignals(previous)
        self.temperature.update()
        self.show_mode(0)
        self.update_scenes()

    def apply_amber(self):
        self.show_mode(0)
        self.colors.set_color(QColor("#FF7900"), True)
        self.flush_choice()

    def white_preset(self, kelvin):
        if self.temperature.value() == kelvin:
            self.edit_number("white", self.kelvin_value, kelvin)
        else:
            self.temperature.setValue(kelvin)

    def edit_number(self, action, other, value):
        self.set_number(other, value)
        self.previsualizar_ajuste(action, value)
        if self.editing_scene is None:
            self.schedule(action, value)

    def previsualizar_ajuste(self, action, value):
        if action == "brightness":
            self.lamp.level = value
        else:
            self.lamp.color = white_preview(value)
        self.lamp.lit = True
        self.lamp.update(animate=False)

    def paso_brillo(self):
        step = self.desktop.value("brightness_step", 10, type=int) if self.desktop is not None else 10
        return step if step in PASOS_BRILLO else 10

    def ajustar_relativo(self, action, direccion):
        if self.configuring or (not self.online and not self.token) or self.editing_scene is not None:
            return
        compatible = action != "white" or self.bulb.features.tunable_white
        if not compatible and not self.habitacion_ajustes:
            return
        if action == "brightness":
            slider, exact, step = self.brightness, self.brightness_value, self.paso_brillo()
        else:
            slider, exact, step = self.temperature, self.kelvin_value, PASO_TEMPERATURA
        paso = direccion * step
        if not self.habitacion_ajustes and (not self.online or not self.isVisible() or self.isMinimized()):
            key = f"relative_{action}"
            self.schedule(key, (*self.pending.get(key, ()), paso))
            return
        current = slider.value()
        value = min(slider.maximum(), max(slider.minimum(), current + paso))
        if compatible and value != current:
            if action == "white":
                self.show_mode(1)
            self.set_number(slider, value)
            self.set_number(exact, value)
            self.previsualizar_ajuste(action, value)
        if not self.habitacion_ajustes:
            if value != current:
                self.schedule(action, value)
            return

        key = f"room_{action}"
        _, pasos, _ = self.pending.get(key, ((), (), 0))
        self.schedule(key, (self.habitacion_ajustes, (*pasos, paso), value))

    def titulos_atajos(self):
        return (tr("Encender o apagar"), *(scene.name for scene in self.scene_slots),
                *(tr(title) for title, _, _ in AJUSTES_RELATIVOS))

    @staticmethod
    def set_number(widget, value):
        blocked = widget.blockSignals(True)
        widget.setValue(value)
        widget.blockSignals(blocked)

    def edit_color(self, color):
        self.lamp.color = color
        self.lamp.lit = True
        self.lamp.update(animate=False)
        if self.editing_scene is None:
            self.schedule("color", (color.red(), color.green(), color.blue()))

    def flush_choice(self, *actions):
        if any(action in self.pending for action in (actions or ("color", "white"))):
            self.send_timer.stop()
            self.pump()

    def requested_power(self):
        if "power" in self.pending:
            return self.pending["power"]
        for action, value, _ in reversed(self.before_toggle):
            if action == "power":
                return value
        if self.in_flight and self.in_flight[0] == "power":
            return self.in_flight[1]
        return self.power_on

    def show_power(self, enabled, *, update_preview=True):
        self.power.setChecked(enabled)
        self.power.setText(tr("Apagar") if enabled else tr("Encender"))
        if update_preview:
            self.lamp.lit = enabled
            self.lamp.update()

    def toggle(self):
        if self.configuring or not self.online:
            self.power.setChecked(self.requested_power())
            return
        self.schedule("power", not self.requested_power())

    def flow_menu(self):
        menu = QMenu(self)
        starting_flow = self.in_flight and self.in_flight[0] == "flow" and self.in_flight[1]
        if self.flowing or starting_flow or self.pending.get("flow"):
            menu.addAction(tr("Parar ciclo"), partial(self.schedule, "flow", False))
            menu.addSeparator()
        for name in FLOW_PRESETS:
            menu.addAction(tr(name), partial(self.schedule, "flow", name))
        menu.exec(self.flow.mapToGlobal(self.flow.rect().bottomLeft()))
        menu.deleteLater()

    def configure_timer(self):
        dialog, form = panel_form(self, tr("Temporizador"))
        remaining = (tr("Quedan aproximadamente {minutes} min.").format(minutes=self.delay_off)
                     if self.delay_off else tr("Elige cuándo se apaga la bombilla."))
        form.addRow(label(remaining, "muted"))
        minutes = self.number(tr("Minutos"), 1, 1440, " min")
        minutes.setValue(self.delay_off or 30)
        field_label(form, tr("Minutos"), minutes)
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        actions.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cerrar"))
        start = actions.addButton(tr("Programar"), QDialogButtonBox.ButtonRole.AcceptRole)
        clear = actions.addButton(tr("Cancelar temporizador"), QDialogButtonBox.ButtonRole.ActionRole)
        clear.setEnabled(bool(self.delay_off))
        clear.clicked.connect(lambda: dialog.done(2))
        start.setObjectName("primary")
        start.clicked.connect(dialog.accept)
        actions.rejected.connect(dialog.reject)
        form.addRow(actions)
        try:
            result = dialog.exec()
            if result:
                self.schedule("timer", minutes.value() if result == 1 else 0)
        finally:
            dialog.deleteLater()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.leave_fullscreen()
        else:
            self.was_maximized = self.isMaximized()
            self.showFullScreen()

    def leave_fullscreen(self):
        if self.was_maximized:
            self.showMaximized()
        else:
            self.showNormal()

    def escape(self):
        if self.isFullScreen():
            self.leave_fullscreen()
        elif self.section_dialog is not None:
            if self.section_dialog.isEnabled():
                self.section_dialog.reject()
            else:
                self.note.setText(tr("Espera a que termine el cambio en curso."))
        else:
            self.cancel_scene_edit()

    def update_scenes(self):
        for index, (control, scene) in enumerate(zip(self.scenes, self.scene_slots)):
            detail = scene.detail()
            short = control.fontMetrics().elidedText(scene.name, Qt.TextElideMode.ElideRight, 105)
            control.setText(f"{short}\n{detail}")
            ink = white_preview(scene.level) if scene.mode == "white" else QColor(*scene.level)
            swatch = QPixmap(control.iconSize())
            swatch.fill(Qt.GlobalColor.transparent)
            painter = QPainter(swatch)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(control.palette().mid().color(), 1))
            painter.setBrush(ink)
            painter.drawRoundedRect(QRectF(1, 1, 46, 22), 8, 8)
            painter.end()
            control.setIcon(QIcon(swatch))
            control.setAccessibleName(f"{scene.name}. {detail}")
            control.setToolTip(f"{scene.name} · {detail}\n{tr('Clic derecho para editar.')}")
            control.setProperty("editing", index == self.editing_scene)
            control.style().unpolish(control)
            control.style().polish(control)
        self.update_tray()

    def activate_scene(self, index):
        if self.editing_scene is not None:
            return
        scene = self.scene_slots[index]
        if not self.online:
            self.note.setText(tr("Conecta la bombilla para activar esta escena."))
            return
        if scene.mode == "color" and not self.bulb.features.rgb:
            self.note.setText(tr("Edita esta escena para guardarla en blanco con esta bombilla."))
            return
        self.show_mode(1 if scene.mode == "white" else 0)
        self.schedule("scene", scene.command())

    def scene_menu(self, index, position):
        menu = QMenu(self)
        menu.addAction(tr("Editar escena"), partial(self.begin_scene_edit, index))
        menu.addAction(tr("Renombrar"), partial(self.rename_scene, index))
        menu.addSeparator()
        menu.addAction(tr("Vaciar"), partial(self.clear_scene, index))
        menu.exec(self.scenes[index].mapToGlobal(position))
        menu.deleteLater()

    def begin_scene_edit(self, index):
        if not self.online:
            self.note.setText(tr("Conecta la bombilla para editar el color de la escena."))
            return
        if not (self.bulb.features.rgb or self.bulb.features.tunable_white):
            self.note.setText(tr("Esta bombilla tiene blanco fijo."))
            return
        self.editing_scene = index
        scene = self.scene_slots[index]
        self.show_mode(1 if scene.mode == "white" else 0)
        self.set_number(self.brightness, scene.brightness)
        self.set_number(self.brightness_value, scene.brightness)
        self.lamp.level = scene.brightness
        if self.pages.currentIndex() == 1:
            if scene.mode == "white":
                self.set_number(self.temperature, scene.level)
                self.set_number(self.kelvin_value, scene.level)
                self.temperature.update()
            self.lamp.color = white_preview(self.temperature.value())
        else:
            self.colors.set_color(QColor(*scene.level))
            self.lamp.color = QColor(*scene.level)
        self.lamp.lit = True
        self.lamp.update()
        self.show_scene_edit_title()
        self.edit_bar.show()
        self.update_scenes()
        self.update_controls()

    def show_scene_edit_title(self):
        name = self.scene_slots[self.editing_scene].name
        self.edit_title.setText(tr("Editando «{name}». Ajusta color y brillo y pulsa Guardar escena.").format(name=name))

    def end_scene_edit(self):
        self.editing_scene = None
        self.edit_bar.hide()
        self.update_scenes()
        self.update_controls()

    def cancel_scene_edit(self):
        if self.editing_scene is not None:
            self.end_scene_edit()
            self.refresh()

    def save_scene_edit(self):
        index = self.editing_scene
        if index is None or not self.online:
            return
        old = self.scene_slots[index]
        white = self.pages.currentIndex() == 1
        level = self.temperature.value() if white else tuple(field.value() for field in self.colors.rgb)
        scene = replace(old, mode="white" if white else "color", level=level, brightness=self.brightness_value.value())
        if self.store_scene(index, scene):
            self.end_scene_edit()
            self.schedule("scene", scene.command())

    def rename_scene(self, index):
        scene = self.scene_slots[index]
        name, accepted = QInputDialog.getText(self, tr("Cambiar nombre"), tr("Nombre de la escena"), text=scene.name)
        if not accepted:
            return
        name = name.strip()
        if not (1 <= len(name) <= 32):
            QMessageBox.warning(self, tr("Nombre de escena"), tr("Introduce entre 1 y 32 caracteres."))
            return
        if self.store_scene(index, replace(scene, name=name)) and index == self.editing_scene:
            self.show_scene_edit_title()

    def clear_scene(self, index):
        scene = self.scene_slots[index]
        prompt = QMessageBox(self)
        prompt.setWindowTitle(tr("Vaciar escena"))
        prompt.setText(tr("¿Seguro que quieres vaciar «{name}»?").format(name=scene.name))
        prompt.setInformativeText(tr("Se restablecerá como Blanco a 4000 K y 100 % de brillo."))
        confirm = prompt.addButton(tr("Vaciar"), QMessageBox.ButtonRole.DestructiveRole)
        cancel = prompt.addButton(tr("Cancelar"), QMessageBox.ButtonRole.RejectRole)
        prompt.setDefaultButton(cancel)
        prompt.setEscapeButton(cancel)
        prompt.exec()
        confirmed = prompt.clickedButton() == confirm
        prompt.deleteLater()
        if confirmed and self.store_scene(index, WHITE_SCENE):
            if index == self.editing_scene:
                self.cancel_scene_edit()

    def store_scene(self, index, scene):
        updated = self.scene_slots.copy()
        updated[index] = scene
        try:
            save_scenes(updated)
        except (OSError, ValueError):
            QMessageBox.warning(self, tr("Escenas"), tr("No se pudieron guardar las escenas en el disco."))
            return False
        self.scenes_error = ""
        self.scene_slots = updated
        self.update_scenes()
        return True

    def backup_menu(self):
        menu = QMenu(self)
        menu.addAction(tr("Exportar escenas…"), self.export_scenes)
        menu.addAction(tr("Importar escenas…"), self.import_scenes)
        menu.exec(self.cursor().pos())
        menu.deleteLater()

    def export_scenes(self):
        name, _ = QFileDialog.getSaveFileName(self, tr("Exportar escenas…"), "escenas.json", "JSON (*.json)")
        if name:
            try:
                path = Path(name)
                self.diagnostico.comprobar_destino(path, para_escenas=True)
                save_scenes(self.scene_slots, path)
            except (OSError, ValueError):
                QMessageBox.warning(self, tr("Escenas"), tr("No se pudo escribir la copia."))

    def import_scenes(self):
        name, _ = QFileDialog.getOpenFileName(self, tr("Importar escenas…"), "", "JSON (*.json)")
        if not name:
            return
        path = Path(name)
        try:
            if not path.is_file():
                raise ValueError()
            scenes = load_scenes(path)
        except (OSError, ValueError):
            QMessageBox.warning(self, tr("Escenas"), tr("La copia debe contener tres escenas válidas."))
            return
        if QMessageBox.question(self, tr("Importar escenas…"),
                                tr("¿Sustituir las tres escenas por las de esta copia?")) != QMessageBox.StandardButton.Yes:
            return
        try:
            save_scenes(scenes)
        except (OSError, ValueError):
            QMessageBox.warning(self, tr("Escenas"), tr("No se pudieron guardar las escenas en el disco."))
            return
        self.scene_slots = scenes
        if self.editing_scene is not None:
            self.end_scene_edit()
        self.update_scenes()
        self.note.setText(tr("Escenas importadas."))

    def exportar_diagnostico(self):
        nombre, _ = QFileDialog.getSaveFileName(self, tr("Exportar diagnóstico"), "luz-diagnostico.txt",
                                                tr("Archivo de texto (*.txt)"))
        if not nombre:
            return
        destino = Path(nombre)
        try:
            self.diagnostico.exportar(destino, self.bulb, self.desktop)
        except (OSError, ValueError):
            QMessageBox.warning(self, tr("Exportar diagnóstico"), tr("No se pudo guardar el diagnóstico."))
        else:
            QMessageBox.information(self, tr("Exportar diagnóstico"),
                                    tr("Diagnóstico guardado. Revísalo antes de compartirlo."))

    def shortcut_status(self, index, sequence, *, attempted=False):
        if not sequence:
            return tr("— No asignado")
        if self.hotkeys is None:
            return tr("◷ Sin comprobar")
        state, code = self.hotkeys.statuses.get(index, ("unchecked", 0))
        if not attempted and any(
            slot == index and self.hotkeys.registered[identifier] == sequence
            for identifier, slot in self.hotkeys.slots.items()
        ):
            state = "registered"
        message = tr({
            "registered": "✓ Registrado",
            "occupied": "× Ocupado por otra aplicación",
            "invalid": "× No válido ({code})",
        }.get(state, "◷ Sin comprobar")).format(code=code)
        if altgr_conflict(sequence):
            message += " · " + tr("Posible conflicto con AltGr")
        if "+NUM" in sequence.upper():
            message += " · " + tr("Requiere teclado numérico")
        if index in self.shortcut_results:
            message += " · " + tr(self.shortcut_results[index])
            if index in self.shortcut_times:
                message += " · " + tr("Última pulsación {time}").format(time=self.shortcut_times[index])
        return message

    def set_shortcut_result(self, index, message):
        if index is not None:
            self.shortcut_results[index] = message
            self.shortcut_feedback.emit()

    def shortcut_help(self):
        keys = self.shortcut_values()
        dialog, form = panel_form(self, tr("Atajos"), scrollable=True)
        descriptions = []
        for index, (title, key) in enumerate(zip(self.titulos_atajos(), keys)):
            if index:
                rule = QFrame()
                rule.setObjectName("rule")
                rule.setFixedHeight(1)
                form.addRow(rule)
            form.addRow(row(label(title, "formLabel"), None, label(key or tr("Sin atajo"), "section")))
            description = label(self.shortcut_status(index, key), "status")
            description.setWordWrap(True)
            form.addRow(description)
            descriptions.append(description)
        form.addRow(label(tr("Pantalla completa")), label("F11", "status"))
        details = label(tr("Clic derecho en una escena para editarla. El menú junto al reloj permite controlar la luz y salir de Luz."), "muted")
        details.setWordWrap(True)
        form.addRow(details)

        def refresh_feedback():
            for index, description in enumerate(descriptions):
                description.setText(self.shortcut_status(index, keys[index]))

        def edit_shortcuts():
            dialog.accept()
            QTimer.singleShot(0, self.desktop_settings)

        form.addRow(row(button(tr("Cambiar atajos…"), edit_shortcuts), None,
                        button(tr("Cerrar"), dialog.accept)))
        self.shortcut_feedback.connect(refresh_feedback)
        try:
            dialog.exec()
        finally:
            self.shortcut_feedback.disconnect(refresh_feedback)
            dialog.deleteLater()

    def setup_help(self):
        dialog, form = panel_form(self, tr("Ayuda"), scrollable=True)
        available = self.screen().availableGeometry()
        width = max(1, available.width() - 32)
        dialog.setMinimumWidth(min(480, width))
        dialog.resize(min(680, width), dialog.height())
        for message, role in (
            ("Volver a configurar una bombilla", "section"),
            ("1. Añade la bombilla a tu Wi-Fi con Xiaomi Home. Si has cambiado de red o la has restablecido, vuelve a añadirla allí. Conecta el PC a la misma red local.", "muted"),
            ("2. Abre Conexión en Luz. Selecciona Añadir bombilla para una nueva, o elige una guardada para actualizar sus datos.", "muted"),
            ("3. Pulsa Obtener token por QR, elige la misma región de Xiaomi Home y genera el QR. Escanéalo con Xiaomi Home y autoriza el acceso en el móvil.", "muted"),
            ("4. Elige tu bombilla para rellenar IP y token. Pulsa Verificar y guardar. Si prefieres introducirlos manualmente, usa Buscar bombillas y Pegar IP y token.", "muted"),
            ("El token se guarda cifrado en este PC. Tras restablecer la bombilla puede cambiar: obtén uno nuevo y vuelve a verificar. No compartas tu token ni el QR.", "muted"),
        ):
            instruction = label(tr(message), role)
            instruction.setWordWrap(True)
            form.addRow(instruction)

        feedback = label("", "status")
        feedback.setWordWrap(True)
        feedback.hide()
        form.addRow(feedback)

        def open_connection():
            if self.configuring or self.future or self.pending or self.before_toggle:
                feedback.setText(tr("Espera a que termine el cambio en curso."))
                feedback.show()
                return
            self.show_section(1, guided=True)
            if self.sections.currentIndex() == 1 and self.section_dialog is not None:
                dialog.accept()

        form.addRow(row(button(tr("Abrir Conexión"), open_connection, "primary"), None,
                        button(tr("Cerrar"), dialog.accept)))
        apply_fonts(QApplication.instance(), dialog)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    def compatibility_catalog(self):
        dialog, form = panel_form(self, tr("Modelos compatibles"))
        dialog.setMinimumWidth(560)
        search = QLineEdit()
        search.setPlaceholderText(tr("Buscar nombre o código de modelo"))
        search.setAccessibleName(search.placeholderText())
        search.setClearButtonEnabled(True)
        form.addRow(search)
        models = QListWidget()
        models.setMinimumHeight(180)
        form.addRow(models)
        detail = label("", "status")
        detail.setWordWrap(True)
        form.addRow(detail)
        def selected_model():
            item = models.currentItem()
            return item.data(Qt.ItemDataRole.UserRole) if item else None

        def open_source():
            model = selected_model()
            if model:
                QDesktopServices.openUrl(QUrl(FICHAS_CATALOGO.get(model.split(".")[-1], FICHA_CONTROLADOR)))

        source = button(tr("Consultar referencia"), open_source, "credit")
        form.addRow(row(source, None, button(tr("Cerrar"), dialog.accept)))

        def update_detail():
            model = selected_model()
            source.setEnabled(bool(model))
            if not model:
                detail.setText(tr("Sin modelos para esa búsqueda."))
                return
            features = capabilities(model)
            controls = [tr("Brillo")]
            if features.rgb:
                controls.append("RGB")
            if features.tunable_white:
                controls.append(f"{features.minimum}–{features.maximum} K")
            else:
                controls.append(tr("Blanco fijo"))
            if features.effects:
                controls.extend((tr("Efectos"), tr("Temporizador")))
            evidence = tr("Probada físicamente con Luz") if model == MODEL else tr("Según la especificación del controlador")
            suffix = model.split(".")[-1]
            reference = MODELOS_CATALOGO[suffix][1]
            identity = model if reference else f'{model} · {tr("Referencia comercial sin confirmar")}'
            detail.setText(identity + "\n" + " · ".join(controls) + "\n" + evidence)

        def filter_models(query):
            models.clear()
            terms = query.casefold().split()
            for suffix, (name, reference) in MODELOS_CATALOGO.items():
                model = f"yeelink.light.{suffix}"
                title = tr(name)
                if reference:
                    title = f"{title} · {reference}"
                else:
                    title = f"{title} · {suffix}"
                haystack = f"{title} {name} {model}".casefold()
                if all(term in haystack for term in terms):
                    item = QListWidgetItem(title, models)
                    item.setData(Qt.ItemDataRole.UserRole, model)
            models.setCurrentRow(0)
            update_detail()

        models.currentItemChanged.connect(update_detail)
        search.textChanged.connect(filter_models)
        filter_models("")
        search.setFocus()
        dialog.exec()
        dialog.deleteLater()

    def shortcut_values(self):
        if self.desktop is None:
            return DEFAULT_SHORTCUTS
        saved = tuple(self.desktop.value(f"hotkey/{index}", key, type=str)
                      for index, key in enumerate(DEFAULT_SHORTCUTS))
        return migrate_shortcuts(saved, schema=self.desktop.value("hotkey_schema", 0, type=int))

    def desktop_settings(self, *, embedded=False):
        if self.desktop is None:
            return
        dialog, form = panel_form(self, tr("Preferencias"), scrollable=not embedded)
        if not embedded:
            dialog.setMinimumWidth(680)
        columns = QVBoxLayout()
        columns.setSpacing(16)
        general_box = QFrame()
        general_box.setObjectName("group")
        general = QFormLayout(general_box)
        general.setSpacing(8)
        general.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        general.setLabelAlignment(Qt.AlignmentFlag.AlignVCenter)
        general.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        general.addRow(label(tr("General"), "section"))
        shortcut_box = QFrame()
        shortcut_box.setObjectName("group")
        shortcuts = QFormLayout(shortcut_box)
        shortcuts.setSpacing(8)
        shortcuts.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        shortcuts.setLabelAlignment(Qt.AlignmentFlag.AlignVCenter)
        shortcuts.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        columns.addWidget(general_box)
        columns.addWidget(shortcut_box)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        general.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        shortcuts.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.addRow(columns)
        language = MenuCombo()
        language.setMaximumWidth(192)
        language.addItem("Español", "es")
        language.addItem("English", "en")
        saved_language = self.desktop.value("language", "es", type=str)
        language.setCurrentIndex(max(0, language.findData(saved_language)))
        theme = MenuCombo()
        theme.setMaximumWidth(192)
        theme.addItem(tr("Oscuro"), "dark")
        theme.addItem(tr("Claro"), "light")
        theme.setCurrentIndex(max(0, theme.findData(self.desktop.value("theme", "dark", type=str))))
        resident = ToggleSwitch(tr("Mantener Luz junto al reloj al cerrar"))
        resident.setChecked(self.desktop.value("tray", True, type=bool))
        field_label(general, tr("Idioma"), language)
        field_label(general, tr("Tema"), theme)
        pasos = MenuCombo()
        pasos.setMaximumWidth(192)
        for paso in PASOS_BRILLO:
            pasos.addItem(f"{paso} %", paso)
        pasos.setCurrentIndex(pasos.findData(self.paso_brillo()))
        field_label(general, tr("Paso de brillo"), pasos)
        general.addRow(resident)
        inicio = ToggleSwitch(tr("Iniciar Luz con Windows"))
        empaquetado = bool(getattr(sys, "frozen", False))
        lectura_inicio_correcta = True
        try:
            anterior_inicio = inicio_windows() if empaquetado else ""
        except OSError:
            anterior_inicio, lectura_inicio_correcta = "", False
        inicio.setChecked(bool(anterior_inicio))
        inicio.setEnabled(empaquetado and lectura_inicio_correcta)
        if not empaquetado:
            inicio.setToolTip(tr("Abre Luz.exe para cambiar el inicio con Windows."))
        elif not lectura_inicio_correcta:
            inicio.setToolTip(tr("No se pudo leer el inicio con Windows."))
        general.addRow(inicio)
        shortcuts.addRow(label(tr("Atajos"), "section"))
        hint = label(tr("Haz clic en un atajo y pulsa la combinación."), "muted")
        hint.setWordWrap(True)
        shortcuts.addRow(hint)
        entries = []
        for index, (title, value) in enumerate(zip(self.titulos_atajos(), self.shortcut_values())):
            entry = ShortcutRecorder(value)
            entry.setObjectName("preferenceShortcut")
            entry.setMinimumWidth(164)
            entry.setAccessibleName(title)
            caption = label(title, "formLabel")
            caption.setWordWrap(True)
            caption.setBuddy(entry)
            if entries:
                separator = QFrame()
                separator.setObjectName("rule")
                separator.setFixedHeight(1)
                shortcuts.addRow(separator)
            entry.setMinimumHeight(FOCUS_HEIGHT)
            controls = QVBoxLayout()
            controls.addWidget(entry, alignment=Qt.AlignmentFlag.AlignRight)
            state = label(self.shortcut_status(index, value), "status")
            state.setWordWrap(True)
            state.setAlignment(Qt.AlignmentFlag.AlignRight)
            controls.addWidget(state)
            if value and (altgr_conflict(value) or "+NUM" in value.upper()):
                alternatives = ("Ctrl+Shift+F9", "Ctrl+Shift+F10", "Ctrl+Shift+F8", "Ctrl+Shift+F7")

                def alternative(slot=index, editor=entry, feedback=state, options=alternatives):
                    if self.hotkeys is None:
                        return
                    others = [candidate.sequence for pos, candidate in enumerate(entries) if pos != slot]
                    for choice in options:
                        try:
                            available = choice != editor.sequence and self.hotkeys.available(choice, others)
                        except ValueError:
                            available = False
                        if available:
                            editor.sequence = choice
                            editor.finish_recording()
                            feedback.setText(tr("Alternativa preparada. Pulsa Guardar."))
                            return
                    feedback.setText(tr("No hay una alternativa disponible."))

                option = button(tr("Usar alternativa"), alternative)
                option.setEnabled(self.hotkeys is not None)
                controls.addWidget(option, alignment=Qt.AlignmentFlag.AlignRight)
            shortcuts.addRow(caption, controls)
            entries.append(entry)
        error = label("", "status")
        error.setWordWrap(True)
        form.addRow(error)
        error.hide()

        def mostrar_error(message):
            error.setText(message)
            error.show()

        restart_notice = label(tr("Luz se reiniciará para aplicar el idioma"), "muted")
        restart_notice.setWordWrap(True)
        restart_notice.setVisible(language.currentData() != current_language())
        language.currentIndexChanged.connect(
            lambda: restart_notice.setVisible(language.currentData() != current_language()))
        form.addRow(restart_notice)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr("Guardar"))
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("primary")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancelar"))
        for control in buttons.buttons():
            control.setMinimumHeight(FOCUS_HEIGHT)
        form.addRow(buttons)

        previous = self.shortcut_values()

        def apply():
            language_changed = current_language() != language.currentData()
            if language_changed and (self.future or self.pending or self.before_toggle or self.configuring):
                mostrar_error(tr("Espera a que termine el cambio en curso."))
                return
            if language_changed and self.editing_scene is not None:
                mostrar_error(tr("Guarda o cancela la escena antes de cambiar el idioma."))
                return
            sequences = tuple(entry.sequence for entry in entries)
            try:
                parsed = [shortcut_parts(sequence) for sequence in sequences if sequence]
                if len(parsed) != len(set(parsed)):
                    raise ValueError(tr("Atajos duplicados."))
            except ValueError as problem:
                mostrar_error(tr(str(problem)))
                return
            failures = self.hotkeys.configure(sequences) if self.hotkeys and sequences != previous else []
            if failures:
                details = [f"{sequence} · {self.shortcut_status(index, sequence, attempted=True)}"
                           for index, sequence in enumerate(sequences) if sequence in failures]
                mostrar_error("\n".join(details))
                return
            cambiar_inicio = inicio.isEnabled() and inicio.isChecked() != bool(anterior_inicio)
            if cambiar_inicio:
                try:
                    guardar_inicio_windows(comando_inicio_windows(sys.executable) if inicio.isChecked() else "")
                except OSError:
                    if self.hotkeys and sequences != previous:
                        self.hotkeys.configure(previous)
                    mostrar_error(tr("No se pudo cambiar el inicio con Windows."))
                    return
            updates = {f"hotkey/{index}": sequence for index, sequence in enumerate(sequences)}
            updates.update(language=language.currentData(), theme=theme.currentData(), tray=resident.isChecked(),
                           brightness_step=pasos.currentData(), hotkey_schema=2)
            if inicio.isEnabled():
                updates["inicio_windows"] = inicio.isChecked()
            saved = {key: self.desktop.value(key) for key in updates if self.desktop.contains(key)}
            for key, value in updates.items():
                self.desktop.setValue(key, value)
            self.desktop.sync()
            if self.desktop.status() != self.desktop.Status.NoError:
                for key in updates:
                    if key in saved:
                        self.desktop.setValue(key, saved[key])
                    else:
                        self.desktop.remove(key)
                if self.hotkeys and sequences != previous:
                    self.hotkeys.configure(previous)
                if cambiar_inicio:
                    try:
                        guardar_inicio_windows(anterior_inicio)
                    except OSError:
                        mostrar_error(tr("No se pudo restaurar el inicio con Windows."))
                        return
                mostrar_error(tr("No se pudieron guardar las preferencias."))
                return
            self.apply_theme()
            if language_changed and not self.restart():
                mostrar_error(tr("El idioma se ha guardado, pero Luz no pudo reiniciarse. Cierra y vuelve a abrir la aplicación."))
                return
            dialog.accept()

        buttons.accepted.connect(apply)
        buttons.rejected.connect(dialog.reject)
        if self.hotkeys:
            self.hotkeys.paused = True
        try:
            if embedded:
                self.mount_section(2, dialog, self.resume_hotkeys)
            else:
                dialog.exec()
        finally:
            if not embedded:
                self.resume_hotkeys()
                dialog.deleteLater()

    def apply_theme(self):
        light = self.desktop.value("theme", "dark", type=str) == "light"
        app = QApplication.instance()
        contrast = high_contrast()
        backdrop = window_backdrop(self, light, contrast)
        colors = colors_for(light, contrast)
        for role in ("accent", "text", "muted", "preview", "bulbOff"):
            app.setProperty("luz" + role[0].upper() + role[1:], colors[role])
        app.setProperty("luzHighContrast", contrast)
        app.setProperty("luzMotion", not contrast and animations_enabled())
        apply_palette(app, colors)
        app.setStyleSheet(theme_style(light, contrast=contrast, backdrop=backdrop))
        apply_fonts(app, self)
        color = QColor(app.property("luzText"))
        for index in range(len(self.section_names)):
            self.navigation.button(index).setIcon(navigation_icon(index, color))
        self.lamp.update()
        self.update_scenes()
        self.layout_lights()

    def install_desktop(self, settings, enable=True):
        self.desktop = settings
        self.winId()
        self.hotkeys = None
        self.apply_theme()
        self.start_heartbeat()
        if not enable:
            return
        if sys.platform == "win32":
            callbacks = (self.tray_toggle, *(partial(self.desktop_scene, i) for i in range(3)),
                         *(partial(self.ajustar_relativo, action, direction) for _, action, direction in AJUSTES_RELATIVOS))
            self.hotkeys = GlobalShortcuts(
                tuple(partial(self.dispatch_shortcut, index, callback) for index, callback in enumerate(callbacks)),
                repeat_from=4,
            )
            QApplication.instance().installNativeEventFilter(self.hotkeys)
            failures = self.hotkeys.configure(self.shortcut_values())
            if failures:
                self.diagnostico.registrar("error", "shortcut-unregistered")
                self.note.setText(tr("Atajos ocupados:") + " " + ", ".join(failures))
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("Luz")
        menu = QMenu(self)
        self.tray_power = menu.addAction("", self.menu_power)
        self.tray_scenes = menu.addMenu(tr("Escenas"))
        self.tray_actions = [self.tray_scenes.addAction("", partial(self.desktop_scene, index))
                             for index in range(len(self.scene_slots))]
        menu.addSeparator()
        menu.addAction(tr("Abrir Luz"), self.restore_window)
        menu.addAction(tr("Salir"), self.quit_desktop)
        menu.aboutToShow.connect(self.open_tray_menu)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        self.update_tray()
        self.tray.show()

    def open_tray_menu(self):
        self.refresh()
        self.update_tray()

    def update_tray(self):
        if self.tray is None:
            return
        self.tray_power.setText(tr("Apagar") if self.power_on else tr("Encender"))
        ready = bool(self.token) and not self.configuring and self.editing_scene is None
        self.tray_power.setEnabled(ready)
        for entry, scene in zip(self.tray_actions, self.scene_slots):
            entry.setText(scene.name)
            entry.setEnabled(ready and (scene.mode != "color" or self.bulb.features.rgb))

    def menu_power(self):
        self.tray_toggle()

    def dispatch_shortcut(self, index, callback):
        self.current_shortcut = index
        self.shortcut_times[index] = strftime("%H:%M:%S")
        self.set_shortcut_result(index, "Windows recibió el atajo")
        try:
            callback()
            if self.shortcut_results[index] == "Windows recibió el atajo":
                self.set_shortcut_result(index, "Acción no disponible ahora")
        finally:
            self.current_shortcut = None

    def tray_toggle(self):
        if not self.configuring and self.token and self.editing_scene is None:
            self.schedule("desktop_power", None)
            self.send_timer.stop()
            self.pump()

    def desktop_scene(self, index):
        if self.configuring:
            return
        if self.online:
            self.activate_scene(index)
        elif self.token and self.editing_scene is None:
            scene = self.scene_slots[index]
            self.schedule("scene", scene.command())

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.restore_window()

    def restore_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.start_heartbeat()
        self.refresh()

    def restart(self):
        arguments = [] if getattr(sys, "frozen", False) else [str(Path(__file__).resolve())]
        arguments.append("--restart")
        if "--sin-bandeja" in sys.argv:
            arguments.append("--sin-bandeja")
        started, _ = QProcess.startDetached(sys.executable, arguments, str(Path(sys.executable).parent))
        if not started:
            return False
        self.quit_desktop()
        return True

    def quit_desktop(self):
        self.exiting = True
        self.close()
        QApplication.instance().quit()

    def lights_menu(self):
        try:
            profiles = profiles_for_display()
        except (OSError, ValueError):
            self.note.setText(tr("No se pudieron leer las luces guardadas."))
            return
        menu = QMenu(self)
        bulbs = []
        rooms = {}
        for mac, name in profiles:
            try:
                bulb = Bulb(mac)
            except ValueError:
                menu.addAction(name).setEnabled(False)
                continue
            bulbs.append(bulb)
            rooms.setdefault(bulb.room, []).append(bulb)
        for room, devices in rooms.items():
            section = menu.addMenu(room) if room else menu
            for bulb in devices:
                title = bulb.name or bulb.xiaomi_name or bulb.model
                state, detail = self.connection_states.get(bulb.mac, ("◷ " + tr("Sin comprobar"), ""))
                item = section.addAction(f"{title} · {state}", partial(self.select_light, bulb))
                item.setToolTip(detail)
                item.setCheckable(True)
                item.setChecked(bulb.mac == self.bulb.mac)
        active_room = rooms.get(self.bulb.room, ())
        if self.bulb.room and len(active_room) > 1:
            scope = menu.addAction(tr("Ajustes relativos en {room}").format(room=self.bulb.room))
            scope.setCheckable(True)
            scope.setChecked(bool(self.habitacion_ajustes))
            scope.triggered.connect(lambda checked: self.elegir_habitacion(active_room if checked else ()))
        if len(bulbs) > 1:
            menu.addSeparator()
            targets = menu.addMenu(tr("Aplicar color actual a…"))
            targets.addAction(tr("Todas las luces"), partial(self.apply_lights, bulbs))
            for room, devices in rooms.items():
                if room:
                    targets.addAction(room, partial(self.apply_lights, devices))
            targets.setEnabled(self.online and self.pages.currentIndex() < 2 and self.editing_scene is None)
        menu.addSeparator()
        menu.addAction(tr("Añadir bombilla"), partial(self.settings, True))
        source = self.sender()
        menu.exec(source.mapToGlobal(source.rect().bottomLeft()) if source else self.cursor().pos())
        menu.deleteLater()

    def elegir_habitacion(self, bulbs):
        if self.future or self.pending:
            self.note.setText(tr("Espera a que termine el cambio en curso."))
            return
        self.habitacion_ajustes = tuple(bulbs)
        self.note.setText(tr("Ajustes relativos en {room}").format(room=self.bulb.room)
                          if bulbs else tr("Ajustes relativos en la bombilla activa"))

    def select_light(self, bulb):
        if bulb.mac == self.bulb.mac:
            return
        if self.configuring or self.future or self.pending:
            self.note.setText(tr("Espera a que termine el cambio en curso."))
            return
        was_online = self.online
        self.update_connection(False, tr("Verificando…"))
        self.submit("settings", (bulb.ip, "", was_online, bulb.name, bulb.mac, bulb.room, bulb.xiaomi_name))

    def apply_lights(self, bulbs):
        if self.configuring or self.future or self.pending or self.editing_scene is not None:
            self.note.setText(tr("Espera a que termine el cambio en curso."))
            return
        if self.pages.currentIndex() == 0:
            action, value = "color", tuple(field.value() for field in self.colors.rgb)
        elif self.pages.currentIndex() == 1:
            action, value = "white", self.kelvin_value.value()
        else:
            return
        self.note.setText(tr("Aplicando color a las luces…"))
        self.submit("group", (bulbs, action, value))

    def settings(self, add_new=False, *, embedded=False, guided=True):
        if self.configuring or self.future or self.pending:
            self.note.setText(tr("Espera a que termine el cambio en curso para abrir Conexión."))
            return
        self.configuring = True
        self.heartbeat.stop()
        was_online = self.online
        try:
            dialog, fields = panel_form(self, tr("Conexión"), scrollable=not embedded, single_column=True)

            def group(title):
                box = QFrame()
                box.setObjectName("group")
                layout = QFormLayout(box)
                layout.setSpacing(8)
                layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
                layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
                layout.addRow(label(tr(title), "section"))
                fields.addWidget(box)
                return layout

            def instruction(layout, text):
                hint = label(tr(text), "muted")
                hint.setWordWrap(True)
                layout.addRow(hint)

            if guided:
                welcome = group("Añade tu bombilla a Luz" if self.token else "Bienvenido a Luz")
                instruction(welcome, "Selecciona Añadir bombilla para configurar otra luz, o elige una guardada para revisar sus datos. El token se guarda cifrado.")
            ip = QLineEdit()
            ip.setObjectName("bulbIp")
            secret = QLineEdit()
            secret.setEchoMode(QLineEdit.EchoMode.Password)
            secret.setObjectName("bulbToken")
            nickname = QLineEdit()
            nickname.setObjectName("bulbName")
            nickname.setMaxLength(48)
            suggestions = [tr(name) for name in ("Bombilla de cocina", "Bombilla del salón", "Bombilla del dormitorio")]
            completer = QCompleter(suggestions, nickname)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            nickname.setCompleter(completer)
            nickname.setPlaceholderText(suggestions[0])
            xiaomi_name = QLineEdit()
            xiaomi_name.setObjectName("xiaomiName")
            xiaomi_name.setMaxLength(128)
            xiaomi_name.setPlaceholderText(tr("Copia o importa el nombre original"))
            room = QLineEdit()
            room.setMaxLength(32)
            devices = MenuCombo()
            devices.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            devices.addItem(tr("Añadir bombilla"), "")
            try:
                for mac, name in profiles_for_display():
                    devices.addItem(name, mac)
            except (OSError, ValueError):
                pass
            network = group("1. Encuentra tu bombilla" if guided else "Red local")
            if guided:
                instruction(network, "Añade primero la bombilla a tu Wi-Fi con Xiaomi Home. Después busca su IP aquí o pégala junto al token.")
            field_label(network, tr("Bombillas guardadas"), devices)
            selected_status = label("", "status")
            selected_status.setWordWrap(True)
            network.addRow(selected_status)
            field_label(network, tr("Dirección IPv4"), ip)
            network.addRow(row(button(tr("Buscar bombillas"), partial(self.buscar_bombillas, dialog, ip)), None))

            access = group("2. Consigue el token" if guided else "Acceso a la bombilla")
            if guided:
                instruction(access, "Pulsa Obtener token por QR y autoriza con Xiaomi Home. Elige tu bombilla para rellenar IP y token automáticamente.")
            field_label(access, tr("Token miIO"), secret)

            error = label("", "status")
            error.setObjectName("connectionFeedback")
            error.setWordWrap(True)
            error.hide()

            def feedback(message):
                error.setText(tr(message))
                error.show()

            def import_token():
                clipboard = QApplication.clipboard()
                copied = clipboard.text()
                try:
                    address, token = parse_extractor_clipboard(copied)
                except ValueError as problem:
                    feedback(str(problem))
                    return
                if address:
                    ip.setText(address)
                secret.setText(token)
                imported_name = re.findall(r"(?im)^[ \t]*NAME[ \t]*:[ \t]*([^\r\n]+)", copied)
                if len(imported_name) == 1:
                    xiaomi_name.setText(imported_name[0].strip())
                if clipboard.text() == copied:
                    clipboard.clear()
                feedback("Datos pegados. Pulsa Verificar y guardar.")

            def import_cloud(device):
                devices.setCurrentIndex(max(0, devices.findData(device.mac)))
                ip.setText(device.ip)
                secret.setText(device.token)
                xiaomi_name.setText(device.name)
                feedback("Datos obtenidos de Xiaomi. Revisa la IP y pulsa Verificar y guardar.")

            access.addRow(row(button(tr("Obtener token por QR"), partial(self.token_help, import_cloud)),
                              button(tr("Pegar IP y token"), import_token), None))

            details = group("3. Detalles opcionales" if guided else "Detalles de la bombilla")
            if guided:
                instruction(details, "Puedes dejar estos campos vacíos. Para terminar, pulsa Verificar y guardar; si falla, podrás corregir los datos sin empezar de nuevo.")
            field_label(details, tr("Etiqueta en Luz"), nickname)
            field_label(details, tr("Nombre en Xiaomi Home"), xiaomi_name)
            field_label(details, tr("Habitación"), room)
            captions = dialog.findChildren(QLabel, "formLabel")
            label_width = max(caption.sizeHint().width() for caption in captions)
            for caption in captions:
                caption.setMinimumWidth(label_width)
            fields.addWidget(error)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
            buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr("Verificar y guardar"))
            buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("primary")
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Configurar más tarde" if guided else "Cancelar"))
            for control in buttons.buttons():
                control.setMinimumHeight(FOCUS_HEIGHT)
            fields.addWidget(buttons)
            buttons.rejected.connect(dialog.reject)

            def verification_finished(message):
                if message is None:
                    dialog.accept()
                else:
                    dialog.setEnabled(True)
                    feedback(message)

            def submit_profile():
                address = ip.text().strip()
                token = secret.text().strip()
                selected = devices.currentData()
                try:
                    IPv4Address(address)
                except ValueError:
                    feedback("Busca la bombilla o introduce una dirección IPv4 válida.")
                    ip.setFocus()
                    return
                if token and not re.fullmatch(r"[0-9a-fA-F]{32}", token):
                    feedback("El token debe tener 32 caracteres hexadecimales.")
                    secret.setFocus()
                    return
                if not (token or selected or (not add_new and devices.count() == 1 and self.token)):
                    feedback("Introduce el token de la bombilla.")
                    secret.setFocus()
                    return
                feedback("Verificando…")
                dialog.setEnabled(False)
                self.connection_result = verification_finished
                self.update_connection(False, tr("Verificando…"))
                self.submit("settings", (address, token, was_online,
                                         nickname.text().strip(), selected, room.text().strip(),
                                         xiaomi_name.text().strip()))

            def select_saved():
                selected = devices.currentData()
                try:
                    if selected == self.bulb.mac or (not add_new and not selected and devices.count() == 1):
                        profile = self.bulb
                    else:
                        profile = Bulb(selected) if selected else None
                except ValueError as problem:
                    feedback(str(problem))
                    profile = None
                state, detail = self.connection_states.get(profile.mac, (tr("Sin comprobar"), "")) if profile and (selected or self.token) else ("", "")
                selected_status.setText(" · ".join(filter(None, (state, detail))))
                selected_status.setVisible(bool(state or detail))
                nickname.setText(profile.name if profile else "")
                xiaomi_name.setText(profile.xiaomi_name if profile else "")
                room.setText(profile.room if profile else "")
                ip.setText(profile.ip if profile else "")
                secret.clear()
                secret.setPlaceholderText(tr("Guardado · escribe solo para cambiarlo") if selected or (profile and self.token)
                                          else tr("Introduce el token una sola vez"))

            devices.currentIndexChanged.connect(select_saved)
            active = devices.findData(self.bulb.mac)
            devices.setCurrentIndex(0 if add_new else max(0, active))
            select_saved()
            buttons.accepted.connect(submit_profile)
            if embedded:
                def dismiss():
                    secret.clear()
                    self.end_configuration()

                self.mount_section(1, dialog, dismiss)
            else:
                try:
                    dialog.exec()
                finally:
                    secret.clear()
                    dialog.deleteLater()
        finally:
            if not embedded or self.section_dialog is None:
                self.end_configuration()

    def end_configuration(self):
        self.connection_result = None
        self.configuring = False
        self.start_heartbeat()

    def buscar_bombillas(self, parent, ip):
        dialog, form = panel_form(parent, tr("Buscar bombillas"))
        estado = label(tr("Buscando dispositivos miIO en la red local…"), "status")
        estado.setWordWrap(True)
        form.addRow(estado)
        resultados = QListWidget()
        form.addRow(resultados)
        aceptar = button(tr("Usar esta IP"), dialog.accept, "primary")
        aceptar.setEnabled(False)
        form.addRow(row(None, aceptar, button(tr("Cerrar"), dialog.reject)))
        resultados.currentItemChanged.connect(lambda item, _: aceptar.setEnabled(item is not None))
        resultados.itemDoubleClicked.connect(dialog.accept)
        future = self.executor.submit(descubrir_bombillas)
        reloj = QTimer(dialog, interval=75)

        def mostrar_resultados():
            if not future.done():
                return
            reloj.stop()
            try:
                dispositivos = future.result()
            except Exception:
                self.diagnostico.registrar("error", "discovery")
                dispositivos = ()
            if not dispositivos:
                estado.setText(tr("No se encontraron bombillas. Comprueba la corriente, la red Wi-Fi y el firewall de Windows. Evita la red de invitados."))
                return
            estado.setText(tr("Elige una dirección. Luz comprobará la bombilla con su token al guardar."))
            for dispositivo in dispositivos:
                partes = [dispositivo.ip]
                partes.append(dispositivo.model or tr("Modelo sin identificar"))
                partes.append(dispositivo.mac or tr("MAC sin identificar"))
                resultados.addItem(" · ".join(partes))
                resultados.item(resultados.count() - 1).setData(Qt.ItemDataRole.UserRole, dispositivo.ip)

        reloj.timeout.connect(mostrar_resultados)
        reloj.start()
        try:
            if dialog.exec() and resultados.currentItem():
                ip.setText(resultados.currentItem().data(Qt.ItemDataRole.UserRole))
        finally:
            reloj.stop()
            future.cancel()
            dialog.deleteLater()

    def token_help(self, on_device=None):
        from TokenXiaomi import TokenDialog
        dialog = TokenDialog(self, MenuCombo())
        apply_fonts(QApplication.instance(), dialog)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected is not None and callable(on_device):
                on_device(dialog.selected)
        finally:
            dialog.stop()
            dialog.selected = None
            dialog.deleteLater()

    def update_controls(self):
        for control in self.controls:
            control.setEnabled(self.online)
        if self.editing_scene is not None:
            for control in (self.power, self.lamp, self.flow, self.timer):
                control.setEnabled(False)

    def update_connection(self, online, title):
        self.online = online
        self.update_controls()
        self.connection.setText(title)
        self.connection.setProperty("offline", not online)
        self.connection.style().unpolish(self.connection)
        self.connection.style().polish(self.connection)
        if self.tray is not None:
            self.tray_power.setEnabled(bool(self.token) and not self.configuring and self.editing_scene is None)

    def schedule(self, action, value):
        recoverable = action in ("desktop_power", "scene") or action.startswith(("relative_", "room_"))
        if self.configuring or (self.in_flight and self.in_flight[0] == "settings"):
            return
        if not self.online and not (self.token and recoverable):
            return
        if action == "desktop_power":
            # A toggle observes all earlier commands, including ones that implicitly turn the light on.
            self.before_toggle.extend((key, target, self.pending_shortcuts.get(key))
                                      for key, target in self.pending.items())
            self.pending.clear()
            self.pending_shortcuts.clear()
        visual = ("color", "white", "scene", "flow")
        for key in visual if action in visual else (action,):
            self.pending.pop(key, None)
            previous = self.pending_shortcuts.pop(key, None)
            if previous is not None and previous != self.current_shortcut:
                self.set_shortcut_result(previous, "Sustituido por un cambio posterior")
        self.pending[action] = value
        self.pending_shortcuts[action] = self.current_shortcut
        self.set_shortcut_result(self.current_shortcut, "Pendiente")
        self.note.setText(tr("Enviando cambio…"))
        if action == "power":
            self.show_power(value)
            self.send_timer.stop()
            self.pump()
        elif not self.send_timer.isActive():
            self.send_timer.start()

    def pump(self):
        if self.future or not self.pending:
            return
        if self.before_toggle:
            action, value, shortcut = self.before_toggle.popleft()
        else:
            action = next(iter(self.pending))
            value = self.pending.pop(action)
            shortcut = self.pending_shortcuts.pop(action, None)
        self.submit(action, value, shortcut=shortcut)

    def check_connection(self):
        if self.configuring or self.future or self.pending:
            self.note.setText(tr("Espera a que termine el cambio en curso."))
        elif self.token:
            self.note.setText(tr("Comprobando…"))
            self.submit("check")
        else:
            self.diagnostico.registrar("check", "unconfigured")
            self.note.setText(tr("Abre Conexión para guardar el token de la bombilla."))

    def start_heartbeat(self):
        if self.token and not self.configuring and not self.closing:
            interval = 60000
            if self.heartbeat.interval() != interval:
                self.heartbeat.setInterval(interval)
            if not self.heartbeat.isActive():
                self.heartbeat.start()

    def refresh(self, *, silent=False):
        if not self.configuring and self.token and not self.future and not self.pending:
            if silent:
                self.submit("status", silent=True)
            else:
                self.submit("status")

    def submit(self, action, value=None, *, shortcut=None, silent=False):
        self.in_flight_silent = silent
        self.in_flight_shortcut = shortcut
        self.set_shortcut_result(self.in_flight_shortcut, "Enviando cambio…")
        self.previous_command_ip = self.bulb.ip
        self.in_flight = (action, value)
        self.future = self.executor.submit(self.call, action, value)
        self.future.add_done_callback(self.notify_finished)

    def notify_finished(self, _):
        if not self.closing:
            self.command_finished.emit()

    def call(self, action, value):
        if action == "retry_group" or action == "group" or action.startswith("room_"):
            if action == "retry_group":
                entries = value
            elif action == "group":
                bulbs, command, target = value
                entries = tuple(GroupEntry(bulb, command, target) for bulb in bulbs)
            else:
                bulbs, steps, _ = value
                command = action.removeprefix("room_")
                entries = tuple(GroupEntry(bulb, command, steps, relative=True) for bulb in bulbs)
            return self.call_group(entries), None
        if action.startswith("relative_"):
            return self.bulb.ajustar_relativo(self.token, action.removeprefix("relative_"), value), None
        if action == "desktop_power":
            state = self.bulb.control(self.token, "status")
            return self.bulb.control(self.token, "power", not state.is_on), None
        if action != "settings":
            return self.bulb.control(self.token, "status" if action == "check" else action, value), None
        ip, replacement, _, name, selected, room, xiaomi_name = value
        if selected:
            candidate = Bulb(selected)
            candidate.ip = ip
            token = replacement or load_token(selected)
        else:
            token = replacement or self.token
            candidate = Bulb.identify(ip, token)
            if not replacement and (candidate.mac, candidate.model) != (self.bulb.mac, self.bulb.model):
                raise ValueError(tr("Introduce el token de la nueva bombilla para cambiar de dispositivo."))
        result = candidate.control(token, "status", recover=False)
        save_profile(candidate, token, name, room, xiaomi_name)
        candidate.name, candidate.room, candidate.xiaomi_name = name, room, xiaomi_name
        return result, (candidate, token)

    def call_group(self, entries):
        active_status = None
        results = []
        deadline = monotonic() + 12
        for entry in entries:
            if self.closing:
                break
            if entry.state in {"applied", "incompatible"}:
                results.append(entry)
                continue
            now = monotonic()
            bulb, command = entry.bulb, entry.command
            if (command == "color" and not bulb.features.rgb
                    or command == "white" and (
                        not bulb.features.tunable_white or
                        (not entry.relative and not bulb.features.minimum <= entry.value <= bulb.features.maximum))):
                results.append(replace(entry, state="incompatible"))
                continue
            if now >= deadline:
                results.append(replace(entry, state="timeout"))
                continue
            deadline_context = COMMAND_DEADLINE.set(min(deadline, now + 3))
            try:
                token = self.token if bulb.mac == self.bulb.mac else load_token(bulb.mac)
                if entry.relative:
                    target = bulb.relative_target(token, command, entry.value, recover=False)
                    entry = replace(entry, value=target, relative=False)
                state = bulb.control(token, command, entry.value, recover=False)
                if bulb.mac == self.bulb.mac:
                    active_status = state
                results.append(replace(entry, state="applied", detail=""))
            except UnsupportedControl:
                results.append(replace(entry, state="incompatible"))
            except (OSError, ValueError, DeviceException) as error:
                detail = mensaje_error_conexion(error) or "La bombilla no responde. Comprueba la Wi-Fi y el token."
                results.append(replace(entry, state="failed", detail=detail))
            finally:
                COMMAND_DEADLINE.reset(deadline_context)
        return active_status, sum(entry.state == "applied" for entry in results), tuple(results)

    def show_group_results(self):
        dialog, form = panel_form(self, tr("Resultado del grupo"), scrollable=True)
        status = {"applied": "+ Aplicada", "failed": "× Fallida",
                  "incompatible": "— Omitida por compatibilidad", "timeout": "… No atendida por tiempo"}
        for entry in self.group_results:
            bulb = entry.bulb
            detail = tr(status[entry.state])
            if entry.detail and entry.state == "failed":
                detail += " · " + tr(entry.detail)
            text = label(detail, "status")
            text.setWordWrap(True)
            text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            form.addRow(label(bulb.name or bulb.xiaomi_name or bulb.model), text)
        def retry():
            if not self.configuring and not self.future and not self.pending:
                dialog.accept()
                self.submit("retry_group", self.group_results)
        action = button(tr("Reintentar las fallidas"), retry)
        action.setEnabled(any(entry.state in {"failed", "timeout"} for entry in self.group_results))
        form.addRow(row(None, action, button(tr("Cerrar"), dialog.reject)))
        dialog.exec()
        dialog.deleteLater()

    def finish(self):
        if self.closing or self.future is None or not self.future.done():
            return
        future, self.future = self.future, None
        action, value = self.in_flight
        settings_changed = action == "settings"
        silent, self.in_flight_silent = self.in_flight_silent, False
        self.in_flight = None
        shortcut, self.in_flight_shortcut = self.in_flight_shortcut, None
        try:
            status, profile = future.result()
        except Exception as error:
            if silent:
                if self.online:
                    self.update_connection(False, tr("Sin conexión"))
                    self.update_tray()
                if not self.send_timer.isActive():
                    self.pump()
                return
            causa = codigo_error_conexion(error) or "connection"
            self.diagnostico.registrar("check" if action == "check" else "error",
                                       "unsupported" if isinstance(error, UnsupportedControl) else causa)
            detalle = mensaje_error_conexion(error)
            if detalle is None and isinstance(error, ValueError) and str(error) in EN:
                detalle = str(error)
            if isinstance(error, CambioNoAplicado):
                self.set_shortcut_result(shortcut, "El cambio no se aplicó")
                self.update_connection(True, tr("●  Conectada"))
                self.render_status(error.status)
                self.note.setText(tr(str(error)))
                self.update_tray()
                if not self.send_timer.isActive():
                    self.pump()
                return
            if isinstance(error, UnsupportedControl):
                self.set_shortcut_result(shortcut, "Control no disponible para esta bombilla.")
                self.note.setText(tr(detalle or "Control no disponible para esta bombilla."))
                if not self.send_timer.isActive():
                    self.pump()
                return
            if shortcut is not None:
                self.set_shortcut_result(shortcut, "El atajo funciona; el fallo es de conexión")
                self.diagnostico.registrar("error", "shortcut-command")
                detalle = " · ".join(filter(None, (tr(self.shortcut_results[shortcut]), tr(detalle) if detalle else "")))
            for _, _, queued_shortcut in self.before_toggle:
                self.set_shortcut_result(queued_shortcut, "Cancelado por un fallo de conexión")
            self.before_toggle.clear()
            for queued_shortcut in self.pending_shortcuts.values():
                self.set_shortcut_result(queued_shortcut, "Cancelado por un fallo de conexión")
            self.pending.clear()
            self.pending_shortcuts.clear()
            if settings_changed:
                message = detalle or "No se pudo verificar la nueva bombilla."
                self.note.setText(tr(message))
                was_online = value[2]
                self.update_connection(was_online, tr("●  Conectada") if was_online else tr("Sin conexión"))
                callback, self.connection_result = self.connection_result, None
                if callback:
                    callback(message)
                return
            state_label = {
                "not-found": "Sin respuesta", "probable-token": "Token rechazado (probable)",
                "authentication": "Token rechazado (probable)", "identity": "IP de otro dispositivo",
                "invalid-response": "Respuesta no válida",
            }.get(causa, "Sin conexión")
            title = "× " + tr(state_label)
            self.connection_states[self.bulb.mac] = (title, tr(detalle or "La bombilla no responde. Comprueba la Wi-Fi y el token."))
            self.update_connection(False, title)
            self.power_readout.setText(tr("Estado desconocido"))
            self.show_power(self.power_on)
            self.lamp.lit = False
            self.lamp.update()
            self.note.setText(tr(detalle or "La bombilla no responde. Comprueba la Wi-Fi y el token."))
            return
        if silent:
            if not self.online or status != self.last_status:
                message = self.note.text()
                self.update_connection(True, tr("●  Conectada"))
                self.connection_states[self.bulb.mac] = (tr("●  Conectada"), "")
                self.render_status(status)
                self.note.setText(message)
                self.update_tray()
            if not self.send_timer.isActive():
                self.pump()
            return
        self.set_shortcut_result(shortcut, "Aplicado")
        if action == "retry_group" or action == "group" or action.startswith("room_"):
            active_status, applied, self.group_results = status
            if active_status:
                title = tr("●  Conectada")
                self.connection_states[self.bulb.mac] = (title, "")
                self.update_connection(True, title)
                self.render_status(active_status)
            message = tr("{count} de {total} luces aplicadas.").format(count=applied, total=len(self.group_results))
            if any(entry.state in {"failed", "timeout"} for entry in self.group_results):
                if shortcut is not None:
                    self.set_shortcut_result(shortcut, "El atajo llegó; hubo luces sin aplicar")
                    self.diagnostico.registrar("error", "shortcut-command")
                self.diagnostico.registrar("error", "group")
                if not self.isVisible() and self.tray is not None:
                    self.tray.showMessage("Luz", message)
            self.note.setText(message)
            self.group_details.show()
            self.update_tray()
            self.pump()
            return
        if profile:
            self.habitacion_ajustes = ()
            self.bulb, self.token = profile
            self.start_heartbeat()
            if self.editing_scene is not None:
                self.end_scene_edit()
            self.update_device()
        self.connection_states[self.bulb.mac] = (tr("●  Conectada"), "")
        self.update_connection(True, tr("●  Conectada"))
        self.render_status(status)
        if settings_changed:
            callback, self.connection_result = self.connection_result, None
            if callback:
                callback(None)
        if action == "check":
            self.diagnostico.registrar("check", "ok")
            mac = ":".join(self.bulb.mac[index:index + 2] for index in range(0, 12, 2))
            self.note.setText(tr("Compatibilidad verificada · {model} · MAC {mac} · {ip}").format(
                model=self.bulb.model, mac=mac, ip=self.bulb.ip))
        if not profile and self.bulb.ip != getattr(self, "previous_command_ip", self.bulb.ip):
            self.note.setText(tr("Nueva IP verificada y adoptada."))
            self.diagnostico.registrar("check", "recovered")
        self.update_tray()
        if not self.send_timer.isActive():
            self.pump()

    def render_status(self, status):
        self.last_status = status
        self.power_on = status.is_on
        self.flowing = status.color_flowing
        self.delay_off = status.delay_off or 0
        brightness_preview = self.brightness.isSliderDown() or "brightness" in self.pending
        self.show_power(self.requested_power(), update_preview=not brightness_preview)
        if not self.power_on:
            self.power_readout.setText(tr("Apagada"))
        elif status.color_flowing:
            self.power_readout.setText(tr("Encendida · Ciclo de color"))
        elif status.color_temp:
            self.power_readout.setText(tr("Encendida · Blanco {temperature} K").format(temperature=status.color_temp))
        elif status.rgb or status.hsv:
            rgb = status.rgb or color_from_hsv(status.hsv).getRgb()[:3]
            self.power_readout.setText(tr("Encendida · #%02X%02X%02X") % rgb)
        else:
            self.power_readout.setText(tr("Encendida"))

        self.timer.setText(tr("Apagado en {minutes} min").format(minutes=self.delay_off) if self.delay_off else tr("Temporizador…"))
        if self.pending or self.send_timer.isActive():
            return
        if self.editing_scene is not None:
            self.note.setText(tr("Vista previa de la escena · los cambios se guardan al confirmar."))
            return
        level = max(1, status.brightness or 1)
        editing_brightness = self.brightness_value.hasFocus() and self.brightness_value.lineEdit().isModified()
        if not brightness_preview and not editing_brightness:
            self.set_number(self.brightness, level)
            self.set_number(self.brightness_value, level)
            self.lamp.level = level
        if status.color_temp:
            if not self.temperature.isSliderDown() and not self.kelvin_value.hasFocus():
                self.set_number(self.temperature, status.color_temp)
                self.set_number(self.kelvin_value, status.color_temp)
                self.temperature.update()
            self.lamp.color = white_preview(status.color_temp)
        elif status.rgb or status.hsv:
            color = QColor(*status.rgb) if status.rgb else color_from_hsv(status.hsv)
            self.lamp.color = color
            fields = (self.colors.hex, self.colors.degrees, *self.colors.rgb)
            if (tuple(field.value() for field in self.colors.rgb) != color.getRgb()[:3]
                    and not self.colors.hue.isSliderDown() and not any(field.hasFocus() for field in fields)):
                self.colors.set_color(color)
        elif not self.bulb.features.tunable_white:
            self.lamp.color = white_preview(self.bulb.features.minimum)
        self.lamp.update()
        self.note.setText(self.scenes_error or tr("Red local · {ip} · MAC verificada").format(ip=self.bulb.ip))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, "heartbeat"):
            if self.isMinimized():
                self.resume_hotkeys()
                self.start_heartbeat()
                if self.tray is not None and self.desktop.value("tray", True, type=bool):
                    QTimer.singleShot(0, self.hide)
            elif self.isVisible():
                self.start_heartbeat()
                self.refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, "editor_card"):
            return
        self.layout_lights()
        self.lamp.setMinimumHeight(max(168, min(280, event.size().height() - 540)))

    def layout_lights(self):
        grid = self.light_grid
        margins = grid.parent().contentsMargins()
        scroll = self.sections.widget(0)
        rail_width = max(self.rail.minimumWidth(), self.rail.minimumSizeHint().width())
        cards_width = self.light.minimumSizeHint().width() + self.editor_card.minimumSizeHint().width()
        scrollbar_width = scroll.verticalScrollBar().sizeHint().width()
        gutters = margins.left() + margins.right() + grid.horizontalSpacing()
        stacked = self.width() < rail_width + cards_width + gutters + scrollbar_width
        if getattr(self, "stacked_lights", None) != stacked:
            self.stacked_lights = stacked
            self.light_grid.addWidget(self.editor_card, int(stacked), int(not stacked))
            self.light_grid.addWidget(self.scenes_card, 2 if stacked else 1, 0, 1, 1 if stacked else 2)
            self.light_grid.setColumnStretch(1, 0 if stacked else 10)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.isMinimized():
            if self.hotkeys and self.section_dialog is not None and self.sections.currentIndex() == 2:
                self.hotkeys.paused = True
            self.start_heartbeat()

    def hideEvent(self, event):
        self.resume_hotkeys()
        super().hideEvent(event)
        if self.closing:
            self.heartbeat.stop()
        else:
            self.start_heartbeat()

    def closeEvent(self, event):
        language_changed = self.desktop is not None and self.desktop.value("language", "es", type=str) != current_language()
        if not self.exiting and not language_changed and self.tray is not None and self.desktop.value("tray", True, type=bool):
            event.ignore()
            self.hide()
            return
        self.closing = True
        if self.tray is not None:
            self.tray.hide()
        if getattr(self, "hotkeys", None):
            self.hotkeys.clear()
            QApplication.instance().removeNativeEventFilter(self.hotkeys)
        self.heartbeat.stop()
        self.send_timer.stop()
        self.executor.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    settings = preferences()
    set_language(settings.value("language", "es", type=str))
    lock = QLockFile(str(PROFILE_FILE.with_name("Luz.lock")))
    oculto = "--oculto" in sys.argv
    manage_desktop = "--sin-bandeja" not in sys.argv
    desktop_owner = desktop_lock() if sys.platform == "win32" and manage_desktop else None
    lock_timeout = 15000 if "--restart" in sys.argv else 0
    if not lock.tryLock(lock_timeout) or (desktop_owner is not None and not desktop_owner.tryLock(lock_timeout)):
        if not oculto:
            QMessageBox.information(None, "Luz", tr("Luz ya está abierta. Búscala junto al reloj de Windows."))
        return 0
    app.setStyle("Fusion")
    app.setWindowIcon(app_icon())
    window = Window()
    window.install_desktop(settings, enable=manage_desktop)
    if getattr(sys, "frozen", False) and not oculto and manage_desktop:
        try:
            actualizar_inicio_windows(sys.executable)
        except OSError:
            window.note.setText(tr("No se pudo actualizar el inicio con Windows."))
    if not oculto or window.tray is None:
        window.show()
        QTimer.singleShot(0, window.start_first_run)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
