// Offline rehearsal against the backed-up production schema and rows. No network.
import {PGlite} from '../.local/sql-runtime/node_modules/@electric-sql/pglite/dist/index.js';
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=path.resolve('.local/production-20261026');
const read=async name=>JSON.parse(await readFile(path.join(root,name),'utf8'));
const schema=await read('schema-before.json');
const db=new PGlite();
const ident=value=>'"'+value.replaceAll('"','""')+'"';
await db.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role BYPASSRLS;');
const tables=[...new Set(schema.columns.map(c=>c.table_name))];
for(const table of tables){
 const columns=schema.columns.filter(c=>c.table_name===table);
 const ddl=columns.map(c=>{
   let type=c.data_type;
   if(c.column_default?.startsWith('nextval(')) type=type==='bigint'?'bigserial':'serial';
   return `${ident(c.column_name)} ${type}${c.is_nullable==='NO'?' NOT NULL':''}${c.column_default&&!c.column_default.startsWith('nextval(')?' DEFAULT '+c.column_default:''}`;
 });
 await db.exec(`CREATE TABLE public.${ident(table)}(${ddl.join(',')});`);
 const records=await read(table+'-before.json');
 await db.query(`INSERT INTO public.${ident(table)} SELECT * FROM jsonb_populate_recordset(NULL::public.${ident(table)}, $1::jsonb)`,[JSON.stringify(records)]);
 if(columns.some(c=>c.column_name==='id'&&c.column_default?.startsWith('nextval('))){
   await db.exec(`SELECT setval(pg_get_serial_sequence('public.${table}','id'), coalesce((SELECT max(id) FROM public.${ident(table)}),1),true);`);
 }
}
for(const c of schema.constraints.filter(c=>!c.definition.startsWith('FOREIGN KEY'))){
 await db.exec(`ALTER TABLE public.${ident(c.table.replace('public.',''))} ADD CONSTRAINT ${ident(c.name)} ${c.definition};`);
}
for(const c of schema.constraints.filter(c=>c.definition.startsWith('FOREIGN KEY'))){
 await db.exec(`ALTER TABLE public.${ident(c.table.replace('public.',''))} ADD CONSTRAINT ${ident(c.name)} ${c.definition};`);
}
const before={};
for(const table of tables)before[table]=(await db.query(`SELECT to_jsonb(t) as row FROM public.${ident(table)} t ORDER BY id`)).rows;
const names=['001_security','002_vimeus_episodes','003_monthly_payments','004_episode_downloads','005_vimeus_live_format','006_popularity','007_okru','008_okru_editor','009_tmdb_metadata','010_profiles','011_import_ratings'];
for(const name of names)await db.exec(await readFile(`migrations/${name}.sql`,'utf8'));
for(const table of tables){
 const oldKeys=schema.columns.filter(c=>c.table_name===table).map(c=>c.column_name);
 const after=(await db.query(`SELECT to_jsonb(t) as row FROM public.${ident(table)} t ORDER BY id`)).rows.map(({row})=>({row:Object.fromEntries(oldKeys.map(k=>[k,row[k]]))}));
 assert.deepEqual(after,before[table],`Migration modified existing ${table}`);
}
const summary={migrations:names.length,tablesPreserved:tables.length,users:before.usuarios.length,titles:before.contenido.length,downloads:before.contenido.filter(r=>r.row.descarga).length,productionWrites:false};
await db.exec(await readFile('migrations/012_catalog_aliases.sql','utf8'));
await db.exec(await readFile('migrations/014_catalog_queue.sql','utf8'));
const dataSql=await readFile(path.join(root,'release-data.sql'),'utf8');
await db.exec(dataSql);
const counts=await db.query('SELECT (SELECT count(*) FROM public.contenido)::int as titles,(SELECT count(*) FROM public.temporadas)::int as seasons,(SELECT count(*) FROM public.episodios)::int as episodes,(SELECT count(*) FROM cine_security.accounts)::int as accounts');
await db.exec(dataSql);
assert.deepEqual((await db.query('SELECT (SELECT count(*) FROM public.contenido)::int as titles,(SELECT count(*) FROM public.temporadas)::int as seasons,(SELECT count(*) FROM public.episodios)::int as episodes,(SELECT count(*) FROM cine_security.accounts)::int as accounts')).rows,counts.rows,'Replaying release duplicated records');
for(const table of ['usuarios','membresias_activas','pagos_manuales'])assert.deepEqual((await db.query(`SELECT to_jsonb(t) as row FROM public.${ident(table)} t ORDER BY id`)).rows,before[table]);
const preservedDownloads=before.contenido.filter(r=>r.row.descarga).map(r=>({id:r.row.id,descarga:r.row.descarga}));
const afterDownloads=(await db.query('SELECT id,descarga FROM public.contenido WHERE descarga IS NOT NULL AND descarga<>\'\' ORDER BY id')).rows;
assert.deepEqual(afterDownloads,preservedDownloads,'Manual download URLs changed');
await db.exec(await readFile('migrations/013_private_business_data.sql','utf8'));
await db.exec('SET ROLE anon;');
for(const table of ['usuarios','pagos_manuales','contenido'])await assert.rejects(()=>db.query(`SELECT * FROM public.${table}`));
await db.exec('RESET ROLE; SET ROLE service_role;');
assert.equal((await db.query('SELECT count(*)::int n FROM public.usuarios')).rows[0].n,before.usuarios.length);
await db.exec('RESET ROLE;');
const automated=await db.query('SELECT public.importar_catalogo_automatico($1::jsonb) AS result',[JSON.stringify({contenido:{tipo:'pelicula',tmdb_media:'movie',tmdb_id:990000001,titulo:'Validación offline',rating:8.4,'año':2026},temporadas:[]})]);
const imported=(await db.query('SELECT rating,"año" FROM public.contenido WHERE id=$1',[automated.rows[0].result.contenido_id])).rows[0];
assert.equal(Number(imported.rating),8.4);assert.equal(imported['año'],2026);
await db.exec('SET ROLE anon;');
await assert.rejects(()=>db.query('SELECT * FROM cine_security.catalog_jobs'));
await db.exec('RESET ROLE;');
summary.releaseData=counts.rows[0];summary.idempotent=true;summary.publicDatabaseAccessDenied=true;
summary.automaticQueueSchemaValidated=true;
await writeFile(path.join(root,'migration-rehearsal.json'),JSON.stringify(summary,null,2));
console.log(JSON.stringify(summary));
await db.close();
