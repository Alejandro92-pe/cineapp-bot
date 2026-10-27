"""Persist completed manual imports in the isolated preview only."""
import copy,json
from services.local_vimeus import apply_local

def apply_saved(db,doc):
    with db.lock:
        before=copy.deepcopy(db.rows)
        try:
            result=apply_local(db,doc)
            path=getattr(db,'manual_vimeus_path',None)
            if path:
                saved=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
                c=doc['contenido'];saved[f"{c['tipo']}:{c['tmdb_id']}"]=doc
                temp=path.with_suffix('.tmp');temp.write_text(json.dumps(saved,ensure_ascii=False),encoding='utf-8');temp.replace(path)
            return {**result,'success':True}
        except Exception:
            db.rows=before
            raise

def restore(db,path):
    db.manual_vimeus_path=path
    if path.exists():
        for doc in json.loads(path.read_text(encoding='utf-8')).values():apply_local(db,doc)
