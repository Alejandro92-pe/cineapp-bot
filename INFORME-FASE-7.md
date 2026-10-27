# Reproductor integrado, series y descargas por episodio

Fecha: 26 de octubre de 2026. Trabajo exclusivamente local; no se desplegó Render, no se modificó Supabase y no se cambió el bot.

## Causa comprobada del botón deshabilitado

La copia local del catálogo tenía las fichas de series, pero no sus temporadas y capítulos. La interfaz y la autorización de reproducción exigían seleccionar un episodio local, por lo que impedían abrirlas. Este hallazgo no demuestra un fallo del reproductor en Telegram.

Vimeus documenta que `se` y `ep` son opcionales: la URL de una serie completa puede abrir el selector del proveedor. Ahora ese caso está habilitado, conservando autenticación y comprobación de membresía. Un ID de episodio explícito incorrecto sigue rechazándose.

Referencia consultada: https://www.vimeus.com/docs/getting-started

## Cambios visibles

- Reproductor dentro de la ficha, con cerrar, reintentar, aviso de publicidad y permisos multimedia del iframe. No abre otra página para reproducir.
- Controles más compactos, fichas adaptadas a móvil/tableta y carrusel horizontal de «Más como esto» usando las mismas tarjetas del inicio.
- Episodios con miniatura, selección y descarga individual cuando el administrador haya asignado un enlace. Las películas conservan su botón de descarga; las series ya no muestran una descarga general que pueda confundirse con todos sus capítulos.
- Editor de enlaces por episodio reservado al administrador, con validación HTTPS. El listado público solamente indica si existe una descarga; la URL se obtiene mediante un endpoint que exige acceso activo.
- Mi lista accesible desde Mi cuenta, con contador y tarjetas guardadas. Historial de títulos abiertos y último episodio seleccionado por cuenta en ese navegador.
- Botón manual «Siguiente episodio» para las series cuyo listado local esté cargado, incluyendo cambio de página y temporada. En el selector interno de Vimeus se utilizan sus propios controles.
- Las películas que originalmente dependían de Telegram y se prueban mediante Vimeus indican que su disponibilidad no está confirmada. No se presentan como vídeos garantizados.

## Pruebas

| Comprobación | Resultado |
| --- | --- |
| Python | 156 pruebas correctas; 20 advertencias existentes de dependencias |
| Node | 45 pruebas correctas |
| Diseño | 320, 390, 768 y 1280 px, sin desbordamiento horizontal de la ficha |
| «Corazón de oro» | El iframe dentro de la ficha abrió portada, controles y selector de 75 episodios |
| Guardados | Guardar el título → Mi cuenta → Mi lista → título visible |
| Descarga por episodio | Administrador asignó un enlace ficticio de MediaFire; miembro activo abrió el enlace desde el episodio |
| Protección | Cuenta sin membresía recibió 403; pruebas cubren CSRF, permisos, cruce de títulos y URLs no válidas |
| Reimportación | Prueba SQL con PGlite confirmó que conserva el enlace de descarga del episodio |
| Túnel | `/health` respondió 200 con `mode: local` |

Evidencias: `.local/phase7-python.xml`, `.local/phase7-python.txt`, `.local/phase7-node.txt`, `.local/phase7-inline-player-mobile.png`, `.local/phase7-related-mobile.png` y `.local/phase7-episodes-mobile.png`.

La prueba de descarga utilizó datos sintéticos en `127.0.0.1:5010`; no descargó un archivo real ni alteró enlaces de producción. La prueba del proveedor utilizó el túnel hacia `127.0.0.1:5011`. La presencia de portada/controles no confirma reproducción completa ni funcionamiento en un teléfono físico dentro de Telegram.

## Límites y pendientes

1. Cerrar y volver a abrir la Mini App en Telegram, probar «Corazón de oro», seleccionar un capítulo y pulsar Play. Falta validar vídeo, audio y fullscreen en el teléfono real.
2. El listado propio completo necesita la API de Listing de Vimeus; la clave de reproducción no sustituye ese permiso. La solución actual permite usar el selector del proveedor sin inventar capítulos en nuestra base.
3. La documentación consultada no ofrece un contrato de eventos de tiempo, fin o reanudación. Se registra el título/episodio abierto, no minutos vistos; no se promete continuar en el segundo exacto ni avanzar automáticamente al finalizar.
4. Los guardados y ese historial permanecen en el navegador/origen; todavía no se sincronizan entre dispositivos.
5. Los enlaces de canales de Telegram no son URLs de vídeo compatibles con un reproductor web. Esos títulos necesitan una fuente web compatible; no se ha añadido un proxy ni extracción de archivos de Telegram.
6. La migración `migrations/004_episode_downloads.sql` añade el campo nullable de descarga por episodio. Está preparada y probada, pero **no aplicada en Supabase**. Antes de producción deben revisarse también las migraciones y pendientes de fases anteriores.
7. Los controles internos y la publicidad del iframe siguen siendo del proveedor. No se ha eludido ni eliminado publicidad.

## Revisar la vista actual

https://clairvoyantly-adactylous-leonida.ngrok-free.dev/

El enlace funciona mientras esta computadora, el servidor local y ngrok permanezcan encendidos. No se habilitaron cobros reales durante estas pruebas.
