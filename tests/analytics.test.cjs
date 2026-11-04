const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const script=fs.readFileSync('static/analytics/measure.js','utf8');
function load({url='https://app.quehay.live/',cookie='',gpc=false,ua='',telegram=false}={}){
  const nodes=[],scripts=[],events={},writes=[];let jar=cookie;
  function node(tag){const n={tag,children:[],append(...c){n.children.push(...c);},setAttribute(){},remove(){n.removed=true;}};nodes.push(n);return n;}
  const document={readyState:'complete',title:'Qué Hay',referrer:'https://example.org/private?email=private@example.org',
    createElement:node,head:{append:n=>scripts.push(n)},body:{append:n=>{}},addEventListener:(k,f)=>events[k]=f};
  Object.defineProperty(document,'cookie',{get:()=>jar,set:v=>{writes.push(v);const pair=v.split(';')[0];jar=jar.split('; ').filter(x=>x.split('=')[0]!==pair.split('=')[0]).concat(pair).join('; ');}});
  const window={Telegram:{WebApp:{initData:telegram?'private-init-data':''}},matchMedia:()=>({matches:false})};
  const context={window,document,location:new URL(url),navigator:{userAgent:ua,globalPrivacyControl:gpc},URL,Date,setTimeout,clearTimeout};
  vm.runInNewContext(script,context);
  const click=label=>nodes.find(n=>n.tag==='button'&&n.textContent===label).onclick();
  const calls=()=>Array.from(window.dataLayer||[],a=>Array.from(a));
  return {window,context,document,nodes,scripts,events,writes,click,calls};
}
test('no Google requests or events until opt-in; decline remains inert',()=>{
  const x=load();x.window.QueHayAnalytics.event('view_content',{content_id:'10'});
  assert.equal(x.scripts.length,0);x.click('Ahora no');assert.equal(x.scripts.length,0);
  assert.match(x.writes[0],/qh_analytics_v1=no;.*Domain=quehay.live/);
});
test('accepted consent loads exactly one tag; no automatic duplicate pageview',()=>{
  const x=load();x.window.QueHayAnalytics.view('inicio');x.click('Aceptar estadísticas');
  vm.runInNewContext(script,x.context);
  assert.equal(x.scripts.length,1);assert.match(x.scripts[0].src,/G-NQWW6WCBR2$/);
  assert.equal(x.calls().filter(c=>c[1]==='page_view').length,1);
  assert.equal(x.calls().find(c=>c[0]==='config')[2].send_page_view,false);
  assert.equal(x.calls().find(c=>c[0]==='consent')[2].ad_storage,'denied');
  x.window.QueHayAnalytics.view('inicio');assert.equal(x.calls().filter(c=>c[1]==='catalog_view').length,1);
  x.window.QueHayAnalytics.view('explorar');assert.equal(x.calls().filter(c=>c[1]==='catalog_view').length,2);
});
test('local, legacy host, TV, admin and sensitive API routes never load tracking',()=>{
  for(const url of ['http://127.0.0.1:5031/','https://cineapp-bot.onrender.com/','https://app.quehay.live/tv','https://app.quehay.live/admin','https://app.quehay.live/api/payments/mine']){
    const x=load({url,cookie:'qh_analytics_v1=yes'});assert.equal(x.scripts.length,0,url);
    assert.equal(x.nodes.length,0,url);
  }
  assert.equal(load({gpc:true,cookie:'qh_analytics_v1=yes'}).scripts.length,0);
});
test('URLs, emails, login fragments, free text and order data cannot enter our events',()=>{
  const x=load({url:'https://app.quehay.live/?token=PRIVATE#tgWebAppData=PRIVATE',cookie:'qh_analytics_v1=yes'});
  x.window.QueHayAnalytics.event('view_content',{content_id:'12',content_name:'Película',email:'private@example.org',telegram_id:'5824989040',url:'https://private.example',order_id:'SECRET'});
  x.window.QueHayAnalytics.event('catalog_filter',{has_query:true,search_term:'private@example.org',result_count:12});
  x.window.QueHayAnalytics.event('purchase',{transaction_id:'SECRET',value:1.5});
  const data=JSON.stringify(x.calls());assert.doesNotMatch(data,/PRIVATE|private@example|5824989040|SECRET|search_term|transaction_id/);
  assert.equal(x.calls().find(c=>c[1]==='page_view')[2].page_referrer,'https://example.org/');
});
test('withdrawal stops event emission and clears only analytics cookies',()=>{
  const x=load({cookie:'qh_analytics_v1=yes; _ga=abc; _ga_NQWW6WCBR2=def; cine_session=KEEP'});
  x.window.QueHayAnalytics.preferences();x.click('Ahora no');const count=x.calls().length;
  x.window.QueHayAnalytics.event('open_catalog',{});assert.equal(x.calls().length,count);
  assert.ok(x.writes.some(v=>v.startsWith('_ga=;')));assert.ok(x.writes.every(v=>!v.startsWith('cine_session=')));
});
test('landing and app share consent but carry distinct site/surface information',()=>{
  for(const [url,ua,telegram,section,surface] of [
    ['https://quehay.live/','',false,'landing','web'],['https://app.quehay.live/','QueHayAndroid/0.5.1',false,'app','android'],['https://app.quehay.live/','',true,'app','telegram']]){
    const x=load({url,ua,telegram,cookie:'qh_analytics_v1=yes'}),page=x.calls().find(c=>c[1]==='page_view')[2];
    assert.equal(page.site_section,section);assert.equal(page.client_surface,surface);
  }
});
test('known payment and APK actions send names only; no navigation interference',()=>{
  const x=load({cookie:'qh_analytics_v1=yes'});
  const anchor={id:'apk-tv',href:'https://quehay.live/apps/QueHay-TV-0.3.0.apk',closest:()=>null};
  x.events.click({target:{closest:()=>anchor}});
  assert.equal(x.calls().at(-1)[1],'download_apk');assert.equal(x.calls().at(-1)[2].app_kind,'tv');
  x.window.QueHayAnalytics.event('select_payment_method',{payment_method:'bmc',payer:'PRIVATE'});
  assert.equal(x.calls().at(-1)[1],'select_payment_method');assert.doesNotMatch(JSON.stringify(x.calls()),/PRIVATE/);
});
test('landing uses identical shared module and supported web pages load it once',()=>{
  for(const name of ['measure.js','measure.css'])assert.equal(fs.readFileSync('landing/assets/'+name,'utf8'),fs.readFileSync('static/analytics/'+name,'utf8'));
  for(const name of ['static/index.html','static/account.html','static/payments/membership.html','static/pwa/install.html','landing/index.html'])assert.equal((fs.readFileSync(name,'utf8').match(/measure\.js/g)||[]).length,1,name);
});
