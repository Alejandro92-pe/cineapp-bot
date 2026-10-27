"""Offline provider and transaction double. Never used in production."""
import copy
from types import SimpleNamespace
from providers.vimeus import VimeusClient, ImportFailure


class DemoVimeus(VimeusClient):
    """Same pagination pipeline as production; synthetic data, no network."""
    def __init__(self):
        self.calls = []
        self.items = {900101: ("serie", "Horizonte · Serie de prueba", [(0, 1), (1, 8), (2, 6)]),
                      900202: ("anime", "Órbita · Anime de prueba", [(1, 60), (2, 12)])}

    def page(self, resource, page=1, **filters):
        self.calls.append((resource, page, filters))
        if resource == "episodes":
            value = self.items.get(int(filters["tmdb_id"]))
            if not value:
                raise ImportFailure("Prueba local: usa 900101 para serie o 900202 para anime.")
            kind, title, seasons = value
            rows = [{"id": number*10000+episode, "content_type": "series" if kind == "serie" else "anime",
                "tmdb_id": int(filters["tmdb_id"]), "title": title, "season": number, "episode": episode}
                for number, count in seasons for episode in range(1, count+1)]
        else:
            rows = [{"tmdb_id": tmdb, "title": title, "total_seasons": len(seasons),
                     "total_episodes": sum(n for _, n in seasons)}
                for tmdb, (kind, title, seasons) in self.items.items() if kind == ("serie" if resource == "series" else "anime")]
        return rows[(page-1)*50:page*50], {"current_page": page, "total_pages": (len(rows)+49)//50,
            "total_results": len(rows), "per_page": 50, "has_next": page*50 < len(rows), "has_prev": page > 1}


def apply_local(database, document):
    """Mirror RPC semantics atomically in the isolated local database."""
    with database.lock:
        before = copy.deepcopy(database.rows)
        try:
            c = document["contenido"]
            matches = database.table("contenido").select("*").eq("tipo", c["tipo"]).eq("tmdb_id", c["tmdb_id"]).execute().data
            if len(matches) > 1:
                raise ImportFailure("Hay títulos duplicados; revísalos antes de importar.")
            if matches:
                item = database.table("contenido").update({"fuente": "vimeus", "playback_unverified": False}).eq("id", matches[0]["id"]).execute().data[0]
                if c.get('rating') is not None:
                    database.table('contenido').update({'rating': c['rating']}).eq('id', item['id']).execute()
                if c.get('trailer_url') and not item.get('trailer_url'):
                    database.table('contenido').update({'trailer_url':c['trailer_url']}).eq('id',item['id']).execute()
            else:
                item = database.table("contenido").insert({**c, "fuente": "vimeus", "disponible": True, "destacado": False}).execute().data[0]
            cid, seen = item["id"], set()
            created, updated, removed, total = 0, 0, 0, 0
            for season in document["temporadas"]:
                matches = database.table("temporadas").select("*").eq("contenido_id", cid).eq("numero", season["numero"]).execute().data
                if len(matches) > 1:
                    raise ImportFailure("Hay temporadas duplicadas; revísalas antes de importar.")
                if matches:
                    sid = matches[0]["id"]
                else:
                    s = {k:v for k,v in season.items() if k != "capitulos"}
                    sid = database.table("temporadas").insert({**s, "contenido_id": cid}).execute().data[0]["id"]
                for episode in season["capitulos"]:
                    seen.add((sid, episode["numero"]))
                    found = database.table("episodios").select("*").eq("temporada_id", sid).eq("numero", episode["numero"]).execute().data
                    if found:
                        changes = {k:v for k,v in episode.items() if v is not None and v != ""}
                        if changes["titulo"] == f"Episodio {episode['numero']}":
                            changes.pop("titulo")
                        database.table("episodios").update({**changes, "disponible": True}).eq("id", found[0]["id"]).execute()
                        updated += 1
                    else:
                        database.table("episodios").insert({**episode, "temporada_id": sid, "disponible": True}).execute()
                        created += 1
                    total += 1
            seasons = database.table("temporadas").select("id").eq("contenido_id", cid).execute().data
            for season in seasons:
                active = 0
                for ep in database.rows["episodios"]:
                    if ep["temporada_id"] != season["id"]:
                        continue
                    if (ep["temporada_id"], ep["numero"]) not in seen and ep["disponible"]:
                        ep["disponible"] = False
                        removed += 1
                    active += int(ep["disponible"])
                database.table("temporadas").update({"episodios": active}).eq("id", season["id"]).execute()
            return {"contenido_id": cid, "titulo": item["titulo"], "temporadas": len(document["temporadas"]),
                    "episodios": total, "creados": created, "actualizados": updated, "retirados": removed}
        except Exception:
            database.rows = before
            raise


def rpc(database, name, args):
    if name != "importar_vimeus":
        raise ValueError("Unsupported local RPC")
    return SimpleNamespace(execute=lambda: SimpleNamespace(data=apply_local(database, args["documento"])))
