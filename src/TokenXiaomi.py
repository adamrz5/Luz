"""Native on-demand QR setup; cloud work never runs on the Qt thread."""
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue
from threading import Event

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt, QTimer
from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QScrollArea, QVBoxLayout, QWidget

from Idioma import tr
from XiaomiCloud import REGIONS, scan


class TokenDialog(QDialog):
    def __init__(self, parent, region_picker):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setWindowTitle(tr("Conectar con Xiaomi"))
        self.setMinimumWidth(540)
        self.resize(600, min(520, parent.screen().availableGeometry().height() - 72))
        self.selected = None
        self.devices = ()
        self.events = Queue()
        self.cancelled = Event()
        self.executor = None
        self.future = None
        self.timer = QTimer(self, interval=100)
        self.timer.timeout.connect(self.poll)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        self.scroll = scroll
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        body = QVBoxLayout(content)
        body.setContentsMargins(24, 20, 24, 22)
        body.setSpacing(12)
        body.setAlignment(Qt.AlignmentFlag.AlignTop)

        def text(message, role="muted"):
            label = QLabel(tr(message))
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setObjectName(role)
            label.setWordWrap(True)
            body.addWidget(label)
            return label

        text("Añade tu bombilla a Luz", "dialogTitle")
        text("1. Añade la bombilla a tu Wi-Fi con Xiaomi Home y conecta el PC a la misma red.")
        text("2. Elige la región de Xiaomi Home y genera el QR. Escanéalo con Xiaomi Home y confirma el acceso en el móvil.")
        text("3. Elige tu bombilla. Luz rellenará IP y token; después pulsa Verificar y guardar en Conexión.")
        text("Solo al generar el QR se conecta con Xiaomi. La sesión se mantiene en memoria y se descarta al terminar; no se guarda tu contraseña.")
        self.region = region_picker
        self.region.setAccessibleName(tr("Región de Xiaomi Home"))
        names = ("Europa (de)", "China (cn)", "Estados Unidos (us)", "Rusia (ru)",
                 "Taiwán (tw)", "Singapur (sg)", "India (in)", "India (i2)")
        for name, code in zip(names, REGIONS):
            self.region.addItem(tr(name), code)
        body.addWidget(self.region)
        self.qr = QLabel(tr("El QR aparecerá aquí al pulsar Generar QR."))
        self.qr.setObjectName("qrPreview")
        self.qr.setFixedSize(256, 256)
        self.qr.setWordWrap(True)
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr.setAccessibleName(tr("QR para autorizar el acceso a Xiaomi"))
        body.addWidget(self.qr, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.qr.hide()
        self.status = text("No se ha iniciado ninguna conexión.", "status")
        self.list = QListWidget()
        self.list.setAccessibleName(tr("Bombillas compatibles encontradas"))
        self.list.setMaximumHeight(130)
        self.list.hide()
        self.list.currentRowChanged.connect(lambda index: self.use.setEnabled(0 <= index < len(self.devices)))
        body.addWidget(self.list)
        actions = QHBoxLayout()
        actions.setContentsMargins(24, 0, 24, 22)
        self.generate = QPushButton(tr("Generar QR"))
        self.generate.setObjectName("primary")
        self.generate.clicked.connect(self.start)
        self.use = QPushButton(tr("Usar esta bombilla"))
        self.use.setObjectName("primary")
        self.use.setEnabled(False)
        self.use.clicked.connect(self.choose)
        self.use.hide()
        close = QPushButton(tr("Cancelar"))
        close.clicked.connect(self.reject)
        for button in (self.generate, self.use, close):
            button.setMinimumHeight(44)
            actions.addWidget(button)
        outer.addLayout(actions)

    def show_qr(self, visible):
        self.qr.setVisible(visible)
        area = self.screen().availableGeometry()
        self.resize(self.width(), min(760 if visible else 520, area.height() - 72))
        frame = self.frameGeometry()
        frame.moveCenter(area.center())
        self.move(frame.topLeft())

    def start(self):
        if self.future is not None and not self.future.done():
            return
        self.cancelled.clear()
        self.devices = ()
        self.list.clear()
        self.list.hide()
        self.use.hide()
        self.use.setEnabled(False)
        self.qr.clear()
        self.show_qr(True)
        self.qr.setText(tr("Generando QR…"))
        self.generate.setEnabled(False)
        self.region.setEnabled(False)
        self.status.setText(tr("Conectando con Xiaomi…"))
        self.events = Queue()
        if self.executor is None:
            self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="luz-qr")
        self.future = self.executor.submit(scan, self.events, self.cancelled, self.region.currentData())
        self.timer.start()

    def poll(self):
        while not self.cancelled.is_set():
            try:
                event, value = self.events.get_nowait()
            except Empty:
                break
            if event == "qr":
                buffer = QBuffer()
                buffer.setData(QByteArray(value))
                buffer.open(QIODevice.OpenModeFlag.ReadOnly)
                reader = QImageReader(buffer)
                size = reader.size()
                if not (0 < size.width() <= 1024 and 0 < size.height() <= 1024):
                    self.cancelled.set()
                    self.qr.clear()
                    self.show_qr(False)
                    self.status.setText(tr("La imagen QR de Xiaomi no es válida."))
                    continue
                image = reader.read()
                if image.isNull():
                    self.cancelled.set()
                    self.qr.clear()
                    self.show_qr(False)
                    self.status.setText(tr("La imagen QR de Xiaomi no es válida."))
                    continue
                self.qr.setPixmap(QPixmap.fromImage(image).scaled(self.qr.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation))
                self.scroll.ensureWidgetVisible(self.qr)
                self.status.setText(tr("Escanea el QR con Xiaomi Home y confirma el acceso en tu móvil."))
            elif event == "scanning":
                self.qr.clear()
                self.show_qr(False)
                self.status.setText(tr("Acceso autorizado. Buscando bombillas compatibles…"))
            elif event == "devices":
                self.devices = value
                self.qr.clear()
                self.show_qr(False)
                self.list.show()
                for device in value:
                    QListWidgetItem(f"{device.name} · {device.ip}\n{device.model}", self.list)
                self.use.show()
                if value:
                    self.list.setCurrentRow(0)
                    self.status.setText(tr("Elige la bombilla que quieres añadir a Luz."))
                else:
                    self.status.setText(tr("No se encontraron bombillas compatibles con IP local. Comprueba la región y que estén conectadas a tu Wi-Fi."))
            elif event == "error":
                self.qr.clear()
                self.show_qr(False)
                self.status.setText(tr(value))
        if (self.future is not None and self.future.done()
                and (self.cancelled.is_set() or self.events.empty())):
            if self.cancelled.is_set():
                self.events = Queue()
            self.timer.stop()
            self.generate.setEnabled(True)
            self.generate.setText(tr("Generar otro QR"))
            self.region.setEnabled(True)

    def choose(self):
        index = self.list.currentRow()
        if 0 <= index < len(self.devices):
            self.selected = self.devices[index]
            self.accept()

    def stop(self):
        self.cancelled.set()
        self.timer.stop()
        self.qr.clear()
        self.devices = ()
        self.list.clear()
        self.events = Queue()
        if self.executor is not None:
            self.executor.shutdown(wait=False, cancel_futures=True)

    def done(self, result):
        self.stop()
        super().done(result)
