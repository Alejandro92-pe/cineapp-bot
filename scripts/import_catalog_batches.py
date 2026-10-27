"""Bounded local batch. Reads provider APIs; only writes .local/import-queue.sqlite."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services.catalog_queue import CatalogQueue, PacedTransport, CachedMetadata, worker_lock, BatchPause
from providers.vimeus import VimeusClient, ImportFailure
from providers.tmdb import TMDBClient


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit',type=int,default=3,help='Máximo de títulos procesados en este lote (1–20).')
    parser.add_argument('--pause',type=float,default=1.2,help='Pausa mínima entre peticiones (>=1 segundo).')
    parser.add_argument('--seconds',type=int,default=180,help='Presupuesto de tiempo por ejecución (30–900).')
    parser.add_argument('--batches',type=int,default=1,help='Número de lotes consecutivos (1–100).')
    parser.add_argument('--batch-pause',type=int,default=30,help='Descanso entre lotes (30–3600 segundos).')
    parser.add_argument('--discover',choices=['movies','series','animes'],help='Leer UNA página nueva de este listado.')
    parser.add_argument('--no-discover',action='store_true',help='Procesar únicamente títulos ya encolados.')
    parser.add_argument('--status',action='store_true',help='Estado sin consultar APIs ni importar.')
    parser.add_argument('--rescan',action='store_true',help='Volver al inicio de los listados para descubrir novedades; no duplica los ya terminados.')
    args=parser.parse_args()
    if not 1<=args.limit<=20 or not 1<=args.pause<=60 or not 30<=args.seconds<=900:
        parser.error('Usa límite 1–20, pausa 1–60 y tiempo 30–900.')
    if not 1<=args.batches<=100 or not 30<=args.batch_pause<=3600:
        parser.error('Usa 1–100 lotes y un descanso entre lotes de 30–3600 segundos.')
    local=ROOT/'.local'
    try:
        with worker_lock(local/'import-queue.lock'):
            queue=CatalogQueue(local/'import-queue.sqlite')
            if args.status:
                print(json.dumps(queue.summary()));return
            if args.rescan:
                with queue.db: queue.db.execute('DELETE FROM cursors')
            secrets=json.loads((local/'telegram-preview.json').read_text(encoding='utf-8'))
            for batch in range(args.batches):
                if batch: time.sleep(args.batch_pause)
                transport=PacedTransport(queue,args.pause,args.seconds)
                provider=VimeusClient(secrets['VIMEUS_API_KEY'],transport)
                metadata=CachedMetadata(queue,TMDBClient(secrets['TMDB_API_KEY'],transport))
                try:
                    if not args.no_discover:
                        resources=['movies','series','animes']
                        index=int(queue.get_setting('discovery_turn'))%3
                        resource=args.discover or resources[index]
                        print(json.dumps({'resource':resource,'queued':queue.discover(provider,resource)}),flush=True)
                        queue.set_setting('discovery_turn',index+1)
                    for result in queue.run(provider,metadata.get,args.limit):print(json.dumps(result,ensure_ascii=True),flush=True)
                except BatchPause:
                    print('Pausa: se conserva el avance para el próximo lote.',flush=True)
                print(json.dumps({'batch':batch+1,'queue':queue.summary(),'requests':transport.requests,'wait_seconds':round(transport.waited,2)}),flush=True)
    except Exception as error:
        print(str(error) if isinstance(error,ImportFailure) else 'No se pudo abrir la configuración o completar el lote local.',file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':sys.exit(main())
