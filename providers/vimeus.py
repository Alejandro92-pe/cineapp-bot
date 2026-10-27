"""Strict adapter for Vimeus Listing API (not Vimeo).

The listing API key is private; the iframe view key is a different credential.
No redirects are followed with credentials and no provider URL is trusted as an embed.
"""
import time
import requests


class ImportFailure(ValueError):
    pass


def integer(value, minimum=0):
    if isinstance(value, bool) or not str(value).isdigit():
        raise ImportFailure("El proveedor devolvió una numeración inválida.")
    number = int(value)
    if not minimum <= number <= 2147483647:
        raise ImportFailure("Numeración fuera del rango permitido.")
    return number


class VimeusClient:
    BASE = "https://vimeus.com/api/listing"

    def __init__(self, api_key, transport=None):
        self.api_key = api_key
        self.transport = transport or requests.Session()

    def page(self, resource, page=1, **filters):
        if not self.api_key:
            raise ImportFailure("Falta VIMEUS_API_KEY en el servidor. La clave del reproductor no sirve para listar capítulos.")
        if resource not in ("movies", "series", "animes", "episodes"):
            raise ImportFailure("Listado no permitido.")
        page = integer(page, 1)
        for attempt in range(2):
            try:
                response = self.transport.get(f"{self.BASE}/{resource}",
                    params={**filters, "page": page}, headers={"X-API-Key": self.api_key},
                    timeout=(5, 15), allow_redirects=False)
            except requests.RequestException:
                if attempt == 0:
                    continue
                raise ImportFailure("Vimeus no respondió. No se guardaron cambios.") from None
            if response.status_code in (429, 502, 503, 504) and attempt == 0:
                continue
            if response.status_code in (401, 403):
                raise ImportFailure("Vimeus rechazó la clave de listado. Revisa su permiso en el servidor.")
            if response.status_code == 404:
                raise ImportFailure("Vimeus no encontró este listado. No se guardaron cambios.")
            if response.status_code != 200:
                raise ImportFailure("El listado de Vimeus no está disponible. Intenta de nuevo.")
            try:
                payload = response.json()
                data = payload["data"]
                # The live API also serves a compact envelope, unlike the docs.
                if 'result' in data and 'pages' in data:
                    rows = data['result']
                    total = integer(data['pages'])
                    if payload.get('error') is not False or not isinstance(rows, list) or len(rows)>5000 or any(not isinstance(row,dict) for row in rows):
                        raise ValueError()
                    if page>max(total,1) or (not rows and total>0) or (rows and total==0):
                        raise ValueError()
                    return rows, {'current_page':page,'total_pages':total,'total_results':None,
                                  'has_next':page<total,'format':'compact'}
                rows, pagination = data[resource], data["pagination"]
                if payload.get("error") is not False or not isinstance(rows, list) or not isinstance(pagination, dict):
                    raise ValueError()
                current = integer(pagination["current_page"], 1)
                total = integer(pagination["total_pages"])
                count = integer(pagination["total_results"])
                if current != page or type(pagination["has_next"]) is not bool or pagination["has_next"] != (page < total):
                    raise ValueError()
                if integer(pagination["per_page"], 1) != 50 or len(rows) > 50 or (not rows and count):
                    raise ValueError()
                if total != (count + 49) // 50 and not (count == 0 and total == 1):
                    raise ValueError()
                expected = min(50, max(0, count - (page-1)*50))
                if len(rows) != expected or any(not isinstance(row, dict) for row in rows):
                    raise ValueError()
                return rows, pagination
            except (ValueError, TypeError, KeyError):
                raise ImportFailure("El formato o la paginación de Vimeus cambió. Se canceló la importación.") from None

    def episodes(self, tmdb_id, kind):
        if kind not in ("serie", "anime"):
            raise ImportFailure("Selecciona serie o anime.")
        expected_kind = {"serie": "series", "anime": "anime"}.get(kind)
        result, seen, provider_ids = [], set(), set()
        totals, deadline = None, time.monotonic() + 90
        for page in range(1, 101):
            if time.monotonic() >= deadline:
                raise ImportFailure("El listado tardó demasiado. Se canceló sin guardar cambios.")
            rows, pagination = self.page("episodes", page, tmdb_id=integer(tmdb_id, 1))
            snapshot = (pagination["total_pages"], pagination["total_results"])
            if totals is not None and totals != snapshot:
                raise ImportFailure("El catálogo cambió durante la lectura. Reintenta para obtenerlo completo.")
            totals = snapshot
            for row in rows:
                content_type = row.get("content_type") or row.get('parent_type')
                if content_type != expected_kind:
                    raise ImportFailure("El tipo devuelto no coincide. Revisa si el ID corresponde a serie o anime.")
                if integer(row.get("tmdb_id"), 1) != int(tmdb_id):
                    raise ImportFailure("El proveedor mezcló capítulos de otro título.")
                key = (integer(row.get("season")), integer(row.get("episode"), 1))
                provider_id = integer(row['id'], 1) if row.get('id') is not None else None
                if key in seen or (provider_id is not None and provider_id in provider_ids):
                    raise ImportFailure("Vimeus devolvió capítulos duplicados. No se guardaron cambios.")
                seen.add(key)
                if provider_id is not None: provider_ids.add(provider_id)
                result.append({**row, 'title':row.get('title') or row.get('show_title'), "season": key[0], "episode": key[1], "id": provider_id})
                if len(result)>5000: raise ImportFailure('El título supera 5.000 capítulos. No se guardaron cambios.')
            if not pagination["has_next"]:
                if not result:
                    raise ImportFailure("Vimeus todavía no tiene capítulos para este ID de TMDB.")
                return sorted(result, key=lambda row: (row["season"], row["episode"]))
        raise ImportFailure("El título supera 5.000 capítulos. Se canceló sin guardar un listado parcial.")
