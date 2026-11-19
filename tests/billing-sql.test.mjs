import {PGlite} from '../.local/sql-runtime/node_modules/@electric-sql/pglite/dist/index.js';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
const db=new PGlite();
await db.exec('CREATE ROLE anon;CREATE ROLE authenticated;');
await db.exec(await readFile(new URL('../migrations/001_security.sql',import.meta.url),'utf8'));
await db.exec(await readFile(new URL('../migrations/003_monthly_payments.sql',import.meta.url),'utf8'));
await db.exec("INSERT INTO cine_security.accounts(id,email,name,created_at) VALUES ('before-017','old@example.test','Old',1)");
await db.exec("INSERT INTO cine_security.payment_orders(id,code,account_id,method,amount_minor,currency,days,status,created_at,updated_at) VALUES ('old-price','QH-old','before-017','bmc',150,'USD',30,'approved',1,1)");
const m017=await readFile(new URL('../migrations/017_bmc_membership.sql',import.meta.url),'utf8');
await db.exec(m017);await db.exec(m017); // idempotent, keeps rows written at the old price
await db.exec("INSERT INTO cine_security.accounts(id,email,name,created_at) VALUES ('test-account','sql@example.test','SQL Test',1)");
const insert=(id,method='bmc',amount=150,currency='USD',days=30,status='pending_provider')=>db.query('INSERT INTO cine_security.payment_orders(id,code,account_id,method,amount_minor,currency,days,status,created_at,updated_at) VALUES ($1,$2,\'test-account\',$3,$4,$5,$6,$7,1,1)',[id,'QH-'+id,method,amount,currency,days,status]);
test('payment migration supports all three fixed prices and rejects forged prices/durations',async()=>{
  await insert('bmc');await insert('yape','yape_plin',550,'PEN');await insert('binance','binance',150,'USDT');
  await assert.rejects(insert('wrong-price','bmc',1),/check constraint/);
  await assert.rejects(insert('wrong-days','bmc',150,'USD',365),/check constraint/);
  await assert.rejects(insert('wrong-state','bmc',150,'USD',30,'paid-client'),/check constraint/);
});
test('017 accepts the new US$2 / S/7.50 / 2 USDT prices and keeps the old ones',async()=>{
  await insert('new-bmc','bmc',200);await insert('new-yape','yape_plin',750,'PEN');await insert('new-binance','binance',200,'USDT');
  assert.equal((await db.query("SELECT count(*)::int n FROM cine_security.payment_orders WHERE id='old-price'")).rows[0].n,1);
  await assert.rejects(insert('between','bmc',175),/check constraint/);
  await assert.rejects(insert('yape-usd','yape_plin',200,'USD'),/check constraint/);
});
test('one receipt cannot activate two orders and one order cannot consume two receipts',async()=>{
  await db.exec("INSERT INTO cine_security.payment_receipts(key,order_id,created_at) VALUES ('receipt','bmc',1)");
  await assert.rejects(db.exec("INSERT INTO cine_security.payment_receipts(key,order_id,created_at) VALUES ('receipt','yape',1)"),/unique constraint/);
  await assert.rejects(db.exec("INSERT INTO cine_security.payment_receipts(key,order_id,created_at) VALUES ('other','bmc',1)"),/unique constraint/);
});
test('public client roles cannot read or modify private orders, entitlements or QR assets',async()=>{
  for(const role of ['anon','authenticated']){
    await db.exec(`SET ROLE ${role}`);
    for(const table of ['payment_orders','paid_access','payment_qr_assets','payment_receipts','payment_review_events','bmc_memberships','bmc_events'])await assert.rejects(db.query(`SELECT * FROM cine_security.${table}`),/permission denied/);
    await db.exec('RESET ROLE');
  }
});
test.after(async()=>await db.close());
