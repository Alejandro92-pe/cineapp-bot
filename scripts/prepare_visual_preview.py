"""Read public catalogue/TMDB into local fixtures; never writes production data."""
import io
import json
import sys
import time
from pathlib import Path
import requests
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from local_support import LocalDatabase
from providers.tmdb import TMDBClient
from services.artwork import ArtworkMaintenance, SNAPSHOT, image, metadata_for
from services.catalog_jobs import DurableQueue
from security_store import SecurityStore


def prepare():
    out=ROOT/'.local/visual-refresh';out.mkdir(exist_ok=True)
    key=json.loads((ROOT/'.local/telegram-preview.json').read_text(encoding='utf-8'))['TMDB_API_KEY']
    tmdb=TMDBClient(key)
    base='https://app.quehay.live'
    def public(filters):
        r=requests.post(base+'/api/contenido',headers={'Origin':base},json=filters,timeout=30);r.raise_for_status();return r.json()
    data=public({'tipo':'pelicula','año':2026,'limit':100})
    db=LocalDatabase();db.rows['contenido']=data['data']
    store=SecurityStore('sqlite:///'+(out/'selection.sqlite').as_posix(),local=True)
    queue=DurableQueue(store)
    service=ArtworkMaintenance(queue,db,tmdb)
    for _ in range(3):
        service.discover_step();time.sleep(.4)
    selection=service.public()
    if len(selection['items'])!=3:raise RuntimeError('No hay tres coincidencias válidas; no se sustituye la selección anterior.')
    (out/'selection.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'catalog-2026.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    response=requests.get(base+'/api/tendencias',timeout=30);response.raise_for_status();heroes=response.json()
    updates=[]
    for row in heroes:
        meta=metadata_for(row,tmdb)
        bg=image(meta.get('backdrop_path'),1280)
        if bg:row['backdrop_url']=bg;updates.append({'id':row['id'],'backdrop_url':bg})
    (out/'heroes.json').write_text(json.dumps(heroes,ensure_ascii=False),encoding='utf-8')
    assets=ROOT/'landing/assets'
    for i,row in enumerate(selection['items'],1):
        r=requests.get(row['poster'].replace('/w342/','/w500/'),timeout=30);r.raise_for_status()
        poster=Image.open(io.BytesIO(r.content)).convert('RGB')
        for width in (185,342,500):
            poster.resize((width,round(poster.height*width/poster.width))).save(assets/f'poster-{i}-{width}.webp','WEBP',quality=83,method=6)
    r=requests.get(selection['items'][0]['backdrop'],timeout=30);r.raise_for_status()
    im=Image.open(io.BytesIO(r.content)).convert('RGB')
    if im.width<1000 or im.width/im.height<1.5:raise ValueError('El fondo no tiene la resolución horizontal necesaria.')
    im.save(assets/'cover.webp','WEBP',quality=85,method=6)
    im.resize((780,round(im.height*780/im.width))).save(assets/'cover-mobile.webp','WEBP',quality=83,method=6)
    markup=(ROOT/'landing/index.html').read_text(encoding='utf-8')
    import re
    markup=re.sub(r' data-selection-ids="[^"]*"','',markup)
    markup=markup.replace('<html lang="es"',f'<html lang="es" data-selection-ids="{",".join(str(r["id"]) for r in selection["items"])}"')
    for i,row in enumerate(selection['items']):
        import html
        markup=re.sub(fr'(<img data-poster="{i}"[^>]*alt=")[^"]*',lambda m:m[1]+html.escape(row['title'],quote=True),markup,count=1)
        def responsive(match):
            tag=re.sub(r' (?:src|srcset|sizes)="[^"]*"','',match[0])
            sizes='(max-width:700px) 150px, 240px' if 'decoding="async"' in tag else '120px'
            return tag.replace('<img ',f'<img src="assets/poster-{i+1}-342.webp" srcset="assets/poster-{i+1}-185.webp 185w, assets/poster-{i+1}-342.webp 342w, assets/poster-{i+1}-500.webp 500w" sizes="{sizes}" ')
        markup=re.sub(fr'<img\b[^>]*data-poster="{i}"[^>]*>',responsive,markup)
    for i,row in enumerate(selection['items']):
        # Captions identify the real selected titles even with JavaScript disabled.
        markup=re.sub(fr'(<figure class="poster poster-{["one","two","three"][i]}"[^>]*>.*?<figcaption>)[^<]*(</figcaption>)',lambda m:m[1]+html.escape(row['title'])+m[2],markup)
    markup=markup.replace('<img data-backdrop src="assets/cover.webp"','<img data-backdrop srcset="assets/cover-mobile.webp 780w, assets/cover.webp 1280w" sizes="100vw" src="assets/cover.webp"')
    markup=markup.replace('Una noche. Muchas posibilidades.',f'Descubre el cine de {selection["year"]}.')
    (ROOT/'landing/index.html').write_text(markup,encoding='utf-8')
    report={'selection':[{'title':r['title'],'year':r['year'],'rating':r['rating'],'content_id':r['id']} for r in selection['items']],
        'backdrop_dimensions':list(im.size),'assets_bytes':{p.name:p.stat().st_size for p in assets.glob('*') if p.name.startswith(('cover','poster'))},
        'hero_repairs_local':updates,'production_writes':0}
    (out/'preparation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))


if __name__=='__main__':prepare()
