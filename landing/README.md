# Landing de Qué Hay Cine para SiteGround

Sitio estático independiente del backend de Render. No contiene claves, pagos,
base de datos, código PHP ni JavaScript. Los accesos apuntan inicialmente a
`https://cineapp-bot.onrender.com`; no usar `app.quehay.live` hasta configurar y
verificar ese dominio en una fase autorizada.

## Preparación local

1. Ejecutar `landing/build.py --out <directorio-publico>` con Python.
2. Ejecutar `scripts/build_legacy_static.py <export-sql-privado> <inventario-csv>
   <equivalencias-csv> <directorio-publico>`. Solo lee contenido publicado del
   archivo; no restaura MySQL ni activa redirecciones.
3. Copiar `landing/siteground.htaccess` como `.htaccess` y `landing/404.html`.
4. Copiar el sitemap generado como `sitemap_index.xml` para conservar el endpoint
   anterior. Este paso debe ir después del generador de páginas antiguas.
5. Empaquetar solo el directorio público, nunca el SQL ni la carpeta `.local`.

## Publicación realizada el 28 de octubre de 2026

La landing está publicada en `https://quehay.live/`. SiteGround confirmó la
eliminación de WordPress y su gestor MySQL quedó sin la base `dbdh2qgccbglsx`.
Se conservaron 721 direcciones inventariadas (719 páginas únicas, con dos alias
sin barra final), y el sitemap contiene 718 URL canónicas indexables con la raíz.
Las comprobaciones y capturas están en `.local/landing-release/`.

Se verificaron en navegador diez tipos de rutas antiguas, incluida codificación
Unicode, y adicionalmente la portada, Privacidad, Palmer, FAQ y la página 404.
En móvil de 390px no se observó desbordamiento horizontal. El comprobador HTTP
genérico recibe 403 en algunas rutas limpias, aunque estas se muestran en el
navegador real; no se desactivaron protecciones para eludirlo. La cobertura
completa de las rutas se verificó en local antes de la publicación.

Se vació únicamente la caché dinámica de quehay.live. NGINX Direct Delivery quedó
habilitado, como estaba. El registro antiguo `php_errorlog` se movió fuera de
`public_html` para conservarlo sin exposición pública. Se respetaron
`.well-known`, el archivo de verificación existente y las copias guardadas.
No hubo cambios de DNS, Render, Supabase, cuentas, descargas, pagos, bot ni cron.

## Alcance y procedimiento para futuras intervenciones

- Revisar la landing y las fichas estáticas antes de publicar.
- El único WordPress objetivo es `quehay.live/`, en su `public_html`.
- Su base identificada es `dbdh2qgccbglsx`, con 32 tablas `wpwz_`.
- El borrado permanente se realizó con la confirmación final del propietario.
- Conservar las copias ya guardadas, los registros, correo y otros sitios.
- Publicar la landing y las rutas estáticas durante la misma intervención.
- Comprobar HTTPS, página principal, fichas con caracteres no ASCII, sitemap,
  robots, error 404, estilos y enlaces a Render. El servidor local no valida
  las directivas Apache de `.htaccess`.
- No cambiar DNS, Supabase, Render, bot, pagos ni cron en esta intervención.

## SEO

Las fichas y taxonomías inventariadas conservan sus rutas y canonical propios;
los textos públicos se exportan sin formularios, anuncios ni reproductores.
Los enlaces de descarga de la aplicación y las cuentas de Supabase no cambian.
Las fichas con coincidencia única de TMDB y tipo enlazan a su contenido actual.
Las demás ofrecen acceso al catálogo, sin prometer que ese título esté disponible.

Las equivalencias 301 son un borrador separado. Deben activarse solamente cuando
el dominio de destino y las páginas SEO equivalentes estén verificados. No se
redirigen títulos sin equivalente indiscriminadamente a la portada. La cobertura
del inventario no garantiza mantener posiciones ni sustituye revisar Search Console.

Los textos legales existentes se conservan como contenido público; deberán
revisarse para reflejar el funcionamiento definitivo de la nueva plataforma.
