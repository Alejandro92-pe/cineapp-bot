const {test}=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');
function setup(fetcher, readyState="loading"){
 const nodes=new Map();const get=id=>{if(!nodes.has(id))nodes.set(id,{hidden:true,textContent:'',classList:{add(){},remove(){}},removeAttribute(k){delete this[k];},scrollIntoView(){}});return nodes.get(id);};
 const events={};const history=[];const support=[];const window={AccessSupport:{handle:(r,p)=>{const reason=require("../static/support/access.js").reason(r,p);if(reason)support.push(reason);return !!reason;}}};const context={window,URL,document:{readyState,getElementById:get,addEventListener:(name,fn)=>events[name]=fn},EpisodeBrowser:{selection:()=>({}),next:async()=>null,hasNext:()=>true},AccountLibrary:{opened:(...args)=>history.push(args)},fetch:fetcher};
 vm.runInNewContext(fs.readFileSync('static/catalog/playback.js','utf8'),context);if(readyState==="loading")events.DOMContentLoaded();return {api:window.InlinePlayback,get,history,context,support};
}
test('opens authorized iframe inside detail with no new browser window',async()=>{const s=setup(async()=>({ok:true,json:async()=>({embed:true,url:'https://vimeus.com/e/movie?tmdb=22'})}));await s.api.start({id:1,titulo:'Movie',tipo:'pelicula'});assert.equal(s.get('inline-player').hidden,false);assert.equal(s.get('iframeReproductor').src,'https://vimeus.com/e/movie?tmdb=22');assert.equal(s.history.length,1);s.api.close();assert.equal(s.get('inline-player').hidden,true);assert.equal(s.get('iframeReproductor').src,undefined);});
test('late playback response cannot reopen a closed title',async()=>{let resolve;const s=setup(()=>new Promise(r=>resolve=r));const pending=s.api.start({id:1,titulo:'Movie'});s.api.close();resolve({ok:true,json:async()=>({embed:true,url:'https://vimeus.com/e/movie'})});await pending;assert.equal(s.get('iframeReproductor').src,undefined);assert.equal(s.history.length,0);});
test('expired access shows support without opening a black player',async()=>{const s=setup(async()=>({ok:false,status:403,json:async()=>({error:'Tu acceso venció',code:'membership_required'})}));await s.api.start({id:1,titulo:'Movie'});assert.deepEqual(s.support,['member']);assert.equal(s.get('inline-player').hidden,true);assert.equal(s.get('player-retry').hidden,true);assert.equal(s.history.length,0);assert.equal(s.get('iframeReproductor').src,undefined);});
test('rejects foreign iframe URLs even if server response is malformed',async()=>{const s=setup(async()=>({ok:true,json:async()=>({embed:true,url:'https://evil.example/video'})}));await s.api.start({id:1});assert.equal(s.get('iframeReproductor').src,undefined);assert.equal(s.history.length,0);});
test('successful embed hides redundant instructions and retry, without claiming playback',async()=>{const s=setup(async()=>({ok:true,json:async()=>({embed:true,url:'https://vimeus.com/e/serie?tmdb=1',provider_selection:true})}));await s.api.start({id:1,titulo:'Series',tipo:'serie'});s.get('iframeReproductor').onload();assert.equal(s.get('player-next').hidden,true);assert.equal(s.get('player-status').hidden,true);assert.equal(s.get('player-status').textContent,'');assert.equal(s.get('player-retry').hidden,true);});
test('next button requests the selected next episode through the protected API',async()=>{
 const calls=[];let selected={episode:{id:1,numero:1},season:{id:10,numero:1}};
 const s=setup(async url=>{calls.push(url);return {ok:true,json:async()=>({embed:true,url:'https://vimeus.com/e/serie'})};});
 s.context.EpisodeBrowser.selection=()=>selected;s.context.EpisodeBrowser.next=async()=>{selected={episode:{id:2,numero:2},season:{id:10,numero:1}};return selected.episode;};
 await s.api.start({id:9,titulo:'Series',tipo:'serie'});await s.get('player-next').onclick();assert.equal(calls.at(-1),'/api/playback/9?episodio_id=2');assert.match(s.get('player-title').textContent,/T1 E2/);
});

test('last episode disables next and offers the current download',async()=>{
 const s=setup(async()=>({ok:true,json:async()=>({embed:true,url:'https://vimeus.com/e/anime'})}));
 s.context.EpisodeBrowser.selection=()=>({episode:{id:58,numero:58,has_download:true},season:{numero:3}});s.context.EpisodeBrowser.hasNext=()=>false;
 const downloads=[];s.context.EpisodeDownloads={download:(...args)=>downloads.push(args)};
 await s.api.start({id:409,tipo:'anime',titulo:'Naruto'});
 assert.equal(s.get('player-next').disabled,true);assert.equal(s.get('player-next').textContent,'Último episodio');
 assert.equal(s.get('player-download').hidden,false);s.get('player-download').onclick();assert.deepEqual(downloads,[[409,58]]);
});
test('rapid next clicks cannot skip episodes and closing cancels pending navigation',async()=>{
 const s=setup(async()=>({ok:true,json:async()=>({embed:true,url:'https://vimeus.com/e/anime'})}));
 let resolve,calls=0;s.context.EpisodeBrowser.selection=()=>({episode:{id:1,numero:1},season:{numero:1}});
 s.context.EpisodeBrowser.next=()=>{calls++;return new Promise(r=>resolve=r);};
 await s.api.start({id:9,tipo:'anime',titulo:'Anime'});
 const pending=s.get('player-next').onclick();await s.get('player-next').onclick();assert.equal(calls,1);
 s.api.close();resolve({id:2});await pending;assert.equal(s.get('iframeReproductor').src,undefined);
});
test('empty next result is visible rather than a hidden status message',async()=>{
 const s=setup(async()=>({ok:true,json:async()=>({embed:true,url:'https://vimeus.com/e/anime'})}));
 await s.api.start({id:9,tipo:'anime',titulo:'Anime'});s.get('iframeReproductor').onload();
 await s.get('player-next').onclick();assert.equal(s.get('player-status').hidden,false);assert.match(s.get('player-status').textContent,/último episodio/);
});

test('guest does not open a player while authorization is pending or denied',async()=>{
 let resolve;const s=setup(()=>new Promise(r=>resolve=r));const promise=s.api.start({id:1});
 assert.equal(s.get('inline-player').hidden,true);resolve({status:401,ok:false,json:async()=>({code:'auth_required'})});await promise;
 assert.deepEqual(s.support,['guest']);assert.equal(s.get('inline-player').hidden,true);assert.equal(s.get('iframeReproductor').src,undefined);
});
test('OK.ru opens only its canonical videoembed path inside the same player',async()=>{
 const s=setup(async()=>({ok:true,status:200,json:async()=>({embed:true,url:'https://ok.ru/videoembed/10328454335072?nochat=1'})}));
 await s.api.start({id:421,tipo:'biblico'});assert.equal(s.get('iframeReproductor').src,'https://ok.ru/videoembed/10328454335072?nochat=1');
 const bad=setup(async()=>({ok:true,status:200,json:async()=>({embed:true,url:'https://ok.ru/login'})}));await bad.api.start({id:421});assert.equal(bad.get('iframeReproductor').src,undefined);
});

test("lazy playback binds controls after DOMContentLoaded",()=>{const s=setup(async()=>({}),"complete");assert.equal(typeof s.get("player-next").onclick,"function");assert.equal(typeof s.get("player-close").onclick,"function");});
