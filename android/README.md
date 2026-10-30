# Qué Hay Android — fase 1, APK privada de prueba

La aplicación reutiliza `https://app.quehay.live` dentro de Android WebView. No duplica catálogo, membresías, Supabase ni cuentas, ni incluye tokens o claves de proveedor. El código de adaptación móvil viaja dentro del APK; esta fase no modifica ni despliega la aplicación web de producción.

## Incluido

- Android 8.0 o superior (API 26), horizontal al entrar en pantalla completa; al salir respeta de nuevo la orientación del teléfono, manejo nativo de pantalla completa y de Volver. La versión instalada de Android System WebView debe admitir la web actual.
- Interfaz móvil específica: seis episodios por bloque, temporada seleccionable, descargas por episodio, botón siguiente, controles de 44 px, selector de proveedores oculto. Oculta la promoción de instalar PWA dentro de la APK.
- VideoAPI sigue primero. La API actual ya puede escoger Vimeus cuando falta un título. La APK añade una segunda tentativa para errores de red/HTTP 5xx o ausencia confirmada, y para errores nativos de carga que correspondan exactamente al iframe activo. Mantiene el mismo título y episodio, evita bucles, descarta respuestas antiguas y vuelve a VideoAPI en el siguiente episodio.
- Un icono de reintentar en la cabecera permite recuperar errores que el proveedor no comunica. No presenta nombres de servidores al usuario.
- OK.ru conserva su enlace configurado; no se inventa un proveedor alternativo para un bíblico sin otra fuente.
- Inicio de sesión en la cuenta existente. La APK tiene su propio almacén de cookies: no copia automáticamente la sesión de Telegram ni del navegador. Usa el correo y contraseña de tu cuenta existente; si solo tienes Telegram, vincula primero ese acceso mediante el flujo actual de Mi cuenta. No crees otra cuenta para recuperar una membresía.
- Las descargas abren su enlace HTTPS en el navegador del teléfono, donde MediaFire u otro proveedor puede completar la descarga. No pide permisos de archivos, cámara, ubicación ni micrófono.

## Seguridad

Solo la navegación principal de `app.quehay.live` permanece dentro de la sesión de la app. Los enlaces externos HTTPS abiertos por el usuario se envían al navegador. Sin `addJavascriptInterface`, sin claves embebidas, sin aceptar certificados inválidos, sin HTTP sin cifrar, sin acceso a archivos locales ni permisos nativos para reproductores externos. Las cookies de terceros están desactivadas; si un reproductor las exige, se registrará como limitación en la prueba, antes de cambiar esa política. La autorización y el CSRF siguen en el servidor. Un error 401/403 nunca provoca un cambio de proveedor para evadir el acceso.

## Limitaciones que debe validar la fase 2

`iframe.onload` no demuestra reproducción. Un reproductor puede devolver HTTP 200 y mostrar su propio mensaje de error; la app no puede inspeccionar su DOM entre dominios ni conocer si el vídeo avanza. No hay temporizador que cambie de proveedor mientras alguien está viendo correctamente. No se han inventado eventos `postMessage`, ni se han extraído URLs privadas de los vídeos.

Falta validar VideoAPI, Vimeus y OK.ru en un teléfono físico: reproducción, anuncios, pantalla completa, giro, pausa/reanudación y sesiones largas. No se afirma que los tres proveedores funcionen hasta hacer esa prueba. Cambiar de proveedor puede empezar el episodio desde el principio, porque no hay progreso compartido verificado.

El APK actual está firmado con una clave **de depuración**, destinado a prueba privada. No se publica en tiendas. Antes de distribuirlo al público se preparará una firma de lanzamiento conservada por el propietario y se validarán los requisitos de distribución correspondientes.

## Estructura y compilación

- `app/src/main/java/live/quehay/app/MainActivity.java`: WebView, navegación, cookies, pantalla completa y errores nativos.
- `app/src/main/assets/mobile.js`: política de proveedor y paginación; `mobile.css`: adaptación visual limitada a la APK.
- `tests/playback-policy.test.cjs`: fallos, cuenta, episodios, respuestas tardías y límites de reintento.
- `../scripts/run_android_preview.py`: vista local en 127.0.0.1:5016, catálogo de muestra y SQLite aislado, red externa del backend bloqueada. No es un emulador Android.
- `../scripts/build_android.ps1`: compila, revisa y verifica la firma; no descarga ni acepta licencias automáticamente.

Requisitos: JDK 17, SDK plataforma 35, Build Tools 35.0.0. Gradle Wrapper 8.11.1 con SHA-256 fijado y Android Gradle Plugin 8.9.2. Herramientas locales instaladas bajo `.local/android-tools` con autorización del propietario el 29/10/2026.

Ejecutar desde la raíz: `node --test android/tests/playback-policy.test.cjs` y `powershell -File scripts/build_android.ps1`.

## Prueba en teléfono

1. Copiar `QueHay-Android-0.3.apk` al teléfono e instalar esta versión de prueba. No hace falta desactivar Play Protect.
2. Abrir **Qué Hay**, iniciar sesión en la cuenta existente y comprobar su acceso.
3. Probar una película y una serie, la paginación, siguiente capítulo y la descarga de un episodio.
4. Pulsar el icono de pantalla completa y comprobar el horizontal incluso con el giro del sistema bloqueado. Volver debe salir primero del vídeo/pantalla completa.
5. Registrar modelo, versión Android, proveedor real en el diagnóstico técnico (sin añadir el selector a la interfaz), resultado y error. Esta matriz se completará en la siguiente fase.

Referencias oficiales: [pantalla completa WebView](https://developer.android.com/reference/android/webkit/WebChromeClient), [seguridad de puentes nativos](https://developer.android.com/privacy-and-security/risks/insecure-webview-native-bridges), [AGP 8.9](https://developer.android.com/build/releases/agp-8-9-0-release-notes).

## Actualización 0.2 (29/10/2026)

El propietario confirmó reproducción de VideoAPI y giro con rotación del sistema habilitada en la 0.1. No implica compatibilidad ya comprobada de Vimeus u OK.ru.

La 0.2 incorpora Compartir nativo (ACTION_SEND), título y enlace directo público sin sesión, y solicita SENSOR_LANDSCAPE solo durante pantalla completa. Web/Telegram comparten el módulo `static/catalog/share.js`, empaquetado por Gradle. El comando nativo solo acepta gestos en navegación principal desde el dominio de la app, valida ID/título y construye internamente el enlace permitido. No expone un puente JavaScript a reproductores.

Validación: 25 pruebas JavaScript aprobadas, compilación y firma verificadas, lint 0 errores / 7 advertencias. Pendiente en teléfono: menú Compartir, recepción del enlace y horizontal con giro del sistema bloqueado. Los cambios web están preparados localmente y aún no desplegados.

## Actualización 0.3 (29/10/2026)

Nombre visible de instalación e icono: **Qué Hay**; versión visible 0.3.0 sin sufijo de prueba. Se conserva el identificador y certificado de las versiones anteriores para actualizar sin borrar la sesión. La compilación desactiva `debuggable`; el certificado sigue siendo el original de desarrollo, pendiente de una estrategia de firma para distribución pública.

Descargas: marcador circular azul solo con icono en tarjetas; los controles y enlaces de descarga se conservan. Encabezado: saludo por el primer nombre para toda cuenta autenticada, sin enlace de compra cuando la consulta existente confirma membresía; cuenta sin acceso mantiene Activar acceso. Los nombres largos se truncan visualmente sin expandir el header. El saludo nunca concede acceso ni usa como identidad una cuenta Telegram sin verificar.

`static/catalog/identity.js` y `identity.css` se comparten con la APK a través de Gradle. La adaptación del APK funciona también contra la versión web aún desplegada. Sin cambios en Render, Supabase, pagos ni descargas.
