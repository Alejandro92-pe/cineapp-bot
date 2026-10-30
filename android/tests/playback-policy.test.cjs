const test=require('node:test'),assert=require('node:assert/strict');
const {PlaybackPolicy}=require('../app/src/main/assets/mobile.js');
const response=(status,data)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});
const video={provider:'videoapi',url:'https://videoapi.la/e/tv/123/1/1',embed:true};
const backup={provider:'vimeus',url:'https://vimeus.com/e/serie?tmdb=123&se=1&ep=1',embed:true};

test('503 switches once, preserves episode and POST headers',async()=>{
 const calls=[];const policy=new PlaybackPolicy(async(url,options)=>{calls.push({url,options});return calls.length===1?response(503,{}):response(200,backup);});
 const options={method:'POST',headers:{'X-CSRF-Token':'fixture-only'},body:'{}'};
 assert.equal((await policy.request('/api/playback/7?episodio_id=99',options,true)).status,200);
 assert.equal(calls.length,2);assert.equal(calls[1].url,'/api/playback/7?episodio_id=99&provider=vimeus');assert.equal(calls[1].options,options);
 assert.equal(policy.actual,'vimeus');assert.equal(policy.fallback(backup.url),false);
});
test('no fallback around account, permission or invalid episode errors',async()=>{
 for(const status of [400,401,403,404,429]){
  let calls=0;const policy=new PlaybackPolicy(async()=>{calls++;return response(status,{error:'Access denied'});});
  assert.equal((await policy.request('/api/playback/7',{},true)).status,status);assert.equal(calls,1);
 }
});
test('known absence and network failure try the backup only once',async()=>{
 for(const network of [false,true]){
  let calls=0;const policy=new PlaybackPolicy(async()=>{calls++;if(calls===1){if(network)throw Error('network');return response(404,{code:'provider_unavailable'});}return response(503,{});});
  assert.equal((await policy.request('/api/playback/7',{},true)).status,503);assert.equal(calls,2);
 }
});
test('native failure must match the active embed; next episode returns to VideoAPI',async()=>{
 const calls=[];const policy=new PlaybackPolicy(async url=>{calls.push(url);return response(200,url.includes('provider=vimeus')?backup:video);});
 await policy.request('/api/playback/7?episodio_id=99',{},true);
 assert.equal(policy.fallback('https://videoapi.la/ad-banner'),false);
 assert.equal(policy.fallback(video.url),true);assert.equal(policy.fallback(video.url),false);
 await policy.request('/api/playback/7?episodio_id=99',{},true);
 assert.match(calls.at(-1),/provider=vimeus/);
 await policy.request('/api/playback/7?episodio_id=100',{},true);
 assert.equal(calls.at(-1),'/api/playback/7?episodio_id=100');
});
test('late responses cannot change the active provider or start extra requests',async()=>{
 let finish;let calls=0;const policy=new PlaybackPolicy(async()=>{calls++;return calls===1?new Promise(r=>finish=r):response(200,video);});
 const old=policy.request('/api/playback/7',{},true);
 await policy.request('/api/playback/8',{},true);
 finish(response(503,{}));await old;
 assert.equal(calls,2);assert.match(policy.key,/playback\/8/);assert.equal(policy.actual,'videoapi');
});
test('OK.ru and titles without a second provider keep their source',async()=>{
 let calls=0;const policy=new PlaybackPolicy(async()=>{calls++;return response(503,{});});
 await policy.request('/api/playback/900421',{},false);assert.equal(calls,1);
});
test('ordinary loading does not schedule a guessed playback timeout',async()=>{
 let calls=0;const policy=new PlaybackPolicy(async()=>{calls++;return response(200,video);});
 await policy.request('/api/playback/7',{},true);assert.equal(calls,1);assert.equal(policy.force,false);
});
