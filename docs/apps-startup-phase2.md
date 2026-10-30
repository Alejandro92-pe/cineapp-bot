# Inicio animado de las APK — fase 2 local

Implementado el 30 de octubre de 2026. Sin publicación ni cambios en Render,
Supabase, bot, pagos o descargas. Los cambios de presentación de la fase 1 se
conservan, pero son independientes de esta animación nativa.

## Comportamiento

- Carita original, sobre un degradado azul noche. Una entrada de escala, giro
  suave y opacidad de hasta 650 ms. Recurso PNG de 3.448 bytes, sin vídeo, GIF,
  dependencias nuevas ni peticiones adicionales.
- La petición de la web empieza inmediatamente. No se espera a terminar la
  animación: `onPageCommitVisible` solicita el primer estado visual y retira la
  cubierta con una salida de 100 ms.
- Si no llega ese estado, la cubierta se retira a los 1.800 ms. Es un máximo,
  no una espera mínima; queda la carga o el error normal de la aplicación.
  El plazo depende del hilo de interfaz, no es una garantía de tiempo real.
- Se cancela al pausar, cerrar, volver o mostrar un error. No reaparece al
  navegar dentro de la web ni al restaurar una actividad con estado guardado.
  Una apertura nueva tras cerrar el proceso sí vuelve a mostrarla.
- Respeta la desactivación de animaciones de Android. Android 12+ usa también
  la carita en su ventana de arranque, sin añadir una espera o salida propia.
- No se incorpora a web, PWA, Telegram ni landing. TV conserva su navegación
  con mando y continúa sin pagos ni descargas.

## Código y compilación

`android-common/` contiene el componente y la imagen compartidos.
`android/` y `android-tv/` lo incluyen por sus sourceSets de Gradle. La copia
del proyecto móvil se tomó de los archivos fuente del checkout principal;
el original y sus cambios previos no se sobrescribieron.

Versiones preparadas: Android 0.5.0 (code 5) y TV 0.3.0 (code 3). Se conservaron
los identificadores `live.quehay.app.preview` y `live.quehay.tv`, respectivamente.
La firma coincide con Android 0.4 y TV 0.2: certificado SHA-256
`8b9eb1ea50e568ea54ba1dd1859fcef647edd3f78a4dd88abc0928508decf681`.
Son compilaciones firmadas con la clave Android Debug histórica del proyecto,
con `debuggable=false`; no se cambió la clave de actualización.

Se necesita instalar una nueva versión de cada APK para recibir este cambio
nativo. No exige cambios de backend ni desinstalar la versión anterior.
No se deben borrar datos o desinstalar para actualizar.

Compilación normal: `:app:assembleDebug :app:lintDebug`. Para TV, añadir
`-PtvOrigin=https://app.quehay.live`. Ambas variantes normales conservan HTTPS
y el único permiso INTERNET. El paquete móvil pasó de 29.971 a 36.907 bytes;
el de TV, de 22.438 a 28.982 bytes.

## Prueba aislada reproducible

1. Servir la copia local aislada en `127.0.0.1:5031`, sin credenciales reales
   y con red externa del backend bloqueada.
2. En el emulador usar `adb reverse tcp:5031 tcp:5031`.
3. Compilar con `-PstartupCheck=true :app:assembleDebugAndroidTest`; para TV,
   también `-PtvOrigin=http://127.0.0.1:5031`.
4. Instalar las aplicaciones y pruebas con sus identificadores separados
   `live.quehay.app.startupcheck` y `live.quehay.tv.startupcheck`. No reemplazan
   las aplicaciones del usuario. HTTP se habilita únicamente para loopback
   en esta variante de prueba.
5. Ejecutar `adb shell am instrument -w` con el componente
   `<paquete>.test/live.quehay.startup.StartupChecks`.

## Resultados

Emulador Android TV API 36, 1280 × 720; ambas aplicaciones abrieron el catálogo
local. Los datos visuales provienen de una copia; no se escribieron cuentas
reales. La prueba móvil se ejecutó en ese mismo emulador, no en un teléfono.

| Validación | Android | TV |
|---|---:|---:|
| Comprobaciones nativas aprobadas | 12 | 12 |
| Retirada tras estado visual listo | 166 ms | 157 ms |
| Retirada con carga detenida | 1.822 ms | 1.803 ms |
| Compilación y lint | 0 errores / 7 avisos | 0 errores / 5 avisos |

Las comprobaciones cubren documento local real, aparición, actividad
restaurada, cancelación inmediata, página lista, plazo máximo, callbacks tardíos,
cookie sintética conservada y navegación sin repetir la entrada. Las medidas
corresponden al componente y a ejecuciones locales puntuales; no miden el tiempo
de Render ni son una prueba de rendimiento en dispositivos físicos.

Además, 9 pruebas de proveedores/fallback y control remoto aprobaron. Los
avisos de lint son de atributos, API desaconsejada, WebView JavaScript, forma del
icono y textos nativos sin recursos de traducción; no hay errores bloqueantes.

Queda pendiente revisar la experiencia en el teléfono y un televisor físicos,
incluyendo actualización sobre la instalación existente. No se ejecutaron
pagos, descargas reales ni pruebas de inicio de sesión contra producción.
La preservación de cuentas se apoya aquí en no modificar datos ni lógica de
autenticación, mantener paquete/firma y comprobar la cookie sintética.

Evidencias locales: `.local/apps-phase2/` (APK, logs, capturas, vídeo e informe).
