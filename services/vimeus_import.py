"""Read and validate a complete snapshot before a single atomic persistence call."""
from collections import defaultdict
import time
from urllib.parse import urlsplit, parse_qs
from providers.tmdb import trailer_url, tmdb_rating
from providers.vimeus import ImportFailure, integer
from services.episode_numbering import metadata_episode


def image_url(path):
    if isinstance(path, str) and path.startswith("/") and not path.startswith("//") and "\\" not in path:
        return "https://image.tmdb.org/t/p/w500" + path
    return ""


def provider_download(row, tmdb_id, kind):
    """Accept only a matching provider download, never its embed or arbitrary URL."""
    value = row.get('download_url')
    if not isinstance(value,str) or len(value)>4096: return None
    url = urlsplit(value)
    query = parse_qs(url.query)
    if (url.scheme!='https' or url.netloc not in ('vimeus.com','www.vimeus.com')
        or url.path not in (('/d/series','/d/serie') if kind=='serie' else ('/d/anime','/d/animes'))
        or query.get('tmdb')!=[str(tmdb_id)] or query.get('se')!=[str(row['season'])]
        or query.get('ep')!=[str(row['episode'])]): return None
    return value


def build_manifest(provider, tmdb_id, kind, tmdb_get=None, metadata_seconds=20):
    tmdb_id = integer(tmdb_id, 1)
    rows = provider.episodes(tmdb_id, kind)
    first = rows[0]
    content = {"tmdb_id": tmdb_id, "tipo": kind, "titulo": str(first.get("title") or f"TMDB {tmdb_id}")[:500],
               "imagen_url": image_url(first.get("poster")), "backdrop_url": image_url(first.get('backdrop')).replace('/w500','/w1280'), "sinopsis": "", "genero": ""}
    warnings = []
    metadata = {}
    metadata_deadline = time.monotonic() + metadata_seconds
    if tmdb_get:
        try:
            metadata = tmdb_get(f"/tv/{tmdb_id}")
            content.update(titulo=metadata.get("name") or content["titulo"],
                sinopsis=metadata.get("overview") or "", imagen_url=image_url(metadata.get("poster_path")) or content["imagen_url"],
                genero=", ".join(g["name"] for g in metadata.get("genres", []) if g.get("name")))
            rating = tmdb_rating(metadata)
            if rating is not None:
                content['rating'] = rating
        except Exception:
            metadata = {}
            warnings.append("TMDB no respondió: se conservaron los datos del listado de Vimeus.")
        trailer = trailer_url(tmdb_get, 'tv', tmdb_id)
        if trailer: content['trailer_url'] = trailer
    groups = defaultdict(list)
    for row in rows:
        groups[row["season"]].append(row)
    season_metadata = {s["season_number"]: s for s in metadata.get("seasons", []) if "season_number" in s}
    seasons = []
    for number, episodes in sorted(groups.items()):
        info = season_metadata.get(number, {})
        details = {}
        if tmdb_get and time.monotonic() < metadata_deadline:
            try:
                details = {e["episode_number"]: e for e in tmdb_get(f"/tv/{tmdb_id}/season/{number}").get("episodes", [])}
            except Exception:
                warnings.append(f"Temporada {number}: títulos descriptivos de TMDB pendientes; capítulos importados desde Vimeus.")
        elif tmdb_get:
            warning = "Se limitó la consulta de descripciones de TMDB por tiempo; todos los capítulos de Vimeus se conservaron."
            if warning not in warnings:
                warnings.append(warning)
        normalized = []
        for row in episodes:
            extra = details.get(metadata_episode(tmdb_id, number, row['episode'],details.keys()), {})
            normalized.append({"numero": row["episode"], "vimeus_id": row["id"],
                "provider_download_url": provider_download(row, tmdb_id, kind),
                "titulo": extra.get("name") or f"Episodio {row['episode']}",
                "sinopsis": extra.get("overview") or "", "imagen_url": image_url(extra.get("still_path")),
                "duracion": extra.get("runtime") if isinstance(extra.get("runtime"), int) and extra["runtime"] > 0 else None})
        seasons.append({"numero": number, "nombre": info.get("name") or ("Especiales" if number == 0 else f"Temporada {number}"),
            "poster_url": image_url(info.get("poster_path")) or content["imagen_url"], "descripcion": info.get("overview") or "",
            "capitulos": normalized})
    return {"contenido": content, "temporadas": seasons}, warnings


class ImportRepository:
    def __init__(self, database):
        self.database = database

    def apply(self, manifest):
        # Supabase RPC executes the complete snapshot in ONE PostgreSQL transaction.
        # The local adapter exposes the same contract and never contacts Supabase.
        return self.database.rpc("importar_vimeus", {"documento": manifest}).execute().data


def import_title(provider, repository, tmdb_id, kind, tmdb_get=None):
    manifest, warnings = build_manifest(provider, tmdb_id, kind, tmdb_get)
    result = repository.apply(manifest)
    return {**result, "warnings": warnings, "success": True}
