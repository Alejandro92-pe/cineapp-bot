# Fase 1 — Seguridad y cuentas, revisión local

Fecha: 26 de octubre de 2026. Proyecto: `cineapp-render`.

## Resultado y alcance

Implementación local para revisión. No se desplegó, no se cambió el cron externo,
no se editaron secretos en Render y no se ejecutaron consultas de escritura ni
migraciones en Supabase. El esquema de Supabase se consultó visualmente, sin copiar
registros de usuarios. El catálogo y las membresías usados en las pruebas son ficticios.

Vista de cuentas: <http://127.0.0.1:5010/cuenta>. Panel: <http://127.0.0.1:5010/admin>.

La propuesta de color de esta pantalla utiliza azul noche, azul claro y acentos dorados.
El catálogo conserva su diseño anterior: el rediseño completo es otra fase.

## Cambios implementados

- Único administrador: `5824989040`. Las variables antiguas y los IDs enviados
  desde el navegador no conceden permisos. Los dos antiguos administradores se
  consideran usuarios normales, incluso con una identidad Telegram auténtica.
- Registro, inicio y cierre de sesión, cambio de contraseña y cierre de otras
  sesiones. Contraseñas bcrypt con coste 12, límite explícito de 72 bytes y mínimo
  de 12 caracteres. El login administrativo acepta hashes bcrypt existentes en
  `ADMIN_PASSWORD_HASH` o `ADMIN_PASSWORD`; no acepta texto plano ni expone el hash.
- Cookies HttpOnly, SameSite=Lax y Secure en producción. Tokens aleatorios de sesión
  guardados como SHA-256 en el servidor. Caducidad: 12 horas para usuarios y una hora
  para administrador. CSRF y origen obligatorio en operaciones con sesión.
- Sesiones y límites de intentos persistentes en base de datos; no dependen de un
  diccionario de memoria de un worker. El cliente no puede elegir su identidad.
- Telegram se valida con firma HMAC, fecha máxima de cinco minutos y rechazo de
  parámetros duplicados. La vinculación exige prueba firmada y no fusiona cuentas
  por el nombre, correo o parecido. El webhook del bot requiere su secret header.
- Cron conserva sus rutas, con `Authorization: Bearer <CRON_SECRET>`. No se cambia
  la frecuencia actual. Los enlaces de reproducción y descarga comprueban la fecha
  de vencimiento y el estado de membresía en cada solicitud, aunque no haya corrido
  todavía el cron.
- El catálogo público indica si hay descarga, pero omite enlaces privados. Las
  descargas siguen almacenadas en `contenido.descarga`. Se obtienen mediante una
  ruta autenticada, admiten HTTPS de MediaFire u otros proveedores y no se borraron
  enlaces existentes. No se descarga ni se retransmite el archivo desde Render.
- La interfaz ofrece un segundo clic explícito para abrir el proveedor. En Telegram
  usa `openLink(..., {try_instant_view:false})`; en navegador, un enlace con aislamiento
  de `opener`. También permite copiarlo. Se corrigieron interpolaciones de texto y
  objetos en las plantillas heredadas y se comprueba el origen de mensajes del iframe.
- La URL de reproducción se obtiene del servidor después de verificar acceso. La
  ruta pública anterior de View Key se retiró. La View Key seguirá siendo visible
  cuando el navegador necesite cargar el iframe: esto no es DRM.
- Buy Me a Coffee conserva la activación automática de compras puntuales. Verifica
  firma del cuerpo original, producto, importe, moneda, cantidad, estado y marca de
  prueba. Los reintentos se deduplican por pago, no por intento de entrega. La
  aprobación manual y el webhook comparten una reserva por pago pendiente.
- Un fallo parcial queda para revisión y no repite una activación a ciegas. Los
  correos con varios pagos pendientes no se asignan por orden. No se almacena el
  cuerpo completo del webhook en el registro de deduplicación.
- PayPal ahora rechaza verificaciones sin `PAYPAL_WEBHOOK_ID`; la carga enviada a su
  verificador tiene el tipo JSON correcto. Su retirada y la conciliación de cualquier
  suscripción anterior corresponden a la fase de cobros.
- Se corrigió una mezcla de fechas con/sin zona horaria en la activación y se conserva
  el tiempo restante exacto al renovar.

## Pruebas ejecutadas

Entorno: Windows, Python 3.12 en `.venv`, Node.js. El `runtime.txt` de producción
continúa indicando Python 3.11; esta fase no valida un despliegue en ese runtime.

| Comprobación | Resultado |
| --- | --- |
| pytest: cuentas, sesiones, permisos, firma Telegram, cron, vigencia, pagos, concurrencia | 56 aprobadas |
| node:test: apertura MediaFire, navegador, URL insegura, sesión vencida, codificación HTML/JSON | 6 aprobadas |
| Sintaxis Python y todos los JS, incluido el script del panel admin | Correcta |
| `pip check` | Sin conflictos de dependencias |
| `git diff --check` | Sin errores |

Las pruebas incluyen un pago ficticio que recorre la función real de activación
contra la base de negocio simulada, conserva los días restantes y añade exactamente
30 días una sola vez. No representan una compra real ni una confirmación del checkout.
Las salidas de red y SMTP se bloquean durante pytest. El servidor local bloquea
resolución/conexiones externas, usa un bot simulado y no carga las credenciales de `.env`.

Comprobaciones adicionales en navegador: registro de `revision@example.test`, sesión
persistente tras reiniciar el servidor, cierre de sesión, acceso del administrador
con contraseña local, ficha con botón Descargar y rechazo de descarga sin sesión.
No se descargó un archivo real de MediaFire ni se probó en un teléfono Android físico.

Evidencias locales (ignoradas por Git):

- `.local/tests-python.txt` y `.local/tests-python.xml`.
- `.local/tests-frontend.txt`.
- `.local/cuentas-local.png`.

pytest emitió 20 avisos de deprecación de dependencias heredadas (`dateutil`/`gotrue`).
No se presentan estas pruebas como una auditoría completa de dependencias ni de RLS.

## Reproducir localmente

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts/run_local.py
```

El servidor escucha únicamente en `127.0.0.1:5010`. Puedes crear cuentas ficticias
en la pantalla. La contraseña administrativa local se genera al primer arranque en
`.local/access.txt`; no es la de Render. No uses contraseñas o correos reales para
esta revisión. La base local persiste en `.local/accounts.sqlite`; el catálogo de
negocio ficticio se reinicia con el servidor.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --test tests/frontend.test.cjs
```

## Decisiones y pendientes antes de producción

1. Las cuentas implementadas son propias del backend, no Supabase Auth. Se usa
   SQLite exclusivamente en local y se preparó un adaptador PostgreSQL con un
   esquema privado `cine_security`. `migrations/001_security.sql` está preparado,
   **no aplicado**. Producción exige PostgreSQL y TLS; nunca usa SQLite de respaldo.
   Falta validar la migración y permisos con una base de staging autorizada.
2. El correo de registro todavía no tiene confirmación de propiedad ni recuperación
   por correo. Por eso no se usa para transferir accesos existentes. En esta fase,
   recuperar una membresía antigua exige vincular el Telegram firmado. La compra
   para cuentas web independientes y su asociación inequívoca se completan en la
   fase de cobros, antes de lanzar el nuevo sistema. El formulario heredado de pagos
   aún necesita esa asociación/verificación antes de desplegarse; en local está bloqueado.
3. La configuración real de BMC debe contrastarse con un evento de prueba y su
   producto real antes de desplegar. Se usó `517243` / `copper` / USD 3.50 solo como
   fixture local provisional. No se cambió el producto externo a USD 1.50 ni el precio
   público. No hace falta entregar claves ni modificar productos para revisar esta fase.
4. El manejador nuevo activa `extra_purchase.created`; los eventos de suscripciones
   anteriores no conceden nuevos días. Antes del reemplazo hay que inventariar y
   conciliar cualquier suscripción anterior. No se canceló ninguna suscripción real.
5. Antes de un futuro despliegue: preparar almacenamiento de sesiones, hash bcrypt,
   secretos de BMC/bot/cron y el encabezado de cron-job.org de forma coordinada. No
   publicar esta versión cambiando solo los archivos: el cron actual necesita ese
   encabezado y el webhook del bot necesita su secreto configurado.
6. No se han validado ni modificado las políticas RLS actuales de las tablas de negocio,
   las credenciales de Render ni el comportamiento completo de PayPal. No se hizo push,
   despliegue, registro de webhook ni cambio de infraestructura.
7. La sesión protege el acceso a enlaces desde la aplicación. Un enlace externo ya
   compartido o un archivo ya descargado no puede revocarse desde nuestra web. Tampoco
   se garantiza interrumpir un iframe de terceros que ya está reproduciendo al vencer.

## Fuentes consultadas

- Telegram: validación de initData y apertura de enlaces:
  <https://core.telegram.org/bots/webapps>.
- Buy Me a Coffee: firmas y eventos:
  <https://help.buymeacoffee.com/en/articles/15743173-how-to-setup-and-use-buy-me-a-coffee-webhooks>.
- Esquema oficial del webhook:
  <https://cdn.buymeacoffee.com/assets/integrations/bmc-webhooks-openapi.json>.
- bcrypt: límites y formato:
  <https://pypi.org/project/bcrypt/>.

La hipótesis sobre el fallo previo de MediaFire es la apertura mediante `window.open`
desde la Mini App y las restricciones del navegador integrado. No se atribuye una
causa definitiva sin un enlace fallido y una prueba en el dispositivo afectado.
