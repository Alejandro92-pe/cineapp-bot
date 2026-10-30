"""Opt-in SQL regression/benchmark on a disposable LOCAL PostgreSQL 17 server.

Requires psycopg and pg_stat_statements preloaded. No .env, Supabase credentials,
production connection, imported application, or external provider requests.
Run: python scripts/verify_incremental_catalog.py --port 55438
Only connects to 127.0.0.1; creates unique synthetic databases, kept for inspection.
"""
import argparse
import copy
import hashlib
import json
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

ROOT=Path(__file__).resolve().parents[1]
MIGRATIONS=['001_security','002_vimeus_episodes','004_episode_downloads',
            '005_vimeus_live_format','007_okru','009_tmdb_metadata','011_import_ratings',
            '012_catalog_aliases','014_catalog_queue','015_videoapi_catalog','016_session_continuity']
SCHEMA='''CREATE TABLE public.contenido(id serial PRIMARY KEY,tipo text,tmdb_id bigint,
 "año" integer,titulo text,imagen_url text,sinopsis text,genero text,fuente text,
 disponible boolean,destacado boolean,descarga text,enlace_canal text);
 CREATE TABLE public.temporadas(id serial PRIMARY KEY,contenido_id integer REFERENCES public.contenido(id),
 numero integer,nombre text,poster_url text,descripcion text,episodios integer,enlace text);'''

def doc(kind='anime', count=1000, seasons=20, tmdb=42):
    media='movie' if kind=='pelicula' else 'tv'
    return {'contenido':{'tipo':kind,'videoapi_kind':kind,'tmdb_media':media,'tmdb_id':tmdb,
            'titulo':'Fixture','sinopsis':'Descripción','imagen_url':'/poster.jpg','backdrop_url':'/background.jpg',
            'genero':'Drama','rating':8.1,'año':2026},
        'temporadas':[{'numero':s,'nombre':f'Temporada {s}','descripcion':'','poster_url':'',
            'capitulos':[{'numero':e,'titulo':f'Episodio {e}','sinopsis':'Resumen. '*10,
                'imagen_url':'/still.jpg','duracion':24,'vimeus_id':s*10000+e,
                'provider_download_url':None} for e in range(1,count//seasons+1)]}
            for s in range(1,seasons+1)] if count else []}

def apply(db, document, fn='importar_videoapi'):
    return db.execute(sql.SQL('SELECT public.{}(%s::jsonb)').format(sql.Identifier(fn)),
                      (Jsonb(document),)).fetchone()[0]

def snapshot(db):
    result={}
    for table in ('contenido','temporadas','episodios'):
        result[table]=db.execute(sql.SQL("SELECT to_jsonb(t)-'created_at'-'updated_at' FROM public.{} t ORDER BY id").format(sql.Identifier(table))).fetchall()
    return result

def semantic_snapshot(db):
    # Bulk INSERT may assign different NEW ids; compare relationships by stable
    # TMDB/season/episode keys. Regression checks separately preserve EXISTING ids.
    return {
      'contenido':db.execute("SELECT to_jsonb(c)-'id' FROM contenido c ORDER BY tipo,tmdb_id").fetchall(),
      'temporadas':db.execute("SELECT (to_jsonb(t)-'id'-'contenido_id') || jsonb_build_object('tmdb',c.tmdb_id,'kind',c.tipo) FROM temporadas t JOIN contenido c ON c.id=t.contenido_id ORDER BY c.tipo,c.tmdb_id,t.numero").fetchall(),
      'episodios':db.execute("SELECT (to_jsonb(e)-'id'-'temporada_id'-'created_at'-'updated_at') || jsonb_build_object('tmdb',c.tmdb_id,'kind',c.tipo,'season',t.numero) FROM episodios e JOIN temporadas t ON t.id=e.temporada_id JOIN contenido c ON c.id=t.contenido_id ORDER BY c.tipo,c.tmdb_id,t.numero,e.numero").fetchall()}

def reset(db):
    db.execute('TRUNCATE public.catalog_aliases,public.episodios,public.temporadas,public.contenido RESTART IDENTITY CASCADE')

def seed_background(db):
    db.execute("INSERT INTO contenido(tipo,tmdb_id,titulo,disponible) SELECT 'serie',1000000+n,'Background',true FROM generate_series(1,1000) n")
    db.execute("INSERT INTO temporadas(contenido_id,numero,nombre,episodios) SELECT id,1,'T1',14 FROM contenido")
    db.execute("INSERT INTO episodios(temporada_id,numero,titulo,disponible) SELECT id,n,'Background',true FROM temporadas CROSS JOIN generate_series(1,14) n")
    db.execute('ANALYZE contenido; ANALYZE temporadas; ANALYZE episodios')

def measure(db, document, fn):
    db.execute('SELECT pg_stat_statements_reset()')
    with db.transaction():
        prior={r[0]:r[1:] for r in db.execute("SELECT relname,n_tup_ins,n_tup_upd,n_tup_del FROM pg_stat_xact_user_tables WHERE schemaname='public'").fetchall()}
        started=time.perf_counter(); result=apply(db,document,fn);elapsed=(time.perf_counter()-started)*1000
        # Capture nested SQL BEFORE the instrumentation queries enter statistics.
        statements=db.execute("SELECT query,calls,rows,wal_bytes FROM pg_stat_statements WHERE dbid=(SELECT oid FROM pg_database WHERE datname=current_database()) AND query NOT LIKE '%%pg_stat_%%' AND query NOT IN ('BEGIN','COMMIT')").fetchall()
        writes=db.execute("SELECT relname,n_tup_ins,n_tup_upd,n_tup_del FROM pg_stat_xact_user_tables WHERE schemaname='public' AND relname IN ('contenido','temporadas','episodios') ORDER BY relname").fetchall()
        writes=[(r[0],*(v-old for v,old in zip(r[1:],prior[r[0]]))) for r in writes]
    encoded=json.dumps({'documento':document},ensure_ascii=False).encode()
    return {'ms':round(elapsed,3),'sql_calls':sum(r[1] for r in statements),
        'input_json_bytes':len(encoded),'output_json_bytes':len(json.dumps(result,ensure_ascii=False).encode()),
        'wal_bytes':int(sum(r[3] for r in statements if r[0].startswith('SELECT public.'))),
        'row_writes':{r[0]:{'insert':r[1],'update':r[2],'delete':r[3]} for r in writes},
        'result':result,'statements':[{'query':r[0],'calls':r[1],'rows':r[2]} for r in statements]}

def benchmark(db):
    result=[]
    for provider,fn in [('videoapi','importar_videoapi'),('vimeus','importar_catalogo_automatico')]:
        for kind,count,seasons in [('pelicula',0,0),('serie',24,2),('anime',1000,20)]:
            for change in ('new','unchanged','one_added','one_changed'):
                runs=[]
                for repetition in range(3):
                    reset(db);seed_background(db)
                    base=doc(kind,count,seasons);current=copy.deepcopy(base)
                    if change!='new':apply(db,base,fn)
                    if change=='one_added' and count:
                        ep=copy.deepcopy(current['temporadas'][-1]['capitulos'][-1]);ep['numero']+=1;ep['vimeus_id']+=1
                        current['temporadas'][-1]['capitulos'].append(ep)
                    elif change=='one_changed':
                        if count:
                            if provider=='videoapi':
                                db.execute("UPDATE episodios SET sinopsis='' WHERE id=(SELECT min(ep.id) FROM episodios ep JOIN temporadas s ON ep.temporada_id=s.id JOIN contenido c ON s.contenido_id=c.id WHERE c.tmdb_id=42)")
                            else: current['temporadas'][0]['capitulos'][0]['vimeus_id']+=100000
                        else:current['contenido']['rating']=8.5
                    runs.append(measure(db,current,fn))
                r=runs[0];r.update(provider=provider,kind=kind,episodes=count,case=change,
                    samples_ms=[x['ms'] for x in runs],median_ms=statistics.median(x['ms'] for x in runs))
                assert len({x['sql_calls'] for x in runs})==1
                r['data_hash']=hashlib.sha256(json.dumps(semantic_snapshot(db),sort_keys=True,default=str).encode()).hexdigest()
                result.append(r)
                print(provider,kind,change,'SQL',r['sql_calls'],'ms',r['median_ms'],flush=True)
    return result

def regressions(db, connect):
    checks=[]
    def ok(name): checks.append(name)
    reset(db)
    original=doc(count=4,seasons=2);first=apply(db,original)
    old=snapshot(db)
    with db.transaction():
        initial=db.execute("SELECT coalesce(sum(n_tup_ins+n_tup_upd+n_tup_del),0) FROM pg_stat_xact_user_tables WHERE schemaname='public'").fetchone()[0]
        repeated=apply(db,original)
        writes=db.execute("SELECT coalesce(sum(n_tup_ins+n_tup_upd+n_tup_del),0) FROM pg_stat_xact_user_tables WHERE schemaname='public'").fetchone()[0]-initial
    assert writes==0 and repeated['actualizados']==0 and repeated['sin_cambios']==4
    assert snapshot(db)==old;ok('identical reimport writes zero rows and preserves ids')
    current=copy.deepcopy(original);current['temporadas'][0]['capitulos'].append(dict(current['temporadas'][0]['capitulos'][0],numero=3,vimeus_id=10003))
    added=apply(db,current);assert added['creados']==1 and added['actualizados']==0;ok('single new episode inserts exactly one')
    db.execute("UPDATE episodios SET sinopsis='' WHERE numero=3")
    changed=apply(db,current);assert changed['actualizados']==1 and changed['creados']==0;ok('single missing description updates exactly one')

    db.execute("UPDATE contenido SET tipo='biblico',fuente='okru',playback_url='https://ok.ru/video/123',descarga='https://mediafire.com/manual',playback_unverified=true")
    db.execute("UPDATE temporadas SET enlace='https://mediafire.com/season'")
    db.execute("UPDATE episodios SET descarga='https://mediafire.com/ep',playback_url='https://ok.ru/video/456',provider_download_url='https://provider/old',vimeus_id=999,disponible=false WHERE numero=1")
    before=db.execute('SELECT id,descarga,playback_url,provider_download_url,vimeus_id,disponible FROM episodios WHERE numero=1 ORDER BY id').fetchall()
    assert apply(db,original)['contenido_id']==first['contenido_id']
    assert db.execute('SELECT id,descarga,playback_url,provider_download_url,vimeus_id,disponible FROM episodios WHERE numero=1 ORDER BY id').fetchall()==before
    assert apply(db,original,'importar_catalogo_automatico')['contenido_id']==first['contenido_id']
    blank=copy.deepcopy(original)
    for season in blank['temporadas']:
        for episode in season['capitulos']:episode['provider_download_url']=''
    apply(db,blank,'importar_catalogo_automatico')
    assert db.execute("SELECT count(*) FROM episodios WHERE numero=1 AND provider_download_url='https://provider/old'").fetchone()[0]==2
    ok('empty provider download cannot erase an existing link')
    row=db.execute('SELECT tipo,fuente,playback_url,descarga,playback_unverified FROM contenido').fetchone()
    assert row==('biblico','okru','https://ok.ru/video/123','https://mediafire.com/manual',True)
    assert db.execute('SELECT count(*) FROM contenido').fetchone()[0]==1;ok('biblical series stays biblical and both providers reuse its identity')
    assert db.execute("SELECT count(*) FROM episodios WHERE numero=3 AND disponible").fetchone()[0]==1
    ok('manual links, visibility for VideoAPI, extra episodes and other providers survive')

    # Manual-only, OK.ru, provider-download and VideoAPI episodes are protected;
    # only an absent Vimeus-only row is retired, without deleting its identity.
    sid=db.execute('SELECT min(id) FROM temporadas').fetchone()[0]
    for number,download,playback,provider,video in [(20,'manual',None,None,False),(21,None,'okru',None,False),(22,None,None,'provider',False),(23,None,None,None,True),(24,None,None,None,False),(25,None,None,None,False)]:
        db.execute('INSERT INTO episodios(temporada_id,numero,titulo,vimeus_id,descarga,playback_url,provider_download_url,videoapi_available) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(sid,number,'Manual',None if number==25 else 9000+number,download,playback,provider,video))
    r=apply(db,original,'importar_catalogo_automatico');assert r['retirados']==1
    assert db.execute('SELECT numero FROM episodios WHERE numero>=20 AND NOT disponible').fetchall()==[(24,)]
    assert db.execute('SELECT count(*) FROM episodios WHERE numero>=20').fetchone()[0]==6
    ok('retirement never deletes rows or hides another source or a manual download')
    r=apply(db,original,'importar_catalogo_automatico');assert r['retirados']==0 and r['actualizados']==0
    ok('provider reimport is idempotent after retirement')

    for label,mutation in [
        ('duplicate episode',lambda d:d['temporadas'][0]['capitulos'].append(copy.deepcopy(d['temporadas'][0]['capitulos'][0]))),
        ('duplicate season',lambda d:d['temporadas'].append(copy.deepcopy(d['temporadas'][0]))),
        ('invalid duration',lambda d:d['temporadas'][1]['capitulos'][-1].update(duracion=-2)),
        ('malformed list',lambda d:d.update(temporadas=None)),
        ('missing identity',lambda d:d['contenido'].pop('tmdb_id')),
    ]:
        before=snapshot(db);bad=copy.deepcopy(original);bad['contenido']['tmdb_id']=999
        mutation(bad)
        try:apply(db,bad)
        except psycopg.Error:pass
        else:raise AssertionError(label+' accepted')
        assert snapshot(db)==before;ok(label+' rejected atomically')
    too_big=doc(count=5001,seasons=1,tmdb=888)
    try:apply(db,too_big)
    except psycopg.Error:pass
    else:raise AssertionError('over-limit accepted')
    assert not db.execute('SELECT 1 FROM contenido WHERE tmdb_id=888').fetchall();ok('5000 episode bound')
    for role in ('anon','authenticated'):
        db.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(role)))
        try:
            for fn in ('importar_videoapi','importar_catalogo_automatico','importar_vimeus','importar_metadatos'):
                try:apply(db,original,fn)
                except psycopg.errors.InsufficientPrivilege:pass
                else:raise AssertionError('public execution granted')
        finally:db.execute('RESET ROLE')
    ok('all entry points reject anon and authenticated')
    db.execute('SET ROLE service_role')
    try:
        assert apply(db,original)['contenido_id']==first['contenido_id']
        try:db.execute("SELECT cine_security.merge_catalog_episodes(1,'[]','vimeus')")
        except psycopg.errors.InsufficientPrivilege:pass
        else:raise AssertionError('private helper exposed')
    finally:db.execute('RESET ROLE')
    ok('service role can publish only through validated entry points')
    reset(db)
    concurrent=doc(count=100,seasons=2,tmdb=777)
    def publish(fn):
        with connect() as other:return apply(other,concurrent,fn)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(publish,['importar_videoapi','importar_catalogo_automatico']))
    assert results[0]['contenido_id']==results[1]['contenido_id']
    assert db.execute('SELECT count(*) FROM contenido').fetchone()[0]==1
    assert db.execute('SELECT count(*) FROM episodios').fetchone()[0]==100
    ok('concurrent providers serialize one title without duplicate episodes')
    reset(db)
    bib=doc(count=6,seasons=2);bib['contenido']['tipo']='biblico'
    apply(db,bib,'importar_metadatos');r=apply(db,bib,'importar_metadatos')
    assert r['actualizados']==0 and r['sin_cambios']==6;ok('biblical metadata import is incremental')
    movie=doc('pelicula',0,0,tmdb=42)
    mid=apply(db,movie)['contenido_id'];assert mid!=1
    assert apply(db,movie)['contenido_id']==mid;ok('same numeric TMDB id movie and series stay separate')
    reset(db)
    # Ambiguous pre-existing editorial identities fail closed, not merged/deleted.
    db.execute("INSERT INTO contenido(tipo,tmdb_id,titulo) VALUES('serie',42,'A'),('anime',42,'B')")
    for fn in ('importar_videoapi','importar_catalogo_automatico'):
        try:apply(db,original,fn)
        except psycopg.Error:pass
        else:raise AssertionError('ambiguity ignored')
    assert db.execute('SELECT count(*) FROM contenido').fetchone()[0]==2;ok('ambiguous identities require review')
    reset(db)
    base=doc(count=4,seasons=2);original_id=apply(db,base)['contenido_id']
    db.execute("INSERT INTO contenido(tipo,tmdb_id,titulo,tmdb_media) VALUES('serie',42,'Alias','tv')")
    alias_id=db.execute('SELECT max(id) FROM contenido').fetchone()[0]
    db.execute('INSERT INTO catalog_aliases(original_id,content_id,start_season) VALUES(%s,%s,0)',(alias_id,original_id))
    for fn in ('importar_videoapi','importar_catalogo_automatico'):
        assert apply(db,base,fn)['contenido_id']==original_id
    assert db.execute('SELECT count(*) FROM contenido').fetchone()[0]==2;ok('aliases are retained and never chosen as canonical target')
    db.execute("INSERT INTO cine_security.accounts(id,name,telegram_id,created_at) VALUES('fixture-owner','Owner',5824989040,0)")
    account_before=db.execute('SELECT to_jsonb(a) FROM cine_security.accounts a').fetchall()
    apply(db,base)
    assert db.execute('SELECT to_jsonb(a) FROM cine_security.accounts a').fetchall()==account_before
    ok('account and owner identity untouched by catalog publication')
    return checks

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=55438)
    parser.add_argument('--tests-only',action='store_true');args=parser.parse_args()
    assert 1024<=args.port<=65535
    config=dict(host='127.0.0.1',port=args.port,user='quehay_local',connect_timeout=5,autocommit=True)
    out=ROOT/'.local/incremental-import';out.mkdir(parents=True,exist_ok=True)
    suffix=uuid.uuid4().hex[:8];outputs={}
    with psycopg.connect(dbname='postgres',**config) as admin:
        for role in ('anon','authenticated','service_role'):
            if not admin.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(role,)).fetchone():admin.execute(sql.SQL('CREATE ROLE {}').format(sql.Identifier(role)))
        for phase in (['after'] if args.tests_only else ['before','after']):
            name=f'qh_incremental_{phase}_{suffix}'
            admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            with psycopg.connect(dbname=name,**config) as db:
                db.execute('CREATE EXTENSION pg_stat_statements')
                db.execute(SCHEMA)
                for migration in MIGRATIONS:db.execute((ROOT/'migrations'/(migration+'.sql')).read_text(encoding='utf-8'))
                if phase=='after': db.execute((ROOT/'migrations/018_incremental_catalog_publication.sql').read_text(encoding='utf-8'))
                output={'database':name,'server_version':db.info.server_version,'production_access':False}
                if phase=='after':
                    output['tests']=regressions(db,lambda:psycopg.connect(dbname=name,**config))
                    print('Regression checks:',len(output['tests']),flush=True)
                if not args.tests_only:output['benchmarks']=benchmark(db)
                (out/(phase+'.json')).write_text(json.dumps(output,indent=2),encoding='utf-8');outputs[phase]=output
    print('Saved local evidence in',out)

if __name__=='__main__':main()
