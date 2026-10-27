"""Read one TMDB title with pacing; prepare an isolated snapshot for the admin UI."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from providers.tmdb import TMDBClient
from services.catalog_queue import CatalogQueue,PacedTransport,worker_lock
from services.metadata_import import build_metadata
from providers.vimeus import VimeusClient
from services.vimeus_import import build_manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('tmdb_id',type=int);p.add_argument('--kind',choices=['pelicula','serie','anime','biblico_pelicula','biblico_serie'],required=True);a=p.parse_args()
    try:
        folder=ROOT/'.local';secret=json.loads((folder/'telegram-preview.json').read_text(encoding='utf-8'))
        with worker_lock(folder/'import-queue.lock'):
            queue=CatalogQueue(folder/'import-queue.sqlite');transport=PacedTransport(queue,1.2,180)
            get=TMDBClient(secret['TMDB_API_KEY'],transport).get
            doc=build_manifest(VimeusClient(secret['VIMEUS_API_KEY'],transport),a.tmdb_id,a.kind,get,metadata_seconds=160)[0] if a.kind in ('serie','anime') else build_metadata(get,a.tmdb_id,a.kind)
            target=folder/'tmdb-imports';target.mkdir(exist_ok=True)
            path=target/f'{a.kind}-{a.tmdb_id}.json';tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(doc,ensure_ascii=False),encoding='utf-8');tmp.replace(path)
            print(json.dumps({'title':doc['contenido']['titulo'],'seasons':len(doc['temporadas']),'episodes':sum(len(s['capitulos']) for s in doc['temporadas']),'requests':transport.requests},ensure_ascii=True))
    except BaseException:
        print('No se completó la lectura. No se guardaron datos parciales ni se modificó el catálogo.',file=sys.stderr);sys.exit(1)
