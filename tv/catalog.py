"""Read-only adapter for the existing Supabase catalog schema. No download fields."""
from providers.videoapi import embed_url
from providers.okru import embed_url as okru_embed

FIELDS = 'id,titulo,tipo,año,genero,sinopsis,imagen_url,backdrop_url,rating'
EPISODES = 'id,temporada_id,numero,titulo,sinopsis,imagen_url,duracion'
KINDS = {'pelicula':'Una noche de películas', 'serie':'Historias para quedarse',
         'anime':'Mundos extraordinarios', 'biblico':'Historias que inspiran'}


class Catalog:
    def __init__(self, database):
        self.db = database

    def titles(self, kind=None, search='', page=1):
        q = self.db.table('contenido').select(FIELDS, count='exact').eq('disponible', True)
        if kind:
            q = q.eq('tipo', kind)
        if search:
            q = q.ilike('titulo', '%'+search+'%')
        r = q.order('id', desc=True).limit(12).offset((page-1)*12).execute()
        return {'items':r.data, 'page':page, 'has_next':page*12 < (r.count or 0)}

    def item(self, cid):
        rows = self.db.table('contenido').select(FIELDS).eq('id', cid).eq('disponible', True).limit(1).execute().data
        return rows[0] if rows else None

    def top_movies(self, scores):
        items = []
        if scores:
            rows = self.db.table('contenido').select(FIELDS).eq('disponible', True).eq('tipo', 'pelicula').in_('id', [s['content_id'] for s in scores]).execute().data
            by_id = {r['id']: r for r in rows}
            items = [by_id[s['content_id']] for s in scores if s['content_id'] in by_id][:10]
        ranked = bool(items)
        if not ranked:
            items = self.db.table('contenido').select(FIELDS).eq('disponible', True).eq('tipo', 'pelicula').order('id', desc=True).limit(10).execute().data
        return {'items': items, 'mode': 'ranked' if ranked else 'discovery', 'window_days': 7}

    def seasons(self, cid):
        return self.db.table('temporadas').select('id,numero,episodios').eq('contenido_id',cid).order('numero').limit(100).execute().data

    def episodes(self, cid, sid, page):
        if not self.item(cid) or not any(s['id'] == sid for s in self.seasons(cid)):
            return None
        rows = self.db.table('episodios').select(EPISODES,count='exact').eq('temporada_id',sid).eq('disponible',True).order('numero').limit(6).offset((page-1)*6).execute()
        return {'items':rows.data, 'total':rows.count, 'page':page, 'has_next':page*6 < (rows.count or 0)}

    def source(self, cid, eid=None):
        rows = self.db.table('contenido').select('id,tipo,fuente,tmdb_id,playback_url').eq('id',cid).eq('disponible',True).limit(1).execute().data
        if not rows:
            return None
        item, ep, season = rows[0], None, None
        seasons = self.seasons(cid)
        if seasons:
            if not eid:
                return None
            eps = self.db.table('episodios').select('id,temporada_id,numero,playback_url').eq('id',eid).eq('disponible',True).limit(1).execute().data
            ep = eps[0] if eps else None
            season = next((s for s in seasons if ep and s['id']==ep['temporada_id']),None)
            if not season:
                return None
        elif eid or item['tipo'] in ('serie','anime'):
            return None
        if item['fuente']=='okru':
            url=okru_embed((ep or item).get('playback_url'))
            return {'url':url,'provider':'okru'} if url else None
        if item['fuente']=='vimeus' and item['tipo'] in ('pelicula','serie','anime') and item.get('tmdb_id'):
            return {'url':embed_url(item['tipo'], item['tmdb_id'], season['numero'] if season else None,
                                   ep['numero'] if ep else None), 'provider':'videoapi'}
        return None

    def next_episode(self,cid,eid):
        seasons=self.seasons(cid)
        ep=self.db.table('episodios').select('temporada_id,numero').eq('id',eid).eq('disponible',True).limit(1).execute().data
        index=next((i for i,s in enumerate(seasons) if ep and s['id']==ep[0]['temporada_id']),None)
        if index is None:return None
        for i,s in enumerate(seasons[index:]):
            q=self.db.table('episodios').select('id,numero,titulo').eq('temporada_id',s['id']).eq('disponible',True)
            if i==0:
                # The offline query adapter compares gte values as strings. Use
                # an explicit numeric predicate there; Supabase uses its column type.
                if hasattr(q,'filters'):
                    q.filters.append(lambda r: r.get('numero',0)>ep[0]['numero'])
                else:q=q.gte('numero',ep[0]['numero']+1)
            rows=q.order('numero').limit(1).execute().data
            if rows:return {**rows[0],'season':s['numero']}
        return None
