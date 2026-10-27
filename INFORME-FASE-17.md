# Fase 17 — Bot y menú de QueHay

26 de octubre de 2026. Implementación y pruebas locales. No se desplegó en Render, no se escribió en Supabase y no se modificaron el webhook, el menú ni los comandos del bot en Telegram.

## Qué se encontró

Las fases anteriores habían actualizado parte de los textos de pago y el administrador permitido. El bot todavía registraba un menú antiguo, una oferta del 50 %, videotutoriales, testimonios estáticos, comandos de activación de planes e invitaciones a canales. También tenía un cron de expulsiones y recordatorios que consultaba las tablas antiguas, sin tener en cuenta los pagos nuevos.

## Menú y comportamiento nuevo

| Botón | Acción |
|---|---|
| 🎬 Ver catálogo | Abre QueHay como Mini App. |
| 🔎 Buscar | Solicita un título; también acepta nombres escritos directamente. Devuelve hasta seis fichas disponibles. |
| ✨ Novedades | Muestra hasta seis incorporaciones, por ID más reciente del catálogo. No se presenta como un ranking de popularidad. |
| 👤 Mi cuenta | Consulta el Telegram del remitente, el acceso de la cuenta y el acceso heredado válido. Indica el vencimiento con hora de Perú; el propietario tiene acceso permanente. |
| 🎟 Acceso mensual | Explica los 30 días, sin renovación automática: US$1.50, S/5.50 o 1.50 USDT. Lleva al flujo web que asocia el pago a la cuenta. |
| 💬 Ayuda | Reproducción, descargas por episodio, estado del pago, instalación en Android y contacto directo con Ale. |

Los botones antiguos y enlaces `start=planes`, `start=miniapp` y `start=pago_…` siguen teniendo una salida útil. Los anuncios ahora abren la ficha concreta mediante `start=contenido_ID`.

Se conservan las publicaciones de marketing desde el panel, el cron protegido de publicaciones y `/publicar ID`, exclusivo del propietario. Esta fase no envió ninguna publicación. La selección de usuarios sin acceso para marketing consulta también los nuevos pagos y excluye al propietario; no depende solo de la bandera antigua.

Se retiraron de las rutas activas los comandos que activaban planes antiguos, las invitaciones, las expulsiones y el reenvío automático de mensajes o archivos a soporte. Los comprobantes se registran en la página de acceso mensual; el botón de contacto abre la conversación con Ale. No se ofrecen pedidos garantizados ni se crean pagos por recibir una foto.

Los recordatorios automáticos del sistema anterior quedan desactivados para evitar avisos erróneos o repetidos. El cron de vencimientos conserva una respuesta válida para el chequeo existente, pero no expulsa a nadie ni modifica membresías. La fecha de acceso se comprueba en cada reproducción y descarga. No se ha añadido una campaña automática nueva de mensajes.

El bot solo atiende estas consultas en privado, verifica remitente y chat, limita solicitudes y escapa los nombres y títulos. Nunca entrega enlaces privados de vídeo o descarga por el chat: abre la ficha con sus controles de acceso.

## Pruebas y vista previa

- **272 pruebas Python aprobadas**, incluidas **25 nuevas** del bot. Se utilizó el despachador real de pyTelegramBotAPI con transporte sustituido y la red externa bloqueada.
- **76 pruebas JavaScript/SQL aprobadas**. Total: **348**.
- Se probaron el menú de seis botones, búsquedas, resultados limitados, títulos ocultos, enlaces antiguos, vencimientos, propietario, remitentes falsos, chats de grupo, comandos retirados, callbacks antiguos, permisos de publicación y ausencia de reenvíos.
- Se verificó que las cuentas pagadas nuevas no aparezcan como usuarios sin acceso cuando el administrador abre marketing.
- Vista previa: `.local/phase17-bot.html`. Contiene seis respuestas generadas por el código; los botones en esta hoja son una presentación, no un cliente de Telegram.
- Evidencia: `.local/phase17-pytest.txt`, `.local/phase17-node.txt` y `.local/phase17-bot-proof.json`.
- **253 enlaces de descarga sin modificaciones** al ejecutar las consultas del bot sobre la copia del catálogo. No se cambiaron el reproductor ni los controladores de descarga.

Reproducir la prueba del bot: `.venv\Scripts\python.exe -m pytest tests/test_telegram_assistant.py -q`.
Regenerar la vista previa: `.venv\Scripts\python.exe scripts/preview_telegram_bot.py`.

## Aplicación futura en Telegram

La lógica está separada en `telegram_bot/assistant.py`. El menú de comandos y el botón «Abrir QueHay» están preparados en `scripts/configure_bot_menu.py` siguiendo la [API oficial de Telegram](https://core.telegram.org/bots/api#inlinekeyboardbutton).

El script solo muestra la configuración por defecto. `--apply` es una escritura externa que queda pendiente para la fase de producción, después de desplegar y verificar el origen HTTPS y el webhook. Configura los comandos predeterminados, de chats privados y del propietario, en español y en el idioma predeterminado. No registra webhooks ni inicia polling. Los teclados de conversaciones antiguas se sustituyen cuando la persona usa `/start` o `/menu`; no se manda un aviso masivo para cambiarlos.

La prueba en un Telegram real queda pendiente de esa fase. La web local a través de ngrok no cambia por sí sola el backend al que Telegram entrega los mensajes del bot.
