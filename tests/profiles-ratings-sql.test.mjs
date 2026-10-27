import {PGlite} from '../.local/sql-runtime/node_modules/@electric-sql/pglite/dist/index.js';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
const db=new PGlite();
await db.exec(`CREATE ROLE anon;CREATE ROLE authenticated;CREATE ROLE service_role;
CREATE TABLE public.contenido(id serial PRIMARY KEY,tipo text,tmdb_id bigint,titulo text,imagen_url text,sinopsis text,genero text,fuente text,disponible boolean,destacado boolean,descarga text,enlace_canal text);
CREATE TABLE public.temporadas(id serial PRIMARY KEY,contenido_id integer REFERENCES public.contenido(id),numero integer,nombre text,poster_url text,descripcion text,episodios integer,enlace text);`);
for(const name of ['001_security','002_vimeus_episodes','004_episode_downloads','005_vimeus_live_format','007_okru','009_tmdb_metadata','010_profiles','011_import_ratings']){
 await db.exec(await readFile(new URL('../migrations/'+name+'.sql',import.meta.url),'utf8'));
}
test.after(()=>db.close());
test('private profile tables migrate on PostgreSQL and deny direct public access',async()=>{
 await db.exec("INSERT INTO cine_security.accounts(id,name,created_at) VALUES('A','Cuenta',0); INSERT INTO cine_security.profiles VALUES('A','fox',0); INSERT INTO cine_security.saved_items VALUES('A',1,1,0)");
 for(const role of ['anon','authenticated']){
  await db.exec('SET ROLE '+role);
  await assert.rejects(db.query('SELECT * FROM cine_security.profiles'),/permission denied/);
  await assert.rejects(db.query("INSERT INTO cine_security.saved_items VALUES('A',2,1,0)"),/permission denied/);
  await db.exec('RESET ROLE');
 }
 await assert.rejects(db.query("UPDATE cine_security.profiles SET avatar='untrusted-url'"),/check constraint/);
 await db.exec("UPDATE cine_security.saved_items SET saved=0 WHERE account_id='A' AND content_id=1;INSERT INTO cine_security.saved_items VALUES('A',1,1,2) ON CONFLICT DO NOTHING");
 assert.equal((await db.query("SELECT saved FROM cine_security.saved_items WHERE account_id='A'")).rows[0].saved,0);
});
const season={numero:1,nombre:'Temporada 1',poster_url:'',descripcion:'',capitulos:[{numero:1,titulo:'Capítulo',sinopsis:'',imagen_url:'',duracion:20,vimeus_id:1}]};
test('actual Vimeus RPC imports and updates rating without changing manual downloads',async()=>{
 const doc={contenido:{tipo:'serie',tmdb_id:120911,titulo:'Serie',rating:7.993},temporadas:[season]};
 const apply=async()=> (await db.query('SELECT public.importar_vimeus($1::jsonb) AS result',[JSON.stringify(doc)])).rows[0].result;
 const result=await apply();
 await db.query("UPDATE public.contenido SET descarga='https://mediafire.com/manual' WHERE id=$1",[result.contenido_id]);
 await db.exec("UPDATE public.episodios SET descarga='https://mediafire.com/episode'");
 doc.contenido.rating=8.2;await apply();
 let row=(await db.query('SELECT * FROM public.contenido WHERE id=$1',[result.contenido_id])).rows[0];
 assert.equal(row.rating,8.2);assert.equal(row.descarga,'https://mediafire.com/manual');
 delete doc.contenido.rating;await apply();
 row=(await db.query('SELECT rating FROM public.contenido WHERE id=$1',[result.contenido_id])).rows[0];
 assert.equal(row.rating,8.2);assert.equal((await db.query('SELECT descarga FROM public.episodios LIMIT 1')).rows[0].descarga,'https://mediafire.com/episode');
});
test('actual TMDB metadata RPC persists biblical rating and preserves OK.ru links',async()=>{
 const doc={contenido:{tipo:'biblico',tmdb_id:66825,tmdb_media:'tv',titulo:'Josué',rating:7.5},temporadas:[season]};
 const apply=async()=> (await db.query('SELECT public.importar_metadatos($1::jsonb) AS result',[JSON.stringify(doc)])).rows[0].result;
 const result=await apply();
 await db.query("UPDATE public.contenido SET playback_url='https://ok.ru/video/123',descarga='https://mediafire.com/biblical' WHERE id=$1",[result.contenido_id]);
 doc.contenido.rating=8.1;await apply();
 const row=(await db.query('SELECT * FROM public.contenido WHERE id=$1',[result.contenido_id])).rows[0];
 assert.equal(row.rating,8.1);assert.equal(row.playback_url,'https://ok.ru/video/123');assert.equal(row.descarga,'https://mediafire.com/biblical');
});
