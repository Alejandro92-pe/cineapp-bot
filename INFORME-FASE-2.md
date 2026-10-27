# Fase 2 — Series y animes de Vimeus

26 de octubre de 2026. Implementación y validación exclusivamente locales.

## Resultado

Se reemplazó la importación de temporadas sin capítulos por una lectura paginada de episodios de Vimeus. Se conservan todas las temporadas devueltas, incluidos especiales (temporada 0), y se guarda la identidad de cada capítulo. El reproductor recibe el TMDB, la temporada y el episodio seleccionados después de verificar la sesión y la vigencia del acceso.

La importación incluye **todos los capítulos disponibles en Vimeus** para el título. TMDB solo enriquece nombres, sinopsis e imágenes; no se inventan capítulos reproducibles que el proveedor no tenga.

El panel permite explorar títulos por páginas o introducir un ID de TMDB, importar y actualizar. La ficha presenta selector de temporada, capítulos seleccionables, carga de más capítulos y botón de reproducción visible al desplazarse. Se emplea azul noche, azul claro y acentos dorados. Esta fase mejora el importador y la ficha; el rediseño integral del inicio y de los planes pertenece a otra fase.

## Preservación y seguridad

- Se leen y validan todas las páginas antes de guardar. Un fallo conocido de red, paginación, identidad, tipo o duplicación cancela sin aplicar el listado parcial.
- La función PostgreSQL guarda el título, las temporadas y los capítulos dentro de una sola transacción. Un error revierte la operación completa.
- Las reimportaciones mantienen los IDs, la descarga del contenido, los enlaces de temporadas y la información editorial existente. No se reemplazan por campos vacíos del proveedor.
- Los capítulos retirados por un listado completo se marcan no disponibles, sin borrarlos. Si vuelven, recuperan su misma identidad.
- La clave privada `VIMEUS_API_KEY` solo viaja en `X-API-Key` al servidor de Vimeus. Es distinta de `VIMEUS_VIEW_KEY`, que utiliza el iframe.
- Importar requiere sesión de administrador y CSRF. El administrador continúa siendo únicamente `5824989040`.
- Los metadatos de capítulos son públicos; la URL de reproducción exige acceso vigente. No se puede reproducir un capítulo de otro título cambiando su ID.
- Las descargas manuales y la apertura con `Telegram.WebApp.openLink` se conservan. Los ensayos de MediaFire son de flujo y enlaces sintéticos, no una descarga real en un teléfono.

## Organización

| Carpeta / archivo | Responsabilidad |
| --- | --- |
| `providers/vimeus.py` | API privada, páginas, límites, validación y fallos controlados |
| `services/vimeus_import.py` | Manifest completo, enriquecimiento TMDB y contrato de persistencia |
| `services/local_vimeus.py` | Proveedor ficticio y transacción en memoria, solo modo local |
| `routes/vimeus.py` | Importador admin, exploración y metadatos de capítulos |
| `static/catalog/episodes.js` y `.css` | Selección de temporadas/episodios y diseño responsive |
| `static/admin/vimeus.js` y `.css` | Formulario de importación, exploración y resultados |
| `migrations/002_vimeus_episodes.sql` | Tabla de capítulos, índices y función transaccional con permisos restringidos |
| `tests/test_vimeus.py` | Contrato de API, importación, permisos y reproducción |
| `tests/episodes.test.cjs` | Paginación visual, cambios rápidos de temporada y recuperación de errores |
| `tests/vimeus-sql.test.mjs` | Ejecución del SQL real en PostgreSQL local mediante PGlite |

Se mantuvieron las rutas anteriores de importación para compatibilidad. Importar series/animes desde ellas utiliza ahora el mismo servicio completo. Se retiró el helper antiguo que solo guardaba un contador de episodios.

## Pruebas ejecutadas: 113 aprobadas

| Grupo | Resultado | Evidencia principal |
| --- | --- | --- |
| Python / Flask | 97 aprobadas | Seguridad anterior y 41 casos nuevos de importación y acceso |
| JavaScript | 10 aprobadas | Descargas, escape de contenido, selección, paginación y respuestas fuera de orden |
| SQL real en PGlite | 6 aprobadas | Transacciones, rollback, reimportación, identidad, retirados y permisos |

Casos destacados:

1. Anime ficticio `900202`: dos temporadas, 60 + 12 = 72 capítulos, dos páginas del proveedor. La ficha carga los primeros 50 y los 10 restantes de la primera temporada.
2. Serie ficticia `900101`: especiales y dos temporadas, 1 + 8 + 6 = 15 capítulos. Los especiales generan `se=0&ep=1`.
3. Reimportación desde el panel real: 0 capítulos nuevos, 72 actualizados, 0 retirados. Descargas conservadas.
4. Selección T2 E12: el backend construye `/e/anime` con `se=2&ep=12`. Rechaza otro título, un capítulo retirado y una cuenta vencida.
5. Error a mitad de la transacción SQL: no queda un título ni un conjunto de capítulos parcial.
6. Fallos del proveedor, páginas truncadas, IDs ajenos y duplicados: no se modifica el catálogo anterior.
7. API de capítulos paginada: no depende del límite por defecto de 1.000 filas de Supabase.

Revisión manual en navegador: ficha en 320 px sin desbordamiento horizontal; panel en 390 px con campos apilados; panel de escritorio medido a 1280 px. Se comprobó cambiar temporadas, seleccionar el último capítulo, cargar la segunda página y consultar especiales. No equivale a una prueba física en Android o Telegram.

Capturas locales: `.local/fase2-movil.png`, `.local/fase2-importador.png`, `.local/fase2-importador-movil.png`.

Comandos reproducibles desde la raíz:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=.local/phase2-python.xml
npm install --prefix .local/sql-runtime --save-exact @electric-sql/pglite@0.5.12
node --test tests/frontend.test.cjs tests/episodes.test.cjs tests/vimeus-sql.test.mjs
node --check static/app.js
node --check static/catalog/episodes.js
node --check static/admin/vimeus.js
git diff --check
```

Resultados guardados en `.local/phase2-python.txt`, `.local/phase2-python.xml` y `.local/phase2-javascript.txt`. Python conserva 20 avisos de deprecación de dependencias ya presentes; no hubo fallos. El entorno probado usa Python 3.12 y Node 20. No se afirma haber probado el runtime Python 3.11 de Render.

## Vista local

```powershell
.\.venv\Scripts\python.exe scripts/run_local.py
```

- Catálogo: `http://127.0.0.1:5010/`
- Serie de prueba: `http://127.0.0.1:5010/?contenido=2`
- Anime de prueba: `http://127.0.0.1:5010/?contenido=3`
- Importador: `http://127.0.0.1:5010/admin`
- Credencial admin de prueba: `.local/access.txt`. No es la de producción.

El arranque utiliza datos sintéticos y bloquea la red saliente del backend. Los datos del catálogo de prueba se reinician al reiniciar el servidor. No hay vídeos externos ni compras reales en esta vista.

## Pendiente antes de cualquier despliegue

No se modificaron Render, Supabase, Buy Me a Coffee ni el bot real. No se ejecutó la migración en producción ni se hizo push.

La integración sigue el [contrato de listado de Vimeus](https://www.vimeus.com/docs/getting-started#list-endpoints) y los [detalles de temporadas de TMDB](https://developer.themoviedb.org/reference/tv-season-details). Se revisó la documentación, pero **no se consultó un catálogo real autenticado de Vimeus**. Falta validar con una clave privada de listado y un título real antes de afirmar compatibilidad completa de la cuenta del proveedor.

La migración queda para revisión. Si existen duplicados en `(tipo, tmdb_id)` o `(contenido_id, numero)`, se detendrá para reconciliarlos sin borrar enlaces. La prueba SQL usó las columnas necesarias de un esquema local equivalente; no certifica todas las políticas, restricciones ni disparadores del Supabase real.

Se limitan las lecturas a 100 páginas / 5.000 capítulos y aproximadamente 90 segundos de listado más la solicitud en curso. TMDB tiene un presupuesto adicional de 20 segundos más la solicitud en curso; si se agota, se importan los capítulos sin todas sus descripciones. Los listados mayores se rechazan sin importar parcialmente. Vimeus no documenta un cursor de instantánea: se detectan cambios en totales y duplicados entre páginas, pero no se puede garantizar que un catálogo que cambia simultáneamente mantenga una instantánea perfecta.

El importador actual es síncrono por título. Antes de desplegar, hay que comprobar el tiempo de respuesta real y los límites del servidor Gunicorn de Render; un título lento podría superar el tiempo de espera del worker. Para importaciones masivas sostenidas conviene una cola persistente. Esta fase no cambia infraestructura ni configura tareas automáticas.

No se avanzó a planes, precios, cambios del bot ni empaquetado Android.
