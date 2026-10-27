"""Read only from Vimeus/TMDB; write snapshots only under .local. No main/env/DB imports."""
import argparse
import concurrent.futures
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from providers.vimeus import VimeusClient, ImportFailure
from providers.tmdb import TMDBClient, trailer_url
from services.vimeus_import import build_manifest


def run():
    parser=argparse.ArgumentParser()
    parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args()
    local=ROOT/'.local'
    secrets=json.loads((local/'telegram-preview.json').read_text(encoding='utf-8'))
    rows=json.loads((local/'catalog-snapshot.json').read_text(encoding='utf-8'))
    bindings_path=local/'anime-bindings.json'
    bindings=json.loads(bindings_path.read_text(encoding='utf-8')) if bindings_path.exists() else []
    for row in rows:
        row['tipo']=str(row.get('tipo','')).strip()
        match=next((b for b in bindings if b['id']==row['id']),None)
        if match:row.update(tmdb_id=match['tmdb_id'],fuente='vimeus')
    destination=local/'vimeus-manifests';destination.mkdir(exist_ok=True)
    targets=[r for r in rows if r.get('tmdb_id') and str(r.get('fuente','')).strip()=='vimeus' and r.get('tipo') in ('serie','anime')]
    def sync(row):
        key=f"{row['tipo']}-{row['tmdb_id']}"
        output=destination/(key+'.json')
        try:
            if output.exists() and not args.refresh:
                manifest=json.loads(output.read_text(encoding='utf-8'));warnings=[]
            else:
                tmdb=TMDBClient(secrets['TMDB_API_KEY'])
                manifest,warnings=build_manifest(VimeusClient(secrets['VIMEUS_API_KEY']),row['tmdb_id'],row['tipo'],tmdb.get)
                temp=output.with_suffix('.tmp');temp.write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8');temp.replace(output)
            return {'id':row['id'],'title':row['titulo'],'status':'ok','seasons':len(manifest['temporadas']),
                'episodes':sum(len(s['capitulos']) for s in manifest['temporadas']),
                'downloads':sum(bool(e.get('provider_download_url')) for s in manifest['temporadas'] for e in s['capitulos']),
                'warnings':warnings}
        except Exception as error:
            return {'id':row['id'],'title':row['titulo'],'status':'pending',
                'reason':str(error) if isinstance(error,ImportFailure) else 'No se pudo completar la lectura externa.'}
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        for result in executor.map(sync,targets):
            results.append(result)
            print(json.dumps(result,ensure_ascii=True),flush=True)
    (local/'phase8-import-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'titles':sum(r['status']=='ok' for r in results),'episodes':sum(r.get('episodes',0) for r in results),
                      'downloads':sum(r.get('downloads',0) for r in results),'pending':sum(r['status']!='ok' for r in results)}),flush=True)


if __name__=='__main__':run()
