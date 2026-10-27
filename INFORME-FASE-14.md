# Fase 14 — Importador unificado y experiencia de cuenta

26 de octubre de 2026. Cambios y pruebas en la copia local expuesta por ngrok. No se modificaron Render, Supabase de producción, bot ni pagos reales.

## Importación automática: estado real y requisito para producción

El trabajador por lotes NO está ejecutándose de forma desatendida. Estado comprobado de `.local/import-queue.sqlite`: 3 trabajos completados, 97 pendientes. El cron de vencimientos no importa contenido.

El usuario pidió activar la importación automática al pasar a producción. Queda como requisito del despliegue; no se activó ahora. Antes de hacerlo hay trabajo pendiente:

1. Llevar la cola, cursores, reintentos y espera entre peticiones a almacenamiento persistente en Supabase; no usar SQLite en el disco efímero de Render.
2. Implementar y validar la publicación transaccional de películas, series y anime desde esa cola. La RPC actual de Vimeus cubre series/anime; el importador manual de películas no constituye una cola de publicación automática.
3. Ejecutar lotes breves con bloqueo/arrendamiento de trabajador, deduplicación, protección de descargas y reanudación. Mantener los límites ensayados: pocos títulos por lote y pausas compartidas entre proveedores.
4. Conectar una ejecución programada autenticada, independiente del navegador del administrador, después de validar las migraciones en PostgreSQL y comprobar el primer lote. No cambiar silenciosamente el cron de vencimientos.
5. Mostrar al administrador estado, último resultado y errores; dejar una forma de detener las importaciones. Los fallos de un proveedor deben conservar lo existente.

La activación solicitada es para la fase de producción, no una promesa de que el proceso local continuará al cerrar el equipo. La sincronización de capítulos nuevos de títulos ya importados sigue siendo un flujo distinto del descubrimiento inicial.

## Un solo importador en el panel

Se retiraron los formularios y funciones de importación antiguos del panel. Se conserva la compatibilidad de los endpoints anteriores, pero la interfaz usa `/api/admin/catalog/import` y ofrece Película, Serie, Anime (serie), Bíblico · Película y Bíblico · Serie.

- Películas: ficha y tráiler de TMDB; el vídeo depende de su disponibilidad en Vimeus. Las películas de anime se importan como película.
- Series y anime: capítulos disponibles en Vimeus, complementados con metadatos de TMDB.
- Bíblicos: metadatos, temporadas y capítulos de TMDB; después se asignan vídeos mediante Reproductores · OK.ru. La importación no inventa URLs ni borra episodios manuales.
- Para bíblicos sin ID previo, el selector permite elegir la ficha existente y asociar el TMDB sin duplicarla. No se reemplaza una ficha asociada a otro TMDB.
- En la vista local, un proceso lector separado consulta exclusivamente las API previstas y prepara un manifiesto completo antes de cambiar el catálogo. El servidor principal conserva el bloqueo de red y el almacenamiento aislado. Hay pausas, bloqueo de trabajador, tiempo máximo, mensajes sin secretos y caché de 24 horas. Importar por el panel no inicia la cola automática.
- Los resultados manuales se guardan en `.local/metadata-preview-edits.json` y `.local/manual-vimeus-preview.json`. Se restauran al arrancar antes de las ediciones OK.ru y las descargas manuales. El archivo privado de claves nunca se publica.

Para producción se preparó `migrations/009_tmdb_metadata.sql`, sin ejecutarla. La migración y su comportamiento en PostgreSQL siguen pendientes de validación real. No se presenta la prueba con el adaptador local como prueba de Supabase.

## Ejemplos reales comprobados

**Josué y la tierra prometida, TMDB 66825:** TMDB devolvió 1 temporada y 179 capítulos. Se importaron desde el panel en la ficha existente 208, cuyo TMDB estaba vacío. Se comprobó el catálogo después de reiniciar: una ficha, 179 números únicos, sin duplicados. Los capítulos sin URL aparecen como Vídeo pendiente y no abren un reproductor vacío. La fuente TMDB no suministra archivos de vídeo.

**Piratas del Caribe: La Maldición del Perla Negra, TMDB 22:** importada/actualizada desde la opción Película. Conservó la ficha 693 y la descarga original. Se ejercitó el lector real aislado desde el panel.

## UX

- Eliminados los banners de prueba local/catálogo copiado de inicio, cuenta, membresía, instalación y administrador. El aislamiento técnico permanece. Solo la ventana de pago de demostración aclara que no cobra y que no se debe transferir dinero.
- Carrusel sin estadísticas: Diez historias para tu próxima sesión de cine. Con ranking real: Lo más visto por nuestra comunidad. No se presentan selecciones iniciales como reproducciones reales.
- Carita del acceso centrada, sin márgenes/baselines heredados que la desplazaban.
- Cuenta con cabecera de avatar y nombre, indicador de acceso, vencimiento, aviso de solicitudes pendientes, contador de compras y seguridad/conexiones agrupadas. Los botones de renovación y navegación tienen espacio y superficie clicable propios.
- Avatares y Mi lista continúan siendo por cuenta y navegador. Sincronizarlos en Supabase entre dispositivos y añadir recuperación segura de contraseña son mejoras posteriores recomendadas, no funciones completadas en esta fase.

Como referencia de organización se consultó https://help.netflix.com/en/node/100627 . El API de temporadas de TMDB está documentado en https://developer.themoviedb.org/reference/tv-season-details .

## Evidencia

- 215 pruebas Python y 63 JavaScript aprobadas: **278**. 20 avisos de obsolescencia de dependencias Python, sin fallos. Registros `.local/phase14-pytest.txt` y `.local/phase14-node.txt`.
- Pruebas nuevas: preservación de descargas/OK.ru/visibilidad/episodios manuales, importación incompleta sin cambios, conflicto de destino/tipo, reversión ante error de disco, autenticación y CSRF, metadatos públicos sin URLs, importación de películas, caché y lector acotado, persistencia Vimeus y claves antiguas de descargas.
- Comparación por ID y valor: **253 enlaces manuales originales idénticos**, conservando también el de la película ensayada. `.local/phase14-integrity.json`.
- Cuenta comprobada en escritorio y viewport móvil de 390 px: ancho útil/documento 375/375, sin desbordamiento. Compras desplegables y selector de avatares revisados.
- Capturas: `.local/phase14-account-entry.png`, `.local/phase14-account-desktop.png`, `.local/phase14-account-mobile.png`, `.local/phase14-import-biblico.png`, `.local/phase14-import-movie.png`.
