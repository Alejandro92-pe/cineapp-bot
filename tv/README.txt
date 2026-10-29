QUÉ HAY TV — primera fase local (29 de octubre de 2026)

ALCANCE
Interfaz independiente para preparar Android TV y Google TV. No se monta en
main.py, no modifica Render ni la APK móvil. Hay un paquete de prueba separado
en android-tv/; véase android-tv/README.txt para vinculación y red local.
Diseño para pantalla grande: hero horizontal, filas de portadas, foco visible,
flechas/OK/volver, buscador, temporadas y capítulos en bloques de seis.
No expone pagos, descargas, descompresión ni enlaces a canales.

ESTRUCTURA
app.py: servidor local separado, autenticación, permisos y rutas.
catalog.py: lectura del catálogo, episodios y selección de reproductor.
store.py: códigos de vinculación y sesiones independientes de TV.
preview.py: carga una copia del catálogo y crea cuentas de demostración.
static/: interfaz TV, navegación y formulario de confirmación para celular.

INICIAR DESDE LA RAÍZ DE ESTE CHECKOUT
Usar el Python del entorno virtual existente y ejecutar:
  python -m tv.preview --snapshot-root "C:\Users\richa\Mis Proyectos\cineapp-render\.local"
Vista: http://127.0.0.1:5020/tv
Confirmación: http://127.0.0.1:5020/tv/vincular
Usuario de demostración: tv@example.test
Contraseña de demostración: Televisor-Local-2026!
Cuenta sin acceso: sinacceso@example.test (misma contraseña).
Estas cuentas son exclusivamente locales; no son cuentas de producción.

AISLAMIENTO
El servidor escucha solo en 127.0.0.1 y bloquea su tráfico saliente.
Lee copias locales del catálogo; guarda las sesiones en .local/tv/preview.sqlite.
No utiliza credenciales de producción ni modifica archivos de las copias fuente.
El navegador sí solicita imágenes de TMDB y el iframe del proveedor al reproducir.
La aplicación rechaza arrancar con una base de seguridad no local.
La URL de loopback solo se puede abrir en esta PC, no desde otro dispositivo.

VINCULACIÓN
El TV obtiene un código de un solo uso que caduca en diez minutos. La cuenta
confirma ese código desde la página adaptada al celular. Código y secretos se
guardan con hash; la sesión del TV es independiente y revocable. Se comprueba
el acceso vigente en cada petición de reproducción. La demostración se probó
con dos pestañas y clientes de prueba independientes, no con un teléfono real.

PRUEBAS REALIZADAS
62 pruebas Python aprobadas: tests/test_tv.py, tests/test_security.py y
tests/test_episode_downloads.py. Dos pruebas Node de navegación aprobadas.
Sintaxis JavaScript comprobada. No hubo errores de consola en la vista final.
Comprobación visual en 1280x720 y 1920x1080; formulario de teléfono en 390x844.
Flechas, selección, búsqueda, volver, cambio de temporada y paginación comprobados.
Vinculación local confirmada; la interfaz actualizó el nombre sin recargar.
VideoAPI reprodujo La casa del dragón T2E1 en el navegador; Siguiente episodio
abrió T2E2. Esto no certifica compatibilidad con un control remoto físico.
Evidencias: .local/tv/home-1080.png, episodes-720.png y link-phone.png.

PENDIENTES PARA LA SIGUIENTE FASE
1. Crear un paquete Android TV independiente, con identificador distinto al móvil.
2. Preparar acceso de prueba HTTPS controlado para vincular un teléfono real.
3. Probar mando físico: foco dentro del iframe, salir con Atrás, pausa, avance,
   pantalla completa, suspensión y recuperación en Android TV/Google TV.
4. Validar cada proveedor. Esta fase selecciona VideoAPI u OK.ru según la ficha;
   todavía no incorpora conmutación automática a Vimeus.
5. El cambio automático al terminar requiere eventos fiables del proveedor.
   Aquí se verificó el botón Siguiente episodio, no detección de fin automática.
6. Antes de producción, integrar las rutas con las cuentas reales, migrar las
   tablas de vinculación a Supabase y revisar revocación por cambios de seguridad,
   cookies HTTPS y límites operativos. No se ha aplicado ninguna migración.

Guía de navegación consultada:
https://developer.android.com/training/tv/get-started/navigation

TOP 10 (revisión posterior)
Primera fila debajo del hero, con números grandes y navegación horizontal.
Solo películas disponibles. Lee el ranking semanal del servicio Popularity,
que cuenta aperturas autorizadas, no minutos vistos. Sin estadísticas muestra
una selección de diez películas recientes, identificada como descubrimiento.
No se copiaron estadísticas de producción ni se inventaron reproducciones.
La prueba local nueva comprueba orden, filtro de series/no disponibles y límite.
10 pruebas TV aprobadas. Captura adicional: .local/tv/top10.png.

FICHAS Y CATÁLOGO LOCAL (29/10/2026)
Fichas independientes en static/detail.js y detail.css: play circular, afiche,
portada horizontal, sinopsis completa, géneros y otras sugerencias del catálogo.
Series: empezar el primer capítulo o elegir temporada; seis episodios por página.
Los capítulos sin fuente reproducible se identifican sin abrir un reproductor vacío.

snapshot.py combina solo campos del catálogo de las copias locales existentes.
Con --refresh-missing consulta exclusivamente GET públicos de temporadas/episodios
para los títulos sin capítulos; guarda resultados en .local/tv/catalog.json.
No hace cambios en Supabase ni utiliza las cuentas privadas de la copia.
Resultado: 776 fichas, 527 temporadas, 9.687 episodios; 174 títulos con episodios.
Se hicieron 129 consultas GET públicas, secuenciales y con pausas; sin errores.
Quedan 31 fichas de series/anime sin episodios: 30 tienen fuente canal y una
no tiene proveedor asignado. Se conserva el estado pendiente; no se inventa
numeración ni se afirma que todos los videos estén verificados.
Detalle: .local/tv/catalog-report.json. Se conservaron las portadas horizontales.

12 pruebas TV y dos de navegación aprobadas. Verificación visual a 1080p y 720p:
Carrie tiene una temporada de ocho capítulos; primera página 1–6 y segunda 7–8.
El play circular abrió VideoAPI T1E1; retorno, sinopsis y navegación comprobados.
No se ha empaquetado, publicado ni modificado la web o APK móvil.

COLECCIONES TV (29/10/2026)
static/browse.js y browse.css presentan películas, series, anime y bíblicos
con cabecera propia, filtros de géneros reales y búsqueda dentro de la categoría.
Orden por recién añadidos, puntuación existente o nombre. Doce títulos por página;
se conservan filtro, orden, página y foco al volver desde una ficha.
Bíblicos: tarjetas horizontales grandes y filtros Películas / Por episodios.
La clasificación por episodios utiliza temporadas existentes, sin inventarlas.

discovery.py trabaja con metadatos públicos en caché durante 60 segundos.
Los filtros abarcan toda la categoría, no solo la página visible. No carga listas
de episodios para explorar; consulta como máximo 10.000 fichas por categoría.
Este servicio sigue siendo exclusivo de la vista local, sin escritura en Supabase.

14 pruebas TV y dos de navegación aprobadas. QA en navegador a 720p y 1080p:
86 películas de terror, segunda página ordenada por puntuación, regreso a Christine
con foco y filtros conservados; 108 series de drama; 10 animes de aventura A–Z.
Bíblicos: 28 fichas, 27 películas y una con temporadas en la copia local.
Verificados búsqueda vacía, quitar filtros, flechas entre controles y tarjetas;
sin desbordamiento horizontal ni errores de consola durante la revisión.
Capturas: .local/tv/catalog-series-1080.png y catalog-biblico-cards.png.
Pendiente revisión del usuario y mando físico. No se ha generado ningún paquete.

FICHA INMERSIVA Y MI LISTA (29/10/2026)
La portada de la ficha ocupa la primera pantalla bajo el menú. Una sola sinopsis,
géneros en la cabecera y recomendaciones/episodios al bajar; retirados Sinopsis,
Detrás del título, La historia y Volver a la ficha. Top 10: números gruesos
parcialmente detrás del afiche, incluyendo espacio específico para el número 10.

Mi lista permite añadir/quitar desde la ficha y abrir los guardados desde el menú.
Reutiliza services.profiles.Profiles sin modificarlo, sobre preview.sqlite local.
No hay escritura en Supabase ni en las cuentas de producción. Una futura integración
usará la identidad real de la cuenta; esta prueba usa solo cuentas de demostración.
GET/POST /tv/api/list exige dispositivo vinculado; POST verifica CSRF y origen.
Guardar no requiere membresía activa; reproducir sigue comprobando el acceso.
Las listas son privadas por cuenta, admiten 200 títulos y páginas de 12 fichas.

16 pruebas TV y dos de navegación aprobadas: aislamiento de cuentas, persistencia
entre dispositivos vinculados, duplicados, quitar, paginación, revocación y CSRF.
QA de navegador: Matchbox guardado, conservado tras recargar, visible en Mi lista
y retirado; Carrie guardada y acceso a temporada con seis episodios visibles.
Ficha comprobada a 720p/1080p, sin sinopsis duplicada ni errores de consola.
Capturas: .local/tv/detail-immersive-720.png, series-immersive-1080.png,
top10-behind-720.png. Sigue pendiente mando físico y aprobación para empaquetar.

INICIO CINEMATOGRÁFICO Y EXPLORACIÓN CONTINUA (29/10/2026)
Esta revisión sustituye la paginación visible descrita en las fases anteriores.
El servidor mantiene límites de 12 títulos y 6 episodios por petición; stream.js
acumula resultados al avanzar con el control o acercarse al final de la sección.
Conserva filtros y fichas cargadas al regresar, evita peticiones simultáneas,
descarta respuestas de vistas abandonadas y ofrece recuperación ante errores.
La recuperación conserva el foco; no es virtualización de todo el catálogo.

home.js presenta tres destacados (película, serie y anime con portada) en una
primera pantalla completa. Alterna cada 20 segundos, admite selección y pausa,
respeta movimiento reducido y detiene la rotación al salir de la zona visible.
La selección usa bloques de tres días y se revisa al volver a renderizar Inicio.
No consulta proveedores durante la rotación; precarga la siguiente imagen.
Carátulas uniformes y más próximas, foco alrededor de la imagen y Top 10 con
trazo azul luminoso, relleno transparente y números parcialmente detrás.

Series: cabecera compacta, temporadas y fila de episodios más pequeños. Al entrar
en episodios se reduce la cabecera al título; Atrás recupera la ficha completa.
Descripción del episodio seleccionado debajo de la fila. Películas conservan
su ficha amplia. Mi lista, cuentas y reproducción mantienen sus controles previos.

Validación: 16 pruebas Python y 6 Node aprobadas. QA Edge sin interfaz a 720p/1080p:
Series 12 a 24 fichas sin duplicados; regreso conserva las fichas; Carrie 6 a 8
episodios; rotación automática, pausa, error 503 simulado y recuperación del foco.
Sin errores JavaScript en el recorrido principal. Evidencia en .local/tv:
experience-qa.json, home-cinematic-1080.png, top10-neon-720.png,
series-compact-720.png y series-compact-episodes-720.png.

Disponibilidad: la copia tiene 519 películas disponibles en catálogo; 295 tienen
fuente canal y carecen de TMDB. No disponen de fuente compatible en esta vista TV.
Las otras 224 tienen configuración vimeus, pero esto NO verifica su reproducción
real ni la disponibilidad actual de los proveedores. Empaquetar no corrige fuentes.
No se han modificado producción, la web móvil, la APK, cuentas ni descargas.
Queda pendiente la revisión del usuario y la prueba física de mando/proveedores.

MENÚ PERSISTENTE TV (29/10/2026)
Corregido el desplazamiento del menú mostrado en menu.mp4: la barra superior
permanece visible al explorar Inicio, categorías y fichas. El scroll reserva
su altura para que la selección no quede debajo. Enfocar el menú no mueve
la posición de lectura del catálogo. El reproductor conserva su capa superior
para ocultar el menú durante el video.
QA local a 720p y 1080p: rueda, flechas, selección de carátulas y episodios,
retorno al menú sin salto y capa de reproducción. Dos pruebas de navegación
aprobadas. Evidencia: .local/tv/menu-fixed-qa.json y menu-fixed-*.png.
Solo archivos TV; sin empaquetado ni cambios en producción.

APK TV DE PRUEBA (29/10/2026)
Android TV / Google TV 0.1 en android-tv/, identificador live.quehay.tv.preview.
No comparte ni reemplaza el proyecto android/ del móvil. Manifest TV, banner,
foco de mando, OK, Atrás, WebView y pantalla completa nativa del proveedor.
Sin pagos, descargas, permisos extra, credenciales ni JavaScriptInterface.
Compila con el SDK/JDK ya instalados. APK firmada para instalación manual.

preview.py mantiene loopback por defecto; solo --lan-host permite una IP privada
explícita, con base preview-lan.sqlite de demostración. Backend sin tráfico
saliente, peticiones de origen exacto y clientes LAN/loopback. No se usa en Render.
Prueba LAN servida en 192.168.100.3:5021: el usuario confirmó acceso desde celular.
Vinculación completa probada con contextos separados, recarga y revocación.
23 pruebas Python y 4 de navegación/adaptador de mando aprobadas. Firma y manifest
APK verificados; compilación y lint sin errores. Mando y reproducción físicos
pendientes. Guía detallada en android-tv/README.txt. No hay integración real todavía.
