const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

test('opening two details shares lazy loads; a failed asset alone can retry',async()=>{
 const nodes=[];
 const context={window:{},document:{createElement:()=>({remove(){}}),head:{append:n=>nodes.push(n)}}};
 vm.runInNewContext(fs.readFileSync('static/catalog/detail-loader.js','utf8'),context);
 assert.equal(nodes.length,0);
 const first=context.window.DetailAssets.ready(),second=context.window.DetailAssets.ready();
 assert.equal(nodes.length,5);
 const results=Promise.allSettled([first,second]);
 nodes[0].onerror();for(const n of nodes.slice(1))n.onload();
 assert.ok((await results).every(r=>r.status==='rejected'));
 const retry=context.window.DetailAssets.ready();
 assert.equal(nodes.length,6);assert.equal(nodes[5].src,nodes[0].src);
 nodes[5].onload();await retry;
 await context.window.DetailAssets.ready();assert.equal(nodes.length,6);
});

test('home starts while account sync is pending; no legacy startup requests',async()=>{
 let release;const calls=[],pages=[];
 const context={window:{ProfileSync:{ready:new Promise(r=>release=r)}},AccountSession:{state:{user:{telegram_id:5824989040},authenticated:true}},
  URLSearchParams,location:{search:''},navigationStarted:false,userId:null,membresiaActiva:null,
  cambiarVista:view=>{pages.push(view);context.navigationStarted=true},document:{getElementById:()=>null},
  console:{log(){},error(){}},fetch:async path=>{calls.push(path);return {ok:true,json:async()=>({active:true,permanent:true})}},
  inicializarUserChip(){},actualizarBadge(){},configurarFooter(){},configurarEventosFooter(){}};
 const source=fs.readFileSync('static/app.js','utf8');
 vm.runInNewContext(source.slice(source.indexOf('async function iniciar()'),source.indexOf('function actualizarBadge()')),context);
 const pending=context.iniciar();assert.deepEqual(pages,['inicio']);assert.deepEqual(calls,[]);
 release();await pending;
 assert.deepEqual(calls,['/api/payments/mine']);
 assert.equal(context.membresiaActiva.membresias_planes.nombre,'Propietario');
});
