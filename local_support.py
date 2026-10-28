"""Explicit offline fixtures. Never import in production."""
import copy
import socket
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace


def block_external_network():
    original = socket.socket.connect
    resolve = socket.getaddrinfo
    def getaddrinfo(host, *args, **kwargs):
        if host not in ("127.0.0.1", "localhost", "::1", None):
            raise RuntimeError("Resolución externa bloqueada en la vista local.")
        return resolve(host, *args, **kwargs)
    def connect(sock, address):
        if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "localhost", "::1"):
            raise RuntimeError("Salida de red bloqueada en la vista local.")
        return original(sock, address)
    socket.socket.connect = connect
    socket.getaddrinfo = getaddrinfo


class LocalBot:
    def __init__(self):
        self.calls = []
    def __getattr__(self, name):
        if name.endswith("handler"):
            return lambda *a, **kw: lambda fn: fn
        def offline(*args, **kwargs):
            self.calls.append(name)
            return SimpleNamespace(invite_link="https://example.org/local-only", message_id=1)
        return offline


class LocalDatabase:
    def __init__(self):
        self.lock = threading.RLock()
        self.reset()
    def reset(self):
        self.catalog_aliases = {}
        self.catalog_merge_archive = []
        now = datetime.now(timezone.utc)
        self.rows = {
            "usuarios": [{"id":1, "telegram_id":900000001, "nombre":"Cuenta de prueba", "email":"demo@example.test",
                "membresia_activa":True, "membresia_tipo":"copper", "fecha_vencimiento":(now+timedelta(days=5)).isoformat(),
                "notificacion_3dias_enviada":False,"notificacion_3horas_enviada":False,"notificacion_vencida_enviada":False}],
            "membresias_planes":[{"id":1,"nombre":"copper","precio_dolares":3.50,"precio_soles":13,
                "duracion_dias":30,"pedidos_por_mes":2}],
            "membresias_activas":[{"id":1,"usuario_id":1,"plan_id":1,"estado":"activa",
                "fecha_inicio":now.isoformat(),"fecha_fin":(now+timedelta(days=5)).isoformat()}],
            "contenido":[{"id":1,"titulo":"Horizonte • contenido de prueba","tipo":"pelicula","genero":"Drama",
                "año":2026,"imagen_url":"/static/placeholder.svg","disponible":True,"destacado":True,
                "orden_destacado":1,"fuente":"vimeus","tmdb_id":1,"rating":8,
                "sinopsis":"Ficha ficticia para comprobar acceso y descargas. No reproduce contenido externo.",
                "descarga":"https://www.mediafire.com/file/local-test/example/file", "enlace_canal":"https://t.me/example/1"}],
            "temporadas":[], "pagos_manuales":[], "pedidos":[], "publicaciones_canal":[]}
    def table(self, name):
        return Query(self, name)

    def rpc(self, name, args):
        from services.local_vimeus import rpc
        return rpc(self, name, args)


class Query:
    def __init__(self, db, name):
        self.db, self.name = db, name
        self.filters, self.operation, self.payload = [], "select", None
        self.columns, self.slice, self.ordering = "*", None, None
        self.negate = False
    def select(self, columns="*", **kwargs):
        self.columns = columns
        return self
    def eq(self, key, value):
        self.filters.append(lambda r: str(r.get(key)) == str(value))
        return self
    def neq(self, key, value):
        self.filters.append(lambda r: r.get(key) != value)
        return self
    def in_(self, key, values):
        self.filters.append(lambda r: r.get(key) in values)
        return self
    def ilike(self, key, value):
        self.filters.append(lambda r: value.strip("%").lower() in str(r.get(key, "")).lower())
        return self
    def gte(self, key, value):
        self.filters.append(lambda r: str(r.get(key, "")) >= str(value))
        return self
    def lte(self, key, value):
        self.filters.append(lambda r: str(r.get(key, "")) <= str(value))
        return self
    def lt(self, key, value):
        self.filters.append(lambda r: r.get(key) is not None and r[key] < value)
        return self
    @property
    def not_(self):
        self.negate = True
        return self
    def is_(self, key, value):
        neg = self.negate
        self.negate = False
        self.filters.append(lambda r: (r.get(key) is None) != neg)
        return self
    def order(self, key, desc=False):
        self.ordering = (key, desc)
        return self
    def limit(self, n):
        self.slice = (0,n)
        return self
    def offset(self, n):
        size = self.slice[1]-self.slice[0] if self.slice else None
        self.slice = (n, n+size if size is not None else None)
        return self
    def range(self, start, end):
        self.slice = (start,end+1)
        return self
    def insert(self, data):
        self.operation, self.payload = "insert", data
        return self
    def upsert(self, data, on_conflict="id"):
        self.operation, self.payload, self.conflict = "upsert", data, on_conflict
        return self
    def update(self, data):
        self.operation, self.payload = "update", data
        return self
    def delete(self):
        self.operation = "delete"
        return self
    def execute(self):
        with self.db.lock:
            rows = self.db.rows.setdefault(self.name, [])
            selected = [r for r in rows if all(fn(r) for fn in self.filters)]
            if self.operation in ("insert", "upsert"):
                existing = next((r for r in rows if r.get(self.conflict)==self.payload.get(self.conflict)), None) if self.operation=="upsert" else None
                if existing is not None:
                    existing.update(self.payload)
                    selected = [existing]
                else:
                    row = copy.deepcopy(self.payload)
                    row.setdefault("id", max([r["id"] for r in rows] or [0])+1)
                    row.setdefault("created_at", datetime.now(timezone.utc).isoformat())
                    rows.append(row)
                    selected = [row]
            elif self.operation == "update":
                for row in selected:
                    row.update(self.payload)
            elif self.operation == "delete":
                self.db.rows[self.name] = [r for r in rows if r not in selected]
            count = len(selected)
            if self.ordering:
                key, reverse = self.ordering
                selected.sort(key=lambda r: r.get(key) or 0, reverse=reverse)
            if self.slice:
                selected = selected[self.slice[0]:self.slice[1]]
            selected = copy.deepcopy(selected)
            if self.columns != "*" and "(" not in self.columns:
                selected = [{k.strip():r.get(k.strip()) for k in self.columns.split(",")} for r in selected]
            return SimpleNamespace(data=selected, count=count)


local_database = LocalDatabase()
