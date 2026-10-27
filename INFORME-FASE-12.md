# Fase 12 — OK.ru, acceso y Popcorn Crítico

26 de octubre de 2026. Implementación y pruebas únicamente en local, expuesta por el ngrok existente. Sin despliegue ni escrituras en Render o Supabase. Sin pagos, cambios de credenciales, mensajes o cambios de configuración del bot.

## Reproducción integrada

- Se añadió `providers/okru.py`, que convierte enlaces HTTPS de `ok.ru/video/ID` o `ok.ru/videoembed/ID` en un iframe canónico. Rechaza dominios parecidos, credenciales en la URL, puertos y rutas ajenas al reproductor. No extrae archivos de vídeo.
- La ruta de reproducción verifica sesión y acceso antes de devolver el embed. Los enlaces privados no aparecen en el catálogo público. Los episodios se validan contra la temporada y el título solicitado.
- El mismo reproductor interno admite Vimeus y OK.ru. La política de seguridad permite específicamente `https://ok.ru` como origen de iframe.
- Se añadió una ficha de prueba independiente, ID `900421`, tipo bíblico: «Final | Pablo El Apóstol | Audio Latino». Utiliza el enlace proporcionado de Estudios 421. Es un fragmento de aproximadamente 7:33, no la serie completa. No sustituye ninguna ficha bíblica existente ni inventa un enlace de descarga.
- El home incluye la sección «Historias que inspiran» para acceder a los bíblicos.
- La integración admite `fuente=okru` y `playback_url` en una ficha o sus episodios. La migración `007_okru.sql` está preparada, **no aplicada en producción**. El panel actual todavía no incluye un editor de estos nuevos enlaces; la muestra local queda configurada en el sembrado de la vista previa.

Prueba visual real: se abrió la ficha con la cuenta local de Ale y acceso activo, se inició el reproductor del proveedor y se observó el tiempo avanzar de 00:31 a 00:38. Vídeo y controles permanecieron dentro de nuestra página. Se pausó después. La carga inicial fue lenta; no se confundió la portada con reproducción. Chrome se abrió como contraste, pero no se completó allí la prueba de reproducción; la evidencia confirmada corresponde al navegador integrado.

No se certificó todavía la reproducción en Telegram Android/iPhone ni se añadió avance automático por eventos del reproductor de OK.ru. Su reproducción y disponibilidad siguen dependiendo del proveedor.

Evidencia: `.local/phase12-okru-playing.png`.

## Ventana de apoyo antes del reproductor

`static/support/access.js` y `access.css` contienen la ventana compartida por reproducción, descarga de película y descarga por episodio. Los códigos del servidor distinguen falta de sesión (`auth_required`) y cuenta sin acceso activo (`membership_required`).

La reproducción mantiene el panel y el iframe cerrados mientras se autoriza. Si falta acceso, muestra la invitación de apoyo y no carga una URL de vídeo. No aparece «Reintentar» por falta de membresía. Los fallos técnicos reales conservan su tratamiento de error; no se presentan como una exigencia de pago.

- Invitado: explica que crear una cuenta es gratuito, permite iniciar sesión o registrarse y ofrece conocer el acceso de 30 días.
- Cuenta sin acceso: invita a activar o renovar; permite revisar la cuenta si ya se realizó un aporte.
- Ambas variantes permiten cerrar la ventana o seguir explorando. El botón principal lleva a `/membresia`.
- Se mantiene US$1.50 por 30 días, sin renovación automática. La página de pago conserva Yape/Plin S/5.50 y Binance Pay 1.50 USDT.

Prueba visual: invitado → Reproducir → ventana de apoyo; iframe sin `src` y panel oculto. El enlace secundario abrió el formulario gratuito, se inició sesión con la cuenta local de pagos y se llegó a la página de membresía. Al volver sin acceso, apareció el texto específico de cuenta existente y el iframe siguió cerrado. No se efectuó ningún pago ni se alteró la membresía para esa prueba.

## Mascota y diseño

Se observó la imagen pública del bot `Popcornqh_admin_bot`: vaso de palomitas rojo y blanco, chaqueta oscura, guantes y zapatillas blancas. Se dibujó una adaptación SVG original con esos rasgos, ojos tristes, lágrimas y un corazón. No es una copia exacta de la imagen 3D del bot.

Archivo editable: `static/support/popcorn.svg`. Se usa en la ventana y en un bloque de apoyo de la página de membresía. El texto invita a mantener el proyecto, sin afirmar un cierre inminente ni inventar urgencia.

Se comprobó visualmente el diálogo en escritorio y móvil de 390 píxeles, sin desbordamiento horizontal. Usa diálogo nativo, etiquetas accesibles, enlaces claros y opciones para volver al catálogo.

Evidencias:

- `.local/phase12-support-mobile.png`
- `.local/phase12-support-account.png`
- `.local/phase12-membership-mobile.png`

## Descargas y pruebas

La vista local sigue publicando **253 títulos con descargas**, coincidiendo con los 253 enlaces manuales del catálogo original. No se modificaron esos campos. Las pruebas verifican que una cuenta activa recibe su enlace manual de MediaFire y que invitados/cuentas sin acceso no reciben la URL. Las pruebas previas de conservación tras importar siguen pasando.

**195 pruebas Python + 63 JavaScript = 258 aprobadas.** Hay 20 avisos de obsolescencia de dependencias Python, sin fallos.

Se añadieron casos de normalización/rechazo de URL de OK.ru, autorización, membresía, pertenencia del episodio, conservación de descargas, espera sin panel negro, ventana para invitados/cuentas sin acceso, validación del iframe y los dos flujos de descarga. No se utiliza la mera carga de un iframe como prueba de reproducción.

```powershell
.venv\Scripts\python.exe -m pytest -q
$tests = @(Get-ChildItem tests -File | Where-Object { $_.Name -match '\.test\.(cjs|mjs)$' } | ForEach-Object { $_.FullName })
node --test @tests
```

Registros: `.local/phase12-pytest.txt` y `.local/phase12-node.txt`.

Acceso a la muestra: https://clairvoyantly-adactylous-leonida.ngrok-free.dev/?contenido=900421
