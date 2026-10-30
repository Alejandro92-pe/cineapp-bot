/* PostgreSQL WASM validation; no network or Supabase connection. */
const {PGlite}=require(process.env.PGLITE_MODULE||'C:/Users/richa/Mis Proyectos/cineapp-render/.local/sql-runtime/node_modules/@electric-sql/pglite');
const fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{const db=new PGlite();try{
 await db.exec('CREATE ROLE anon; CREATE ROLE authenticated;');
 await db.exec(fs.readFileSync('migrations/001_security.sql','utf8'));
 await db.exec("INSERT INTO cine_security.accounts(id,name,telegram_id,created_at) VALUES ('test-owner','Local owner',5824989040,1)");
 const before=(await db.query('SELECT * FROM cine_security.accounts')).rows;
 const migration=fs.readFileSync('migrations/017_tv_pairing.sql','utf8');await db.exec(migration);await db.exec(migration);
 assert.deepEqual((await db.query('SELECT * FROM cine_security.accounts')).rows,before);
 const rows=(await db.query("SELECT relname,relrowsecurity FROM pg_class WHERE relname IN ('tv_pairings','tv_devices') ORDER BY relname")).rows;
 assert.equal(rows.length,2);assert(rows.every(x=>x.relrowsecurity));
 for(const role of ['anon','authenticated']){
  await db.exec('SET ROLE '+role);
  await assert.rejects(db.query('SELECT * FROM cine_security.tv_devices'),/permission denied/);
  await assert.rejects(db.query('INSERT INTO cine_security.tv_pairings(device_hash,code_hash,expires_at,state) VALUES (\'x\',\'y\',1,\'pending\')'),/permission denied/);
  await db.exec('RESET ROLE');
 }
 await assert.rejects(db.exec("INSERT INTO cine_security.tv_pairings(device_hash,code_hash,expires_at,state) VALUES ('a','b',1,'admin')"),/check constraint/);
 await assert.rejects(db.exec("INSERT INTO cine_security.tv_devices(token_hash,account_id,identity_stamp,csrf,expires_at,created_at) VALUES ('x','missing','stamp','csrf',2,1)"),/foreign key/);
 await db.exec("INSERT INTO cine_security.tv_devices(token_hash,account_id,identity_stamp,csrf,expires_at,created_at) VALUES ('x','test-owner','stamp','csrf',2,1)");
 await db.exec("DELETE FROM cine_security.accounts WHERE id='test-owner'");
 assert.equal((await db.query('SELECT * FROM cine_security.tv_devices')).rows.length,0);
 console.log(JSON.stringify({postgresWasm:true,idempotent:true,accountsPreserved:true,rls:true,anonymousDenied:true,authenticatedDenied:true,foreignKeys:true,accountDeleteCascades:true,remoteWrites:0}));
 }finally{await db.close();}})().catch(e=>{console.error(e);process.exitCode=1});
