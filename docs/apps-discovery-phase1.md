# Opciones de aplicación · Fase 1 local

## Alcance

El inicio compartido por web y Telegram presenta Android, Android TV / Google TV y PWA. `/instalar` explica las diferencias, conserva la instalación real de la PWA y enlaza a la vinculación TV existente. La landing usa la misma presentación. Las APK todavía no tienen enlaces de distribución pública: se indica «Descarga directa en preparación» y los enlaces llevan a instrucciones reales.

No se modifican cuentas, sesiones, membresías, reproducción, descargas de contenido, proveedores, APK nativas ni la interfaz de TV. No hay publicación, cambios de DNS o altas de servicios.

## Archivos

- `static/catalog/browse.js`: bloque final de las tres opciones.
- `static/pwa/platforms.css`: presentación de tarjetas, ilustraciones CSS y adaptación móvil; sin nuevas bibliotecas, videos ni imágenes pesadas.
- `static/pwa/install.html` y `options.css`: página de instalación e instrucciones.
- `static/pwa/install.js`: instrucciones por plataforma; instalación solo ante una oferta real del navegador y acción del usuario.
- `landing/index.html` y `landing/assets/platforms.css`: presentación equivalente y compatibilidad TV actualizada.

`landing/assets/platforms.css` es la copia de distribución estática de `static/pwa/platforms.css`. Al cambiar el diseño compartido, sincronizar ambos archivos. El constructor de la landing genera nombres con hash para invalidar sus cachés.

## Pruebas realizadas

- `python -m pytest tests/test_pwa.py tests/test_landing_build.py -q`: 11 pruebas aprobadas.
- `node --test tests/pwa.test.cjs tests/landing-selection.test.cjs`: 20 pruebas aprobadas.
- Sintaxis de ambos módulos JavaScript y `git diff --check`: correctos.
- Inspección visual local a 390 × 844 y 1366 × 900. En móvil, ancho útil y ancho del contenido de 375 px, sin desbordamiento horizontal en las tres superficies.
- Enlaces de las opciones, expansión de instrucciones Safari y rutas de cuenta/vinculación conservados. No se inició una compra ni una vinculación real.

Telegram: pruebas del contexto en el módulo compartido, sin ensayo en teléfono físico. No se afirma instalación real de una nueva APK en esta fase.

## Revisión

Servidor existente y aislado: `http://127.0.0.1:5031`.

- `/instalar`: página de opciones.
- `/`: bloque al final del inicio.
- `/static/_design-preview/index.html`: resumen visual y enlaces a las tres vistas.

`static/_design-preview/` contiene solo copias de recursos públicos para revisar, está excluido de Git y no debe desplegarse. La landing local sustituye únicamente en esa copia los enlaces hacia la aplicación por el origen local.

La animación de arranque, la compilación/firma de APK y la publicación de archivos corresponden a las fases siguientes.
