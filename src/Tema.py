from ctypes import Structure, byref, c_int, c_uint, c_void_p, sizeof
import ctypes
import sys

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette

FOCUS_HEIGHT = 44
PANEL_RADIUS = 16
MOTION_MS = 180


def high_contrast():
    if sys.platform != "win32":
        return False

    class HighContrast(Structure):
        _fields_ = [("size", c_uint), ("flags", c_uint), ("scheme", c_void_p)]

    setting = HighContrast()
    setting.size = sizeof(setting)
    return bool(ctypes.windll.user32.SystemParametersInfoW(0x42, setting.size, byref(setting), 0)
                and setting.flags & 1)


def animations_enabled():
    if sys.platform != "win32":
        return True
    setting = c_int()
    return bool(ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, byref(setting), 0)
                and setting.value)


def apply_palette(app, roles):
    palette = QPalette()
    names = {"Window": "canvas", "WindowText": "text", "Base": "surface",
             "AlternateBase": "raised", "Button": "raised", "ButtonText": "text",
             "Text": "text", "Highlight": "accent", "HighlightedText": "ink",
             "ToolTipBase": "surface", "ToolTipText": "text", "Mid": "muted",
             "Link": "accent"}
    for name, role in names.items():
        palette.setColor(QPalette.ColorRole[name], QColor(roles[role]))
    for name in ("WindowText", "Text", "ButtonText"):
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole[name], QColor(roles["muted"]))
    app.setPalette(palette)


def window_backdrop(widget, light, contrast):
    if sys.platform != "win32" or widget.window().windowHandle() is None:
        return False
    handle = c_void_p(int(widget.winId()))
    dark = c_int(int(not light and not contrast))
    dwm = ctypes.windll.dwmapi
    dwm.DwmSetWindowAttribute(handle, 20, byref(dark), sizeof(dark))
    if sys.getwindowsversion().build < 22621:
        return False
    # DWM applies the OS transparency and power preferences to the backdrop.
    material = c_int(1 if contrast else 2)
    return dwm.DwmSetWindowAttribute(handle, 38, byref(material), sizeof(material)) == 0 and not contrast


def apply_fonts(app, parent):
    font = QFont(app.font())
    families = QFontDatabase.families()
    font.setFamily("Segoe UI Variable" if "Segoe UI Variable" in families else "Segoe UI")
    app.setFont(font)
    scale = {"title": 2, "dialogTitle": 1.7, "section": 1.3,
             "toolbarTitle": 1.15, "muted": .92, "status": .92, "brand": 1.15}
    from PySide6.QtWidgets import QLabel
    for item in parent.findChildren(QLabel):
        relative = scale.get(item.objectName())
        if relative:
            styled = QFont(font)
            if font.pointSizeF() > 0:
                styled.setPointSizeF(font.pointSizeF() * relative)
            else:
                styled.setPixelSize(round(font.pixelSize() * relative))
            if relative > 1:
                styled.setWeight(QFont.Weight.DemiBold)
            item.setFont(styled)


def colors_for(light, contrast=False):
    colors = (
        ("#f5f5f5", "#eaeaea", "#ffffff", "#e9e9e9", "#d2d2d2", "#1c1c1e",
         "#525252", "#007aff", "#dbeaff", "#236243", "#e3f0e8", "#65521d", "#f3eedc")
        if light else
        ("#232323", "#303030", "#292929", "#383838", "#474747", "#f4f4f4",
         "#bcbcbc", "#0a84ff", "#243d58", "#b4dfc2", "#253a2e", "#e8d394", "#373220")
    )
    (canvas, rail, surface, raised, line, text, muted, accent, selected,
     success, success_bg, warning, warning_bg) = colors
    if contrast:
        from PySide6.QtWidgets import QApplication
        indices = {"Window": 5, "WindowText": 8, "Highlight": 13, "HighlightedText": 14}

        def color(role):
            if sys.platform == "win32":
                value = ctypes.windll.user32.GetSysColor(indices[role])
                return QColor(value & 255, (value >> 8) & 255, (value >> 16) & 255).name()
            return QApplication.style().standardPalette().color(QPalette.ColorRole[role]).name()
        canvas = rail = surface = raised = color("Window")
        line = text = muted = success = warning = color("WindowText")
        accent, selected = color("Highlight"), color("Window")
        success_bg = warning_bg = canvas
    edge = "#858585"
    accent_text = "#0058b8" if light else "#78b9ff"
    preview, bulb_off = ("#e9e9e9", "#777777") if light else ("#202020", "#585858")
    if contrast:
        edge = accent_text = text
        preview, bulb_off = canvas, muted
    ink = "#101010" if not contrast else color("HighlightedText")
    return dict(canvas=canvas, rail=rail, surface=surface, raised=raised, line=line,
                text=text, muted=muted, accent=accent, selected=selected, success=success,
                success_bg=success_bg, warning=warning, warning_bg=warning_bg, ink=ink,
                preview=preview, bulbOff=bulb_off, edge=edge, accentText=accent_text)


def theme_style(light, *, contrast=False, backdrop=False):
    roles = colors_for(light, contrast)
    (canvas, rail, surface, raised, line, text, muted, accent, selected, success, success_bg,
     warning, warning_bg, ink) = (roles[role] for role in (
        "canvas", "rail", "surface", "raised", "line", "text", "muted", "accent", "selected",
        "success", "success_bg", "warning", "warning_bg", "ink",
    ))
    edge, accent_text = roles["edge"], roles["accentText"]
    selection_bg, selection_text = (accent, ink) if contrast else (selected, text)
    chrome = rail
    chrome_layer = "transparent" if backdrop and not contrast else chrome
    return f"""
    QWidget {{ color:{text}; }}
    QDialog, QWidget#workspace, QWidget#canvasViewport {{ background:{canvas}; }}
    QScrollArea {{ border:0; background:{canvas}; }}
    QWidget#window {{ background:{chrome}; }}
    QFrame#rail, QFrame#toolbar {{ background:{chrome_layer}; }}
    QFrame#rail {{ border-right:1px solid {line}; }}
    QFrame#toolbar {{ border-bottom:1px solid {line}; }}
    QFrame#card, QDialog#panel {{ background:{surface}; }}
    QFrame#card {{ border-radius:{PANEL_RADIUS}px; }}
    QFrame#shelf {{ border-top:1px solid {line}; }}
    QFrame#rule {{ background:{line}; }}
    QFrame#group {{ background:{canvas}; border-radius:{PANEL_RADIUS}px; }}
    QPushButton#preferenceShortcut {{ padding:5px 8px; }}
    QFrame#segments {{ background:{raised}; border-radius:11px; }}
    QLabel#muted, QLabel#formLabel, QLabel#status, QLabel#connectionFeedback {{ color:{muted}; }}
    QLabel#connection {{ color:{success}; background:{success_bg}; border:1px solid {success_bg};
        border-radius:9px; padding:6px 9px; }}
    QLabel#connection[offline="true"] {{ color:{warning}; background:{warning_bg}; }}
    QPushButton {{ background:{raised}; border:1px solid {line}; border-radius:9px;
        padding:7px 11px; font-weight:600; }}
    QPushButton:hover {{ background:{selected}; }}
    QPushButton:focus, QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color:{accent}; }}
    QPushButton:disabled {{ color:{muted}; background:{rail}; }}
    QPushButton#primary {{ background:{accent}; color:{ink}; border-color:{accent}; }}
    QPushButton#primary:hover {{ background:{accent}; border-color:{accent}; }}
    QPushButton#primary:focus {{ border:2px solid {text}; }}
    QPushButton#primary:disabled {{ color:{muted}; background:{rail}; border-color:{line}; }}
    QPushButton#nav {{ background:transparent; border-color:transparent; text-align:left; }}
    QPushButton#nav:checked {{ background:{selected}; border-color:{accent}; border-radius:16px; }}
    QPushButton#nav:hover {{ background:{raised}; border-color:{line}; }}
    QPushButton#nav:focus {{ border-color:{accent}; }}
    QPushButton#credit {{ color:{accent_text}; text-align:left; }}
    QPushButton#segment {{ background:transparent; border-color:transparent; border-radius:8px; }}
    QPushButton#segment:checked {{ background:{surface}; border-color:{line}; }}
    QPushButton#segment:focus {{ border-color:{accent}; }}
    QToolButton#scene {{ padding:8px; background:{surface}; border:1px solid transparent; border-radius:12px; }}
    QToolButton#scene:hover, QToolButton#scene[editing="true"] {{ background:{selected}; }}
    QToolButton#scene:focus, QToolButton#scene[editing="true"] {{ border-color:{accent}; }}
    QLineEdit, QSpinBox, QComboBox {{ background:{canvas}; border:1px solid {edge}; border-radius:8px;
        padding:6px 8px; selection-background-color:{selection_bg}; selection-color:{selection_text}; }}
    QComboBox {{ padding-right:29px; }}
    QComboBox::drop-down {{ subcontrol-origin:padding; width:25px; border:0; }}
    QComboBox::down-arrow {{ image:none; }}
    QCheckBox {{ spacing:8px; }}
    QCheckBox::indicator {{ width:36px; height:20px; background:transparent; }}
    QCheckBox:disabled {{ color:{muted}; }}
    QComboBox QAbstractItemView {{ background:{surface}; selection-background-color:{selection_bg}; selection-color:{selection_text}; }}
    QSpinBox::up-button,QSpinBox::down-button {{ width:0; }}
    QListWidget {{ background:{canvas}; border:1px solid {line}; border-radius:8px; padding:4px;
        selection-background-color:{selection_bg}; selection-color:{selection_text}; }}
    QListWidget::item {{ padding:6px 8px; border-radius:5px; }}
    QListWidget::item:selected {{ background:{selection_bg}; color:{selection_text}; }}
    QLineEdit[invalid="true"] {{ border-color:{warning}; }}
    QSlider {{ background:transparent; }}
    QSlider::groove:horizontal {{ height:6px; background:{line}; border-radius:3px; }}
    QSlider::sub-page:horizontal {{ background:{accent}; border-radius:3px; }}
    QSlider::handle:horizontal {{ background:{surface}; border:1px solid {edge};
        width:16px; margin:-6px 0; border-radius:9px; }}
    QSlider::handle:horizontal:focus {{ background:{accent}; border-color:{text}; }}
    """


STYLE = theme_style(False)
