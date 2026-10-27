# Fase 16 — Marca QueHay y acceso del propietario

26 de octubre de 2026. Cambios en local; sin despliegue ni escrituras en Supabase o Render.

## Reproductor

Se consultaron la documentación y el configurador oficial de Vimeus:

- https://www.vimeus.com/docs/getting-started — apartado «Personalización de player» del SDK.
- https://www.vimeus.com/player — genera `title=QueHay` y `theme=blue` al elegir esos valores.

Las URLs de películas, series, animes y episodios incluyen ahora `title=QueHay`, `theme=blue`, `primary_color=78b7fb` y el logotipo oficial de la aplicación mediante `logo_url` cuando el origen configurado es HTTPS. Los parámetros se deciden en el servidor; no se aceptan marcas o direcciones suministradas por el navegador. Se mantienen la clave de visualización, TMDB, temporada y episodio.

El tema azul aporta las superficies oscuras y el acento claro mantiene legibles los controles. La cabecera de nuestro reproductor muestra también el logotipo y QUEHAY. Se verificaron el iframe real y la apertura del servidor de vídeo; no se certifica una reproducción completa ni se ocultan anuncios. El selector del proveedor puede conservar nombres técnicos como `vimeos.net`: personalizar la marca no cambia la identidad de esos servidores externos.

El círculo de carga de nuestra página dejó el naranja y utiliza un degradado de azul noche a azul claro. Incluye alternativa sin máscara para navegadores antiguos y respeta la preferencia de reducir movimiento. Se comprobó el CSS servido y cargado en el navegador.

## Acceso exclusivo del propietario

El ID de Telegram **5824989040**, obtenido de la cuenta verificada en el servidor, tiene acceso permanente a reproducción y descargas. No se creó una membresía ficticia ni un pago, ni se asignó una fecha artificial de vencimiento.

Mi cuenta muestra «Propietario», «Acceso permanente» y «Sin vencimiento ni pagos». Las compras de los tres métodos se rechazan para esa cuenta con un mensaje explicativo; la página de membresía deshabilita sus botones de pago. El historial anterior se conserva. El privilegio también funciona al verificar esa misma cuenta desde Telegram.

Los demás usuarios siguen necesitando acceso vigente. Escribir el ID del propietario en un formulario, manipular una petición o falsificar los datos de Telegram no concede el privilegio. Una sesión del propietario vencida sigue exigiendo autenticación.

## Evidencias

- **247 pruebas Python + 76 pruebas JavaScript/SQL = 323 aprobadas.** Se mantienen los 20 avisos de deprecación de dependencias preexistentes.
- Pruebas nuevas: propietario sin filas de membresía/pago, acceso mediante Telegram verificado, sesión vencida, identidad falsificada, usuarios normales, bloqueo de compra en los tres métodos, película/serie/anime/episodio y descarga por episodio.
- Prueba del servidor local: acceso permanente activo y sin vencimiento, marca y logotipo en el embed, **253 enlaces originales de descarga sin cambios**.
- Archivos: `.local/phase16-pytest.txt`, `.local/phase16-node.txt`, `.local/phase16-integrity.json`, `.local/phase16-player.png`, `.local/phase16-owner.png`.

Esta fase no requiere una migración nueva. El privilegio y la personalización entrarán en producción cuando se despliegue este código junto con las migraciones pendientes de las fases anteriores. No se cambiaron los ajustes globales de la cuenta de Vimeus.
