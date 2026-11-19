// A provider that is down or lacks the title shows QueHay's own notice, never the provider's broken page.
const {test}=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');
function setup(responses){
 const nodes=new Map();const created=[];
 const make=tag=>{const n={tag,hidden:false,textContent:'',children:[],className:'',style:{},classList:{add(){},remove(){}},setAttribute(){},removeAttribute(k){delete this[k];},
   append(...c){this.children.push(...c);},before(x){created.push(x);x.parent=this;},remove(){const i=created.indexOf(this);if(i>=0)created.splice(i,1);},scrollIntoView(){}};return n;};
 const get=id=>{if(!nodes.has(id)){const n=make('div');n.hidden=true;if(id==='btnDescargar')n.style.display='none';nodes.set(id,n);}return nodes.get(id);};
 const calls=[];const window={AccessSupport:{handle:()=>false}};
 const document={readyState:'complete',head:{append(){}},getElementById:get,createElement:make,addEventListener(){}};
 const context={window,URL,URLSearchParams,document,EpisodeBrowser:{selection:()=>({}),next:async()=>null,hasNext:()=>true},AccountLibrary:{opened(){}},
  fetch:async url=>{calls.push(url);const r=responses.shift();return {ok:r.ok,status:r.status||200,json:async()=>r.body};}};
 vm.runInNewContext(fs.readFileSync('static/catalog/playback.js','utf8'),context);
 const text=n=>[n.textContent,...(n.children||[]).map(text)].join(' ');
 return {api:window.InlinePlayback,get,created,calls,text,buttons:()=>created[0]?created[0].children.find(c=>c.className==='player-unavailable-actions').children:[]};
}
const down={ok:false,status:404,body:{error:'x',code:'provider_down',provider:'vimeus'}};
test('vimeus down shows our notice and never loads its page',async()=>{
 const s=setup([down]);await s.api.start({id:7,titulo:'Así aprenderás',tipo:'pelicula'});
 assert.equal(s.get('iframeReproductor').src,undefined);assert.equal(s.get('iframeReproductor').hidden,true);
 assert.equal(s.created.length,1);assert.match(s.text(s.created[0]),/no está disponible por ahora/);
 assert.equal(s.get('player-retry').hidden,true);
 assert.deepEqual(s.buttons().map(b=>b.textContent),['Volver a la ficha']);
});
test('offers the other server once, then stops when both fail',async()=>{
 const s=setup([{ok:false,status:404,body:{error:'No está en esta opción.',code:'provider_unavailable',provider:'videoapi'}},down]);
 const item={id:8,titulo:'Serie',tipo:'pelicula',videoapi_enabled:true};
 await s.api.start(item);assert.deepEqual(s.buttons().map(b=>b.textContent),['Probar el otro servidor','Volver a la ficha']);
 await s.buttons()[0].onclick();
 assert.match(s.calls[1],/provider=vimeus/);assert.equal(s.created.length,1);
 assert.deepEqual(s.buttons().map(b=>b.textContent),['Volver a la ficha']);
});
test('download is offered when the title has one, and closing removes the notice',async()=>{
 const s=setup([down]);s.get('btnDescargar').style.display='inline-flex';let downloaded=0;s.get('btnDescargar').click=()=>downloaded++;
 await s.api.start({id:9,titulo:'Peli',tipo:'pelicula'});
 const labels=s.buttons().map(b=>b.textContent);assert.deepEqual(labels,['Descargar','Volver a la ficha']);
 s.buttons()[0].onclick();assert.equal(downloaded,1);
 s.api.close();assert.equal(s.created.length,0);assert.equal(s.get('inline-player').hidden,true);
});
