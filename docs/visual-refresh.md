# Imágenes y selección de la landing

Preparado y probado en local. No se publican créditos ni cambios en las condiciones de TMDB en esta fase.

## Aplicación

- `static/catalog/artwork.js` sirve fondos horizontales responsivos de 780/1280 px al hero y a todas las fichas, incluidas series y animes. Las tarjetas usan póster vertical de 185/342/500 px.
- Si falta el fondo, el póster se contiene sin estirarlo. La ficha no tiene desenfoque artificial.
- La rotación del hero existente conserva sus tres días y su selección compartida.
- El importador de Vimeus ahora conserva también el `backdrop_path` recibido de TMDB.

## Landing y mantenimiento

- `/api/public/landing` devuelve solo tres fichas públicas: ID, título, año, puntuación, póster y fondo. Sin cuentas, códigos, cookies ni descargas.
- Permite lectura CORS exclusivamente desde quehay.live/www.quehay.live (y las vistas loopback autorizadas en modo local). El resto de la API conserva su política original.
- La selección se guarda en PostgreSQL/Supabase mediante la tabla `catalog_cache` existente, no en el disco efímero de Render. Sigue disponible si TMDB falla o Render reinicia.
- Se renueva cada tres días, eligiendo tres entre las doce mejor valoradas que coincidan con el catálogo disponible, dentro de las primeras tres páginas populares del año actual con al menos 100 votos. No es una afirmación de ranking global.
- Se verifican año, ausencia de contenido adulto, imagen válida y disponibilidad local. Si no hay tres coincidencias, se conserva la selección anterior. No se crean títulos ni identificadores de reproducción.
- `landing/assets/selection.js` actualiza las tres carátulas de arriba, las tres del televisor, el celular y el fondo. Mantiene las imágenes WebP incluidas si el servicio no responde. Si la selección no cambió, evita descargar otra vez las mismas imágenes desde TMDB.
- `landing/build.py` publica los recursos referenciados con una huella de su contenido en el nombre. Cambiar el fondo genera una URL nueva, evitando reutilizar la imagen anterior de la caché anual de SiteGround o del navegador. Se conservan los archivos originales para las páginas antiguas.
- `/cron/actualizar_imagenes` usa el mismo mecanismo Bearer del cron existente. Se configura como **trabajo independiente cada 15 minutos**, con `ARTWORK_REFRESH_ENABLED=true`. Hasta entonces está desactivado. No modifica los horarios ni los turnos 4:1 de importación.
- Un trabajo consulta como máximo un título pendiente y una página de selección. Tiempo de conexión/lectura TMDB: 2/4 s. Evita solaparse con importaciones mediante el bloqueo compartido; limita reentradas a una cada diez minutos.
- Los fondos se actualizan condicionalmente por ID, identificador TMDB y valor previo. No se reemplaza un fondo manual distinto. Los títulos antiguos sin ID solo se identifican con coincidencia única de título y año; una coincidencia ambigua queda pendiente.

## Antes de publicar

1. Revisar las vistas locales 5014 y 5015 y los resultados en `.local/visual-refresh/`.
2. Autorizar la publicación. Aplicar los fondos revisados con comparación contra los valores anteriores y publicar el código en Render. No cambiar tablas de cuentas ni descargas.
3. Guardar una selección inicial válida en `catalog_cache`, activar `ARTWORK_REFRESH_ENABLED` y crear el cron independiente autenticado.
4. Construir la landing sobre una copia del paquete existente: conservar las 719 páginas antiguas, ambos sitemaps, el archivo de verificación y `.well-known`. `landing/build.py` ya no sobrescribe un sitemap existente. Publicar únicamente archivos públicos del paquete, incluida la política CSP para las imágenes y el feed.
5. Verificar la primera ejecución del nuevo cron, la lectura de la landing, las fichas, las sesiones y descargas.

Las vistas locales tienen red del backend bloqueada y cuentas SQLite independientes. Los scripts de preparación leen el catálogo público y TMDB, y producen archivos locales; no usan un cliente Supabase ni escriben en producción.
