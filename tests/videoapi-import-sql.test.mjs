import {PGlite} from '../.local/sql-runtime/node_modules/@electric-sql/pglite/dist/index.js';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
const db=new PGlite();
await db.exec(`CREATE ROLE anon;CREATE ROLE authenticated;CREATE ROLE service_role;
CREATE TABLE public.contenido(id serial PRIMARY KEY,tipo text,tmdb_id bigint,"año" integer,titulo text,imagen_url text,sinopsis text,genero text,fuente text,disponible boolean,destacado boolean,descarga text,enlace_canal text);
CREATE TABLE public.temporadas(id serial PRIMARY KEY,contenido_id integer REFERENCES public.contenido(id),numero integer,nombre text,poster_url text,descripcion text,episodios integer,enlace text);`);
for(const name of ['001_security','002_vimeus_episodes','004_episode_downloads','005_vimeus_live_format','007_okru','009_tmdb_metadata','011_import_ratings','012_catalog_aliases','014_catalog_queue','015_videoapi_catalog','016_session_continuity'])
 await db.exec(await readFile(new URL('../migrations/'+name+'.sql',import.meta.url),'utf8'));
test.after(()=>db.close());
const doc={contenido:{tipo:'anime',videoapi_kind:'anime',tmdb_id:22,tmdb_media:'tv',titulo:'Serie',rating:8.1},temporadas:[{numero:1,nombre:'T1',capitulos:[{numero:1,titulo:'Uno',sinopsis:'',imagen_url:''},{numero:2,titulo:'Dos',sinopsis:'',imagen_url:''}]}]};
const apply=async(d=doc,fn='importar_videoapi')=>(await db.query(`SELECT public.${fn}($1::jsonb) AS result`,[JSON.stringify(d)])).rows[0].result;

test('real PostgreSQL RPC merges TV/anime, keeps downloads and does not retire other provider episodes',async()=>{
 const old=structuredClone(doc);old.contenido.tipo='serie';old.temporadas[0].capitulos=[{numero:1,titulo:'Uno',sinopsis:'',imagen_url:'',vimeus_id:111,provider_download_url:'https://vimeus.com/d/111'},{numero:3,titulo:'Tres',sinopsis:'',imagen_url:'',vimeus_id:333}];
 const a=await apply(old,'importar_vimeus');
 await db.query("UPDATE public.contenido SET descarga='https://mediafire.com/movie',fuente='okru',playback_url='https://ok.ru/video/123' WHERE id=$1",[a.contenido_id]);
 await db.exec("UPDATE public.episodios SET descarga='https://mediafire.com/episode',playback_url='https://ok.ru/video/456' WHERE numero=1");
 const b=await apply(),c=await apply();
 assert.equal(a.contenido_id,b.contenido_id);assert.equal(b.contenido_id,c.contenido_id);
 assert.equal((await db.query('SELECT count(*)::int n FROM contenido')).rows[0].n,1);
 let episodes=(await db.query('SELECT * FROM episodios ORDER BY numero')).rows;
 assert.equal(episodes.length,3);assert.ok(episodes.every(e=>e.disponible));
 assert.equal(episodes[0].descarga,'https://mediafire.com/episode');assert.equal(episodes[0].vimeus_id,111);
 assert.equal(episodes[0].provider_download_url,'https://vimeus.com/d/111');assert.equal(episodes[0].playback_url,'https://ok.ru/video/456');
 await apply(old,'importar_vimeus');
 episodes=(await db.query('SELECT * FROM episodios ORDER BY numero')).rows;assert.equal(episodes[1].disponible,true);
 const item=(await db.query('SELECT * FROM contenido')).rows[0];assert.equal(item.descarga,'https://mediafire.com/movie');assert.equal(item.fuente,'okru');assert.equal(item.rating,8.1);
});
test('movies are idempotent and a failed document is atomic',async()=>{
 const movie={contenido:{tipo:'pelicula',videoapi_kind:'pelicula',tmdb_id:22,tmdb_media:'movie',titulo:'Movie'},temporadas:[]};
 assert.equal((await apply(movie)).contenido_id,(await apply(movie)).contenido_id);
 const broken=structuredClone(doc);broken.contenido.tmdb_id=999;broken.temporadas[0].capitulos.push({numero:'invalid'});
 await assert.rejects(apply(broken));assert.equal((await db.query('SELECT count(*)::int n FROM contenido WHERE tmdb_id=999')).rows[0].n,0);
});
test('private queues, leases and publisher reject anon and authenticated roles',async()=>{
 for(const role of ['anon','authenticated']){
  await db.exec('SET ROLE '+role);
  await assert.rejects(db.query('SELECT * FROM cine_security.videoapi_jobs'),/permission denied/);
  await assert.rejects(db.query('SELECT * FROM cine_security.admin_leases'),/permission denied/);
  await assert.rejects(apply(),/permission denied/);
  await db.exec('RESET ROLE');
 }
});
test('session migration keeps admin deadline, extends viewing only once and fails safe for older code',async()=>{
 await db.exec("INSERT INTO cine_security.accounts(id,name,created_at) VALUES('legacy','Owner',0); INSERT INTO cine_security.sessions(token_hash,account_id,csrf,expires_at,admin) VALUES('legacy-token','legacy','csrf',extract(epoch FROM now())+3600,1)");
 const sql=await readFile(new URL('../migrations/016_session_continuity.sql',import.meta.url),'utf8');
 const old=(await db.query("SELECT expires_at FROM cine_security.sessions WHERE token_hash='legacy-token'")).rows[0].expires_at;
 await db.exec(sql);
 const row=(await db.query("SELECT * FROM cine_security.sessions WHERE token_hash='legacy-token'")).rows[0];
 assert.equal(row.admin,0);assert.ok(row.expires_at>old+500000);
 assert.equal((await db.query("SELECT expires_at FROM cine_security.admin_leases WHERE token_hash='legacy-token'")).rows[0].expires_at,old);
 await db.exec(sql);assert.equal((await db.query("SELECT expires_at FROM cine_security.sessions WHERE token_hash='legacy-token'")).rows[0].expires_at,row.expires_at);
 await db.exec("DELETE FROM cine_security.sessions WHERE token_hash='legacy-token'");
 assert.equal((await db.query("SELECT count(*)::int n FROM cine_security.admin_leases WHERE token_hash='legacy-token'")).rows[0].n,0);
});
