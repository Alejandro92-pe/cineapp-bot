# Temporadas propias y ficha a pantalla completa

26 de octubre de 2026. Solo local. No se desplegó, no se modificó Render ni Supabase, y no se cambió el bot.

## Resultado de la importación real

Se leyó la clave de listado existente desde la cuenta abierta de Vimeus, sin regenerarla ni guardar cambios allí. Permanece en `.local/telegram-preview.json`, excluido de Git y fuera del servidor estático. Las consultas externas fueron lecturas a Vimeus y TMDB; los resultados se guardaron en archivos locales. El servidor de prueba sigue con sus conexiones salientes bloqueadas.

La API real devuelve `data.result` y `data.pages`, con páginas de tamaño variable, `parent_type`, `show_title`, numeración como texto y sin ID interno de episodio. Es diferente de la documentación, que muestra `data.episodes` y `data.pagination`. El adaptador ahora acepta ambos formatos, verifica el título/tipo, rechaza duplicados y no inventa identificadores. Mantiene límites de tiempo y cantidad y valida todo antes de persistir.

| Importación local | Resultado |
| --- | ---: |
| Series | 67 |
| Animes | 6 |
| Temporadas | 182 |
| Episodios | 3.083 |
| Enlaces de descarga por episodio | 3.083 |
| Tráileres encontrados | 28: 12 de series/animes y 16 de películas |

Se normalizaron espacios accidentales en el tipo/fuente de la copia local. Los seis animes asociados son Sword Art Online, Death Note, Akame ga Kill!, Dragon Ball Daima, Dragon Ball Super y Dragon Ball. Las asociaciones se basaron en el catálogo real, sin trasladar por semejanza las ediciones especiales.

Los ocho animes anteriores sin asociación segura se conservan pendientes: Naruto Shippuden sin relleno, Naruto sin relleno, Alicization - War of Underworld, Alicization, Sword Art Online II, Dragon Ball Héroes, Dragon Ball GT y Dragon Ball Z. Las series antiguas que solo tenían fuente de canal tampoco se anuncian como importadas desde Vimeus.

## Descargas y persistencia

- Cada episodio ofrece la descarga que devuelve el proveedor. Se valida dominio, ruta, título, temporada y capítulo antes de guardarla.
- Un enlace manual de MediaFire u otro alojamiento tiene prioridad. Vaciar ese campo vuelve a usar la descarga del catálogo cuando existe.
- La reimportación conserva los enlaces manuales. Los cambios manuales en el túnel quedan en `.local/episode-downloads.json` y sobreviven al reinicio, mediante claves de título/temporada/episodio y no IDs locales temporales.
- El endpoint exige sesión y membresía activa. El listado público solo publica `has_download`; no entrega la URL privada.
- Los 253 enlaces de descarga de las fichas originales se conservan. No se descargaron archivos de vídeo completos ni se verificaron individualmente los 3.083 destinos externos.

## Diseño y reproducción

- La ficha ocupa toda la ventana con fondo opaco; su contenido se centra en un ancho legible. Ya no muestra las tarjetas del inicio alrededor.
- Imágenes horizontales de TMDB para el fondo, Play circular, descarga y tráiler en una fila cuando están disponibles. Me gusta, Guardar y Compartir quedan centrados entre dos líneas.
- Al reproducir se oculta la fila principal, evitando repetir Play debajo del vídeo. Se retiraron «Probar en Vimeus» y las instrucciones permanentes. Reintentar aparece únicamente ante un error de autorización/carga de nuestra integración.
- El Play interno, la publicidad y el arranque del iframe siguen dependiendo de Vimeus. No se afirma reproducción automática con un solo toque ni control completo sobre ese iframe.
- Los capítulos se seleccionan en nuestra página. El botón manual Siguiente avanza por el listado propio; no se promete detectar automáticamente el final del vídeo.
- Los títulos se consultan con `language=es-MX`. Los tráileres priorizan oficiales de México, luego Latinoamérica y finalmente España, según la respuesta del usuario. Si no existe uno compatible, el botón no se muestra; se conservan enlaces editoriales existentes cuando una importación no encuentra sustituto.
- Se corrigió el bloqueo de los tráileres por CSP: solo se añadió `https://www.youtube-nocookie.com` a los orígenes de iframe permitidos. El parser rechaza URLs ajenas, esquemas inseguros y IDs inválidos.

## Pruebas realizadas

- **164 pruebas Python + 48 Node = 212 aprobadas.** Python conserva 20 advertencias de dependencias. Se ejecutó la migración y la función reales con PGlite local, sin conexión a Supabase.
- La ficha se midió a **320, 390, 768, 1600 y 2560 px**: borde izquierdo 0 y ancho de contenido igual al ancho desplazable, sin desbordamiento horizontal.
- Corazón de oro: se cargaron 50 episodios y después los 25 restantes mediante Ver más capítulos; 75 botones de descarga, sin duplicados. La descarga de episodio 2 devolvió `se=1&ep=2`.
- La Reina del Flow: temporadas de 82, 89 y 65 capítulos. Seleccionar temporada 3 y Play abrió `se=3&ep=1`; Siguiente abrió `se=3&ep=2`.
- Death Note: 37 episodios y 37 botones de descarga dentro de nuestra ficha.
- Piratas del Caribe 5: el tráiler oficial importado abrió YouTube, y al pulsar Play se observó reproducción de imágenes y subtítulos. Se cerró al terminar la comprobación.
- HTTPS del túnel: `/health` 200, modo local. Archivos privados `.local` 404. Descarga por episodio sin sesión 401.
- Pruebas cubren formato real, paginación variable, duplicados, URLs del episodio correcto, prioridad manual, persistencia local, membresía, permisos, CSRF, preservación al reimportar y selección regional de tráileres.

Evidencias: `.local/phase8-python.xml`, `.local/phase8-python.txt`, `.local/phase8-node.txt`, `.local/phase8-import-results.json`, `.local/phase8-detail-desktop.png`, `.local/phase8-detail-mobile.png`, `.local/phase8-anime-mobile.png`.

## Estructura y operación local

- `providers/vimeus.py` y `providers/tmdb.py`: contratos de proveedor y metadatos.
- `services/vimeus_import.py`, `services/preview_downloads.py`: importación y persistencia local.
- `routes/episode_downloads.py`: acceso protegido y edición de descargas.
- `static/catalog/`: ficha, episodios, reproductor y tráileres separados.
- `scripts/sync_preview_catalog.py`: lectura del listado y guardado de manifiestos; reutiliza la caché salvo `--refresh`.
- `scripts/sync_preview_metadata.py`: refresca imágenes horizontales y tráileres de la selección local.

Los scripts no importan `main`, no cargan `.env` ni acceden a bases de producción. Después de sincronizar se reinicia `scripts/run_local.py --public-origin <origen-ngrok>` para cargar los archivos. El panel del túnel continúa con las limitaciones de prueba anteriores; la sincronización real de esta fase se realizó mediante estos scripts locales.

## Pendiente antes de producción

La migración `005_vimeus_live_format.sql` permite ID de proveedor ausente y agrega descarga del proveedor, tráiler y fondo horizontal. **No se aplicó en Supabase.** Antes de cualquier despliegue hay que revisar las migraciones pendientes, configurar la clave de listado en el entorno de producción y validar estos flujos allí con autorización.

Falta la prueba física en Telegram Desktop/Android de vídeo, sonido y pantalla completa. La vista ancha no equivale a una aplicación para televisor. Una versión Android/Google TV necesita navegación con mando y validación del reproductor; Cast requiere integración adicional. No se añadió un botón de transmisión sin funcionamiento comprobado.

Fuentes revisadas: [Vimeus](https://www.vimeus.com/docs/getting-started), [idiomas TMDB](https://developer.themoviedb.org/docs/languages), [región TMDB](https://developer.themoviedb.org/docs/region-support), [Android TV](https://developer.android.com/training/tv/get-started/create), [Google Cast](https://developers.google.com/cast/docs/web_sender).

Vista actual: https://clairvoyantly-adactylous-leonida.ngrok-free.dev/
