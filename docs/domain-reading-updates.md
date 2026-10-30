# Dominio antiguo, sinopsis y actualizaciones

Preparado en local el 30 de octubre de 2026. No desplegado.

## Redirección gradual

`services/canonical_origin.py` envuelve el router web/TV. Solo redirige documentos
GET/HEAD del host exacto `cineapp-bot.onrender.com` a `https://app.quehay.live`,
conservando la ruta y la consulta. La lista explícita incluye inicio, cuenta,
membresía, instalar, admin y páginas de entrada/vinculación TV.

`LEGACY_REDIRECT_MODE`:

- Ausente u `off`: desactivada (valor por defecto).
- `temporary`: 302 sin caché, para validar el despliegue reversible.
- `permanent`: 301 sin caché, para la etapa definitiva autorizada.

Se mantiene desactivada en APP_MODE local y si APP_ORIGIN no coincide con el
dominio oficial. No se redirigen APIs, cron, webhooks, callbacks de pago,
manifest, service worker, archivos estáticos ni métodos de escritura. No se
leen cuentas ni se emiten cookies al redirigir. No confiar en X-Forwarded-Host.

Antes de publicar: confirmar autorización, subir por GitHub y activar primero
`temporary` en Render. Comprobar páginas y enlaces de títulos; observar que las
integraciones continúen sin redirecciones. Pasar a `permanent` solo tras la
validación aprobada. Para revertir, usar `off`. No deshabilitar el subdominio en
Render: eso devuelve 404 y evita que la petición alcance la regla.

Las cookies siguen aisladas por host; un usuario con sesión únicamente en la
dirección antigua puede necesitar iniciar sesión en el dominio oficial. Su
cuenta y acceso no se eliminan. Las PWA antiguas no se trasladan de origen
automáticamente; conservar las rutas técnicas evita retirarlas abruptamente.

## Lectura y avisos

`static/catalog/synopsis.js` se carga al abrir una ficha, mediante DetailAssets.
Muestra tres líneas en fichas y dos en episodios. Ver más/Ver menos solo aparece
si hay texto recortado. No modifica datos ni solicita información adicional.
La lectura está fuera del botón de reproducción y conserva las descargas.

El aviso compartido de `static/updates/notice.js` solo se inicia con los
identificadores QueHayAndroid/ o QueHayTV/ de las APK actuales. Es detección de
presentación, nunca autorización. No crear observadores ni consultar versiones
desde navegadores normales. Las comprobaciones de reproducción impiden mostrar
el aviso o recargar mientras hay un reproductor abierto. El usuario decide
Actualizar o Más tarde. El aviso PWA independiente fue retirado; su worker se
activa mediante el ciclo normal del navegador, sin recargas forzadas.

No cambia código nativo: estos ajustes no requieren recompilar las APK. Una
modificación nativa futura sí requeriría distribuir un archivo nuevo.

## Evidencia local

- Suite Python: 588 pruebas correctas (incluye acceso del propietario, sesiones,
  descargas, pagos con fixtures y redirecciones).
- Suite Node CJS: 114 pruebas correctas. Se actualizó el fixture de rendimiento
  para las dependencias de artwork/sinopsis y el nuevo recurso diferido.
- `node tests/domain-ux.browser.cjs`: 10 escenarios de navegador, con extractos
  a 1366 y 390 px, lectura sin solicitudes API, acción de descarga conservada,
  textos breves/ausentes/HTML literal, siete perfiles de ejecución y PWA en espera.
- Dependencias Python emiten advertencias de obsolescencia conocidas; no fallos.

Pruebas de redirección usan hosts simulados en el cliente WSGI local; no cambian
DNS ni alcanzan Render. Pruebas de APK usan sus user agents en Chromium: no son
validación en teléfono/TV físico ni reproducción real del proveedor.

La vista de revisión es `http://127.0.0.1:5031/?contenido=835`.
El informe y capturas están en `.local/domain-ux/`. El servidor usa SQLite y una
copia local del catálogo, con llamadas externas de backend bloqueadas.
