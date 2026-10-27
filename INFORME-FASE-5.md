# Fase 5 — Instalación en Android mediante PWA

Validación local: 26 de octubre de 2026. Producción, Render y Supabase remoto permanecen intactos. No se instalaron SDK, se publicaron paquetes ni se realizaron pagos o transferencias.

## Resultado preparado

QueHay tiene manifiesto, iconos y soporte de instalación como aplicación web progresiva (PWA). La identidad de la app es «QueHay Cine», su inicio y alcance pertenecen al mismo sitio y el modo solicitado es `standalone`. Se añadieron iconos PNG de 192 y 512 píxeles y un icono adaptable a las máscaras de Android. Son un monograma original de la marca, no un QR de pagos.

La ruta `/instalar` explica cómo abrir la página desde Chrome en Android, instalar desde el navegador y continuar con la misma cuenta. Hay enlaces desde la portada, la cuenta y la membresía. El botón de instalación solo aparece si el navegador emite una oferta real mediante `beforeinstallprompt`; nunca se presenta un botón decorativo que afirme instalar sin hacerlo. En Telegram se indica abrir un navegador externo.

Aceptar una oferta no se presenta como instalación completada: el mensaje de instalación confirmada requiere `appinstalled`. La app reconoce también cuando se está ejecutando en modo independiente. Si el navegador no ofrece instalación, muestra pasos alternativos y permite seguir navegando.

Esta entrega es una **PWA**, no un archivo APK firmado, una publicación en Google Play ni una instalación ya comprobada en un Android físico. La experiencia de instalación depende del navegador y del dispositivo. Chrome documenta criterios que incluyen manifiesto, iconos y HTTPS para promocionar la instalación; se revisará la instalación final sobre el origen HTTPS autorizado. [Requisitos oficiales](https://web.dev/articles/install-criteria).

## Conexión, acceso y descargas

El service worker guarda únicamente cinco recursos públicos: el aviso sin conexión, su CSS y los tres iconos. No guarda páginas de cuenta, respuestas de API, estados de membresía, pagos, QR, enlaces privados ni videos.

Las navegaciones principales consultan la red. Si falla la conexión, presentan el aviso estático. Una respuesta HTTP de error o denegación se conserva; no se sustituye con un acceso anterior. Los endpoints de reproducción y descarga siguen verificando la sesión y el vencimiento en el servidor.

Las descargas conservan su recorrido: abrir la ficha → Descargar → comprobación de acceso → enlace de MediaFire u otro proveedor. El archivo se obtiene en el sitio del proveedor. Instalar QueHay no descarga videos automáticamente ni habilita reproducción sin internet. El controlador de descargas y su uso de Telegram `openLink` no se modificaron.

Las actualizaciones del service worker no recargan una sesión abierta sin una acción del usuario. Si hay una versión esperando, aparece una opción «Actualizar ahora» o «Más tarde». La limpieza de caché afecta solo versiones antiguas del aviso de QueHay, no otras aplicaciones ni los favoritos.

## Archivos

| Archivo | Función |
| --- | --- |
| `routes/pwa.py` | Recursos públicos `/instalar`, `/offline`, `/manifest.webmanifest` y `/sw.js` |
| `static/pwa/manifest.webmanifest` | Nombre, modo de apertura, alcance e iconos |
| `static/pwa/install.html`, `install.css`, `install.js` | Guía, detección de instalación y actualizaciones |
| `static/pwa/offline.html`, `sw.js` | Aviso sin conexión y política de caché limitada |
| `static/pwa/icons/` | Iconos opacos y versión maskable |
| `scripts/generate_app_icons.py` | Generación reproducible de los iconos con Pillow y Arial Bold de Windows |
| `tests/test_pwa.py`, `tests/pwa.test.cjs` | Contratos HTTP, seguridad, caché e interacción de instalación |

Se declaró `worker-src 'self'` y `manifest-src 'self'` en la política de contenido. Se conserva la comprobación estricta del origen. El saneamiento de JSON ahora se limita a las rutas de catálogo y temporadas que lo necesitan: intentar leer todos los archivos JSON como respuestas de API impedía servir correctamente el manifiesto. La regresión quedó cubierta por las pruebas.

## Pruebas realizadas

**166 pruebas aprobadas: 134 Python y 32 Node.js/SQL.**

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=.local/phase5-python.xml
node --test tests/frontend.test.cjs tests/episodes.test.cjs tests/vimeus-sql.test.mjs tests/billing-sql.test.mjs tests/pwa.test.cjs
node --check static/pwa/install.js
node --check static/pwa/sw.js
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Evidencia: `.local/phase5-python.xml`, `.local/phase5-python.txt`, `.local/phase5-javascript.txt`. Hubo 20 advertencias de dependencias Python, sin fallos. Comprobaciones sintácticas y de dependencias correctas.

Las nuevas pruebas verifican manifiesto y dimensiones de PNG, acceso público a recursos de instalación, restricciones de origen y reproducción, lista exacta de recursos cacheables, exclusión de pagos/descargas/API/video/admin, navegación sin red, mantenimiento de errores HTTP, limpieza limitada de versiones, activación explícita de actualizaciones, confirmación y cancelación de instalación, modo independiente y contexto Telegram. Los eventos nativos de instalación se ejercitan mediante dobles en Node; eso no equivale a instalar en un teléfono.

### Comprobación real en navegador

1. Se abrió `/instalar` en el navegador integrado. El service worker se registró y la página confirmó que el aviso sin conexión estaba preparado.
2. Se detuvo el proceso local de Flask. Al navegar a `/cuenta`, se mostró la pantalla de aviso sin conexión almacenada, sin formularios ni datos privados de la cuenta.
3. Se reinició Flask y se pulsó «Volver a intentar». Se recuperó el catálogo.
4. Desde la ficha destacada se preparó el enlace de MediaFire de prueba. Se mostró el diálogo con abrir, copiar y cerrar; no se abrió el archivo externo ficticio.
5. La página de instalación se revisó a 320, 390 y 1280 px, sin desbordamiento horizontal en las comprobaciones.

El navegador integrado no presentó una oferta nativa de instalación durante la prueba; por eso el botón quedó oculto y se mostraron instrucciones. No se afirmó que estuviera instalada. No se conectó un teléfono ni se validó un paquete WebAPK. No se encontró `adb` en PATH ni en la ubicación habitual del SDK local, y no se instaló Android Studio o un emulador.

Capturas: `.local/fase5-instalar.png` (vista final), `.local/fase5-instalar-escritorio.png`, `.local/fase5-instalar-movil.png`, `.local/fase5-instalar-320.png`, `.local/fase5-sin-conexion.png` y `.local/fase5-descarga-recuperada.png`.

## Prueba pendiente en tu Android, manteniendo el servidor local

Chrome permite reenviar un puerto del teléfono al servidor local mediante USB. Este procedimiento no requiere publicar el proyecto. [Documentación oficial de reenvío por USB](https://developer.chrome.com/docs/devtools/remote-debugging/local-server).

1. Mantener ejecutándose ` .\.venv\Scripts\python.exe scripts/run_local.py ` en esta carpeta.
2. Conectar el Android por USB y configurar la depuración remota con Chrome, aceptando la autorización del ordenador en el teléfono.
3. En Chrome del ordenador, abrir `chrome://inspect/#devices`, activar la detección USB y configurar el reenvío del puerto **5010** hacia **127.0.0.1:5010**.
4. En Chrome del teléfono, abrir **http://127.0.0.1:5010/instalar**. Se usa exactamente ese host porque el servidor local valida el origen; no se ha abierto el servidor a la red local.
5. Comprobar navegación, inicio de sesión de prueba, retorno desde un proveedor de descargas y las opciones de instalación que ofrezca el navegador. La disponibilidad y el tipo de instalación de un origen local pueden variar; no sustituyen la comprobación final con HTTPS.

La autorización USB y la confirmación nativa corresponden al usuario. No se cambiaron opciones del teléfono desde esta sesión. Las credenciales de prueba siguen en `.local/payment-demo.txt`; no son credenciales de producción.

## Antes de publicar en una fase autorizada

- Validar en Android real el icono, la apertura independiente, la cuenta, el reproductor, el retorno desde MediaFire y la renovación/vencimiento con el origen HTTPS elegido.
- Mantener `APP_ORIGIN` igual al origen público final y comprobar las rutas del manifiesto y del worker después del despliegue.
- Aumentar la versión `quehay-offline-v1` al cambiar recursos precargados; comprobar la actualización desde una instalación anterior.
- No se modificaron los pendientes de pagos documentados en la fase 3 ni se habilitó Binance sin su QR oficial.
- Un APK firmado o una publicación en tienda sería un trabajo adicional con identidad, firma, dominio verificado y pruebas propias. No forma parte del binario entregado en esta fase, porque aquí no se generó un binario.
