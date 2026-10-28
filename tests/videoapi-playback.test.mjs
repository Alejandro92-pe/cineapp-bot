import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';

function setup(){
 const nodes=new Map(),requests=[];
 const node=id=>{if(!nodes.has(id))nodes.set(id,{hidden:false,value:'',textContent:'',classList:{add(){},remove(){}},scrollIntoView(){},removeAttribute(name){delete this[name];}});return nodes.get(id);};
 const context={URL,URLSearchParams,document:{readyState:'complete',getElementById:node},EpisodeBrowser:{selection:()=>({}),hasNext:()=>false},AccountLibrary:{opened(){}},fetch:url=>new Promise(resolve=>requests.push({url,resolve})),AccessSupport:{handle:()=>false}};
 context.window=context;vm.createContext(context);
 vm.runInContext(fs.readFileSync('static/catalog/playback.js','utf8'),context);
 return {context,node,requests};
}
const response=(url,provider)=>({ok:true,json:async()=>({embed:true,url,provider})});

test('switch removes the old iframe URL and ignores a stale provider response',async()=>{
 const {context,node,requests}=setup();const item={id:1,titulo:'Prueba',tipo:'pelicula',videoapi_enabled:true};
 const first=context.InlinePlayback.start(item);
 assert.match(requests[0].url,/provider=videoapi/);
 node('player-provider').onchange({target:{value:'vimeus'}});
 assert.equal(node('iframeReproductor').src,undefined);
 assert.match(requests[1].url,/provider=vimeus/);
 requests[1].resolve(response('https://vimeus.com/e/movie?tmdb=1','vimeus'));
 await new Promise(r=>setImmediate(r));
 requests[0].resolve(response('https://videoapi.la/e/movie/1','videoapi'));
 await first;
 assert.match(node('iframeReproductor').src,/^https:\/\/vimeus.com/);
 context.InlinePlayback.close();assert.equal(node('iframeReproductor').src,undefined);
});

test('normal titles keep their original request and reject unexpected VideoAPI responses',async()=>{
 const {context,node,requests}=setup();
 const pending=context.InlinePlayback.start({id:2,titulo:'Normal',tipo:'pelicula'});
 assert.equal(requests[0].url,'/api/playback/2');
 assert.equal(node('player-provider-label').hidden,true);
 requests[0].resolve(response('https://videoapi.la/e/movie/2','videoapi'));await pending;
 assert.equal(node('iframeReproductor').src,undefined);
 assert.equal(node('player-status').textContent,'Reproductor no permitido.');
});

test('automatic fallback shows the actual provider and still prefers VideoAPI on the next request',async()=>{
 const {context,node,requests}=setup();const item={id:1,titulo:'Movie',tipo:'pelicula',videoapi_enabled:true};
 let pending=context.InlinePlayback.start(item);
 requests[0].resolve(response('https://vimeus.com/e/movie?tmdb=1','vimeus'));await pending;
 assert.equal(node('player-provider').value,'vimeus');
 pending=context.InlinePlayback.start(item);
 assert.match(requests[1].url,/provider=videoapi/);
 requests[1].resolve(response('https://videoapi.la/e/movie/1?primary_color=78b7fb&secondary_color=111d30&icon_color=edf5ff','videoapi'));await pending;
 assert.equal(node('player-provider').value,'videoapi');
 assert.match(node('iframeReproductor').src,/primary_color=78b7fb/);
});

test('provider query cannot request paid features or arbitrary navigation',async()=>{
 for(const query of ['vip=1','origin=https://evil.test','primary_color=invalid']){
  const {context,node,requests}=setup();const pending=context.InlinePlayback.start({id:1,videoapi_enabled:true});
  requests[0].resolve(response('https://videoapi.la/e/movie/1?'+query,'videoapi'));await pending;
  assert.equal(node('iframeReproductor').src,undefined);
 }
});
