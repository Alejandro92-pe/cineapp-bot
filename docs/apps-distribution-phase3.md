# Distribución de APK — fase 3 preparada en local

Fecha: 30 de octubre de 2026. Estado: artefactos y botones verificados localmente;
pendiente de aprobar el alojamiento propuesto y la publicación. No se ha subido
ningún archivo ni cambiado Render, SiteGround, DNS, Supabase, bot, pagos o cron.

## Propuesta de alojamiento

Usar el SiteGround existente para los dos archivos estáticos:

- `https://quehay.live/apps/QueHay-Android-0.5.0.apk` (36.907 bytes).
- `https://quehay.live/apps/QueHay-TV-0.3.0.apk` (28.982 bytes).

Son rutas propuestas, no descargas públicas comprobadas. Son aplicaciones
contenedoras: su pequeño tamaño no significa que incluyan el catálogo o los
vídeos. No necesitan S3 ni pasar por MediaFire para estos dos archivos. La
aplicación y sus servicios siguen en Render; las descargas de películas y
episodios conservan sus proveedores y controles de acceso.

## Resultado implementado

- `/instalar` tiene dos botones separados con versión, tamaño, Android mínimo
  y huella SHA-256 opcional. La PWA conserva su instalación y guía independientes.
- Los enlaces del inicio, Telegram y landing llevan a la sección apropiada.
  No se confunde la instalación de la APK TV con la vinculación de la cuenta.
- Desde Telegram, un clic llama a `WebApp.openLink` para abrir el archivo en el
  navegador externo. Si no existe o falla ese método, queda el enlace normal.
  No se inicia ninguna descarga automáticamente.
- `static/pwa/apk-releases.json` queda con `published: false`. El módulo no ofrece
  archivos hasta recibir un manifiesto publicado y válido. Los únicos destinos
  de producción admitidos son los nombres de APK de `https://quehay.live/apps/`.
  No se envían credenciales al consultar ese manifiesto.
- La vista local usa una copia de ese manifiesto y las mismas APK en la carpeta
  ignorada `static/_design-preview/distribution/`. No debe desplegarse.
- Las pruebas y el empaquetado no modifican los binarios; preservan sus firmas.
  La animación y los cambios nativos continúan en las versiones de la fase 2.

## Preparación reproducible

`scripts/package_apks.py` recibe `--android`, `--tv`, `--build-tools` y `--out`.
Requiere el JDK ya instalado en `JAVA_HOME` para ejecutar `apksigner.bat`.
Valida ambas firmas con herramientas oficiales, identificadores de paquete,
versión, permiso INTERNET, Android mínimo, ausencia de depuración y origen HTTPS.
Rechaza los paquetes locales `.startupcheck`. No permite sobrescribir una
versión ya empaquetada con bytes diferentes.

Artefactos preparados bajo `.local/apps-phase3/`:

- `quehay-apps-siteground.zip`: cinco archivos públicos dentro de `apps/`;
  dos APK, `.htaccess`, `releases.json` y `SHA256SUMS.txt`.
- `quehay-landing-overlay.zip`: solamente `index.html` y `assets/`, con nombres
  versionados. Excluye `.htaccess` raíz, sitemap, robots y las páginas SEO antiguas.
- `activation/apk-releases.json`: manifiesto que se copiará a `static/pwa/`
  **solo después** de verificar las dos descargas públicas.
- `local-download-checks.json`: respuestas HTTP, tamaños y hashes locales.
- `descarga-movil.png`: comprobación visual a 390 × 844.

No incluyen claves, keystores, archivos de cuentas ni bases de datos. La clave
de firma original permanece local y fuera de estos paquetes.

## Pruebas y límites

44 pruebas aprobadas: 18 pytest (empaquetado, PWA y constructor de landing) y
26 Node (distribución, PWA y selección de imágenes de landing).

Se probaron manifiestos inactivos, caída de red, URL ajena o maliciosa, cambio
de paquete, credenciales en URL, versiones y hashes inválidos, clic Telegram,
separación local/producción, firma distinta, APK depurable, HTTP y conflicto de
una versión inmutable. Las comprobaciones negativas de herramientas usan
fixtures; las dos APK reales se verificaron además con `apksigner` y `aapt`.

Ambas descargas locales devolvieron HTTP 200 y los hashes esperados. El servidor
local ofrece `application/octet-stream`; SiteGround recibirá la configuración
`application/vnd.android.package-archive` y `Content-Disposition: attachment`.
La efectividad de esas cabeceras, la caché de SiteGround/Cloudflare y la apertura
en un Telegram físico deben verificarse tras subir los archivos. El navegador
integrado no confirmó un evento de descarga en la comprobación UI; no se cuenta
como instalación ni descarga validada en teléfono. Sí se comprobaron los enlaces
y los bytes servidos por HTTP.

En 390 px, el contenido midió 375 px sin desbordamiento horizontal. La fase 2
ya contiene las pruebas nativas de arranque. No se repitieron compras reales,
inicio de sesión real o reproducción de proveedores para esta fase de archivos.

## Orden de publicación propuesto

1. Obtener aprobación para usar `quehay.live/apps/` en el SiteGround existente
   y publicar los bloques de instalación de web/Telegram y landing.
2. Comprobar el `public_html` de **quehay.live** y que no haya otra carpeta
   `apps` incompatible. Añadir solo esos cinco archivos; no borrar contenido.
3. Descargar las dos URL HTTPS desde fuera, comprobar tamaño, SHA-256, tipo,
   descarga sin autenticación y acceso desde teléfono. No activar enlaces si falla.
4. Copiar el manifiesto de activación al código. Revisar el diff acumulado de
   fases 1–3, excluir `.local` y `_design-preview`, publicar por GitHub/Render.
5. Publicar solo la portada y los assets de la landing; conservar SEO, sitemap,
   redirecciones, `.well-known`, otras webs y la configuración raíz existente.
6. Verificar inicio, `/instalar`, Telegram, cuenta y vinculación TV. En teléfono,
   instalar como actualización sobre la versión anterior sin borrar datos.

Para retirar una descarga, poner `published: false` o retirar solo su entrada
del manifiesto. Mantener las APK versionadas para recuperación; no sobrescribir
silenciosamente un archivo con el mismo nombre. Este manifiesto controla las
descargas ofrecidas, no instala ni fuerza actualizaciones en los dispositivos.

## Referencias técnicas consultadas

- [Telegram Mini Apps: openLink](https://core.telegram.org/bots/webapps#initializing-mini-apps):
  apertura externa únicamente ante una interacción del usuario.
- [Android: cómo funcionan las actualizaciones](https://developer.android.com/google/play/app-updates):
  actualización compatible por paquete, firma y código de versión.

## Publicación autorizada y verificación de archivos

El propietario autorizó explícitamente la publicación en SiteGround y la
activación de enlaces en web/Telegram. Las dos URL HTTPS se descargaron con el
navegador y sus bytes coincidieron con las huellas del manifiesto. El cliente
HTTP genérico recibió 403, también en páginas anteriores del sitio; no se
cambiaron reglas de protección. El manifiesto de producción se activó después
de la verificación de ambas descargas. Evidencias: `.local/apps-release/`.
