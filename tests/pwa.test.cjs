const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const ORIGIN='http://127.0.0.1:5010';
function worker(){
  const handlers={},stores=new Map(),network=[],calls={claim:0,skip:0};let fail=false,status=200,badMime=false;
  const key=r=>{const u=new URL(typeof r==='string'?r:r.url,ORIGIN);return u.pathname+u.search;};
  async function fetcher(r){network.push(typeof r==='string'?r:r.url);if(fail)throw Error('offline');const path=key(r);return new Response(path==='/offline'?'offline-card':'network',{status,headers:{'Content-Type':badMime?'text/html':path.includes('.css?')?'text/css':path.includes('.png?')?'image/png':'text/html'}});}
  const caches={async keys(){return [...stores.keys()]},async delete(name){return stores.delete(name)},async open(name){
    if(!stores.has(name))stores.set(name,new Map());const data=stores.get(name);
    return {async put(r,response){data.set(key(r),response);},async addAll(reqs){for(const r of reqs){const response=await fetcher(r);if(!response.ok)throw Error('precache failed');data.set(key(r),response);}},async match(r){return data.get(key(r))?.clone()}};
  }};
  const self={location:{origin:ORIGIN},addEventListener(n,fn){handlers[n]=fn},clients:{async claim(){calls.claim++}},skipWaiting(){calls.skip++}};
  class LocalRequest{constructor(url,opts){this.url=new URL(url,ORIGIN).href;Object.assign(this,opts);}}
  const context={self,caches,URL,Request:LocalRequest,Response,fetch:fetcher,Set};vm.createContext(context);vm.runInContext(fs.readFileSync('static/pwa/sw.js','utf8'),context);
  const lifecycle=async name=>{let pending;handlers[name]({waitUntil(p){pending=p}});await pending;};
  async function dispatch(path,{method='GET',mode='cors'}={}){let response;handlers.fetch({request:{url:new URL(path,ORIGIN).href,method,mode},respondWith(p){response=p}});return response?await response:null;}
  return {handlers,stores,network,calls,lifecycle,dispatch,setOffline(){fail=true},setStatus(s){status=s},setBadMime(){badMime=true},setOnline(){fail=false}};
}
test('worker precaches only the offline notice, stylesheet and app icons',async()=>{
  const w=worker();await w.lifecycle('install');
  const paths=[...w.stores.values()][0].keys();
  assert.deepEqual([...paths].sort(),['/offline','/static/pwa/install.css?v=3','/static/pwa/icons/icon-192.png?v=3','/static/pwa/icons/icon-512.png?v=3','/static/pwa/icons/maskable-512.png?v=3'].sort());
  assert.equal(w.calls.skip,0);
});
test('navigation uses network without storing account or membership responses',async()=>{
  const w=worker();await w.lifecycle('install');const size=[...w.stores.values()][0].size;
  for(const path of ['/','/cuenta','/membresia','/instalar'])assert.equal(await (await w.dispatch(path,{mode:'navigate'})).text(),'network');
  assert.equal([...w.stores.values()][0].size,size);
});
test('offline navigation falls back to the cached public notice',async()=>{
  const w=worker();await w.lifecycle('install');w.setOffline();
  const r=await w.dispatch('/cuenta?next=membership',{mode:'navigate'});assert.equal(r.status,200);assert.equal(await r.text(),'offline-card');
  const noCache=worker();noCache.setOffline();assert.equal((await noCache.dispatch('/',{mode:'navigate'})).status,503);
});
test('API, payments, downloads, admin, external media and mutations are never intercepted',async()=>{
  const w=worker();await w.lifecycle('install');w.setOffline();
  for(const path of ['/api/auth/me','/api/payments/mine','/api/payments/qr/yape_plin','/api/download/1','/api/playback/1','/api/admin/payments','/admin','/webhook/buymeacoffee','https://www.mediafire.com/file/example','https://vimeus.com/e/movie']){
    assert.equal(await w.dispatch(path,{mode:'navigate'}),null,path);
  }
  assert.equal(await w.dispatch('/',{method:'POST',mode:'navigate'}),null);
});
test('HTTP failures are returned unchanged, never replaced with a cached entitlement',async()=>{
  const w=worker();await w.lifecycle('install');w.setStatus(403);assert.equal((await w.dispatch('/cuenta',{mode:'navigate'})).status,403);
});
test('activation removes only obsolete QueHay offline caches',async()=>{
  const w=worker();await w.lifecycle('install');w.stores.set('quehay-offline-v0',new Map());w.stores.set('other-app-cache',new Map());await w.lifecycle('activate');
  assert(!w.stores.has('quehay-offline-v0'));assert(w.stores.has('other-app-cache'));assert(w.stores.has('quehay-offline-v3'));assert.equal(w.calls.claim,1);
});
test('updating an open app waits for explicit activation',async()=>{
  const w=worker();await w.lifecycle('install');assert.equal(w.calls.skip,0);w.handlers.message({data:{type:'unrelated'}});assert.equal(w.calls.skip,0);w.handlers.message({data:{type:'ACTIVATE_UPDATE'}});assert.equal(w.calls.skip,1);
});
test('asset query strings do not alias the public cache',async()=>{
  const w=worker();await w.lifecycle('install');assert.equal(await w.dispatch('/static/pwa/icons/icon-192.png?secret=private'),null);
});

function installer({standalone=false,telegram=false,secure=true,sw=true,userAgent='',platform='',maxTouchPoints=0}={}){
  const handlers={},elements={},calls={register:0,prompt:0};
  for(const id of ['install-button','install-status','install-local-help','install-guide','install-copy','install-runtime'])elements[id]={hidden:false,textContent:'',disabled:false};
  const registration={waiting:null,addEventListener(){}};
  const document={readyState:'complete',getElementById(id){return elements[id]||null}};
  const navigator={userAgent,platform,maxTouchPoints,clipboard:{async writeText(value){calls.copied=value;}},...(sw?{serviceWorker:{register:async()=>{calls.register++;return registration},ready:Promise.resolve(registration),addEventListener(){}}}:{})};
  const window={isSecureContext:secure,matchMedia:()=>({matches:standalone,addEventListener(){}}),addEventListener(name,fn){handlers[name]=fn},Telegram:{WebApp:{initData:telegram?'verified-data':''}}};
  const context={document,navigator,window,location:{hostname:'127.0.0.1',origin:ORIGIN},console};vm.createContext(context);vm.runInContext(fs.readFileSync('static/pwa/install.js','utf8'),context);
  function offer(outcome){handlers.beforeinstallprompt({preventDefault(){},async prompt(){calls.prompt++},userChoice:Promise.resolve({outcome})});}
  return {elements,handlers,calls,offer};
}
test('install button waits for a browser offer and an explicit click',async()=>{
  const i=installer();assert(i.elements['install-button'].hidden);i.offer('accepted');assert(!i.elements['install-button'].hidden);assert.equal(i.calls.prompt,0);
  await i.elements['install-button'].onclick();assert.equal(i.calls.prompt,1);assert(i.elements['install-button'].hidden);assert.match(i.elements['install-status'].textContent,/Solicitud aceptada/);
  assert(!i.elements['install-guide'].hidden);i.handlers.appinstalled();assert.match(i.elements['install-status'].textContent,/confirmó la instalación/);assert(i.elements['install-guide'].hidden);
});
test('dismissing the native prompt never claims that the app is installed',async()=>{
  const i=installer();i.offer('dismissed');await i.elements['install-button'].onclick();assert.match(i.elements['install-status'].textContent,/más adelante/);assert(!i.elements['install-guide'].hidden);
});
test('standalone and Telegram contexts receive appropriate installation guidance',()=>{
  const app=installer({standalone:true});assert(app.elements['install-button'].hidden);assert.match(app.elements['install-status'].textContent,/pantalla de inicio/);
  const mini=installer({telegram:true});mini.offer('accepted');assert(mini.elements['install-button'].hidden);assert.match(mini.elements['install-status'].textContent,/Chrome/);
});

test('iPhone and touch iPad get Safari guidance, Telegram keeps the external-browser step',()=>{
  for(const options of [{userAgent:'Mozilla iPhone'},{platform:'MacIntel',maxTouchPoints:5}]){
    const i=installer(options);assert.match(i.elements['install-status'].textContent,/Safari/);assert(i.elements['install-button'].hidden);assert.equal(i.calls.prompt,0);
    const t=installer({...options,telegram:true});assert.match(t.elements['install-status'].textContent,/navegador externo/);assert.equal(t.calls.prompt,0);
  }
});

test('copy installation link points to the browser guide without account information',async()=>{
  const i=installer();await i.elements['install-copy'].onclick();assert.equal(i.calls.copied,ORIGIN+'/instalar#navegador');
});
test('insecure or unsupported contexts keep browsing available without a service worker',()=>{
  const insecure=installer({secure:false});assert.equal(insecure.calls.register,0);assert.match(insecure.elements['install-status'].textContent,/HTTPS/);
  const unsupported=installer({sw:false});assert.equal(unsupported.calls.register,0);assert.match(unsupported.elements['install-runtime'].textContent,/seguir usando/);
});

test('incorrect HTML cannot become a cached stylesheet or icon',async()=>{
 const w=worker();w.setBadMime();await assert.rejects(w.lifecycle('install'),/Invalid public asset/);
 const r=await w.dispatch('/static/pwa/install.css?v=3');assert.equal(r.status,503);
 assert.equal([...w.stores.values()][0].size,0);
});
test('fresh assets replace stale responses and offline fallback validates MIME',async()=>{
 const w=worker();await w.lifecycle('install');const store=[...w.stores.values()][0];
 store.set('/static/pwa/install.css?v=3',new Response('<html>old</html>',{headers:{'Content-Type':'text/html'}}));
 assert.equal((await w.dispatch('/static/pwa/install.css?v=3')).headers.get('Content-Type'),'text/css');
 w.setOffline();assert.equal((await w.dispatch('/static/pwa/install.css?v=3')).headers.get('Content-Type'),'text/css');
 store.set('/static/pwa/icons/icon-192.png?v=3',new Response('wrong',{headers:{'Content-Type':'text/html'}}));
 assert.equal((await w.dispatch('/static/pwa/icons/icon-192.png?v=3')).status,503);
});
