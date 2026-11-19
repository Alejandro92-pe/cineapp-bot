# El Expediente · videos de TikTok

Cada película del catálogo se presenta como un archivo secreto: carpeta manila, sello rojo de
CLASIFICADO, fotos de evidencia, frases censuradas con barras negras y un cierre que manda a
`quehay.live`. El número de expediente es el id del título en la web (`?contenido=464`).

## Qué necesitas

- **Voice Creator Pro abierto**, con la HTTP API activa en el puerto 8100.
- En `.env` (ya está en `.gitignore`):
  - `VOICE_API_KEY=` la clave de la API de Voice Creator Pro.
  - `TMDB_API_KEY=` (opcional pero recomendada) para bajar 6-8 fondos de cada película.
    Sin ella, las fotos salen de recortes del póster.
- ffmpeg, Python 3 y Node 22 o superior. El script usa el Node 26 de Herd si el del sistema es viejo.

La voz es **Ale QH** (`voice_90ecd71e`). Para cambiarla: variable `EXPEDIENTE_VOZ`.

## Los 3 pasos

```powershell
python tiktok/expediente.py nuevo 464            # o un título: nuevo "amnesia"
# escribe tiktok/videos/464-amnesia/guion.txt (o pídeselo a Claude)
python tiktok/expediente.py todo 464-amnesia     # voz + video → 464-amnesia.mp4
```

- `voz` y `video` también existen por separado.
- `--borrador` renderiza rápido y en menor calidad para revisar.
- `--sin-render` arma la composición sin renderizar. Para verla:
  `npx hyperframes preview tiktok/videos/<carpeta>/proyecto`.
- Si cambias una sola frase del guion, solo esa frase se vuelve a generar: las demás se reutilizan.

## Cómo se escribe el guion

```
@portada
[sorpresa:fuerte] Este hombre no recuerda nada de lo que pasó hace quince minutos.

@sujeto Leonard Shelby | No puede formar recuerdos nuevos
[neutral] Se llama Leonard...

@evidencia A | Fotos con notas
[miedo:suave] Para no perderse, le toma fotos a todo...

@censura El asesino de su esposa es [[alguien que ya conoce]]
[desesperacion:normal] Su única misión es encontrar al asesino.

@cierre
[neutral] ¿La entendiste a la primera? El expediente completo está en Qué Hay Cine. Link en mi perfil.
```

- `@escena`: cambia la hoja de la carpeta. Cada escena lleva una o más frases debajo.
- `[emocion:intensidad]`: cómo dice la frase la voz. Si no pones nada, sale neutral.
  - Emociones: neutral, tristeza, alegria, ira, miedo, asco, sorpresa, desprecio, asombro,
    desaprobacion, remordimiento, indignacion, desesperacion.
  - Intensidad: muy_suave, suave, normal, fuerte, extrema.
- `[[texto]]` dentro de `@censura` se tapa con una barra negra.
- En `@sujeto` y `@evidencia` puedes elegir la foto con un tercer campo:
  `@evidencia B | Tatuajes | fondo8`. Los fondos están en `assets/` de la carpeta del video.
  Si no eliges ninguno, se usan en orden.

**Reglas que funcionan:** gancho en la primera frase, entre 35 y 55 segundos en total, no contar el
final (el final "está en la web") y terminar con una pregunta para que comenten.

## Al publicar en TikTok

El video sale sin música. Ponle un sonido en tendencia desde TikTok al 5-10 % de volumen: así
ayuda al alcance y la voz se sigue entendiendo. Pon el link de la web en tu perfil.
