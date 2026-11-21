"""Spanish source strings with English desktop translations."""
_language = "es"


def set_language(language):
    global _language
    _language = language


def current_language():
    return _language


def tr(message):
    return EN.get(message, message) if _language == "en" else message


EN = dict(line.split("|", 1) for line in """
Abre Conexión para guardar el token de la bombilla.|Open Connection to save the bulb token.
Abrir GitHub|Open GitHub
Abrir Luz|Open Luz
Ajustes de conexión|Connection settings
Acceso a la bombilla|Bulb access
Busca la bombilla o introduce una dirección IPv4 válida.|Find the bulb or enter a valid IPv4 address.
Detalles de la bombilla|Bulb details
Red local|Local network
Apagada|Off
Apagar|Turn off
Atajos duplicados.|Duplicate shortcuts.
Atajos ocupados:|Shortcuts already in use:
Ayuda|Help
Azul|Blue
Blanco|White
Blanco fijo|Fixed white
Blanco fijo · ajusta el brillo desde la tarjeta de la bombilla.|Fixed white · adjust brightness from the bulb card.
Bombilla Xiaomi|Xiaomi bulb
Bombillas guardadas|Saved bulbs
Brillo|Brightness
Brillo exacto|Exact brightness
Buscando la bombilla en la red local…|Looking for the bulb on the local network…
Cambiar nombre|Rename
Cancelar|Cancel
Cancelar temporizador|Cancel timer
Cerrar|Close
Ciclo de color|Color cycle
Claro|Light
Clic derecho en una escena para editarla. El menú junto al reloj permite controlar la luz y salir de Luz.|Right-click a scene to edit it. Use the tray menu to control the bulb or quit Luz.
Color|Color
Color hexadecimal|Hex color
Comprobando…|Checking…
Comprobar conexión|Check connection
Comprueba la IPv4 y el token de 32 caracteres.|Check the IPv4 address and 32-character token.
Conecta la bombilla para activar esta escena.|Connect the bulb to activate this scene.
Conecta la bombilla para editar el color de la escena.|Connect the bulb to edit the scene color.
Copia de escenas|Scene backup
Cálido|Warm
Datos pegados. Pulsa Verificar y guardar.|Details pasted. Select Verify and save.
Dirección IPv4|IPv4 address
Edita esta escena para guardarla en blanco con esta bombilla.|Edit this scene to use white on this bulb.
Efectos|Effects
El token debe tener 32 caracteres.|The token must have 32 characters.
Elige cuándo se apaga la bombilla.|Choose when the bulb turns off.
Encender|Turn on
Encender o apagar|Toggle power
Encendida|On
Encendida · Ciclo de color|On · Color cycle
Entendido|Got it
Enviando cambio…|Sending change…
Escenas|Scenes
Editar escena|Edit scene
Editando «{name}». Ajusta color y brillo y pulsa Guardar escena.|Editing “{name}”. Adjust color and brightness, then select Save scene.
Escenas importadas.|Scenes imported.
Espera a que termine el cambio en curso para abrir Conexión.|Wait for the current change before opening Connection.
Esta bombilla tiene blanco fijo.|This bulb has fixed white.
Estado desconocido|Unknown status
Estado pendiente|Waiting for status
Exportar escenas…|Export scenes…
Frío|Cool
Guardado · escribe solo para cambiarlo|Saved · enter a replacement to change it
Guardar|Save
Guardar escena|Save scene
Idioma|Language
Importar escenas…|Import scenes…
Introduce #RRGGBB y pulsa Intro. Ejemplo: #176CE3.|Enter #RRGGBB and press Enter. Example: #176CE3.
Introduce el token de la bombilla.|Enter the bulb token.
Introduce el token de la nueva bombilla para cambiar de dispositivo.|Enter the new bulb token to switch devices.
Introduce el token una sola vez|Enter the token once
Introduce entre 1 y 32 caracteres.|Enter 1 to 32 characters.
La bombilla no responde. Comprueba la Wi-Fi y el token.|The bulb is not responding. Check Wi-Fi and the token.
La copia debe contener tres escenas válidas.|The backup must contain three valid scenes.
Mantener Luz junto al reloj al cerrar|Keep Luz in the system tray when closing
Minutos|Minutes
No se pudieron guardar las escenas en el disco.|Could not save the scenes to disk.
No se pudieron leer las escenas guardadas. Se muestran las iniciales.|Could not read the saved scenes. Showing defaults.
No se pudo escribir la copia.|Could not write the backup.
No se pudo verificar la nueva bombilla.|Could not verify the new bulb.
Nombre de escena|Scene name
Nombre de la escena|Scene name
Oscuro|Dark
Pantalla completa|Full screen
Parar ciclo|Stop cycle
Pegar IP y token|Paste IP and token
Preferencias|Preferences
Preferencias…|Preferences…
Programar|Schedule
Renombrar|Rename
Rojo|Red
Salir|Quit
Se restablecerá como Blanco a 4000 K y 100 % de brillo.|This resets the scene to White at 4000 K and 100% brightness.
Sin conexión|Disconnected
Sin configurar|Not configured
Tema|Theme
Temperatura|Temperature
Temperatura de blanco|White temperature
Temperatura exacta|Exact temperature
Temporizador|Timer
Temporizador…|Timer…
Token miIO|miIO token
Tono|Hue
Usa Ctrl o Alt, modificadores opcionales y una letra o un número.|Use Ctrl or Alt, optional modifiers, and a letter or number.
Vaciar|Reset
Vaciar escena|Reset scene
Verde|Green
Verificando…|Verifying…
Verificar y guardar|Verify and save
Vista previa de la escena · los cambios se guardan al confirmar.|Scene preview · changes are saved when confirmed.
Windows no pudo abrir el token guardado. Vuelve a introducirlo en Conexión.|Windows could not open the saved token. Enter it again in Connection.
¿Sustituir las tres escenas por las de esta copia?|Replace the three scenes with this backup?
Ámbar RGB|RGB amber
●  Conectada|●  Connected
¿Seguro que quieres vaciar «{name}»?|Reset “{name}”?
Red local · {ip} · MAC verificada|Local network · {ip} · MAC verified
Encendida · Blanco {temperature} K|On · White {temperature} K
Apagado en {minutes} min|Off in {minutes} min
Quedan aproximadamente {minutes} min.|About {minutes} min remaining.
Encendida · #%02X%02X%02X|On · #%02X%02X%02X
""".strip().splitlines())

EN.update({
    "No se pudieron guardar las preferencias.": "Could not save the preferences.",
    "Copia solo el bloque de una bombilla o un token de 32 caracteres.": "Copy the block for one bulb or a 32-character token.",
    "La IP copiada no es válida. Copia el token y escribe la IP en Conexión.": "The copied IP is invalid. Copy the token and enter the IP in Connection.",
    "Este modelo no admite colores RGB.": "This model does not support RGB colors.",
    "El efecto no está validado para este modelo.": "This effect has not been verified for this model.",
    "Introduce un token miIO de 32 caracteres.": "Enter a 32-character miIO token.",
    "Sin conexión con la bombilla. Comprueba la corriente y la Wi-Fi. Si cambió su IP, introdúcela en Conexión.": "The bulb is offline. Check power and Wi-Fi. If its IP changed, enter the new one in Connection.",
})

EN.update({
    "Haz clic en un atajo y pulsa la combinación.": "Click a shortcut and press the key combination.",
    "Clic para grabar. Clic derecho para desactivar.": "Click to record. Right-click to disable.",
    "Pulsa la combinación…": "Press the shortcut…",
    "Sin atajo": "No shortcut",
    "Desactivar atajo": "Disable shortcut",
})

EN.update({"Conexión": "Connection", "Atajos": "Shortcuts"})

EN.update({
    "Apariencia": "Appearance",
    "Añadir bombilla": "Add bulb",
    "El perfil de la bombilla seleccionada no es válido.": "The selected bulb profile is invalid.",
})

EN.update({
    "Luces": "Lights",
    "Habitación": "Room",
    "No se pudieron leer las luces guardadas.": "Could not read the saved lights.",
    "Aplicar color actual a…": "Apply current color to…",
    "Todas las luces": "All lights",
    "Espera a que termine el cambio en curso.": "Wait for the current change to finish.",
    "Aplicando color a las luces…": "Applying color to the lights…",
    "Color aplicado a {count} luces.": "Color applied to {count} lights.",
    "Sin aplicar en {lights}.": "Could not apply it to {lights}.",
    "Luz ya está abierta. Búscala junto al reloj de Windows.": "Luz is already open. Check the Windows system tray.",
})

EN.update({
    "El archivo antiguo no contiene un token válido.": "The old file does not contain a valid token.",
    "El archivo de bombillas no es válido.": "The bulb file is invalid.",
    "El perfil de la bombilla no contiene un token válido.": "The bulb profile does not contain a valid token.",
    "El token debe tener 32 caracteres hexadecimales.": "The token must contain 32 hexadecimal characters.",
    "Este modelo tiene blanco fijo.": "This model has fixed white.",
    "La bombilla devolvió un estado inválido.": "The bulb returned an invalid status.",
    "La bombilla no coincide con la MAC y el modelo guardados.": "The bulb does not match the saved MAC address and model.",
    "La bombilla no devolvió un modelo miIO válido.": "The bulb did not return a valid miIO model.",
    "La bombilla no devolvió una MAC válida.": "The bulb did not return a valid MAC address.",
    "La bombilla seleccionada ya no está guardada.": "The selected bulb is no longer saved.",
    "La lista de bombillas no es válida.": "The bulb list is invalid.",
    "La versión del perfil no es compatible.": "The profile version is not supported.",
    "Modelo sin control local compatible: {model}": "Model without compatible local control: {model}",
    "No se encontró la bombilla activa en el archivo de perfiles.": "The active bulb was not found in the profiles file.",
    "Sin conexión con la bombilla. No se pudo consultar la red local de Windows.": "The bulb is offline. Could not query the Windows local network.",
})

EN.update({
    "El idioma se aplicará la próxima vez que abras Luz. Cerrar ahora saldrá de la aplicación.": "The language will apply the next time you open Luz. Closing now will exit the app.",
    "Usa Ctrl o Alt con una letra, número o F1–F11": "Use Ctrl or Alt with a letter, number or F1–F11",
    "Cambiar atajos…": "Edit shortcuts…",
    "Océano": "Ocean",
    "Atardecer": "Sunset",
    "Respiración": "Breathing",
    "Efectos…": "Effects…",
    "Efecto desconocido.": "Unknown effect.",
    "Compatibilidad verificada · {model} · MAC {mac} · {ip}": "Compatibility verified · {model} · MAC {mac} · {ip}",
    "Modelos compatibles": "Compatible models",
    "Buscar nombre o código de modelo": "Search name or model code",
    "Sin modelos para esa búsqueda.": "No matching models.",
    "Probada físicamente con Luz": "Tested on physical hardware with Luz",
    "Según la especificación del controlador": "Based on the driver specification",
    "Blanco regulable": "Tunable white",
})

EN.update({
    "Etiqueta en Luz": "Label in Luz",
    "Nombre en Xiaomi Home": "Name in Xiaomi Home",
    "Copia o importa el nombre original": "Copy or import the original name",
    "Bombilla de cocina": "Kitchen light",
    "Bombilla del salón": "Living room light",
    "Bombilla del dormitorio": "Bedroom light",
})

EN.update({
    "Subir brillo": "Increase brightness",
    "Bajar brillo": "Decrease brightness",
    "Subir temperatura": "Increase color temperature",
    "Bajar temperatura": "Decrease color temperature",
    "Paso de brillo": "Brightness step",
    "Ajustes relativos en {room}": "Relative adjustments in {room}",
    "Ajustes relativos en la bombilla activa": "Relative adjustments for the active bulb",
    "Ajuste aplicado a {count} luces.": "Adjustment applied to {count} lights.",
})

EN.update({
    "Iniciar Luz con Windows": "Start Luz with Windows",
    "Abre Luz.exe para cambiar el inicio con Windows.": "Open Luz.exe to change Windows startup.",
    "No se pudo leer el inicio con Windows.": "Could not read Windows startup.",
    "No se pudo cambiar el inicio con Windows.": "Could not change Windows startup.",
    "No se pudo restaurar el inicio con Windows.": "Could not restore the Windows startup setting.",
    "No se pudo actualizar el inicio con Windows.": "Could not update Windows startup.",
    "Exportar diagnóstico": "Export diagnostics",
    "Archivo de texto (*.txt)": "Text file (*.txt)",
    "No se pudo guardar el diagnóstico.": "Could not save the diagnostic report.",
    "Diagnóstico guardado. Revísalo antes de compartirlo.": "Diagnostics saved. Review the report before sharing it.",
    "Modelo": "Model",
    "Última comprobación de conexión": "Last connection check",
    "Últimos eventos": "Recent events",
    "Buscar bombillas": "Find bulbs",
    "Buscando dispositivos miIO en la red local…": "Searching the local network for miIO devices…",
    "Usar esta IP": "Use this IP",
    "No se encontraron bombillas. Comprueba la corriente, la red Wi-Fi y el firewall de Windows. Evita la red de invitados.": "No bulbs found. Check power, Wi-Fi and the Windows firewall. Avoid guest networks.",
    "Elige una dirección. Luz comprobará la bombilla con su token al guardar.": "Choose an address. Luz will verify the bulb with its token when you save.",
    "Modelo sin identificar": "Unknown model",
    "MAC sin identificar": "Unknown MAC",
    "Control no disponible para esta bombilla.": "Control unavailable for this bulb.",
    "No se encontró la bombilla. Comprueba la corriente y que el PC y la bombilla estén en la misma red Wi-Fi. Usa Buscar bombillas o reserva la IP en el router.": "Bulb not found. Check power and that the PC and bulb are on the same Wi-Fi. Use Find bulbs or reserve its IP in the router.",
    "La bombilla no autenticó la respuesta. Vuelve a obtener su token en Conexión → Obtener token por QR.": "Could not authenticate the bulb response. Get its token again in Connection → Get token by QR.",
    "La MAC o el modelo no coinciden. Comprueba la IP: podría ser otra bombilla.": "The MAC or model does not match. Check the IP address: it may be a different bulb.",
    "La bombilla no respondió a tiempo. Reintenta y comprueba que el firewall de Windows permite el tráfico UDP de Luz.": "The bulb did not respond in time. Retry and check that the Windows firewall allows Luz UDP traffic.",
})

EN.update({
    "Xiaomi Mi LED Smart Bulb Essential (Luz blanca y de color)": "Xiaomi Mi LED Smart Bulb Essential (White and Color)",
    "Xiaomi Mi LED Smart Bulb (Luz blanca y de color)": "Xiaomi Mi LED Smart Bulb (White and Color)",
    "Yeelight LED Bulb (Color, 2.ª generación)": "Yeelight LED Bulb (Color, 2nd generation)",
    "Yeelight LED Bulb (Blanco fijo)": "Yeelight LED Bulb (Fixed White)",
    "Yeelight GU10 Smart Bulb W1 (Blanco fijo)": "Yeelight GU10 Smart Bulb W1 (Dimmable)",
    "Yeelight LED Bulb (Blanco regulable)": "Yeelight LED Bulb (Tunable White)",
    "Consultar referencia": "View reference",
    "Referencia comercial sin confirmar": "Retail model number unconfirmed",
})

EN["General"] = "General"

EN["Clic derecho para editar."] = "Right-click to edit."

EN.update({
    "Vista previa de la bombilla": "Bulb preview",
    "El estado de la luz se indica debajo de la vista previa.": "The light status is shown below the preview.",
    "Usa las flechas, Inicio, Fin, Re Pág o Av Pág para ajustar el valor.": "Use the arrow, Home, End, Page Up or Page Down keys to adjust the value.",
})

EN["Respuesta no válida. Comprueba de nuevo la conexión."] = "Invalid response. Check the connection again."

EN.update({
    "Token rechazado (probable). Comprueba el token y vuelve a comprobar.": "Token probably rejected. Check the token and try again.",
    "Hay varias IP posibles. Comprueba la dirección manualmente.": "Multiple possible IPs. Check the address manually.",
})

EN.update({
    "Sin respuesta": "No response",
    "Token rechazado (probable)": "Token probably rejected",
    "IP de otro dispositivo": "IP belongs to another device",
    "Respuesta no válida": "Invalid response",
    "Nueva IP verificada y adoptada.": "New IP verified and adopted.",
})

EN.update({
    "Resultado del grupo": "Group result",
    "+ Aplicada": "+ Applied",
    "× Fallida": "× Failed",
    "— Omitida por compatibilidad": "— Skipped: incompatible",
    "… No atendida por tiempo": "… Skipped: time budget exceeded",
    "Reintentar las fallidas": "Retry failed lights",
    "{count} de {total} luces aplicadas.": "{count} of {total} lights applied.",
})

EN.update({
    "— No asignado": "— Unassigned",
    "◷ Sin comprobar": "◷ Unchecked",
    "✓ Registrado": "✓ Registered",
    "× Ocupado por otra aplicación": "× In use by another application",
    "× No válido ({code})": "× Invalid ({code})",
    "Posible conflicto con AltGr": "Possible AltGr conflict",
    "Requiere teclado numérico": "Numeric keypad required",
    "Windows recibió el atajo": "Windows received the shortcut",
    "Usar alternativa": "Use alternative",
    "Alternativa preparada. Pulsa Guardar.": "Alternative ready. Select Save.",
    "No hay una alternativa disponible.": "No alternative is available.",
})

EN["Comprobar de nuevo"] = "Check again"
EN["Sin comprobar"] = "Unchecked"

EN.update({
    "El atajo funciona; el fallo es de conexión": "The shortcut works; the connection failed",
    "El atajo llegó; hubo luces sin aplicar": "The shortcut was received; some lights did not apply the change",
})


EN.update({
    "Última pulsación {time}": "Last pressed {time}",
    "Acción no disponible ahora": "Action unavailable right now",
    "Pendiente": "Pending",
    "Aplicado": "Applied",
    "Sustituido por un cambio posterior": "Replaced by a later change",
    "Cancelado por un fallo de conexión": "Cancelled because the connection failed",
})


EN["Haz clic en la bombilla para encenderla o apagarla."] = "Click the bulb to turn it on or off."


EN.update({
    "La bombilla no confirmó el cambio. Vuelve a intentarlo.": "The bulb did not confirm the change. Try again.",
    "El cambio no se aplicó": "The change was not applied",
})

EN.update({
    "Bienvenido a Luz": "Welcome to Luz",
    "Selecciona Añadir bombilla para configurar otra luz, o elige una guardada para revisar sus datos. El token se guarda cifrado.": "Select Add bulb to set up another light, or choose a saved bulb to review its details. The token is stored encrypted.",
    "1. Encuentra tu bombilla": "1. Find your bulb",
    "Añade primero la bombilla a tu Wi-Fi con Xiaomi Home. Después busca su IP aquí o pégala junto al token.": "First add the bulb to your Wi-Fi with Xiaomi Home. Then find its IP here or paste it together with the token.",
    "2. Consigue el token": "2. Get the token",
    "3. Detalles opcionales": "3. Optional details",
    "Puedes dejar estos campos vacíos. Para terminar, pulsa Verificar y guardar; si falla, podrás corregir los datos sin empezar de nuevo.": "You can leave these fields empty. Select Verify and save to finish; if it fails, you can correct the details without starting again.",
    "Configurar más tarde": "Set up later",
})

EN.update({
    "Obtener token por QR": "Get token by QR",
    "Conectar con Xiaomi": "Connect to Xiaomi",
    "Añade tu bombilla a Luz": "Add your bulb to Luz",
    "Pulsa Obtener token por QR y autoriza con Xiaomi Home. Elige tu bombilla para rellenar IP y token automáticamente.": "Select Get token by QR and authorize with Xiaomi Home. Choose your bulb to fill in its IP and token automatically.",
    "1. Añade la bombilla a tu Wi-Fi con Xiaomi Home y conecta el PC a la misma red.": "1. Add the bulb to your Wi-Fi with Xiaomi Home and connect your PC to the same network.",
    "2. Elige la región de Xiaomi Home y genera el QR. Escanéalo con Xiaomi Home y confirma el acceso en el móvil.": "2. Choose your Xiaomi Home region and generate the QR. Scan it with Xiaomi Home and approve access on your phone.",
    "3. Elige tu bombilla. Luz rellenará IP y token; después pulsa Verificar y guardar en Conexión.": "3. Choose your bulb. Luz fills in its IP and token; then select Verify and save in Connection.",
    "Solo al generar el QR se conecta con Xiaomi. La sesión se mantiene en memoria y se descarta al terminar; no se guarda tu contraseña.": "Luz connects to Xiaomi only when you generate the QR. The session stays in memory and is discarded afterward; your password is not stored.",
    "Región de Xiaomi Home": "Xiaomi Home region",
    "Europa (de)": "Europe (de)", "China (cn)": "China (cn)",
    "Estados Unidos (us)": "United States (us)", "Rusia (ru)": "Russia (ru)",
    "Taiwán (tw)": "Taiwan (tw)", "Singapur (sg)": "Singapore (sg)",
    "India (in)": "India (in)", "India (i2)": "India (i2)",
    "El QR aparecerá aquí al pulsar Generar QR.": "Select Generate QR to display the code here.",
    "QR para autorizar el acceso a Xiaomi": "QR to authorize Xiaomi access",
    "No se ha iniciado ninguna conexión.": "No connection has been started.",
    "Bombillas compatibles encontradas": "Compatible bulbs found",
    "Generar QR": "Generate QR", "Generar otro QR": "Generate another QR",
    "Usar esta bombilla": "Use this bulb", "Generando QR…": "Generating QR…",
    "Conectando con Xiaomi…": "Connecting to Xiaomi…",
    "La imagen QR de Xiaomi no es válida.": "The Xiaomi QR image is invalid.",
    "Escanea el QR con Xiaomi Home y confirma el acceso en tu móvil.": "Scan the QR with Xiaomi Home and approve access on your phone.",
    "Acceso autorizado. Buscando bombillas compatibles…": "Access authorized. Looking for compatible bulbs…",
    "Elige la bombilla que quieres añadir a Luz.": "Choose the bulb you want to add to Luz.",
    "No se encontraron bombillas compatibles con IP local. Comprueba la región y que estén conectadas a tu Wi-Fi.": "No compatible bulbs with a local IP were found. Check the region and that they are connected to your Wi-Fi.",
    "Datos obtenidos de Xiaomi. Revisa la IP y pulsa Verificar y guardar.": "Details retrieved from Xiaomi. Check the IP and select Verify and save.",
    "No se pudo completar la conexión segura con Xiaomi.": "The secure connection to Xiaomi could not be completed.",
    "La respuesta de Xiaomi no es válida.": "The Xiaomi response is invalid.",
    "Elige la misma región que utilizas en Xiaomi Home.": "Choose the same region you use in Xiaomi Home.",
    "No se pudo generar el QR de Xiaomi. Inténtalo de nuevo.": "Could not generate the Xiaomi QR. Try again.",
    "El QR ha caducado o no se ha autorizado. Genera otro QR.": "The QR expired or was not authorized. Generate another QR.",
    "Xiaomi no autorizó la sesión. Genera otro QR.": "Xiaomi did not authorize the session. Generate another QR.",
    "No se pudo conectar con Xiaomi. Comprueba Internet y vuelve a intentarlo.": "Could not connect to Xiaomi. Check your internet connection and try again.",
})

EN.update({
    "Volver a configurar una bombilla": "Set up a bulb again",
    "1. Añade la bombilla a tu Wi-Fi con Xiaomi Home. Si has cambiado de red o la has restablecido, vuelve a añadirla allí. Conecta el PC a la misma red local.": "1. Add the bulb to your Wi-Fi using Xiaomi Home. If you changed networks or reset it, add it there again. Connect your PC to the same local network.",
    "2. Abre Conexión en Luz. Selecciona Añadir bombilla para una nueva, o elige una guardada para actualizar sus datos.": "2. Open Connection in Luz. Select Add bulb for a new light, or choose a saved bulb to update its details.",
    "3. Pulsa Obtener token por QR, elige la misma región de Xiaomi Home y genera el QR. Escanéalo con Xiaomi Home y autoriza el acceso en el móvil.": "3. Select Get token by QR, choose your Xiaomi Home region and generate the QR. Scan it with Xiaomi Home and approve access on your phone.",
    "4. Elige tu bombilla para rellenar IP y token. Pulsa Verificar y guardar. Si prefieres introducirlos manualmente, usa Buscar bombillas y Pegar IP y token.": "4. Choose your bulb to fill in its IP and token. Select Verify and save. For manual setup, use Find bulbs and Paste IP and token.",
    "El token se guarda cifrado en este PC. Tras restablecer la bombilla puede cambiar: obtén uno nuevo y vuelve a verificar. No compartas tu token ni el QR.": "The token is stored encrypted on this PC. Resetting the bulb may change it: obtain a new token and verify again. Do not share your token or QR.",
    "Abrir Conexión": "Open Connection"
})
