# Reproducción en Telegram, Top 10 e importación por lotes

26 de octubre de 2026. Todo se trabajó en local. No se cambió Render, Supabase, el bot ni sus webhooks. No se activó ninguna importación masiva ni tarea programada.

## Prueba real en Telegram Desktop

Se utilizó la miniapp abierta del bot Popcorn Crítico, apuntando al túnel local. La sesión antigua mostraba «No se pudo verificar Telegram. Abre de nuevo la Mini App». Se cerró y reabrió desde «Abrir App», sin enviar mensajes ni modificar el bot. La nueva sesión se verificó con la cuenta del propietario.

En Naruto Shippuden, temporada 1, episodio 1:

1. La ficha cargó temporadas y capítulos propios.
2. El reproductor abrió dentro de la ficha.
3. Se activaron los controles Play del proveedor y se mostró su anuncio. Se usó su botón normal «Saltar» cuando estuvo disponible.
4. El anime se reprodujo: se observaron imágenes diferentes y subtítulos del episodio.
5. «Siguiente episodio» cambió al episodio 2 en la misma ficha; tanto el encabezado propio como la carátula del proveedor indicaban T1 E2.

Evidencia: `.local/phase10-telegram-play.png` y `.local/phase10-telegram-next.png`.

Esto prueba Telegram Desktop en este equipo. No se ha probado un teléfono Android o iPhone ni todos los animes del catálogo.

### Paso al siguiente capítulo

El avance es manual mediante el botón visible junto al reproductor. Cruza páginas y temporadas disponibles y deshabilita el botón en el último episodio. Se corrigió el mensaje de final que antes podía quedar oculto y se bloquean clics rápidos repetidos o respuestas tardías después de cerrar la ficha.

La documentación de Vimeus consultada ofrece URLs de inserción, selección por temporada/capítulo y personalización visual. No se encontró una API documentada de eventos `ended`, progreso o reproducción iniciada. No se simula el final con un temporizador ni se intenta leer el vídeo de otro origen. Por eso no se promete reproducción automática al terminar ni continuidad exacta por segundo. Los controles Play y anuncios dentro del iframe siguen dependiendo del proveedor.

## Descargas: resultado y límite encontrado

Se añadió «Descargar episodio» junto al reproductor; solicita el enlace del capítulo actualmente abierto. Los botones de descarga de cada fila permanecen y los enlaces manuales mantienen prioridad.

Desde Telegram, el botón preparó el enlace de Shippuden T1 E2 y `Telegram.WebApp.openLink` lo abrió en Chrome. El enlace entregado por Vimeus usa `/d/animes` y respondió **HTTP 404**. Se investigó también `/d/anime`: responde HTTP 200, pero devuelve **cero bytes** y una página en blanco. Ocurrió tanto con la clave incluida en el listado como con la clave del reproductor configurada. No se conservaron cambios hacia esa alternativa porque tampoco entrega una descarga funcional.

La salida desde Telegram funciona; el destino probado del proveedor no. No se descargó un archivo de vídeo completo ni se comprobó cada enlace externo del catálogo. No se sustituyeron enlaces manuales por rutas inventadas. Los 253 enlaces originales siguen en la copia local y las descargas manuales de MediaFire conservan su comportamiento y prioridad, con autorización y membresía verificadas en el servidor.

## Top 10 automático

- Fila numerada 1–10, horizontal y adaptable, situada arriba, después del carrusel.
- Con datos: «Top 10 de la semana», acompañado por «Según aperturas de reproducción de la comunidad».
- Sin datos: «10 para descubrir», con diez títulos reales y un aviso de que el ranking se formará con las primeras reproducciones. No se inventan vistas.
- La métrica es la apertura autorizada del reproductor; **no mide minutos vistos ni confirma que el vídeo empezó**.
- Se cuenta como máximo una apertura por cuenta y título por día, aunque se abran muchos capítulos. Ventana: hoy y los seis días anteriores, con fecha de Perú.
- No cuentan visitas a la ficha, lecturas GET, acceso vencido, episodios inválidos o sesiones de administrador. Las pruebas del propietario no inflan el ranking.
- Desempates por ID estable. Los títulos ocultos se excluyen. La respuesta pública no expone cuentas, enlaces privados ni contadores individuales.
- Los datos persisten en SQLite local. La tabla privada y el índice para PostgreSQL están preparados en `migrations/006_popularity.sql`, **sin aplicar en Supabase**. Se conservan hasta 30 días; se depuran al registrar nuevas aperturas.
- Los destacados manuales siguen sirviendo para el carrusel; el Top 10 usa su propio cálculo.

La reproducción usa POST con sesión, origen y CSRF verificados para registrar actividad. GET continúa siendo una consulta sin alterar métricas. Un fallo al registrar estadísticas no impide autorizar un vídeo.

Capturas: `.local/phase10-top10-desktop.png` y `.local/phase10-top10-mobile.png`.

## ¿Se puede importar automáticamente todo Vimeus?

Sí. Su documentación muestra listados paginados de películas, series, animes y episodios. El importador actual ya procesa temporadas y capítulos de series/animes identificados; todavía no es una cola que recorra todo el catálogo ni importa películas desde el listado de Vimeus.

Propuesta para la siguiente fase:

1. Descubrir títulos por páginas de Vimeus y encolarlos con la pareja tipo + TMDB ID, evitando duplicados.
2. Un solo trabajador, lotes pequeños configurables —por ejemplo cinco títulos— y separación conservadora entre peticiones. Guardar el avance para reanudar tras una pausa o reinicio.
3. Consultar TMDB una vez por título y temporada; cada respuesta de temporada ya contiene sus episodios. Reutilizar caché en español de México y conservar la preferencia de tráiler acordada.
4. Ante HTTP 429, respetar `Retry-After` si existe y aplicar espera creciente. Limitar reintentos; un error queda pendiente sin detener indefinidamente el resto.
5. Validar el conjunto de capítulos antes de publicar cada título. Conservar siempre enlaces manuales, detectar cambios de numeración y registrar huecos del proveedor.
6. Separar descubrimiento, importación y publicación. Primero se demostraría con un lote local pequeño; la persistencia y ejecución periódica en producción se aprobarían después.

No se ha puesto en marcha esta cola. La pausa debe aplicarse a cada petición y no solo entre títulos: un anime largo requiere varias temporadas. En el alojamiento gratuito, el diseño debe tolerar interrupciones; no conviene depender de un bucle infinito dentro del servidor web.

Fuentes oficiales consultadas: [Vimeus](https://www.vimeus.com/docs/getting-started), [límites de TMDB](https://developer.themoviedb.org/docs/rate-limiting) y [Telegram Mini Apps](https://core.telegram.org/bots/webapps). TMDB indica que sus límites pueden cambiar y que se debe respetar la respuesta 429.

## Pruebas reproducibles

**171 pruebas Python + 54 pruebas JavaScript = 225 aprobadas.** Python registra 20 avisos de obsolescencia de dependencias, sin fallos. Registros: `.local/phase10-pytest.txt` y `.local/phase10-node.txt`.

```powershell
.venv\Scripts\python.exe -m pytest -q
$phase10Tests = @(Get-ChildItem tests -File | Where-Object { $_.Name -match '\.test\.(cjs|mjs)$' } | ForEach-Object { $_.FullName })
node --test @phase10Tests
```

Cobertura añadida: ranking que cambia con distintas cuentas, límite de diez resultados, deduplicación, ventana semanal, medianoche de Perú, persistencia, protección de datos, exclusión de administración/acceso inválido, descarga del episodio actual, último episodio, clics rápidos y cancelación de navegación tardía. Las pruebas existentes de autorización, importación y conservación de descargas siguen pasando.

Revisión visual del Top 10 a 320, 390, 768 y 1440 píxeles, sin desbordamiento horizontal de la página. Los carteles móviles de la fila numerada conservan 136 px de ancho. Se restableció el tamaño normal del navegador después de las pruebas.

Pendiente externo: descarga efectiva del proveedor y API de fin de vídeo. Pendiente de otra fase: importador masivo por cola y despliegue con migración 006. Nada de esto se presenta como ya resuelto en producción.
