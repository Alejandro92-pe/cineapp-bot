# Fase 15 — Cuenta sincronizada, instalación y puntuaciones

26 de octubre de 2026. Cambios y pruebas en la copia local publicada por el túnel existente. **No se modificaron Render, Supabase, el bot ni los cobros de producción.**

## Resultado

- Avatar elegido y Mi lista se guardan por cuenta verificada. Dos navegadores independientes recuperan la misma selección. Se actualizan al entrar, volver a la ventana y cada 30 segundos mientras la página está visible.
- Los favoritos y el avatar anteriores del navegador se incorporan una vez por cuenta. Las bajas dejan una marca en el servidor para impedir que un dispositivo antiguo vuelva a añadirlos. Se conservan los datos anteriores del navegador.
- Sin conexión, un cambio fallido se revierte y se informa; no se presenta como guardado. Las respuestas atrasadas y los cambios de cuenta no mezclan preferencias. Límite: 200 títulos guardados.
- Mi cuenta indica el estado de sincronización y el número de guardados. La entrada muestra un estado de carga en vez de presentar brevemente el formulario antes de reconocer la sesión.
- Las menciones «prueba local» y «catálogo copiado» no aparecen en las pantallas revisadas. La ficha de muestra de Estudios 421 también perdió ese rótulo. Los avisos de no transferir dinero en los pagos de demostración permanecen mientras se ensaya.

## Instalación

Se reprodujo el fallo del usuario en el navegador integrado: fuente Times New Roman e icono con ancho natural 0. Las nuevas direcciones versionadas del CSS y los iconos evitan la caché anterior sin borrar datos personales. La nueva caché usa red primero y comprueba el tipo de contenido; no guarda una página HTML como CSS o PNG. La actualización sigue esperando la elección del usuario y no recarga una reproducción por la fuerza.

Después: estilos cargados, icono de 512 píxeles y comprobación a 390 píxeles de ancho sin desbordamiento horizontal. No se realizó una instalación nativa en un teléfono físico; se verificaron la página responsive, el manifiesto, los recursos y el flujo de instalación con sus pruebas automatizadas.

## Puntajes de TMDB

El manifiesto de series/animes omitía `vote_average`. Además, la actualización de fichas existentes y las funciones SQL de importación no persistían `rating`. Se corrigieron esas rutas, incluidas películas/bíblicos. Un fallo de TMDB no borra una puntuación existente y los valores inválidos no se convierten en estrellas ficticias.

Se hicieron **3 consultas de lectura** a TMDB, espaciadas mediante el control de pausas existente. Solo se cambió `rating` en los tres documentos ya completados del lote local:

| Título | TMDB | Valor recibido | Visible |
|---|---:|---:|---:|
| La lista terminal | 120911 | 7.993 | 8.0 |
| Cyberpunk: Edgerunners | 105248 | 8.505 | 8.5 |
| Helluva Boss | 289892 | 7.5 | 7.5 |

El tercer título del lote es Helluva Boss; no se encontró Vox Machina entre esos tres. El arreglo del importador también se aplica a futuras series. La copia previa del lote se conserva en `.local/phase15-ratings-before.json`. Los 16, 20 y 23 episodios de esos documentos no se alteraron.

## Pruebas

- **236 pruebas Python + 76 JavaScript/SQL = 312 aprobadas.** Hay 20 avisos de deprecación de dependencias ya existentes.
- Pruebas HTTP con dos sesiones y pruebas reales en Chrome y navegador integrado: cambio de Gato a Zorro, propagación, guardado de Piratas del Caribe en un navegador y retirada desde el otro. Al terminar se restauraron Gato y la lista original con Corazón de oro.
- Aislamiento de cuentas, CSRF, expiración de sesión, respuestas atrasadas, clics rápidos, fallos de conexión, importación de favoritos anteriores, límite de lista y escrituras concurrentes.
- Migraciones y funciones SQL ejecutadas en PostgreSQL local mediante PGlite. Se comprobó que `anon` y `authenticated` no leen ni escriben las nuevas tablas privadas, y que las funciones de importación mantienen las descargas manuales y los enlaces de OK.ru.
- **253 enlaces de descarga del catálogo original permanecen idénticos.** Se comprobó además que el único cambio en los documentos del lote fue la puntuación.
- Capturas: `.local/phase15-install-desktop.png`, `.local/phase15-install-mobile.png`, `.local/phase15-account-second-browser.png`, `.local/phase15-list-second-browser.png`, `.local/phase15-ratings-desktop.png`.
- Registros: `.local/phase15-pytest.txt`, `.local/phase15-node.txt`, `.local/phase15-integrity.json`, `.local/phase15-ratings.json`.

## Límite de esta fase y paso a producción

El servidor de ensayo usa SQLite aislado; las migraciones se probaron además con PostgreSQL local. **La sincronización todavía no está activada en el Supabase de producción.** Su implementación usará la conexión privada PostgreSQL de Supabase configurada en `SECURITY_DATABASE_URL`, sin exponer credenciales al navegador.

Para desplegar esta fase habrá que aplicar `010_profiles.sql` después de la migración de cuentas y `011_import_ratings.sql` después de las migraciones 005 y 009, junto con las demás migraciones pendientes de las fases anteriores. Después deben verificarse la conexión real, los permisos y dos dispositivos en el dominio definitivo. Eso queda para la fase de publicación autorizada.

El historial de títulos abiertos sigue siendo del navegador; esta fase sincroniza avatar y Mi lista. El cron/importador automático de producción y el análisis de capacidad de Render no se activaron ni modificaron en esta revisión.
