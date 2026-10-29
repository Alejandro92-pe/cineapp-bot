"""Bounded image maintenance, independent of payments and catalogue imports.

Only the authenticated cron calls TMDB. Visitors read a durable public snapshot.
No video, account, membership or download column is ever written here.
"""
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from sqlalchemy import select
from services.catalog_jobs import cache
from services.hero import PERIOD, LIMA_OFFSET

IMAGE = re.compile(r'^https://(?:image\.tmdb\.org|media\.themoviedb\.org)/t/p/(?:w\d+(?:_and_h\d+_face)?|original)/([\w]+\.(?:jpg|png|webp))$', re.I)
PATH = re.compile(r'^/[\w]+\.(?:jpg|png|webp)$', re.I)
FIELDS = 'id,titulo,tipo,tmdb_id,tmdb_media,imagen_url,backdrop_url,año,rating'
SNAPSHOT = 'visual:landing:v1'


def image(path, width):
    return f'https://image.tmdb.org/t/p/w{width}{path}' if isinstance(path,str) and PATH.fullmatch(path) else ''


def needs_backdrop(row):
    bg = row.get('backdrop_url') or ''
    if not bg: return True
    a,b = IMAGE.fullmatch(bg), IMAGE.fullmatch(row.get('imagen_url') or '')
    return bool(a and b and a[1] == b[1])


def metadata_for(row,tmdb):
    media=row.get('tmdb_media') or ('movie' if row['tipo'] in ('pelicula','Peliculas anime') else 'tv' if row['tipo'] in ('serie','anime') else '')
    uncertain_biblical=not media and row['tipo']=='biblico'
    if uncertain_biblical and not row.get('tmdb_id'):return {}
    if uncertain_biblical:media='movie'
    if media not in ('movie','tv'):return {}
    def normalize(s):return ''.join(c for c in unicodedata.normalize('NFKD',s.casefold()) if c.isalnum())
    def matches(meta):
        title=meta.get('title' if media=='movie' else 'name','')
        original=meta.get('original_title' if media=='movie' else 'original_name','')
        year=str(meta.get('release_date' if media=='movie' else 'first_air_date',''))[:4]
        poster=IMAGE.fullmatch(row.get('imagen_url') or '')
        same_poster=poster and meta.get('poster_path')=='/'+poster[1]
        return year==str(row.get('año')) and (same_poster or normalize(row['titulo']) in {normalize(title),normalize(original)})
    if row.get('tmdb_id'):
        meta=tmdb.get(f"/{media}/{int(row['tmdb_id'])}")
        if meta.get('id')!=row['tmdb_id']:raise ValueError('TMDB no coincide.')
        if uncertain_biblical and not matches(meta):return {}
        return meta
    if not row.get('año'):return {}
    results=(tmdb.search_movie(row['titulo'],row['año']) if media=='movie' else tmdb.search_title(media,row['titulo'],row['año'])).get('results',[])
    matched=[r for r in results if matches(r)]
    # Ambiguous matches remain untouched. Never alter playback identifiers.
    return matched[0] if len(matched)==1 else {}


def apply_reviewed(catalog, changes, apply=False):
    """Import only approved background URLs; compare originals before every update."""
    result={'eligible':0,'updated':0,'conflicts':[],'unmatched':0}
    for change in changes:
        url=change.get('backdrop_url') or ''
        if not url:result['unmatched']+=1;continue
        if not IMAGE.fullmatch(url) or type(change.get('id')) is not int:
            raise ValueError('Cambio de imagen inválido.')
        rows=catalog.table('contenido').select(FIELDS).eq('id',change['id']).execute().data
        row=rows[0] if len(rows)==1 else None
        if row and row.get('backdrop_url')==url:continue
        if not row or any(row.get(k)!=change.get(k) for k in ('titulo','tipo','tmdb_id')) or row.get('backdrop_url')!=change.get('previous_backdrop'):
            result['conflicts'].append(change['id']);continue
        result['eligible']+=1
        if not apply:continue
        q=catalog.table('contenido').update({'backdrop_url':url}).eq('id',change['id']).eq('titulo',change['titulo']).eq('tipo',change['tipo'])
        q=q.eq('tmdb_id',change['tmdb_id']) if change.get('tmdb_id') else q.is_('tmdb_id','null')
        q=q.is_('backdrop_url','null') if change.get('previous_backdrop') is None else q.eq('backdrop_url',change['previous_backdrop'])
        if q.execute().data:result['updated']+=1
        else:result['conflicts'].append(change['id'])
    return result


class ArtworkMaintenance:
    def __init__(self, queue, catalog, tmdb=None):
        self.queue,self.catalog,self.tmdb=queue,catalog,tmdb

    def read(self, key):
        with self.queue.engine.connect() as c:
            value=c.execute(select(cache.c.payload).where(cache.c.key==key)).scalar_one_or_none()
        return json.loads(value) if value else None

    def save(self,key,value,ttl=10*365*86400):
        # Retain last-good output across outages and the import cache cleanup.
        statement=self.queue.insert(cache).values(key=key,payload=json.dumps(value),expires=self.queue.clock()+ttl)
        with self.queue.engine.begin() as c:
            c.execute(statement.on_conflict_do_update(index_elements=['key'],set_={
                'payload':json.dumps(value),'expires':self.queue.clock()+ttl}))

    def public(self):
        snapshot=self.read(SNAPSHOT) or {'items':[]}
        ids=[r['id'] for r in snapshot['items']]
        if not ids:return {'items':[]}
        visible=self.catalog.table('contenido').select('id').in_('id',ids).eq('disponible',True).execute().data
        allowed={r['id'] for r in visible}
        return {**snapshot,'items':[r for r in snapshot['items'] if r['id'] in allowed]}

    def repair_one(self):
        cursor=int(self.queue.get_setting('visual:cursor'))
        rows=self.catalog.table('contenido').select(FIELDS).eq('disponible',True).gte('id',cursor+1).order('id').limit(100).execute().data
        for row in rows:
            self.queue.set_setting('visual:cursor',row['id'])
            if not needs_backdrop(row):continue
            media=row.get('tmdb_media') or ('movie' if row['tipo'] in ('pelicula','Peliculas anime') else 'tv' if row['tipo'] in ('serie','anime') else '')
            if media not in ('movie','tv') and row['tipo']!='biblico':continue
            key=f"visual:checked:{row['id']}"
            if self.queue.get_setting(key)>self.queue.clock()-7*86400:continue
            meta=metadata_for(row,self.tmdb)
            self.queue.set_setting(key,self.queue.clock())
            url=image(meta.get('backdrop_path'),1280)
            if not url:return {'checked':row['id'],'updated':False}
            query=self.catalog.table('contenido').update({'backdrop_url':url}).eq('id',row['id'])
            query=query.eq('tmdb_id',row['tmdb_id']) if row.get('tmdb_id') else query.is_('tmdb_id','null')
            # Do not overwrite an editor's concurrent change.
            query=query.is_('backdrop_url','null') if row.get('backdrop_url') is None else query.eq('backdrop_url',row['backdrop_url'])
            changed=query.execute().data
            return {'checked':row['id'],'updated':bool(changed)}
        if len(rows)<100:self.queue.set_setting('visual:cursor',0)
        return {'updated':False}

    def discover_step(self):
        now=self.queue.clock();period=int((now-LIMA_OFFSET)//PERIOD)
        year=datetime.fromtimestamp(now-LIMA_OFFSET,timezone.utc).year
        previous=self.read(SNAPSHOT) or {}
        if previous.get('period')==period:return {'waiting':True}
        key=f'visual:pool:{period}'
        pool=self.read(key) or {'page':1,'items':[]}
        if pool['page']<=3:
            response=self.tmdb.discover_movies(year,pool['page'])
            if not isinstance(response.get('results'),list):raise ValueError('Listado incompleto.')
            valid=[r for r in response['results'] if str(r.get('release_date','')).startswith(f'{year}-')
                   and r.get('adult') is False and isinstance(r.get('vote_count'),int) and r['vote_count']>=100
                   and image(r.get('poster_path'),342) and image(r.get('backdrop_path'),1280)]
            pool['items'].extend(valid)
            pool['page']+=1
            if pool['page']>min(3,int(response.get('total_pages',3))):pool['page']=4
            self.save(key,pool,ttl=7*86400)
        if pool['page']<=3:return {'page':pool['page']-1,'collecting':True}
        ids=[r['id'] for r in pool['items']]
        if not ids:return {'kept_previous':True}
        matches=self.catalog.table('contenido').select(FIELDS).eq('tipo','pelicula').eq('disponible',True).eq('año',year).in_('tmdb_id',ids).execute().data
        by_tmdb={}
        for row in sorted(matches,key=lambda r:r['id']):by_tmdb.setdefault(row['tmdb_id'],row)
        candidates={r['id']:r for r in pool['items'] if r['id'] in by_tmdb}
        # Top twelve rated titles among the popular, available, sufficiently voted pool.
        ranked=sorted(candidates.values(),key=lambda r:(float(r.get('vote_average') or 0),int(r['vote_count'])),reverse=True)[:12]
        old={r['tmdb_id'] for r in previous.get('items',[])}
        ranked.sort(key=lambda r:(r['id'] in old,hashlib.sha256(f"landing:{period}:{r['id']}".encode()).digest()))
        chosen=ranked[:3]
        if len(chosen)<3:return {'kept_previous':True,'available':len(chosen)}
        items=[]
        for meta in chosen:
            row=by_tmdb[meta['id']]
            items.append({'id':row['id'],'tmdb_id':meta['id'],'title':row['titulo'],'year':year,
                'rating':round(float(meta.get('vote_average') or 0),1),'poster':image(meta['poster_path'],342),
                'backdrop':image(meta['backdrop_path'],1280)})
        self.save(SNAPSHOT,{'period':period,'year':year,'updated_at':int(now),'items':items})
        return {'published':len(items)}

    def run(self):
        with self.queue.lock() as acquired:
            if not acquired:return {'busy':True}
            if self.queue.get_setting('visual:after')>self.queue.clock():return {'waiting':True}
            self.queue.set_setting('visual:after',self.queue.clock()+600)
            result={}
            # Each part may fail independently; last-good selection remains intact.
            for name,action in [('artwork',self.repair_one),('landing',self.discover_step)]:
                try:result[name]=action()
                except Exception:result[name]={'retry_later':True}
            return result
