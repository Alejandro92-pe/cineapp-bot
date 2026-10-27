# Prueba local por Telegram y ngrok

Fecha: 26 de octubre de 2026. No se desplegó ni se modificó Render, Supabase ni la configuración del bot.

## Enlace activo

https://clairvoyantly-adactylous-leonida.ngrok-free.dev

El túnel apunta exclusivamente a `127.0.0.1:5011`. La vista sintética anterior continúa en `127.0.0.1:5010`. El enlace requiere que esta computadora, el servidor y ngrok permanezcan encendidos. Ngrok gratuito puede presentar primero «Visit Site».

Para recibir la identidad firmada de Telegram, debe abrirse desde un botón Mini App del bot `@Popcornqh_admin_bot`. Pegar el enlace como mensaje permite navegar, pero no equivale al inicio firmado de una Mini App. No se envió ningún mensaje ni se modificó el menú/webhook del bot. Referencia: https://core.telegram.org/bots/webapps

## Implementación y separación de datos

- 644 fichas copiadas del catálogo público mediante solicitudes de lectura; 253 enlaces de descarga conservados. No se copiaron usuarios ni pagos reales.
- Las películas con TMDB se dirigen al reproductor de Vimeus solo en esta copia. Esto no garantiza disponibilidad de todos los títulos.
- La copia no dirige a canales. Series/animes aún requieren el listado real de capítulos; no se inventan episodios a partir de TMDB.
- Cuentas y solicitudes del túnel se guardan en `.local/telegram-preview.sqlite`, independiente de producción y de la demo anterior.
- El ID 5824989040 tiene acceso local de prueba por 30 días. No representa una compra ni modifica su acceso real. Las demás cuentas no reciben acceso automáticamente.
- Telegram se verifica con HMAC y caducidad; se conserva el SDK real en el túnel. El backend permanece sin conexiones salientes y utiliza un bot simulado que no envía mensajes.
- El origen HTTPS exacto se valida, la cookie es Secure/HttpOnly y se mantiene CSRF. Cron, webhooks e importaciones reales están bloqueados en el túnel.
- Las claves necesarias se leyeron de Render sin modificarlo y se guardaron únicamente bajo `.local`, excluido de Git y no servido por Flask. No se copiaron claves de Supabase, correo ni pagos.
- Buy Me a Coffee no abre un checkout real en esta prueba. Yape/Plin y Binance deben probarse con referencias ficticias, sin enviar dinero.

## Cuenta, identidad visual y navegación

- Se restauró el logo original de la carita en inicio, cuenta, membresía e instalación, incluidos los iconos de Android.
- Los ocho avatares originales se comparten entre cuenta y cabecera. Se conserva la clave anterior por usuario de Telegram. La selección permanece en ese navegador/origen; todavía no se sincroniza entre dispositivos.
- Mi cuenta muestra acceso activo/vencido, fecha, renovación manual e historial de solicitudes con sus estados. Permite actualizar el estado.
- Se restauraron las estrellas de puntuación: verde desde 7, amarillo desde 5 y rojo por debajo de 5; el número acompaña al color.
- La cuenta autenticada prioriza el perfil y la membresía en celular, sin anteponer la presentación de registro.
- Se corrigió una carrera que devolvía al inicio al pulsar Catálogo durante la carga inicial.
- Se corrigió el cierre del reproductor: el SDK real de Telegram lanzaba `WebAppMethodUnsupported` fuera de Telegram e impedía cerrar. El cierre ya no depende del fullscreen nativo.

## Evidencia

- Python: **148 pruebas correctas**, 20 advertencias de dependencias ya existentes. `.local/phase6-python.xml` y `.local/phase6-python.txt`.
- Node: **39 pruebas correctas**. `.local/phase6-node.txt`.
- HTTPS público `/health`: 200 y modo local. Intento de leer `/.local/telegram-preview.json`: 404.
- Perfil probado en 320, 390, 768 y 1280 px, sin desbordamiento horizontal.
- Elección de Zorro persistió al recargar y apareció en la cabecera con Ale y Acceso mensual.
- Solicitud BMC ficticia visible en Mi cuenta como «Esperando confirmación», sin abrir un cobro real.
- Descarga de «El Curioso Caso de Benjamin Button» conserva su enlace original de MediaFire. No se descargó el archivo completo.
- Vimeus cargó la portada y controles de «Piratas del Caribe: La maldición de la Perla Negra». Apertura y cierre verificados después de corregir el fallo. **No se confirma reproducción completa ni funcionamiento en Telegram Android físico.**
- Capturas: `.local/phase6-account-mobile.png`, `.local/phase6-player-mobile.png`.

## Pendientes reales

1. Probar desde el botón Mini App en el teléfono: identidad firmada real, vídeo, fullscreen, sonido, regreso y descarga externa. La prueba de navegador usó acceso administrativo local, no una sesión física de Telegram.
2. Obtener/configurar `VIMEUS_API_KEY` de Listing. Render muestra la clave del reproductor, que no sustituye al permiso de listado. El importador completo tiene pruebas sintéticas; aún falta validarlo con el proveedor real.
3. Configurar el producto BMC a US$1.50 con código de compra, aportar QR oficial de Binance Pay y completar pruebas de pagos antes de habilitar cobros. El QR de Yape se conserva.
4. Antes de producción: revisar/aplicar las migraciones privadas y la configuración de cuentas/pagos de fases anteriores, con autorización. Todavía no se aplicaron en Supabase.
5. Validar instalación y reproducción en Android físico. La PWA está preparada; no se ha generado ni firmado un APK.

## Incidencia de registro corregida

Durante la preparación, la lectura del portapapeles de Render devolvió un valor anterior y el token del bot quedó temporalmente en el campo de nombre del bot. Un registro de arranque lo imprimió en la salida de esta sesión. Se releyeron los campos directamente, se validó su formato y se eliminó el registro que imprimía valores de configuración. No se rotó el token ni se modificó producción. Conviene renovar ese token antes de publicar o compartir esta sesión.

## Reabrir la prueba

Desde la carpeta del proyecto, en dos terminales:

```powershell
ngrok http http://127.0.0.1:5011 --inspect=false --log=.local/ngrok.log --log-format=json
```

Consultar el origen que devuelve el agente:

```powershell
(Invoke-RestMethod http://127.0.0.1:4040/api/tunnels).tunnels.public_url
```

Pasar ese origen exacto al servidor:

```powershell
.venv\Scripts\python.exe scripts/run_local.py --public-origin https://clairvoyantly-adactylous-leonida.ngrok-free.dev
```

Si ngrok entrega otro dominio, usar el nuevo origen. No cargar `.env` de producción. Cerrar ambos procesos detiene la prueba. Documentación de ngrok: https://ngrok.com/docs/gateway/agent/cli
