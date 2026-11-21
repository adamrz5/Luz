<div align="center">
  <img src="assets/Marca-Luz.png" width="80" alt="Icono de Luz">
  <h1>Luz</h1>
  <p>Tus luces Xiaomi, desde el escritorio de Windows.</p>
  <p><a href="https://github.com/adamrz5/Luz/releases/latest"><strong>Descargar para Windows</strong></a> · <a href="README.md">English</a> · <a href="docs/REFERENCE.es.md">Documentación</a></p>
</div>

![Luz: vista previa de la bombilla, controles de iluminación y escenas guardadas](assets/screenshot-dark.png)

Controla bombillas Wi-Fi Xiaomi y Yeelight compatibles desde tu red local. Ajusta el ambiente, guarda una escena y ten tus luces a mano, también desde la bandeja del sistema.

## Qué puedes hacer

- Ajustar brillo, color RGB/HEX y temperatura de blanco con vista previa inmediata.
- Guardar tres escenas; editarlas, renombrarlas, vaciarlas o exportarlas.
- Organizar bombillas y habitaciones, con ajustes de iluminación compartidos.
- Controlar encendido y escenas desde la bandeja o con atajos personalizables.
- Elegir modo claro u oscuro, en español o inglés.

## Primeros pasos

**Windows x64 · Windows 10 1809 o posterior · No necesitas instalar Python.**

1. Descarga el instalador `.exe` desde [Releases](https://github.com/adamrz5/Luz/releases/latest) e instala Luz.
2. Añade la bombilla a tu Wi-Fi con **Xiaomi Home**. Mantén el PC en la misma red local.
3. En Luz, abre **Conexión → Obtener token por QR**, elige tu región de Xiaomi Home y genera el QR.
4. Escanéalo con Xiaomi Home, autoriza el acceso y selecciona tu bombilla.
5. Pulsa **Verificar y guardar**. Luz comprueba el dispositivo antes de guardar sus credenciales.

También puedes introducir la IP y el token manualmente. Para añadir otra bombilla, utiliza **Conexión → Añadir bombilla**. La guía sigue disponible en **Ayuda → Ayuda**.

> El instalador no tiene firma digital. Windows puede mostrar un aviso de editor desconocido. Compara su SHA-256 con `SHA256SUMS.txt` de la misma versión.

## Compatibilidad

**Probada físicamente:** Xiaomi Mi Smart LED Bulb Essential (**MJDPL01YL**, `yeelink.light.color5`).

Los demás modelos miIO admitidos cuentan con comprobaciones del controlador y pruebas simuladas; no todos se han probado con bombillas reales. Consulta **Ayuda → Modelos compatibles** o la [tabla de compatibilidad](docs/REFERENCE.es.md#bombillas-compatibles). Este transporte no admite bombillas Bluetooth, Zigbee, Matter ni las que requieren una pasarela.

## Atajos

Controla el encendido y las escenas con atajos globales; personalízalos en **Preferencias**. Consulta los valores y su estado en **Ayuda → Atajos** o en la [guía de atajos](docs/REFERENCE.es.md#uso-diario).

## Privacidad

Las órdenes de iluminación se envían por la red local mediante miIO. El acceso a la nube de Xiaomi solo se utiliza cuando solicitas la configuración por QR. Los tokens seleccionados se guardan cifrados con **Windows DPAPI**; las credenciales de la sesión de nube permanecen en memoria y se descartan al terminar el trabajador. Las etiquetas locales no cambian el nombre en Xiaomi Home.

Desinstalar conserva tus datos. Si reinstalas Windows, obtén el token de nuevo: las credenciales DPAPI pertenecen al usuario de Windows que las guardó. Consulta [almacenamiento y límites del protocolo](docs/REFERENCE.es.md#privacidad-y-datos).

## Desarrollo

Requiere Windows x64 y Python 3.11. Sigue la [guía de instalación desde el código](docs/REFERENCE.es.md#desarrollo).

Ejecuta las pruebas seguras con `.\.venv\Scripts\python.exe -B tests/ejecutar-seguras.py`. Utilizan datos temporales y no controlan una bombilla real.

[Arquitectura](docs/REFERENCE.es.md#arquitectura) · [Compilar y firmar](docs/REFERENCE.es.md#compilación-y-firma) · [CI de Windows](https://github.com/adamrz5/Luz/actions) · [Límites de validación](docs/REFERENCE.es.md#validación-y-límites)

[Informa de un fallo](https://github.com/adamrz5/Luz/issues) indicando el modelo de bombilla, la versión de Windows y los pasos para reproducirlo. No compartas tokens ni credenciales. Si modificas el código, limita los cambios al problema y ejecuta las pruebas seguras.

## Licencia

[GPL-3.0](LICENSE) · Creado por [adamrz5](https://github.com/adamrz5).

Desarrollado con [python-miio](https://github.com/rytilahti/python-miio), [PySide6](https://doc.qt.io/qtforpython-6/) y el extractor comunitario [Xiaomi Cloud Tokens Extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor). Consulta las [licencias de terceros y créditos](docs/REFERENCE.es.md#licencia-y-créditos).
