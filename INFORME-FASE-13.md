# Fase 13 — Editor de OK.ru y bloque Android

Trabajo exclusivamente local, accesible mediante el túnel existente de ngrok. Sin despliegues, cambios en Render, escrituras en Supabase de producción ni modificaciones del bot.

## Editor para el administrador

En `/admin`, la pestaña **Reproductores · OK.ru** permite buscar bíblicos, pegar el enlace de un vídeo completo y crear o actualizar capítulos indicando temporada y número. Admite los enlaces públicos de vídeo y embed de OK.ru; se normalizan y validan en el servidor. Repetir temporada y capítulo actualiza el existente. Un nombre vacío conserva el título anterior.

Los cambios de reproducción conservan los enlaces de descarga manuales, enlaces del proveedor y la visibilidad de episodios existentes. La autorización sigue limitada al propietario y las escrituras requieren CSRF. Las respuestas públicas de episodios no exponen el enlace del reproductor.

En la vista local se guardan los cambios en `.local/okru-preview-edits.json`, con escritura atómica y restauración al arrancar. Se verificó mediante la interfaz el vídeo de prueba 900421 y su temporada 1, capítulo 1, usando el enlace de Estudios 421. Se guardó dos veces, se reinició el servidor y continuó existiendo un solo capítulo con su enlace y título. Solo se editaron datos de esa muestra local.

Seguimos con Supabase para producción. La migración `migrations/008_okru_editor.sql` prepara la operación transaccional para ese entorno, pero **no se ejecutó ni se probó contra PostgreSQL** en esta fase. Su aplicación y validación quedan pendientes antes de desplegar.

## Inicio: invitación a instalar en Android

Nueva tarjeta con fondo azul oscuro, logo real, vista decorativa de teléfono con imágenes del catálogo, texto breve y botón de instalación destacado. En móvil se simplifica a una columna y un botón ancho. Sigue llevando a la guía `/instalar` y se oculta cuando la aplicación funciona en modo independiente.

Se separaron los estilos en `static/pwa/promo.css` para evitar la copia antigua de la hoja de instalación conservada por el service worker. Se comprobó visualmente en escritorio y en un viewport de 390 píxeles; el documento móvil mide 375 píxeles útiles y no presenta desbordamiento horizontal. El botón abrió correctamente la guía. Esta fase no incluye una instalación real en un teléfono Android.

## Pruebas y evidencia

- 206 pruebas Python aprobadas y 63 JavaScript: **269 en total**. Los 20 avisos Python corresponden a obsolescencias de dependencias.
- 11 pruebas específicas del editor: autorización, CSRF, conservación de descargas y visibilidad, actualización sin duplicados, persistencia, reproducción de episodio, rechazo de datos inválidos, reversión ante error de disco y paginación. Se repitieron satisfactoriamente después del último ajuste del validador.
- La API local sigue ofreciendo **253 títulos con descarga**, igual que antes del cambio.
- Registros completos: `.local/phase13-pytest.txt` y `.local/phase13-node.txt`.
- Capturas: `.local/phase13-admin-desktop.png`, `.local/phase13-admin-mobile.png`, `.local/phase13-android-desktop.png` y `.local/phase13-android-mobile.png`.

El GIF de la mascota sigue pendiente de que el usuario adjunte el archivo. No se sustituyó la imagen actual sin él.
