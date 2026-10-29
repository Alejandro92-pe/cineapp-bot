QUÉ HAY TV — primera fase local (29 de octubre de 2026)

ALCANCE
Interfaz independiente para preparar Android TV y Google TV. No se monta en
main.py, no modifica Render ni la APK móvil. No es todavía una APK de TV.
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
