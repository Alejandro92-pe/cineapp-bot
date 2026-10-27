"""Reviewed local consolidation; keep original records and all links recoverable."""
import copy

SAO_PARTS = {405:2,406:3,407:4}


def consolidate_preview(database):
    database.catalog_aliases={}
    database.catalog_merge_archive=[]
    canonical=next((r for r in database.rows['contenido'] if r['id']==404 and r.get('tmdb_id')==45782),None)
    if not canonical:return
    for old_id,number in SAO_PARTS.items():
        old=next((r for r in database.rows['contenido'] if r['id']==old_id),None)
        season=next((s for s in database.rows['temporadas'] if s['contenido_id']==404 and s['numero']==number and s.get('episodios',0)>0),None)
        if not old or not season:continue
        # A unique legacy download requires a transfer plan, never silent removal.
        if old.get('descarga') and old['descarga']!=canonical.get('descarga'):continue
        database.catalog_merge_archive.append(copy.deepcopy(old))
        old['disponible']=False
        database.catalog_aliases[old_id]={'id':404,'start_season':number}
