# Fase 4 — Portada y catálogo

Validación local: 26 de octubre de 2026. No se modificó producción, Render, Supabase remoto, webhooks ni proveedores de pago. No hubo transferencias, envíos por Telegram ni reproducción externa real.

## Cambios visibles

- Portada con título destacado, sinopsis, ficha accesible y acceso al catálogo. Usa una entrada disponible del catálogo; no atribuye popularidad ni recomendaciones personalizadas inexistentes.
- Filas horizontales de recién llegados, películas, series y anime, con botones para explorar cada categoría. Las filas vacías no se muestran.
- Paleta azul oscuro, azul claro y dorado, y tipografía coherente con la membresía.
- Navegación de escritorio y barra inferior en móvil: Inicio, Catálogo, Mi lista y Acceso. La cuenta y la membresía permanecen accesibles en la cabecera. El panel del administrador se abre desde su cuenta; ya no aparece un botón administrativo flotante a todos los visitantes.
- Catálogo con búsqueda por título, filtros combinables por tipo, género, año y disponibilidad de descarga. Paginación explícita de 24 títulos mediante «Cargar más», estados vacíos y reintento ante fallos.
- Mi lista permite guardar y quitar títulos. Se conserva en este navegador, por cuenta; se mantienen las claves anteriores de Telegram. Las cuentas de correo ya no comparten el almacenamiento de invitado. No se promete sincronización de favoritos entre dispositivos.
- Fichas de contenido con la misma paleta, temporadas y capítulos existentes, botón de descarga, cierre con Escape y navegación de teclado contenida en la ficha.

El contenido dinámico de las nuevas tarjetas se inserta como texto o mediante propiedades DOM. La codificación de imágenes distingue atributos HTML de propiedades DOM, conservando correctamente las URL con parámetros. Los destacados excluyen ahora títulos no disponibles. El filtro de año se aplica en el servidor y rechaza valores inválidos.

## Descargas y reproducción

Se conserva `static/downloads.js` y la consulta autenticada a `/api/download/<id>`. La ficha muestra el botón si existe descarga. Después de comprobar el acceso, presenta el dominio, el enlace explícito y la opción de copiar; dentro de Telegram continúa usando `openLink` con Instant View desactivado. No se expone la URL privada en el catálogo público.

Los módulos de temporadas, episodios y reproducción autenticada se mantienen. La prueba de navegador seleccionó la temporada 2 del anime de demostración y mostró «Reproducir · T2 E1». Se abrió el diálogo de MediaFire desde anime y serie, sin navegar al archivo ficticio. Esto verifica el recorrido y la conservación del enlace, no la disponibilidad de un archivo real del proveedor.

## Organización

| Archivo | Responsabilidad |
| --- | --- |
| `static/catalog/browse.js` | Portada, tarjetas, búsqueda, filtros, paginación y lista de guardados |
| `static/catalog/browse.css` | Diseño compartido, adaptación a tamaños de pantalla y fichas |
| `static/catalog/episodes.js` y `episodes.css` | Temporadas y capítulos; conservados |
| `static/index.html` | Estructura semántica, navegación y carga de módulos |
| `static/app.js` | Integración con sesión, favoritos y fichas existentes |
| `scripts/seed_local_catalog.py` | 27 títulos ficticios y carteles vectoriales de demostración, solo para el lanzador local |
| `tests/test_catalog.py` | Combinación de filtros, año, paginación y destacados disponibles |

La portada, el catálogo y la búsqueda dejan de usar sus recorridos antiguos. Parte de `app.js` y `styles.css` sigue dando soporte a vistas y funciones heredadas; esta fase no pretende haber reescrito toda la aplicación. Se retiró la carga del SDK de Supabase del navegador porque este recorrido usa la API del propio servidor.

## Pruebas y evidencia

**144 pruebas aprobadas: 124 Python y 20 Node.js/SQL.**

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=.local/phase4-python.xml
node --test tests/frontend.test.cjs tests/episodes.test.cjs tests/vimeus-sql.test.mjs tests/billing-sql.test.mjs
node --check static/catalog/browse.js
node --check static/app.js
node --check static/escape.js
git diff --check
```

Resultados: `.local/phase4-python.txt`, `.local/phase4-python.xml`, `.local/phase4-javascript.txt`. Python produjo 20 advertencias de dependencias, sin fallos. Se conservan las pruebas de seguridad, pagos, vencimientos, descargas e importación de las fases anteriores.

Comprobaciones de navegador realizadas con datos locales:

1. Catálogo inicial de 24 tarjetas; «Cargar más» completó 27, sin duplicados y ocultó el botón al finalizar.
2. Filtro Anime: una ficha. Guardarla y abrir Mi lista mostró el título guardado.
3. Buscar «Luz del norte»: cuatro resultados; añadir 2025: dos; añadir «Con descarga»: cero y mensaje claro. Limpiar filtros y seleccionar solo descargas: once resultados.
4. Selección de temporada 2 del anime: doce episodios y botón asociado a T2 E1.
5. Descarga: diálogo de MediaFire con abrir, copiar y cerrar; no se descargó ni solicitó un archivo real.
6. Escape cerró la ficha. Shift+Tab desde el botón volver mantuvo el foco en la ficha.
7. Anchos de 320, 390, 768 y 1280 px: sin desbordamiento horizontal del documento en las vistas comprobadas. A 768 px el catálogo mostró cuatro columnas. Se revisaron las capturas de móvil y escritorio y no hubo imágenes rotas en la portada comprobada.

Esto valida el navegador integrado a esos tamaños; no equivale a una prueba en dispositivos físicos Android/iOS ni a un APK.

Capturas:

- `.local/fase4-inicio-escritorio.png`
- `.local/fase4-catalogo-escritorio.png`
- `.local/fase4-inicio-movil.png`
- `.local/fase4-catalogo-320.png`
- `.local/fase4-descarga-movil.png`

Los carteles y títulos visibles son una demostración identificada como local. En producción las tarjetas seguirán usando las imágenes y los datos importados del catálogo. No se alteró ningún catálogo remoto para obtener estas capturas.

## Revisar

Ejecutar ` .\.venv\Scripts\python.exe scripts/run_local.py ` y abrir <http://127.0.0.1:5010/>. El lanzador conserva el aislamiento del backend y las credenciales de prueba de las fases anteriores. La membresía sigue en <http://127.0.0.1:5010/membresia>.

La siguiente fase y cualquier publicación en producción quedan pendientes de la revisión del usuario. Siguen vigentes los pendientes de pagos descritos en `INFORME-FASE-3.md`, incluido el QR oficial de Binance y la configuración real de Buy Me a Coffee.
