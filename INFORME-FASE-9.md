# Animes completos, episodios compactos y carrusel

26 de octubre de 2026. Trabajo exclusivamente local, accesible mediante el túnel de prueba. No se desplegó ni se modificaron Render, Supabase o la configuración del bot.

## Criterio confirmado

La última indicación sustituye la anterior: incluir todos los capítulos que devuelve Vimeus, también los de relleno. Las fichas locales se llaman Naruto y Naruto Shippuden; ya no anuncian «sin relleno». No se aplica ningún filtro de relleno.

Vimeus aporta la disponibilidad real, las coordenadas del reproductor y las descargas. TMDB aporta títulos, imágenes, sinopsis y duración; no aloja los vídeos. Supabase sigue siendo la base prevista para producción. El túnel utiliza una copia local aislada y archivos locales para estas importaciones.

## Ocho fichas pendientes revisadas

| Ficha original | Resultado local |
| --- | --- |
| Naruto sin relleno, 408 | Naruto: 218 capítulos, 4 temporadas, incluyendo relleno |
| Naruto Shippuden sin relleno, 409 | Naruto Shippuden: 472 capítulos, 19 temporadas disponibles, incluyendo relleno |
| Sword Art Online II, 405 | Integrada en Sword Art Online, temporada 2 |
| Alicization, 406 | Integrada en Sword Art Online, temporada 3 |
| Alicization - War of Underworld, 407 | Integrada en Sword Art Online, temporada 4 |
| Dragon Ball Z, 371 | Vimeus devuelve listado vacío para TMDB 12971 |
| Dragon Ball GT, 373 | Vimeus devuelve listado vacío para TMDB 12697 |
| Dragon Ball Héroes, 376 | Vimeus devuelve listado vacío para TMDB 80020 |

Sword Art Online queda en una ficha, con 85 capítulos repartidos en cuatro temporadas: 25, 24, 24 y 12. Las tres fichas anteriores se ocultan del catálogo, conservando sus registros y resolviendo sus enlaces antiguos hacia la temporada correspondiente. Si una ficha tiene una descarga exclusiva, el consolidador se niega a ocultarla automáticamente. El catálogo original de 644 registros permanece intacto en el archivo privado de respaldo.

### Huecos reales del proveedor

- Naruto: no devuelve temporada 4, episodios 10 y 11 (168 y 169 en numeración absoluta).
- Shippuden: no devuelve la temporada 15, episodios absolutos 321–348.
- Sword Art Online: la temporada 4 devuelve 12 episodios; faltan 13–23 respecto de la temporada de 23 capítulos registrada por TMDB.
- No se generaron enlaces ficticios para completar esos huecos ni para los tres Dragon Ball pendientes.

## Numeración y descargas

Naruto utiliza números relativos a la temporada en Vimeus. Shippuden utiliza números absolutos. La respuesta consultada de TMDB utiliza números absolutos en ambos casos. Se añadió un mapa explícito para buscar los metadatos correctos, compatible también con una respuesta relativa completa de TMDB. No se cambian las coordenadas de reproducción o descarga. Si la numeración deja de coincidir con el mapa conocido, la importación falla en vez de asociar capítulos por posición.

La copia local contiene ahora 75 títulos importados, 205 temporadas y 3.773 episodios con descarga del proveedor. Los 253 enlaces de descarga de las fichas originales se conservan. Los enlaces manuales por episodio siguen teniendo prioridad y se restauran desde su archivo local al reiniciar. Los ocho registros revisados no tenían una descarga manual de ficha que transferir.

## Interfaz

- Inicio con cuatro películas: flechas, indicadores, contador y pausa. Rotación cada 7,5 segundos; se detiene con foco/interacción, ficha abierta, pestaña oculta o preferencia de movimiento reducido. El temporizador se elimina al salir del inicio.
- El botón «Ver detalles» abre la película actualmente seleccionada.
- Episodios más compactos, con miniatura, título y duración. Descarga independiente mediante icono; edición de enlace visible solo para el administrador.
- En la sesión de administrador las filas medidas ocupan 94 px en móvil y 84 px en escritorio. La sinopsis completa permanece en los datos y como ayuda del botón; se oculta de la fila móvil para reducir altura.
- Las fichas se actualizan al abrirlas para resolver títulos antiguos guardados y enlaces de fichas consolidadas.

## Pruebas

**167 pruebas Python y 51 pruebas JavaScript aprobadas: 218 en total.** Python registra 20 avisos de obsolescencia de dependencias, sin fallos.

Comandos reproducibles en PowerShell:

```powershell
.venv\Scripts\python.exe -m pytest -q
$phase9Tests = @(Get-ChildItem tests -File | Where-Object { $_.Name -match '\.test\.(cjs|mjs)$' } | ForEach-Object { $_.FullName })
node --test @phase9Tests
```

Evidencia guardada en `.local/phase9-pytest.txt` y `.local/phase9-node.txt`. Las pruebas incluyen conservación de episodios de relleno y su descarga, numeración absoluta/relativa, consolidación reversible, negativa a ocultar una descarga exclusiva y controles/temporizador del carrusel.

Comprobaciones de navegador sobre el servidor real local a través de ngrok:

- Shippuden, temporada 3: capítulos 54–71; 57 y 58 presentes con su botón de descarga.
- El enlace antiguo `/?contenido=405` abre Sword Art Online en temporada 2, con 24 episodios.
- Carrusel con cuatro películas; recorrido del primero al último y regreso al primero; apertura de la ficha de Chavín de Huántar desde su diapositiva.
- Sin desbordamiento horizontal de página o ficha a 320, 390, 768, 1440 y 2560 px. Se ajustaron los controles del carrusel para que también entren completos en 320 px.
- API local: Naruto 218, Shippuden 472 y SAO 85 episodios. El archivo privado de configuración devuelve 404 por HTTP y la descarga sin sesión devuelve 401.

Capturas: `.local/phase9-home-desktop.png`, `.local/phase9-home-mobile.png` y `.local/phase9-episodes-mobile.png`.

No se reprodujeron ni descargaron individualmente los 3.773 vídeos. Estas pruebas confirman importación, asociación, controles y protección de acceso; no garantizan disponibilidad continua de cada archivo externo ni reproducción en todos los clientes de Telegram. Los tres Dragon Ball y los huecos indicados requieren que el proveedor los incorpore o que se asigne otra fuente válida.
