QUÉ HAY TV 0.2 — PRUEBA HTTPS CON CUENTAS REALES
Paquete independiente live.quehay.tv. Origen https://app.quehay.live/tv.
No depende de la PC ni de la misma red local; requiere internet.
Sin pagos ni descargas. No reemplaza la APK móvil ni la antigua prueba LAN.
Desde el celular: https://app.quehay.live/tv/vincular, iniciar sesión con la
cuenta existente y confirmar el código de la TV. Una cuenta solo de Telegram
necesita sesión verificada en el mismo navegador o contexto de Mini App.
Compilar: powershell -File scripts/build_android_tv.ps1 -Origin https://app.quehay.live
Salida: .local/tv-apk/QueHay-TV-0.2.apk. Firma de desarrollo para prueba privada,
depuración deshabilitada y tráfico HTTP bloqueado. No publicar en tiendas.
Sesión autenticada: siete días, independiente del acceso permanente del propietario.
El proveedor de video todavía debe validarse en TV física.

DOCUMENTACIÓN HISTÓRICA: PRUEBA LAN 0.1 (NO ES LA APK HTTPS)

QUÉ HAY TV — APK 0.1 PARA PROBAR CON MANDO

Paquete separado: live.quehay.tv.preview. No reemplaza live.quehay.app.preview.
Android TV / Google TV con Android 8 o posterior y WebView actualizado.
No se instala directamente en LG webOS ni Samsung Tizen. No hay publicación
en tiendas, integración de pagos ni descarga de películas en este paquete.

ARQUITECTURA DE ESTA PRUEBA
Shell nativo Android/Java que carga exclusivamente /tv desde el servidor de
demostración en la PC. El catálogo e interfaz se sirven por la red local y los
reproductores externos por HTTPS. La APK no contiene claves de Supabase, Render,
Telegram ni contraseñas. No hay interfaz nativa JavaScript expuesta a iframes.
Cuenta, códigos y sesiones se guardan en .local/tv/preview-lan.sqlite, separado
incluso de preview.sqlite. Producción y la APK móvil no se modifican.

VINCULACIÓN
1. TV, PC y celular en la misma red. PC encendida, servidor en 192.168.100.3:5021.
2. Abrir Qué Hay TV y elegir Vincular cuenta. Anotar el código (vence en 10 min).
3. Desde el celular abrir http://192.168.100.3:5021/tv/vincular.
4. Correo: tv@example.test; contraseña: Televisor-Local-2026!
5. Introducir el código y confirmar. La TV detecta la vinculación automáticamente.
La página del celular es web: no exige PWA, APK móvil ni callback. En producción
se integrará con la cuenta real a través de HTTPS; todavía no está conectado.
No introducir contraseñas reales en esta demostración HTTP de red privada.

La sesión de TV dura hasta siete días, o hasta que se cierre/revoque; la cuenta
de demostración tiene acceso temporal para la prueba. Cada reproducción consulta
el permiso vigente. Revocar desde el celular invalida las sesiones de esa cuenta.

MANDO
Flechas: mover la selección. OK: abrir ficha o ejecutar la acción seleccionada.
Atrás: salir del modo de video, volver a la ficha/listado o confirmar salida.
Dentro del video, Controles del video entrega el foco al proveedor. Los botones
de pausa, avance y pantalla completa dependen de su soporte real para mando.
La app puede mostrar pantalla completa nativa cuando el reproductor la solicita.
No se afirma compatibilidad de VideoAPI/OK.ru en una TV física hasta probarla.

COMPILAR Y ARRANCAR
Desde la raíz del checkout: powershell -File scripts/build_android_tv.ps1
La instalación oficial de JDK/SDK existente se reutiliza, sin cambios en android/.
Para cambiar IP, pasar -Origin http://IP_PRIVADA:5021 y recompilar. El build rechaza
orígenes públicos, credenciales en URL y rutas adicionales.
Servidor: powershell -File scripts/start_tv_lan.ps1
No cambia el firewall, el router, DNS, Render ni otros sitios. HTTP solo está
habilitado en la APK para la IP privada compilada; otros orígenes requieren HTTPS.

SEGURIDAD Y VALIDACIÓN
Solo permiso INTERNET. Sin almacenamiento, cámara, micrófono ni descargas.
Sin copia de seguridad Android, depuración WebView ni omisión de errores TLS.
App debuggable=false, firma de pruebas v2; no es el paquete final de tienda.
23 pruebas Python (TV y frontera LAN), 4 Node (navegación/adaptador de mando).
Build assembleDebug y lintDebug aprobados; 0 errores lint, 7 advertencias revisadas:
compatibilidad de atributos, orientación TV, JavaScript necesario, icono y textos.
Manifest verificado: LEANBACK_LAUNCHER, touchscreen opcional, leanback requerido.
Prueba con dos contextos de navegador: código, confirmación, sesión persistente
al recargar, acceso, selección de VideoAPI, revocación desde el celular.
El usuario confirmó que el formulario abre desde su celular por la red local.
No había dispositivos Android conectados a ADB; falta instalar y probar físicamente.

LIMITACIONES
La PC debe permanecer encendida. Si cambia la IP local hay que regenerar el APK.
El catálogo es la copia local; las películas de canal sin fuente compatible siguen
sin reproducción TV. La conmutación de proveedor y fin automático de episodio
no se certifican con este empaquetado. Sí se conserva Siguiente episodio.
El SDK oficial confirma los requisitos de launcher TV y banner:
https://developer.android.com/training/tv/get-started/create
