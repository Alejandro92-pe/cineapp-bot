// Local browser regression tests. API fixtures never reach production.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/richa/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'), fs=require('node:fs');
const origin=process.env.QH_TEST_ORIGIN || 'http://127.0.0.1:5031';
if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin))throw Error('Local origin required');
const out='.local/domain-ux', results=[];
const long='Una familia vuelve a encontrarse después de muchos años. Cada recuerdo cambia su forma de ver el futuro, mientras descubren historias que nunca se habían contado. '.repeat(9)+'<img src=x onerror=alert(1)>';
const item={id:990050,titulo:'Una historia para volver',tipo:'serie',fuente:'okru',año:2026,
 imagen_url:'/static/placeholder.svg',backdrop_url:'',sinopsis:long,has_download:false};
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  for(const width of [1366,390]){
   const page=await browser.newPage({viewport:{width,height:850}});let api=0, fixtureItem={...item};
   await page.route('**/*',async route=>{
    if(!route.request().url().startsWith(origin)){await route.abort();return;}
    const url=new URL(route.request().url());
    if(url.pathname.includes('/api/'))api++;
    if(url.pathname==='/api/contenido' && route.request().postDataJSON()?.id===item.id)return route.fulfill({json:{data:[fixtureItem]}});
    if(url.pathname==='/api/temporadas/990050')return route.fulfill({json:{temporadas:[{id:20,numero:2,episodios:2}]}});
    if(url.pathname==='/api/episodios/990050/20')return route.fulfill({json:{episodios:[
     {id:21,numero:1,titulo:'Un nuevo comienzo',sinopsis:long,has_playback:false,has_download:true},
     {id:22,numero:2,titulo:'El encuentro',sinopsis:'Una historia breve.',has_playback:true,has_download:false}],page:1,total:2,has_next:false}});
    await route.continue();
   });
   await page.goto(origin);await page.waitForFunction(()=>typeof abrirModalContenido==='function');
   await page.evaluate(item=>abrirModalContenido(item),item);
   const title=page.locator('#detalleSinopsis'), toggle=title.locator('button');
   await toggle.waitFor({state:'visible'});
   assert.equal(await title.locator('p').textContent(),long);
   assert.equal(await title.locator('img').count(),0);
   await page.evaluate(()=>{window.__plays=0;window.__downloads=0;InlinePlayback.start=()=>window.__plays++;EpisodeDownloads.download=()=>window.__downloads++;});
   const requestsBefore=api;
   await toggle.focus();await page.keyboard.press('Enter');
   assert.equal(await toggle.getAttribute('aria-expanded'),'true');
   assert(await title.locator('p').evaluate(e=>e.scrollHeight<=e.clientHeight+1));
   assert(await toggle.evaluate(e=>e===document.activeElement));
   await toggle.click();assert.equal(await toggle.getAttribute('aria-expanded'),'false');
   await title.evaluate(el=>{document.getElementById('modalDetalle').scrollTop+=el.getBoundingClientRect().top-120;});
   await page.screenshot({path:`${out}/title-${width}.png`,fullPage:false});
   const episode=page.locator('.episode-row').first();
   const read=episode.locator('.qh-synopsis-toggle');await read.click();
   assert.equal(await read.getAttribute('aria-expanded'),'true');
   await page.screenshot({path:`${out}/expanded-${width}.png`,fullPage:false});
   assert.equal(await episode.locator('.episode-card').isDisabled(),true);
   assert.equal(await page.locator('[aria-label="Seleccionar temporada"]').inputValue(),'20');
   assert.deepEqual(await page.evaluate(()=>[window.__plays,window.__downloads]),[0,0]);
   assert.equal(api,requestsBefore,'reading must not request APIs');
   await read.click();
   assert.equal(await page.locator('.episode-row').nth(1).locator('.qh-synopsis-toggle').isVisible(),false);
   await episode.locator('[aria-label="Descargar episodio 1"]').click();
   assert.equal(await page.evaluate(()=>window.__downloads),1);
   await page.screenshot({path:`${out}/synopsis-${width}.png`,fullPage:false});
   await page.evaluate(()=>cerrarModalDetalle());
   fixtureItem={...item,tipo:'pelicula',sinopsis:'Breve.'};
   await page.evaluate(item=>abrirModalContenido({...item,tipo:'pelicula',sinopsis:'Breve.'}),item);
   assert.equal(await toggle.isVisible(),false);
   fixtureItem={...item,tipo:'pelicula',sinopsis:null};
   await page.evaluate(item=>abrirModalContenido({...item,tipo:'pelicula',sinopsis:null}),item);
   assert.equal(await title.locator('p').textContent(),'Sin sinopsis disponible.');
   assert.equal(await toggle.isVisible(),false);
   results.push({test:'synopsis',width,full_text_preserved:true,reading_api_calls:0,download_action_preserved:true,short_and_missing:true});
   await page.close();
  }
  const notice=fs.readFileSync('static/updates/notice.js','utf8');
  for(const [name,ua,tv,native] of [
   ['web','Mozilla/5.0 Chrome/130',false,false],['android-browser','Mozilla/5.0 Android 12 Chrome/130',false,false],
   ['telegram','Mozilla/5.0 Android 12 Telegram/11',false,false],['pwa','Mozilla/5.0 Android 12 Chrome/130',false,false],
   ['tv-browser','Mozilla/5.0 Android 12',true,false],['mobile-apk','Mozilla/5.0 Android 12 QueHayAndroid/0.3',false,true],
   ['tv-apk','Mozilla/5.0 Android 12 QueHayTV/1.0',true,true]]){
   const context=await browser.newContext({userAgent:ua}), page=await context.newPage();let checks=0;
   await page.route(origin+'/**',route=>{
    if(route.request().url().endsWith('/version.json')){checks++;return route.fulfill({json:{version:'bbbbbbbbbbbbbbbbbbbb'}});}
    return route.fulfill({contentType:'text/html',body:`<meta name="qh-release" content="aaaaaaaaaaaaaaaaaaaa" data-endpoint="/version.json"><body>${tv?'<nav class="topbar" data-row="navigation"><button id="account-nav">Mi cuenta</button></nav>':''}<div id="${tv?'player':'inline-player'}" hidden><iframe src="about:blank"></iframe></div></body>`});
   });
   if(name==='pwa')await page.addInitScript(()=>Object.defineProperty(navigator,'standalone',{value:true}));
   await page.goto(origin+'/notice-test');await page.addScriptTag({content:notice});
   assert.equal(await page.locator('#qh-update').count(),native?1:0);
   if(native){
    await page.evaluate(()=>QHUpdates.check());await page.locator('#qh-update').waitFor({state:'visible'});
    await page.evaluate(tv=>{document.getElementById(tv?'player':'inline-player').hidden=false;},tv);
    await page.locator('#qh-update').waitFor({state:'hidden'});
    const before=checks;await page.evaluate(()=>QHUpdates.check());assert.equal(checks,before);
    assert.equal(await page.locator('iframe').getAttribute('src'),'about:blank');
    await page.evaluate(tv=>{document.getElementById(tv?'player':'inline-player').hidden=true;},tv);
    await page.locator('#qh-update').waitFor({state:'visible'});
    await page.locator('#qh-update-later').click();await page.locator('#qh-update').waitFor({state:'hidden'});
   }else assert.equal(checks,0);
   results.push({test:'update-notice',platform:name,notice_allowed:native,hidden_while_playing:true,automatic_reload:false});
   await context.close();
  }
  // An existing waiting service worker must not create a second PWA notice or reload.
  const p=await browser.newPage();await p.route(origin+'/**',r=>r.fulfill({contentType:'text/html',body:'<body></body>'}));
  await p.goto(origin+'/pwa-test');
  await p.evaluate(()=>{window.__swMessages=0;Object.defineProperty(navigator,'serviceWorker',{value:{register:async()=>({waiting:{postMessage:()=>window.__swMessages++}}),ready:Promise.resolve({})}});});
  await p.addScriptTag({content:fs.readFileSync('static/pwa/install.js','utf8')});
  assert.equal(await p.locator('#pwa-update').count(),0);assert.equal(await p.evaluate(()=>window.__swMessages),0);
  results.push({test:'waiting-pwa-worker',prompt:false,forced_activation:false});await p.close();
  fs.writeFileSync(out+'/browser.json',JSON.stringify(results,null,2));console.log(JSON.stringify(results,null,2));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
