# Fase 11 — Importación por lotes y carruseles

Trabajo local del 26 de octubre de 2026. Sin despliegue, cambios en Supabase, Render, configuración del bot o pagos. La URL de ngrok sigue apuntando al servidor local.

## Resultado probado

Se consultó una página real de series de Vimeus: 100 títulos encolados. Se procesaron únicamente tres:

| Título | TMDB | Temporadas de Vimeus | Capítulos de Vimeus |
|---|---:|---:|---:|
| Helluva Boss | 289892 | 3 | 23 |
| Cyberpunk: Edgerunners | 105248 | 2 | 20 |
| La lista terminal | 120911 | 2 | 16 |

Total: 3 títulos, 7 temporadas, 59 capítulos. 17 peticiones externas y 13,39 segundos acumulados de espera deliberada. No hubo advertencias del importador. Estas cifras reflejan el listado devuelto por Vimeus; no certifican que cada vídeo reproduzca o coincida con toda la emisión oficial de la serie. Los otros 97 trabajos están pendientes, no publicados. El proceso terminó: no quedó una importación masiva ejecutándose.

Los tres títulos ya aparecen en el catálogo local. En el navegador se verificó Helluva Boss, el cambio de temporada 1 a 3, sus tres capítulos y los botones individuales de descarga.

La disponibilidad y numeración vienen de Vimeus. TMDB aporta títulos, imágenes, descripciones y tráileres en español de México, permitiendo el tráiler de España cuando no hay latino. Si falta una descripción de TMDB, se conserva el capítulo del proveedor con su número; TMDB no suministra archivos de vídeo.

## Funcionamiento

- `services/catalog_queue.py`: cola SQLite privada, cursor de cada listado, estados y manifiestos completos.
- `scripts/import_catalog_batches.py`: trabajador independiente de Flask; no importa la aplicación ni conecta con Supabase.
- Una página de descubrimiento por lote, alternando películas, series y anime. Cada lote procesa como máximo el límite configurado.
- Por defecto: 3 títulos, 1,2 segundos mínimos entre inicios de peticiones, 180 segundos de presupuesto antes de nuevas peticiones y 30 segundos de descanso entre lotes. Una petición ya iniciada conserva su timeout de red.
- El intervalo se comparte entre Vimeus y TMDB. Los límites 429/errores transitorios conservan una espera global en disco; se respeta `Retry-After` y se vuelve a intentar en una ejecución posterior. Una espera que excede el presupuesto detiene el lote.
- Caché de metadatos TMDB durante 24 horas. Los errores normales de un título tienen reintentos espaciados; tras tres intentos quedan en estado `failed` para revisión.
- Bloqueo de un solo trabajador. Tras cerrar o interrumpir el proceso, la próxima ejecución recupera los trabajos en curso. La publicación del manifiesto y su estado se hacen en una transacción.
- Solo los manifiestos `done` se aplican al iniciar la vista previa. En esta fase hay que reiniciar el servidor local después de un nuevo lote para ver nuevos resultados. No se añadieron rutas públicas para lanzar importaciones.
- `--rescan` reinicia los cursores para buscar nuevos IDs sin duplicar los ya terminados. No actualiza automáticamente las temporadas de títulos ya completados; esa sincronización es un flujo distinto.
- Los archivos, caché y claves permanecen en `.local/`, excluido de Git. No se registran claves en consola.

### Comandos

Desde la carpeta del proyecto, consultar el estado sin peticiones externas:

```powershell
.venv\Scripts\python.exe scripts/import_catalog_batches.py --status
```

Un lote pequeño de la cola existente:

```powershell
.venv\Scripts\python.exe scripts/import_catalog_batches.py --no-discover --limit 3
```

Ejemplo preparado para tres lotes consecutivos, con descanso. **No se ejecutó este ejemplo contra el catálogo real**:

```powershell
.venv\Scripts\python.exe scripts/import_catalog_batches.py --batches 3 --limit 3 --pause 1.2 --batch-pause 30
```

Se puede detener con Ctrl+C; el siguiente arranque recupera el trabajo. No se configuró un cron ni un proceso permanente. Antes de llevarlo a Render hace falta decidir almacenamiento persistente para la cola y publicación transaccional en Supabase; esta SQLite local no debe depender del disco efímero de Render.

## Conservación de descargas

Se aplicaron los manifiestos a una copia aislada del catálogo y se repitió la aplicación: las **253 descargas manuales originales** conservaron exactamente sus valores y no crecieron los conteos de fichas, temporadas o capítulos en la segunda aplicación. Una prueba adicional verifica un enlace manual de MediaFire por episodio frente a una reimportación. El arranque restaura además las ediciones manuales persistidas por número de temporada y capítulo.

Importar un enlace no significa que el servidor de descargas entregue el archivo. Sigue pendiente el problema externo de descargas de Vimeus documentado en la fase 10; esta fase no lo da por resuelto ni sustituye enlaces manuales.

Evidencia: `.local/phase11-integrity.json`.

## Carruseles del home

Las filas tienen flechas en escritorio y ninguna barra horizontal visible. Una flecha de «Recién llegados» se accionó y se verificó el desplazamiento real. El carrusel continúa siendo desplazable y accesible por teclado.

En pantallas pequeñas o dispositivos con puntero táctil se ocultan las flechas, incluidas las del destacado principal. Se conserva el desplazamiento táctil y los indicadores del destacado. Se respetan las preferencias de movimiento reducido.

Vistas verificadas: 1440, 390 y 320 píxeles, sin desbordamiento horizontal de la página. Evidencia:

- `.local/phase11-desktop.png`
- `.local/phase11-mobile.png`
- `.local/phase11-imported-season.png`

## Pruebas automatizadas

**180 pruebas Python + 54 JavaScript = 234 aprobadas.** Python mantiene 20 avisos de obsolescencia de dependencias; no hay fallos.

Las nueve pruebas nuevas cubren publicación completa, límite por lote, reanudación tras interrupción, idempotencia, página inválida sin avance del cursor, pausas compartidas, 429 persistente, presupuesto, caché persistente y caducidad, reintentos, bloqueo concurrente, conservación de descargas y dos lotes consecutivos con descanso. Las pruebas automatizadas bloquean conexiones externas; el lote real descrito arriba se ejecutó por separado.

```powershell
.venv\Scripts\python.exe -m pytest -q
$tests = @(Get-ChildItem tests -File | Where-Object { $_.Name -match '\.test\.(cjs|mjs)$' } | ForEach-Object { $_.FullName })
node --test @tests
```

Registros: `.local/phase11-pytest.txt`, `.local/phase11-node.txt`.

## Bíblicos: Telegram y OK.ru

El ejemplo facilitado es [Final | Pablo El Apóstol | Audio Latino](https://ok.ru/video/10328454335072), de ESTUDIOS 421, con aproximadamente 7 minutos y 33 segundos. Se observó reproducción en su página y el propio reproductor ofreció este destino de inserción: `https://ok.ru/videoembed/10328454335072?nochat=1`. La página del reproductor insertable también cargó.

[OK.ru documenta el reproductor insertable](https://new.apiok.ru/en/ext/video). Es una opción para mantener la reproducción dentro de nuestra ficha, siempre que el vídeo permanezca disponible y permita inserción. Este ejemplo no demuestra que estén disponibles todos los capítulos de Estudios 421. No se ha integrado todavía OK.ru en las rutas de reproducción ni se ha probado este embed dentro de Telegram Android/iPhone.

[Telegram permite insertar publicaciones de canales/grupos públicos](https://core.telegram.org/widgets/post), pero esa opción conserva la dependencia de Telegram. No independiza los archivos que actualmente están en los canales.

Para independizar los bíblicos tanto de Telegram como de OK.ru, se necesitan archivos que puedas alojar y un servicio de almacenamiento/distribución de vídeo. La aplicación podría usar un reproductor propio con una URL de vídeo por episodio, conservando las mismas fichas, temporadas y descargas. Una carga por lotes con una tabla de correspondencias título/temporada/episodio evita registrarlos uno por uno. No se descargaron, copiaron ni migraron vídeos en esta fase.

Como siguiente fase concreta, se puede añadir una fuente alternativa por episodio: Vimeus para lo disponible allí, OK.ru para enlaces insertables verificados y alojamiento propio cuando se disponga de los archivos. La decisión sobre alojamiento, coste y migración queda pendiente; no es un requisito para revisar los cambios locales entregados.
