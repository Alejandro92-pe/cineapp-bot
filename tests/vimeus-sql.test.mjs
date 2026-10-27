// Execute the actual migration and RPC in local PostgreSQL (PGlite/WASM).
// Install: npm install --prefix .local/sql-runtime --save-exact @electric-sql/pglite@0.5.12
import { PGlite } from '../.local/sql-runtime/node_modules/@electric-sql/pglite/dist/index.js';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';

const migration = await readFile(new URL('../migrations/002_vimeus_episodes.sql', import.meta.url), 'utf8');
const db = new PGlite();
await db.exec(`
  CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;
  CREATE TABLE public.contenido(id serial PRIMARY KEY, tipo text, tmdb_id bigint, titulo text,
    imagen_url text, sinopsis text, genero text, fuente text, disponible boolean, destacado boolean, descarga text, enlace_canal text);
  CREATE TABLE public.temporadas(id serial PRIMARY KEY, contenido_id integer REFERENCES public.contenido(id), numero integer,
    nombre text, poster_url text, descripcion text, episodios integer, enlace text);
`);
await db.exec(migration);
await db.exec(await readFile(new URL('../migrations/004_episode_downloads.sql', import.meta.url), 'utf8'));
await db.exec(await readFile(new URL('../migrations/005_vimeus_live_format.sql', import.meta.url), 'utf8'));
const manifest = () => ({contenido:{tipo:'anime',tmdb_id:900202,titulo:'Anime SQL',imagen_url:'',sinopsis:'',genero:''},
  temporadas:[{numero:0,nombre:'Especiales',poster_url:'',descripcion:'',capitulos:[ep(1)]},
    {numero:1,nombre:'Temporada 1',poster_url:'',descripcion:'',capitulos:Array.from({length:60},(_,i)=>ep(i+1))}]});
function ep(numero){return {numero,vimeus_id:1000+numero,titulo:`Episodio ${numero}`,sinopsis:'',imagen_url:'',duracion:null};}
const apply = async document => (await db.query('SELECT public.importar_vimeus($1::jsonb) AS result',[JSON.stringify(document)])).rows[0].result;

test('actual SQL imports full seasons and reimports without duplicate IDs or losing downloads',async()=>{
  const first=await apply(manifest()); assert.equal(first.episodios,61); assert.equal(first.creados,61);
  await db.query('UPDATE public.contenido SET descarga=$1,titulo=$2,disponible=false WHERE id=$3',['https://www.mediafire.com/file/keep/file','Editorial',first.contenido_id]);
  await db.exec("UPDATE public.temporadas SET enlace='https://example.org/keep',nombre='Editorial season'");
  const ids=(await db.query('SELECT id FROM public.episodios ORDER BY id')).rows;
  const second=await apply(manifest()); assert.equal(second.creados,0); assert.equal(second.actualizados,61);
  assert.deepEqual((await db.query('SELECT id FROM public.episodios ORDER BY id')).rows,ids);
  const content=(await db.query('SELECT * FROM public.contenido')).rows[0];
  assert.equal(content.descarga,'https://www.mediafire.com/file/keep/file'); assert.equal(content.titulo,'Editorial'); assert.equal(content.disponible,false);
  assert.ok((await db.query('SELECT * FROM public.temporadas')).rows.every(s=>s.nombre==='Editorial season' && s.enlace==='https://example.org/keep'));
});
test('a constraint failure rolls back the entire SQL import',async()=>{
  const bad=manifest(); bad.contenido.tmdb_id=900999; bad.temporadas[1].capitulos[45].duracion=0;
  await assert.rejects(apply(bad),/check constraint/);
  assert.equal((await db.query('SELECT count(*)::int AS n FROM public.contenido WHERE tmdb_id=900999')).rows[0].n,0);
  assert.equal((await db.query('SELECT count(*)::int AS n FROM public.episodios')).rows[0].n,61);
});
test('SQL keeps retired chapters recoverable and restores them on reimport',async()=>{
  const smaller=manifest(); smaller.temporadas=smaller.temporadas.slice(1); smaller.temporadas[0].capitulos=smaller.temporadas[0].capitulos.slice(0,58);
  const result=await apply(smaller); assert.equal(result.retirados,3);
  assert.equal((await db.query('SELECT count(*)::int AS n FROM public.episodios')).rows[0].n,61);
  assert.equal((await db.query('SELECT count(*)::int AS n FROM public.episodios WHERE disponible')).rows[0].n,58);
  const restored=await apply(manifest()); assert.equal(restored.creados,0);
  assert.equal((await db.query('SELECT count(*)::int AS n FROM public.episodios WHERE disponible')).rows[0].n,61);
});
test('different media kinds sharing a TMDB number remain separate',async()=>{
  const other=manifest(); other.contenido.tipo='serie'; await apply(other);
  assert.equal((await db.query('SELECT count(*)::int AS n FROM public.contenido WHERE tmdb_id=900202')).rows[0].n,2);
});
test('anonymous and authenticated Supabase roles cannot execute import or read episode table',async()=>{
  for(const role of ['anon','authenticated']){
    await db.exec(`SET ROLE ${role}`);
    await assert.rejects(apply(manifest()),/permission denied/);
    await assert.rejects(db.query('SELECT * FROM public.episodios'),/permission denied/);
    await db.exec('RESET ROLE');
  }
  await db.exec('SET ROLE service_role');
  assert.equal((await apply(manifest())).episodios,61);
  await db.exec('RESET ROLE');
});
test('repeated queued imports produce one identity for every episode',async()=>{
  await Promise.all(Array.from({length:4},()=>apply(manifest())));
  const counts=await db.query('SELECT temporada_id,numero,count(*)::int AS n FROM public.episodios GROUP BY temporada_id,numero HAVING count(*)>1');
  assert.equal(counts.rows.length,0);
});
test('live provider supports missing IDs, private downloads and preserves manual overrides and trailers',async()=>{
 const live=manifest();live.contenido.tmdb_id=777;live.contenido.trailer_url='https://www.youtube.com/watch?v=abcdefghijk';
 live.temporadas=[{...live.temporadas[0],capitulos:[{...ep(1),vimeus_id:null,provider_download_url:'https://vimeus.com/d/anime?tmdb=777&se=0&ep=1'}]}];
 const result=await apply(live);
 const query=`SELECT ep.* FROM public.episodios ep JOIN public.temporadas t ON t.id=ep.temporada_id WHERE t.contenido_id=$1`;
 const episode=(await db.query(query,[result.contenido_id])).rows[0];assert.equal(episode.vimeus_id,null);assert.match(episode.provider_download_url,/vimeus/);
 await db.query('UPDATE public.episodios SET descarga=$1 WHERE id=$2',['https://mediafire.com/file/manual/file',episode.id]);
 live.temporadas[0].capitulos[0].provider_download_url+='&updated=1';await apply(live);
 const updated=(await db.query(query,[result.contenido_id])).rows[0];assert.match(updated.descarga,/mediafire/);assert.match(updated.provider_download_url,/updated=1/);
 assert.equal((await db.query('SELECT trailer_url FROM public.contenido WHERE id=$1',[result.contenido_id])).rows[0].trailer_url,live.contenido.trailer_url);
});
test.after(async()=>{await db.close();});
test('episode download survives SQL reimport and remains denied to public roles',async()=>{
 await apply(manifest());
 await db.query("UPDATE public.episodios SET descarga=$1 WHERE numero=1",['https://mediafire.com/file/episode/file']);
 await apply(manifest());
 assert.ok((await db.query("SELECT descarga FROM public.episodios WHERE numero=1")).rows.every(r=>r.descarga==='https://mediafire.com/file/episode/file'));
 await db.exec('SET ROLE anon');
 await assert.rejects(()=>db.query('SELECT descarga FROM public.episodios'));
 await db.exec('RESET ROLE');
});
