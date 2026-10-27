# Fase 3 — Acceso mensual y página de membresía

Validación local: 26 de octubre de 2026. No se desplegó, no se ejecutaron migraciones en Supabase y no se realizaron cobros, transferencias ni envíos reales por Telegram.

## Resultado

Un único acceso de 30 días, sin renovación automática, con tres formas de pago:

| Método | Importe | Activación |
| --- | --- | --- |
| Buy Me a Coffee | US$1.50 | Webhook firmado de compra única |
| Yape / Plin | S/5.50 | Revisión y aprobación del administrador |
| Binance Pay | 1.50 USDT | Revisión y aprobación del administrador; falta configurar el QR oficial |

La página `/membresia` explica el catálogo, temporadas y capítulos, descargas disponibles, publicidad del reproductor, inicio del período, renovación voluntaria y conservación del tiempo restante. Tiene diseño azul oscuro, azul claro y dorado, con disposición adaptable a pantallas pequeñas. Se retiraron del recorrido de compra la oferta especial, el cupón, la cuenta regresiva, los videotutoriales y PayPal.

Las descargas se conservan: se exige acceso vigente y se mantiene la apertura explícita de enlaces externos, incluidos MediaFire. El aporte no promete eliminar la publicidad del proveedor.

## Flujo manual

1. El usuario inicia sesión, elige Yape/Plin o Binance Pay y ve el importe y el QR del receptor.
2. Después de pagar, registra el número de operación, el nombre del titular y la fecha. Esto deja una solicitud pendiente; no concede acceso.
3. En **Admin → Pagos**, el administrador comprueba el ingreso en su billetera. Debe marcar la confirmación antes de aprobar. También puede rechazar con un motivo.
4. La aprobación añade 30 días al vencimiento vigente, o al momento actual si el acceso ya venció. Repetir la aprobación no añade días otra vez; un número de operación ya utilizado no puede activar otra cuenta.

El QR original de Yape se sirve sin alterar sus bytes y se muestra sobre fondo blanco. Se comprobó su lectura local sin imprimir el contenido del QR. El panel permite cargar imágenes oficiales PNG/JPG de hasta 1 MB y conservarlas en la base privada. No se generó un QR de Binance ficticio.

## Seguridad y estructura

- `billing/`: configuración, tablas privadas, transacciones y validación de webhooks.
- `routes/payments.py`: página, solicitudes propias, QR y controles administrativos.
- `static/payments/`: HTML, CSS y JavaScript de membresía.
- `static/admin/payments.*`: revisión de pagos y configuración de QR.
- `migrations/003_monthly_payments.sql`: tablas, restricciones e índices para PostgreSQL. No aplicada en producción.
- `tests/test_billing.py` y `tests/billing-sql.test.mjs`: nuevas verificaciones del flujo.

El servidor decide cuenta, importe, moneda y duración. Se mantienen sesión, CSRF y autorización del único administrador, `5824989040`. Una transacción guarda el pago utilizado, la aprobación y el vencimiento; si falla una parte, se revierte todo. En PostgreSQL, las renovaciones de la misma cuenta se serializan bloqueando su fila. Las solicitudes pendientes siguen apareciendo aunque haya más de 100 entradas recientes en el historial.

Las nuevas compras activan la cuenta web sin invitaciones a canales. Los accesos anteriores vigentes se tienen en cuenta para no perder días. El bot conserva su función de marketing y dirige las nuevas compras a la membresía. La conciliación histórica permanece separada en el panel.

## Pruebas

**135 pruebas aprobadas: 116 de Python y 19 de Node.js/SQL.**

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=.local/phase3-python.xml
node --test tests/frontend.test.cjs tests/episodes.test.cjs tests/vimeus-sql.test.mjs tests/billing-sql.test.mjs
```

Evidencia guardada en `.local/phase3-python.txt`, `.local/phase3-python.xml` y `.local/phase3-javascript.txt`. Las pruebas cubren importación anterior, descargas, vencimiento, aislamiento entre cuentas, importes manipulados, CSRF, firma incorrecta, eventos de prueba, códigos de compra, pago repetido, aprobación concurrente, reversión ante fallo, conservación de días y restricciones SQL. Los casos del antiguo webhook de varios planes fueron reemplazados por los del plan único.

Las migraciones se ejecutaron sobre PGlite local para verificar restricciones y aislamiento de roles. Las pruebas de transacciones usaron SQLite local; esto no equivale a una prueba de concurrencia contra PostgreSQL de producción. Python emitió 20 advertencias de dependencias, sin fallos. `pip check`, la comprobación sintáctica de los JavaScript modificados y `git diff --check` finalizaron sin errores de contenido.

En navegador se comprobó: registro de una operación ficticia de Yape → estado pendiente sin acceso → rechazo de aprobación sin confirmar revisión → aprobación local; y simulación administrativa de webhook BMC → segundo período acumulado. La cuenta de prueba mostró ambas compras aprobadas y 60 días de acceso. No hubo transferencia real.

Capturas:

- `.local/fase3-membresia.png`: página de membresía en escritorio.
- `.local/fase3-yape.png`: formulario con QR conservado y aviso de entorno local.
- `.local/fase3-aprobaciones.png`: historial de las dos aprobaciones ficticias.
- `.local/fase3-movil.png`: comprobación visual de la cabecera y tarjeta a 390 px, usando el mismo HTML y CSS en un marco de prueba. El ajuste de tamaño del navegador integrado no se aplicó a la pestaña; esta captura valida esa disposición visual, no el proceso completo en un teléfono. El archivo temporal de comprobación se retiró.

## Antes de una futura puesta en producción

1. Configurar el producto de compra única de Buy Me a Coffee `517243` a **US$1.50**, con la pregunta obligatoria **Código de compra**. Confirmar el producto real antes de habilitar `BMC_MONTHLY_READY=true`; actualmente el valor documentado es `false`. El código aleatorio asocia el pago a una cuenta, sin confiar en un correo escrito en el checkout.
2. Subir el QR oficial de Binance Pay preparado para USDT desde **Admin → Pagos → Configurar QR oficiales**. Hasta entonces se muestra pendiente de habilitar.
3. Revisar y aplicar las migraciones privadas necesarias, configurar secretos y probar el webhook real en una fase autorizada. Aquí solo se verificaron eventos sintéticos ajustados al contrato documentado.
4. Los eventos de reembolso, suscripción recurrente, importe incorrecto o código faltante quedan para conciliación. No activan automáticamente el nuevo acceso. No hay resolución automática de reembolsos ni una interfaz completa para resolver excepciones BMC; requieren revisión antes de habilitar pagos reales.
5. El cambio local no cancela suscripciones que pudieran existir previamente en proveedores externos. Deben revisarse por separado antes de publicar el nuevo modelo. No se modificó ninguna cuenta de pagos externa.

Contrato consultado: [webhooks de Buy Me a Coffee](https://help.buymeacoffee.com/en/articles/15743173-how-to-setup-and-use-buy-me-a-coffee-webhooks) y [especificación oficial](https://cdn.buymeacoffee.com/assets/integrations/bmc-webhooks-openapi.json). Se verifica HMAC-SHA256 sobre el cuerpo original y se distingue `extra_purchase.created` de eventos recurrentes y de prueba.

## Abrir la vista local

```powershell
.\.venv\Scripts\python.exe scripts/run_local.py
```

Membresía: <http://127.0.0.1:5010/membresia>. Panel: <http://127.0.0.1:5010/admin>. Las credenciales exclusivamente locales están en `.local/access.txt` y `.local/payment-demo.txt`; no son las de producción. El servidor de pruebas bloquea conexiones externas del backend y no carga secretos de producción.
