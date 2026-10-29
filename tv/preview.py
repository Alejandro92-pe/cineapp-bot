"""Run: python -m tv.preview --snapshot-root <existing .local directory>."""
import argparse
import json
import time
from pathlib import Path
from tv.store import PairingStore  # Register new tables before local schema creation.
from security_store import SecurityStore
from security import password_hash
from billing.schema import access
from sqlalchemy import select
from local_support import LocalDatabase, block_external_network
from tv.app import create_app


def load_snapshot(root):
    db=LocalDatabase()
    complete=Path(__file__).resolve().parents[1]/'.local/tv/catalog.json'
    if complete.is_file():
        data=json.loads(complete.read_text(encoding='utf8'))
        for table in ('contenido','temporadas','episodios'):
            db.rows[table]=data[table]
        return db
    path=root/'visual-refresh/catalog-all.json'
    if not path.is_file():raise RuntimeError('Falta la copia local del catálogo; no se consulta producción.')
    rows=json.loads(path.read_text(encoding='utf8'))
    db.rows['contenido']=rows
    db.rows['temporadas']=[];db.rows['episodios']=[]
    artwork=root/'visual-refresh/backfill.json'
    if artwork.exists():
        for row in json.loads(artwork.read_text(encoding='utf8')).values():
            match=next((x for x in rows if x['id']==row['id']),None)
            if match and row.get('backdrop_url'):match['backdrop_url']=row['backdrop_url']
    for path in sorted((root/'vimeus-manifests').glob('*.json')):
        manifest=json.loads(path.read_text(encoding='utf8'));meta=manifest['contenido']
        match=next((r for r in rows if r.get('tmdb_id')==meta.get('tmdb_id') and r.get('tipo')==meta.get('tipo')),None)
        if not match:continue
        match['fuente']='vimeus'
        for season in manifest['temporadas']:
            sid=len(db.rows['temporadas'])+1
            db.rows['temporadas'].append({'id':sid,'contenido_id':match['id'],'numero':season['numero'],'episodios':len(season['capitulos'])})
            for ep in season['capitulos']:
                db.rows['episodios'].append({**{k:v for k,v in ep.items() if k in ('numero','titulo','sinopsis','imagen_url','duracion','playback_url')},'id':len(db.rows['episodios'])+1,'temporada_id':sid,'disponible':True})
    return db


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--snapshot-root',type=Path,required=True);parser.add_argument('--port',type=int,default=5020)
    args=parser.parse_args();out=Path(__file__).resolve().parents[1]/'.local/tv';out.mkdir(parents=True,exist_ok=True)
    block_external_network()  # Backend cannot reach Render, Supabase, mail, bots or imports.
    store=SecurityStore('sqlite:///'+(out/'preview.sqlite').as_posix(),local=True)
    for name,email,enabled in [('Ale · demo','tv@example.test',True),('Invitado · demo','sinacceso@example.test',False)]:
        account=store.account(email=email)
        if not account:account=store.create_account(name,email,password_hash('Televisor-Local-2026!'))
        if enabled:
            with store.engine.begin() as c:
                if not c.execute(select(access).where(access.c.account_id==account['id'])).first():
                    c.execute(access.insert().values(account_id=account['id'],expires_at=time.time()+30*86400))
    database=load_snapshot(args.snapshot_root.resolve())
    app=create_app(database,store,origin=f'http://127.0.0.1:{args.port}')
    print(f'TV local: http://127.0.0.1:{args.port}/tv | Demo: tv@example.test / Televisor-Local-2026!',flush=True)
    app.run(host='127.0.0.1',port=args.port,debug=False,use_reloader=False)


if __name__=='__main__':main()
