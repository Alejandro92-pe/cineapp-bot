"""Read TMDB metadata into private local snapshots. Never imports production code."""
import concurrent.futures
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from providers.tmdb import TMDBClient,trailer_url
from services.vimeus_import import image_url


def run():
    local=ROOT/'.local'
    secret=json.loads((local/'telegram-preview.json').read_text(encoding='utf-8'))
    catalog=json.loads((local/'catalog-snapshot.json').read_text(encoding='utf-8'))
    paths=list((local/'vimeus-manifests').glob('*.json'))
    def series(path):
        document=json.loads(path.read_text(encoding='utf-8'));item=document['contenido']
        client=TMDBClient(secret['TMDB_API_KEY'])
        try:
            data=client.get(f"/tv/{item['tmdb_id']}")
            item['backdrop_url']=image_url(data.get('backdrop_path')).replace('/w500','/w1280')
            trailer=trailer_url(client.get,'tv',item['tmdb_id'])
            if trailer:item['trailer_url']=trailer
            temp=path.with_suffix('.tmp');temp.write_text(json.dumps(document,ensure_ascii=False),encoding='utf-8');temp.replace(path)
            return bool(item.get('trailer_url'))
        except Exception:return bool(item.get('trailer_url'))
    targets=[r for r in catalog if r.get('tipo')=='pelicula' and r.get('tmdb_id') and
             (str(r.get('fuente','')).strip()=='vimeus' or 'Piratas del Caribe' in r.get('titulo',''))]
    def movie(row):
        try:
            client=TMDBClient(secret['TMDB_API_KEY']);data=client.get(f"/movie/{row['tmdb_id']}")
            metadata={'titulo':data.get('title') or row['titulo'],
                      'backdrop_url':image_url(data.get('backdrop_path')).replace('/w500','/w1280')}
            trailer=trailer_url(client.get,'movie',row['tmdb_id'])
            if trailer:metadata['trailer_url']=trailer
            return {'id':row['id'],'metadata':metadata}
        except Exception:return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        series_count=sum(pool.map(series,paths))
        movies=[r for r in pool.map(movie,targets) if r]
    output=local/'movie-metadata.json';temp=output.with_suffix('.tmp')
    temp.write_text(json.dumps(movies,ensure_ascii=False),encoding='utf-8');temp.replace(output)
    print(json.dumps({'series_anime_trailers':series_count,'movie_trailers':sum(bool(r['metadata'].get('trailer_url')) for r in movies),'movies':len(movies)}))


if __name__=='__main__':run()
