/* Only a public offline notice and its fixed artwork are cached. Never videos,
 * account pages, API responses, payment data, QR codes or download links. */
const OFFLINE_CACHE='quehay-offline-v3';
const OFFLINE_URL='/offline';
const PUBLIC_ASSETS=[OFFLINE_URL,'/static/pwa/install.css?v=3','/static/pwa/icons/icon-192.png?v=3','/static/pwa/icons/icon-512.png?v=3','/static/pwa/icons/maskable-512.png?v=3'];
const NAVIGATIONS=new Set(['/','/cuenta','/membresia','/instalar']);

async function valid(response,path){
  if(!response||!response.ok||response.redirected)return false;
  const mime=(response.headers.get('Content-Type')||'').split(';')[0].trim();
  if(path===OFFLINE_URL)return mime==='text/html'&&(await response.clone().text()).includes('offline-card');
  return path.includes('.css?')?mime==='text/css':mime==='image/png';
}
self.addEventListener('install',event=>{
  event.waitUntil((async()=>{
    const responses=await Promise.all(PUBLIC_ASSETS.map(async path=>{
      const response=await fetch(new Request(path,{cache:'reload',credentials:'omit'}));
      if(!await valid(response,path))throw Error('Invalid public asset');
      return [path,response];
    }));
    const cache=await caches.open(OFFLINE_CACHE);
    await Promise.all(responses.map(([path,response])=>cache.put(path,response)));
  })());
});
self.addEventListener('activate',event=>{
  event.waitUntil((async()=>{
    const names=await caches.keys();
    await Promise.all(names.filter(name=>name.startsWith('quehay-offline-')&&name!==OFFLINE_CACHE).map(name=>caches.delete(name)));
    await self.clients.claim();
  })());
});
self.addEventListener('message',event=>{
  if(event.data?.type==='ACTIVATE_UPDATE')self.skipWaiting();
});
self.addEventListener('fetch',event=>{
  const request=event.request,url=new URL(request.url);
  if(request.method!=='GET'||url.origin!==self.location.origin)return;
  if(request.mode==='navigate'&&NAVIGATIONS.has(url.pathname)){
    event.respondWith(fetch(request).catch(async()=>{
      const cached=await (await caches.open(OFFLINE_CACHE)).match(OFFLINE_URL);
      return await valid(cached,OFFLINE_URL)?cached:new Response('Sin conexión. Conéctate a internet y vuelve a abrir QueHay.',{status:503,headers:{'Content-Type':'text/plain; charset=utf-8'}});
    }));
    return;
  }
  const path=url.pathname+url.search;
  if(PUBLIC_ASSETS.includes(path)){
    event.respondWith((async()=>{
      const cache=await caches.open(OFFLINE_CACHE);
      try{
        const response=await fetch(request);
        if(await valid(response,path)){await cache.put(path,response.clone());return response;}
      }catch{}
      const cached=await cache.match(path);
      return await valid(cached,path)?cached:new Response('Recurso no disponible. Vuelve a intentarlo.',{status:503});
    })());
  }
});
