"""Diagnostic snapshots built from an explicit set of non-secret fields."""
import logging
import os
import platform
import re
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from tempfile import NamedTemporaryFile

from BombillaLocal import IP_FILE, PROFILE_FILE, STATE_DIR, TOKEN_FILE, capabilities
from Escenas import SCENE_FILE
from Idioma import tr

LUZ_VERSION = "1.0.1"
EVENTOS = {
    "check": {"ok", "recovered", "unconfigured", "not-found", "authentication", "probable-token", "invalid-response", "identity", "timeout", "connection"},
    "error": {"not-found", "authentication", "probable-token", "invalid-response", "identity", "timeout", "connection", "unsupported", "group", "discovery", "shortcut-unregistered", "shortcut-command"},
}
LIMITE_REGISTRO = 64 * 1024

# The driver may include handshake checksums and payloads in its own logs.
for nombre in ("miio", *(key for key in logging.root.manager.loggerDict if key.startswith("miio."))):
    logging.getLogger(nombre).setLevel(logging.CRITICAL + 1)


class Diagnostico:
    def __init__(self, carpeta=STATE_DIR):
        self.registro = carpeta / "luz-diagnostico.log"
        self.anterior = self.registro.with_suffix(".log.1")

    def registrar(self, evento, resultado):
        if resultado not in EVENTOS.get(evento, ()):
            return
        linea = f"{datetime.now():%Y-%m-%dT%H:%M:%S} {evento}: {resultado}\n"
        try:
            self.registro.parent.mkdir(parents=True, exist_ok=True)
            if self.registro.exists() and self.registro.stat().st_size + len(linea) > LIMITE_REGISTRO:
                self.registro.replace(self.anterior)
            with self.registro.open("a", encoding="utf-8", newline="\n") as registro:
                registro.write(linea)
        except OSError:
            pass

    def comprobar_destino(self, ruta, *, para_escenas=False):
        destino = ruta.resolve()
        protegidos = (self.registro, self.anterior, IP_FILE, PROFILE_FILE, TOKEN_FILE,
                      STATE_DIR / "preferencias.ini", STATE_DIR / "Luz.lock",
                      Path(os.environ["LOCALAPPDATA"]) / "Luz" / "escritorio.lock")
        if ((not para_escenas and destino == SCENE_FILE.resolve())
                or any(destino == path.resolve() for path in protegidos)):
            raise ValueError("protected path")

    def exportar(self, ruta, bombilla, ajustes):
        self.comprobar_destino(ruta)
        lineas = [
            f"Luz {LUZ_VERSION}", f"Windows: {platform.release()} ({platform.version()})",
            f"Python: {platform.python_version()}",
        ]
        for libreria in ("PySide6_Essentials", "python-miio", "PyInstaller"):
            try:
                instalada = version(libreria)
            except PackageNotFoundError:
                instalada = "—"
            lineas.append(f"{libreria}: {instalada}")
        try:
            features = capabilities(bombilla.model)
        except ValueError:
            lineas.append(f'{tr("Modelo")}: —')
        else:
            lineas.extend((
                f'{tr("Modelo")}: {bombilla.model}',
                f"RGB: {features.rgb} · {features.minimum}–{features.maximum} K · {tr('Efectos')}: {features.effects}",
            ))
        if ajustes is not None:
            lineas.append(tr("Preferencias"))
            for campo, etiqueta, validos in (
                ("language", "Idioma", ("es", "en")), ("theme", "Tema", ("light", "dark")),
                ("tray", "Mantener Luz junto al reloj al cerrar", (True, False)),
                ("inicio_windows", "Iniciar Luz con Windows", (True, False)),
                ("brightness_step", "Paso de brillo", (5, 10, 15)),
            ):
                valor = ajustes.value(campo)
                lineas.append(f"{tr(etiqueta)}: {valor if valor in validos else '—'}")
        registros = []
        for origen in (self.anterior, self.registro):
            try:
                with origen.open(encoding="utf-8", errors="replace") as fichero:
                    registros_archivo = fichero.read(LIMITE_REGISTRO).splitlines()
            except OSError:
                continue
            for linea in registros_archivo:
                match = re.fullmatch(r"([0-9T:-]{19}) (check|error): ([a-z-]+)", linea)
                if match and match[3] in EVENTOS[match[2]]:
                    registros.append(linea)
        ultima = next((linea for linea in reversed(registros) if " check: " in linea), "—")
        lineas.extend(("", tr("Última comprobación de conexión"), ultima, "", tr("Últimos eventos")))
        lineas.extend(registros[-40:])
        temporal = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=ruta.parent,
                                    prefix=".luz-diagnostico-", delete=False) as archivo:
                temporal = Path(archivo.name)
                archivo.write("\n".join(lineas) + "\n")
            temporal.replace(ruta)
        finally:
            if temporal:
                temporal.unlink(missing_ok=True)
