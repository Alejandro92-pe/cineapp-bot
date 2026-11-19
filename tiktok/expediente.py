"""El Expediente: genera videos verticales para TikTok a partir del catálogo de Qué Hay Cine.

Uso:
  python tiktok/expediente.py nuevo <id del catálogo | título>
  python tiktok/expediente.py voz   <carpeta>
  python tiktok/expediente.py video <carpeta> [--borrador]
  python tiktok/expediente.py todo  <carpeta> [--borrador]

La carpeta es la que crea `nuevo`, dentro de tiktok/videos/. Ver tiktok/README.md.
"""
import base64
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.parse
import urllib.request
import wave
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent
VIDEOS = RAIZ / "videos"
CATALOGO = REPO / ".local" / "catalog-snapshot.json"
PLANTILLA = RAIZ / "plantilla" / "expediente.html"

VOZ_API = os.getenv("VOICE_API_URL", "http://127.0.0.1:8100")
VOZ_ID = os.getenv("EXPEDIENTE_VOZ", "voice_90ecd71e")  # Ale QH
WEB = "quehay.live"

EMOCIONES = {
    "neutral": "neutral", "tristeza": "sad", "alegria": "joy", "ira": "anger", "miedo": "fear",
    "asco": "disgust", "sorpresa": "surprise", "desprecio": "contempt", "asombro": "awe",
    "desaprobacion": "disapproval", "remordimiento": "remorse", "indignacion": "outrage",
    "desesperacion": "despair",
}
INTENSIDADES = {"muy_suave": "very_mild", "suave": "mild", "normal": "normal", "fuerte": "strong", "extrema": "extreme"}

PAUSA_LINEA = 0.18   # silencio entre frases de una misma escena
PAUSA_ESCENA = 0.40  # silencio al cambiar de escena
INICIO = 0.20        # la voz empieza un poco después del primer fotograma
COLA = 1.8           # el cierre se queda en pantalla tras la última frase


# ---------------------------------------------------------------- utilidades

def leer_env():
    """Lee .env del repo (tolera el BOM/UTF-16 que deja PowerShell)."""
    ruta = REPO / ".env"
    if not ruta.exists():
        return {}
    crudo = ruta.read_bytes()
    for codif in ("utf-8-sig", "utf-16"):
        try:
            texto = crudo.decode(codif)
            break
        except UnicodeDecodeError:
            continue
    else:
        return {}
    valores = {}
    for linea in texto.splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            k, v = linea.split("=", 1)
            valores[k.strip()] = v.strip().strip('"').strip("'")
    return valores


ENV = leer_env()


def clave(nombre):
    return os.getenv(nombre) or ENV.get(nombre)


def slug(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:40] or "video"


def descargar(url, destino):
    req = urllib.request.Request(url, headers={"User-Agent": "quehay-expediente/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        destino.write_bytes(r.read())


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def duracion_wav(ruta):
    with wave.open(str(ruta)) as w:
        return w.getnframes() / w.getframerate()


def carpeta_de(arg):
    p = Path(arg)
    if not p.exists():
        p = VIDEOS / arg
    if not (p / "guion.txt").exists():
        sys.exit(f"No encuentro guion.txt en {p}")
    return p.resolve()


# ---------------------------------------------------------------- nuevo

def cmd_nuevo(consulta):
    if not CATALOGO.exists():
        sys.exit(f"No encuentro el catálogo local en {CATALOGO}")
    items = json.loads(CATALOGO.read_text(encoding="utf-8"))
    if consulta.isdigit():
        hallados = [x for x in items if str(x.get("id")) == consulta]
    else:
        q = slug(consulta)
        hallados = [x for x in items if q in slug(x.get("titulo", ""))]
    if not hallados:
        sys.exit("No está en el catálogo. Prueba con el id de la web (el número de ?contenido=).")
    if len(hallados) > 1:
        print("Hay varios resultados, usa el id:")
        for x in hallados[:15]:
            print(f"  {x['id']}: {x['titulo']} ({x.get('año')}) · {x.get('tipo')}")
        return
    item = hallados[0]
    carpeta = VIDEOS / f"{item['id']}-{slug(item['titulo'])}"
    assets = carpeta / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    imagenes = []
    poster = item.get("imagen_url") or ""
    if poster:
        grande = re.sub(r"/t/p/w\d+/", "/t/p/original/", poster)
        descargar(grande, assets / "poster.jpg")
    tmdb_key = clave("TMDB_API_KEY")
    if tmdb_key and item.get("tmdb_id"):
        media = "movie" if item.get("tipo") == "pelicula" else "tv"
        url = (f"https://api.themoviedb.org/3/{media}/{int(item['tmdb_id'])}/images?"
               + urllib.parse.urlencode({"api_key": tmdb_key, "include_image_language": "null"}))
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                fondos = json.load(r).get("backdrops", [])
            fondos.sort(key=lambda b: (b.get("vote_count", 0), b.get("width", 0)), reverse=True)
            for i, b in enumerate(fondos[:8], 1):
                nombre = f"fondo{i}.jpg"
                descargar("https://image.tmdb.org/t/p/w1280" + b["file_path"], assets / nombre)
                imagenes.append(nombre)
        except Exception as e:  # sin fondos el video usa recortes del póster
            print("Aviso: no pude bajar fondos de TMDB:", e)
    else:
        print("Aviso: sin TMDB_API_KEY en .env; el video usará recortes del póster.")

    datos = {
        "id": item["id"], "titulo": item["titulo"], "año": item.get("año"),
        "genero": item.get("genero") or "", "rating": item.get("rating"),
        "tipo": item.get("tipo"), "sinopsis": item.get("sinopsis") or "",
        "poster": "poster.jpg" if poster else None, "imagenes": imagenes,
        "enlace": f"https://app.{WEB}/?contenido={item['id']}",
    }
    (carpeta / "datos.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    guion = carpeta / "guion.txt"
    if not guion.exists():
        guion.write_text(PLANTILLA_GUION.format(**datos), encoding="utf-8")
    print(f"Listo: {carpeta}\nAhora escribe el guion en {guion}")


PLANTILLA_GUION = """# EXPEDIENTE N.º {id} · {titulo} ({año})
# Sinopsis del catálogo: {sinopsis}
#
# Escenas: @portada · @sujeto NOMBRE | DATO · @evidencia LETRA | ETIQUETA
#          @censura TEXTO con [[parte secreta]] · @cierre
# Voz:     [emocion:intensidad] frase   (una frase por línea)
# Emociones: neutral tristeza alegria ira miedo asco sorpresa desprecio asombro
#            desaprobacion remordimiento indignacion desesperacion
# Intensidad: muy_suave suave normal fuerte extrema

@portada
[sorpresa:fuerte] Gancho de una línea.

@cierre
[neutral] El expediente completo está en Qué Hay Cine. Link en mi perfil.
"""


# ---------------------------------------------------------------- guion

def leer_guion(carpeta):
    escenas = []
    for n, bruto in enumerate((carpeta / "guion.txt").read_text(encoding="utf-8-sig").splitlines(), 1):
        linea = bruto.strip()
        if not linea or linea.startswith("#"):
            continue
        if linea.startswith("@"):
            tipo, _, resto = linea[1:].partition(" ")
            tipo = tipo.lower()
            if tipo not in ("portada", "sujeto", "evidencia", "censura", "cierre"):
                sys.exit(f"guion.txt línea {n}: escena desconocida @{tipo}")
            escenas.append({"tipo": tipo, "args": [a.strip() for a in resto.split("|")] if resto else [], "frases": []})
            continue
        if not escenas:
            sys.exit(f"guion.txt línea {n}: la primera escena debe empezar con @portada")
        m = re.match(r"\[([a-zñáéíóú_]+)(?::([a-z_]+))?\]\s*(.+)", linea, re.I)
        emo, inten, texto = ("neutral", None, linea) if not m else (m.group(1).lower(), m.group(2), m.group(3))
        emo = unicodedata.normalize("NFKD", emo).encode("ascii", "ignore").decode()
        if emo not in EMOCIONES:
            sys.exit(f"guion.txt línea {n}: emoción '{emo}' no existe. Usa: {', '.join(EMOCIONES)}")
        if inten and inten.lower() not in INTENSIDADES:
            sys.exit(f"guion.txt línea {n}: intensidad '{inten}' no existe. Usa: {', '.join(INTENSIDADES)}")
        escenas[-1]["frases"].append({"emocion": emo, "intensidad": (inten or "normal").lower(), "texto": texto.strip()})
    vacias = [e["tipo"] for e in escenas if not e["frases"]]
    if vacias:
        sys.exit(f"Estas escenas no tienen frases de voz: {', '.join(vacias)}")
    return escenas


# ---------------------------------------------------------------- voz

def generar_frase(frase, destino):
    k = clave("VOICE_API_KEY")
    if not k:
        sys.exit("Falta VOICE_API_KEY en .env")
    cuerpo = {"voice_id": VOZ_ID, "target_text": frase["texto"], "language": "Spanish"}
    if frase["emocion"] != "neutral":
        cuerpo.update(emotion=EMOCIONES[frase["emocion"]], intensity=INTENSIDADES[frase["intensidad"]])
    req = urllib.request.Request(f"{VOZ_API}/api/v1/generation/clone?sync=true", data=json.dumps(cuerpo).encode(),
                                 headers={"X-API-Key": k, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            res = json.load(r)
    except urllib.error.URLError as e:
        sys.exit(f"No pude hablar con Voice Creator Pro en {VOZ_API} ({e}). ¿Está abierta la app?")
    if not res.get("success"):
        sys.exit(f"Voice Creator Pro falló: {res.get('error_detail') or res.get('status')}")
    bruto = destino.with_suffix(".raw.wav")
    bruto.write_bytes(base64.b64decode(res["audio_base64"]))
    # Recorta silencios del principio y del final para que el ritmo lo marquen las pausas del script.
    corte = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.04"
    ffmpeg("-i", str(bruto), "-af", f"{corte},areverse,{corte},areverse", "-ar", "48000", "-ac", "1",
           "-c:a", "pcm_s16le", str(destino))
    bruto.unlink()


def cmd_voz(carpeta):
    escenas = leer_guion(carpeta)
    cache = carpeta / "voz"
    cache.mkdir(exist_ok=True)
    total = sum(len(e["frases"]) for e in escenas)
    hecho = 0
    for e in escenas:
        for f in e["frases"]:
            h = hashlib.sha1(json.dumps([VOZ_ID, f["emocion"], f["intensidad"], f["texto"]]).encode()).hexdigest()[:12]
            f["archivo"] = cache / f"{h}.wav"
            hecho += 1
            if f["archivo"].exists():
                print(f"  [{hecho}/{total}] (ya estaba) {f['texto'][:60]}")
                continue
            print(f"  [{hecho}/{total}] {f['emocion']}:{f['intensidad']} {f['texto'][:60]}")
            generar_frase(f, f["archivo"])

    # Une las frases con pausas y calcula los tiempos de cada palabra.
    rate = 48000
    cursor = INICIO
    tiempos = []
    pcm = bytearray(b"\x00\x00" * int(INICIO * rate))
    for i, e in enumerate(escenas):
        if i:
            pcm += b"\x00\x00" * int((PAUSA_ESCENA - PAUSA_LINEA) * rate)
            cursor += PAUSA_ESCENA - PAUSA_LINEA
        escena = {"tipo": e["tipo"], "args": e["args"], "inicio": round(cursor, 3), "frases": []}
        for j, f in enumerate(e["frases"]):
            if j or i:
                pcm += b"\x00\x00" * int(PAUSA_LINEA * rate)
                cursor += PAUSA_LINEA
            with wave.open(str(f["archivo"])) as w:
                cuadros = w.readframes(w.getnframes())
                dur = w.getnframes() / w.getframerate()
            pcm += cuadros
            escena["frases"].append({"texto": f["texto"], "inicio": round(cursor, 3), "fin": round(cursor + dur, 3),
                                     "palabras": repartir_palabras(f["texto"], cursor, dur)})
            cursor += dur
        tiempos.append(escena)
    crudo = carpeta / "voz_cruda.wav"
    with wave.open(str(crudo), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(bytes(pcm))
    assets = carpeta / "assets"
    assets.mkdir(exist_ok=True)
    ffmpeg("-i", str(crudo), "-af", "loudnorm=I=-15:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "1", str(assets / "voz.wav"))
    crudo.unlink()
    (carpeta / "tiempos.json").write_text(json.dumps({"duracion_voz": round(cursor, 3), "escenas": tiempos},
                                                     ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Voz lista: {cursor:.1f} s de audio")


def repartir_palabras(texto, inicio, dur):
    """Reparte la duración de la frase entre sus palabras según su largo y la puntuación."""
    palabras = texto.split()
    pesos = []
    for p in palabras:
        peso = len(re.sub(r"[^\wáéíóúñü]", "", p, flags=re.I)) + 1.5
        if re.search(r"[,;:]$", p):
            peso += 3
        if re.search(r"(\.\.\.|…|[.?!])$", p):
            peso += 5
        pesos.append(peso)
    total = sum(pesos) or 1
    t = inicio
    salida = []
    for p, peso in zip(palabras, pesos):
        d = dur * peso / total
        salida.append({"texto": p, "inicio": round(t, 3), "fin": round(t + d, 3)})
        t += d
    return salida


# ---------------------------------------------------------------- video

def cmd_video(carpeta, borrador=False):
    if not (carpeta / "tiempos.json").exists():
        sys.exit("Primero genera la voz: python tiktok/expediente.py voz <carpeta>")
    datos = json.loads((carpeta / "datos.json").read_text(encoding="utf-8"))
    tiempos = json.loads((carpeta / "tiempos.json").read_text(encoding="utf-8"))
    proyecto = carpeta / "proyecto"
    # Solo se reemplazan los assets; .hyperframes/ (cachés y revisiones) se conserva.
    shutil.rmtree(proyecto / "assets", ignore_errors=True)
    shutil.copytree(carpeta / "assets", proyecto / "assets")
    shutil.copytree(PLANTILLA.parent / "fonts", proyecto / "assets" / "fonts", dirs_exist_ok=True)
    (proyecto / "hyperframes.json").write_text(json.dumps({"paths": {"assets": "assets"}, "authoringSkill": "hyperframes"}))
    (proyecto / "meta.json").write_text(json.dumps({"id": carpeta.name, "name": datos["titulo"]}))
    (proyecto / "index.html").write_text(componer(datos, tiempos), encoding="utf-8")

    npx = preparar_node()
    salida = carpeta / f"{carpeta.name}.mp4"
    print("Revisando la composición…")
    subprocess.run([npx, "hyperframes", "check", str(proyecto)], check=False)
    if "--sin-render" in sys.argv:
        print(f"Composición lista en {proyecto} (sin render). Vista previa: npx hyperframes preview \"{proyecto}\"")
        return
    print("Renderizando (tarda unos minutos)…")
    subprocess.run([npx, "hyperframes", "render", str(proyecto), "-o", str(salida),
                    "--quality", "draft" if borrador else "delivery", "--skill=hyperframes"], check=True)
    print(f"\nVideo listo: {salida}")


def preparar_node():
    """HyperFrames necesita Node 22+. Si el Node del sistema es viejo, usa uno de nvm/Herd."""
    def mayor(exe):
        try:
            return int(subprocess.run([exe, "-v"], capture_output=True, text=True).stdout.strip().lstrip("v").split(".")[0])
        except Exception:
            return 0
    if mayor("node") >= 22:
        return shutil.which("npx") or "npx"
    candidatos = sorted(Path.home().glob(".config/herd/bin/nvm/v*/node.exe"), reverse=True)
    candidatos += sorted(Path(os.getenv("APPDATA", "")).glob("nvm/v*/node.exe"), reverse=True)
    for exe in candidatos:
        if mayor(str(exe)) >= 22:
            os.environ["PATH"] = str(exe.parent) + os.pathsep + os.environ["PATH"]
            return str(exe.parent / ("npx.cmd" if os.name == "nt" else "npx"))
    sys.exit("HyperFrames necesita Node 22 o superior y no encontré ninguno.")


E = html.escape


def componer(datos, tiempos):
    escenas = tiempos["escenas"]
    total = round(tiempos["duracion_voz"] + COLA, 2)
    for i, e in enumerate(escenas):
        e["ini"] = 0.0 if i == 0 else round(e["inicio"] - 0.12, 3)
    for i, e in enumerate(escenas):
        e["fin"] = escenas[i + 1]["ini"] if i + 1 < len(escenas) else total
        e["dur"] = round(e["fin"] - e["ini"], 3)

    fondos = list(datos.get("imagenes") or [])
    poster = datos.get("poster")
    encuadres = ["50% 18%", "50% 55%", "50% 82%", "30% 40%", "70% 40%"]
    usados = {"n": 0}

    def siguiente_imagen(elegida=None):
        """El guion puede pedir un fondo concreto (3.er campo: fondo4); si no, van en orden."""
        if elegida:
            nombre = elegida if elegida.endswith(".jpg") else elegida + ".jpg"
            if nombre in fondos or nombre == poster:
                return nombre, "50% 50%"
            print(f"Aviso: el guion pide {nombre}, que no existe; uso el siguiente fondo.")
        n = usados["n"]; usados["n"] += 1
        if fondos:
            return fondos[n % len(fondos)], "50% 50%"
        return poster, encuadres[n % len(encuadres)]

    num = f"{int(datos['id']):04d}"
    paginas, js = [], []
    for i, e in enumerate(escenas):
        pid = f"b{i}"
        ini, fin, dur = e["ini"], e["fin"], e["dur"]
        cuerpo, anim = ESCENAS[e["tipo"]](pid, e, datos, num, siguiente_imagen, ini, dur)
        paginas.append(
            f'<div id="{pid}" class="clip page" data-start="{ini}" data-duration="{dur}" data-track-index="2" '
            f'data-layout-allow-overlap data-layout-allow-overflow><div id="{pid}-sheet" class="sheet">{cuerpo}</div></div>')
        if i:  # entra como una hoja nueva que se desliza sobre la carpeta
            js.append(f'tl.fromTo("#{pid}-sheet",{{x:150,rotation:2.5,opacity:0}},{{x:0,rotation:0,opacity:1,duration:0.5,ease:"expo.out"}},{ini});')
        if i + 1 < len(escenas):
            js.append(f'tl.to("#{pid}-sheet",{{x:-170,rotation:-3,opacity:0,duration:0.22,ease:"power3.in"}},{round(fin - 0.24, 3)});')
        js.extend(anim)

    subtitulos, js_sub = componer_subtitulos(escenas)
    js.extend(js_sub)
    plantilla = PLANTILLA.read_text(encoding="utf-8")
    return (plantilla.replace("{{DURACION}}", str(total)).replace("{{DURACION_VOZ}}", str(tiempos["duracion_voz"])).replace("{{NUM}}", num)
            .replace("{{TITULO}}", E(datos["titulo"])).replace("{{PAGINAS}}", "\n".join(paginas))
            .replace("{{SUBTITULOS}}", "\n".join(subtitulos)).replace("{{JS}}", "\n".join(js)))


def tecleo(sel, texto, t, vel=0.028):
    """Revela un texto de izquierda a derecha como si lo escribiera una máquina."""
    n = max(4, len(texto))
    return f'tl.fromTo("{sel}",{{clipPath:"inset(0 100% 0 0)"}},{{clipPath:"inset(0 0% 0 0)",duration:{round(n * vel, 2)},ease:"steps({n})"}},{round(t, 3)});'


def sello(sel, t, giro):
    return (f'tl.fromTo("{sel}",{{scale:2.3,opacity:0,rotation:{giro}}},'
            f'{{scale:1,opacity:0.94,rotation:{giro},duration:0.2,ease:"power4.in"}},{round(t, 3)});')


def foto(pid, imagen, encuadre, ini, dur, clase="photo"):
    src, pos = imagen
    return (f'<div class="{clase}"><img id="{pid}-img" src="assets/{E(src)}" style="object-position:{pos}" alt=""></div>',
            f'tl.fromTo("#{pid}-img",{{scale:1.07,x:-14}},{{scale:1.17,x:14,duration:{dur},ease:"none"}},{ini});')


def escena_portada(pid, e, d, num, img, ini, dur):
    anio = d.get("año") or ""
    genero = ", ".join([g.strip() for g in re.split(r"[,/]", d.get("genero") or "") if g.strip()][:2]).upper()
    nota = f"{d['rating']:.1f}/10" if isinstance(d.get("rating"), (int, float)) else "—"
    f_html, f_js = foto(pid, (d.get("poster"), "50% 50%"), None, ini, dur, "photo poster")
    campos = [("AÑO", str(anio)), ("GÉNERO", genero), ("NOTA", nota)]
    filas = "".join(f'<div id="{pid}-c{k}" class="field"><span>{E(a)}:</span> {E(b)}</div>' for k, (a, b) in enumerate(campos))
    cuerpo = (f'{f_html}<div class="col"><div class="kicker">ARCHIVO N.º {num}</div>'
              f'<div class="title">{E(d["titulo"])}</div>{filas}</div>'
              f'<div id="{pid}-st" class="stamp big" data-layout-allow-occlusion>CLASIFICADO</div>'
              f'<div class="foot">Abierto por: Qué Hay Cine</div>')
    # El primer fotograma es la miniatura: la ficha ya está escrita y el sello cae enseguida.
    js = [f_js, sello(f"#{pid}-st", ini + 0.12, -13)]
    return cuerpo, js


def escena_sujeto(pid, e, d, num, img, ini, dur):
    nombre = e["args"][0] if e["args"] else "Desconocido"
    dato = e["args"][1] if len(e["args"]) > 1 else ""
    f_html, f_js = foto(pid, img(e["args"][2] if len(e["args"]) > 2 else None), None, ini, dur, "photo wide")
    cuerpo = (f'{f_html}<div id="{pid}-pin" class="pin"></div>'
              f'<div class="lbl" style="top:600px">SUJETO</div><div id="{pid}-n" class="name">{E(nombre)}</div>'
              f'<div class="lbl" style="top:745px">ESTADO</div><div id="{pid}-d" class="state">{E(dato)}</div>')
    js = [f_js, tecleo(f"#{pid}-n", nombre, ini + 0.45, 0.04), tecleo(f"#{pid}-d", dato, ini + 0.9, 0.022)]
    return cuerpo, js


def escena_evidencia(pid, e, d, num, img, ini, dur):
    letra = e["args"][0] if e["args"] else "A"
    nota = e["args"][1] if len(e["args"]) > 1 else ""
    f_html, f_js = foto(pid, img(e["args"][2] if len(e["args"]) > 2 else None), None, ini, dur, "shot")
    giro = -3 if (ord(letra[:1] or "A") % 2) else 3
    cuerpo = (f'<div id="{pid}-pol" class="polaroid">{f_html}<div id="{pid}-note" class="note">{E(nota)}</div></div>'
              f'<div id="{pid}-tag" class="stamp tag">EVIDENCIA {E(letra.upper())}</div>')
    js = [f_js,
          f'tl.fromTo("#{pid}-pol",{{y:-70,rotation:{giro * 3},opacity:0}},{{y:0,rotation:{giro},opacity:1,duration:0.55,ease:"expo.out"}},{ini + 0.05});',
          sello(f"#{pid}-tag", ini + 0.55, 7), tecleo(f"#{pid}-note", nota, ini + 0.8)]
    return cuerpo, js


def escena_censura(pid, e, d, num, img, ini, dur):
    texto = e["args"][0] if e["args"] else "[[INFORMACIÓN CLASIFICADA]]"
    partes = re.split(r"(\[\[.+?\]\])", texto)
    palabras_html, barras, k = [], [], 0
    for p in partes:
        if not p:
            continue
        secreto = p.startswith("[[")
        for w in (p[2:-2] if secreto else p).split():
            wid = f"{pid}-w{k}"
            if secreto:
                palabras_html.append(f'<span id="{wid}" class="w secret">{E(w)}<i id="{wid}-bar" class="bar"></i></span>')
                barras.append(f"#{wid}-bar")
            else:
                palabras_html.append(f'<span id="{wid}" class="w">{E(w)}</span>')
            k += 1
    cuerpo = (f'<div class="kicker red" style="top:70px">INFORMACIÓN CLASIFICADA · EXP. {num}</div>'
              f'<div class="redacted">{" ".join(palabras_html)}</div>'
              f'<div class="lines"></div>')
    js = [f'tl.fromTo("#{pid} .w",{{opacity:0.08}},{{opacity:1,duration:0.08,stagger:0.09,ease:"none"}},{ini + 0.35});']
    t_barras = ini + 0.35 + k * 0.09 + 0.5
    for n, b in enumerate(barras):
        js.append(f'tl.fromTo("{b}",{{scaleX:0}},{{scaleX:1,duration:0.16,ease:"power3.out"}},{round(t_barras + n * 0.07, 3)});')
    return cuerpo, js


def escena_cierre(pid, e, d, num, img, ini, dur):
    f_html, f_js = foto(pid, (d.get("poster"), "50% 50%"), None, ini, dur, "photo mini")
    cuerpo = (f'<div id="{pid}-st" class="stamp open">CASO ABIERTO</div>{f_html}'
              f'<div class="cta"><div id="{pid}-l1" class="cta1">Expediente completo en</div>'
              f'<div id="{pid}-l2" class="cta2">{WEB.upper()}</div>'
              f'<div id="{pid}-l3" class="cta3">Link en mi perfil</div></div>')
    js = [f_js, sello(f"#{pid}-st", ini + 0.3, -8),
          tecleo(f"#{pid}-l1", "Expediente completo en", ini + 0.6),
          f'tl.fromTo("#{pid}-l2",{{opacity:0,filter:"blur(8px)"}},{{opacity:1,filter:"blur(0px)",duration:0.2,ease:"power4.out"}},{ini + 1.35});',
          tecleo(f"#{pid}-l3", "Link en mi perfil", ini + 1.7)]
    return cuerpo, js


ESCENAS = {"portada": escena_portada, "sujeto": escena_sujeto, "evidencia": escena_evidencia,
           "censura": escena_censura, "cierre": escena_cierre}


def componer_subtitulos(escenas):
    """Grupos de 2-3 palabras; la palabra que suena se pinta de amarillo."""
    grupos = []
    for e in escenas:
        for f in e["frases"]:
            grupo = []
            pals = f["palabras"]
            for k, p in enumerate(pals):
                grupo.append(p)
                if re.search(r"[,.;:?!…]$", p["texto"]) or len(grupo) == 3 or k == len(pals) - 1:
                    ini = max(0.1, round(grupo[0]["inicio"] - 0.06, 3))
                    fin = round(grupo[-1]["fin"] + (0.15 if k == len(pals) - 1 else 0.0), 3)
                    grupos.append([ini, fin, grupo])
                    grupo = []
    for a, b in zip(grupos, grupos[1:]):  # nunca dos grupos en pantalla a la vez
        a[1] = min(a[1], b[0])
    html_g, js = [], []
    for n, (ini, fin, grupo) in enumerate(grupos):
        gid = f"cap{n}"
        texto = " ".join(x["texto"] for x in grupo)
        tam = min(84, int(900 / (0.74 * max(8, len(texto)))))
        spans = " ".join(f'<span id="{gid}-{m}" class="cw">{E(x["texto"])}</span>' for m, x in enumerate(grupo))
        html_g.append(f'<div id="{gid}" class="clip cap" data-start="{ini}" data-duration="{round(fin - ini, 3)}" '
                      f'data-track-index="5"><div id="{gid}-in" class="capin" style="font-size:{tam}px">{spans}</div></div>')
        js.append(f'tl.fromTo("#{gid}-in",{{scale:0.86,opacity:0}},{{scale:1,opacity:1,duration:0.12,ease:"back.out(2)"}},{ini});')
        for m, x in enumerate(grupo):
            js.append(f'tl.set("#{gid}-{m}",{{color:"#e8c581"}},{x["inicio"]});')
            if m < len(grupo) - 1:
                js.append(f'tl.set("#{gid}-{m}",{{color:"#edf3fc"}},{x["fin"]});')
    return html_g, js


# ---------------------------------------------------------------- main

def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, arg = sys.argv[1], sys.argv[2]
    borrador = "--borrador" in sys.argv
    if cmd == "nuevo":
        cmd_nuevo(" ".join(a for a in sys.argv[2:] if not a.startswith("--")))
    elif cmd == "voz":
        cmd_voz(carpeta_de(arg))
    elif cmd == "video":
        cmd_video(carpeta_de(arg), borrador)
    elif cmd == "todo":
        c = carpeta_de(arg)
        cmd_voz(c)
        cmd_video(c, borrador)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
