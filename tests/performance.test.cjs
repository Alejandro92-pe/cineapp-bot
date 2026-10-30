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
 assert.equal(nodes.length,7);
 const results=Promise.allSettled([first,second]);
 nodes[0].onerror();for(const n of nodes.slice(1))n.onload();
 assert.ok((await results).every(r=>r.status==='rejected'));
 const retry=context.window.DetailAssets.ready();
 assert.equal(nodes.length,8);assert.equal(nodes[7].src,nodes[0].src);
 nodes[7].onload();await retry;
 await context.window.DetailAssets.ready();assert.equal(nodes.length,8);
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

test('detail is visible before chapters finish and does not wait for account sync',async()=>{
 const nodes=new Map();
 function node(){return {style:{},classList:{values:new Set(),contains(x){return this.values.has(x)},add(x){this.values.add(x)},toggle(){}},querySelector:()=>({focus(){},setAttribute(){}}),setAttribute(){}};}
 const doc={activeElement:{},body:{style:{}},getElementById:id=>{if(!nodes.has(id))nodes.set(id,node());return nodes.get(id)}};
 let release;
 const context={document:doc,detalleOpenRevision:0,contenidoSeleccionado:null,detallePreviousFocus:null,
  fetch:async()=>({ok:true,json:async()=>({data:[{id:7,titulo:'Historia',tipo:'anime'}]})}),
  DetailAssets:{ready:async()=>{}},AccountSession:{ready:new Promise(()=>{})},InlinePlayback:{close(){}},
  CatalogArtwork:{detail(){}},CatalogSynopsis:{set(){}},
  _resetTemporadas(){},safeImageSrc:()=>'',safeImageUrl:()=>'',escapeHtml:x=>x,esFavorito:()=>false,
  actualizarBtnFav(){},actualizarBtnLike(){},localStorage:{getItem:()=>null},cargarRelacionados(){},
  cargarTemporadas:()=>new Promise(r=>release=r),alert:message=>{throw Error(message)}};
 const source=fs.readFileSync('static/app.js','utf8');
 vm.runInNewContext(source.slice(source.indexOf('async function abrirModalContenido('),source.indexOf('function actualizarBtnFav(')),context);
 const pending=context.abrirModalContenido({id:7});await new Promise(r=>setImmediate(r));
 assert.equal(nodes.get('detalleTitulo').textContent,'Historia');assert.ok(nodes.get('modalDetalle').classList.contains('active'));
 release();await pending;
});

test('public cache coalesces requests, expires and evicts failures',async()=>{
 const source=fs.readFileSync('static/catalog/browse.js','utf8');
 let now=1000,calls=0;
 const ctx={Date:{now:()=>now},Map,Promise};
 vm.runInNewContext(source.slice(source.indexOf('  const publicCache='),source.indexOf('  const el=')),ctx);
 const load=async()=>{calls++;return {data:[1]}};
 await Promise.all([ctx.cachedPublic('home',load),ctx.cachedPublic('home',load)]);assert.equal(calls,1);
 now+=61000;await ctx.cachedPublic('home',load);assert.equal(calls,2);
 await assert.rejects(ctx.cachedPublic('bad',async()=>{throw Error('network')}));
 assert.deepEqual(await ctx.cachedPublic('bad',load),{data:[1]});assert.equal(calls,3);
});
