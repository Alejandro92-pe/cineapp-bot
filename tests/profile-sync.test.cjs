const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function device(fetcher,stored={}){
  const events={},storage=new Map(Object.entries(stored)),notices=new Map();
  const document={hidden:false,addEventListener(){},getElementById:id=>notices.get(id),createElement:()=>({setAttribute(){}}),body:{append(n){notices.set(n.id,n)}}};
  const root={AccountSession:{state:{authenticated:true,user:{id:'A',telegram_id:42}},ready:Promise.resolve()},
    addEventListener(n,fn){(events[n]??=[]).push(fn)},dispatchEvent(e){for(const fn of events[e.type]||[])fn(e)},document};
  const context={window:root,document,Event,fetch:fetcher,localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},setInterval(){},setTimeout(){},clearTimeout(){},console};
  vm.createContext(context);vm.runInContext(fs.readFileSync('static/profile/sync.js','utf8'),context);
  return {sync:root.ProfileSync,root,storage};
}
function server(){
  let avatar='tg',items=[],fail=false;const calls=[];
  async function fetcher(path,opts={}){
    const b=opts.body?JSON.parse(opts.body):null;calls.push(b);
    if(fail)throw Error('Sin conexión');
    if(b?.action==='avatar')avatar=b.avatar;
    if(b?.action==='bootstrap'){avatar=b.avatar;items=b.saved_ids.map(id=>({id,titulo:'Título '+id}));}
    if(b?.action==='saved'){items=items.filter(r=>r.id!==b.content_id);if(b.saved)items.push({id:b.content_id,titulo:'Título '+b.content_id});}
    return {ok:true,json:async()=>({account_id:'A',avatar,items:structuredClone(items),saved_ids:items.map(i=>i.id)})};
  }
  return {fetcher,calls,fail(){fail=true}};
}
test('independent browsers synchronize avatar, save and removal through the server',async()=>{
  const s=server(),a=device(s.fetcher),b=device(s.fetcher);await Promise.all([a.sync.ready,b.sync.ready]);
  a.sync.select('fox');a.sync.toggle({id:10});await a.sync.refresh();await b.sync.refresh();
  assert.equal(b.sync.avatar(),'fox');assert.equal(b.sync.has(10),true);
  b.sync.toggle({id:10});await b.sync.refresh();await a.sync.refresh();assert.equal(a.sync.has(10),false);
  assert.equal(a.storage.size,0);assert.equal(b.storage.size,0);
});
test('legacy browser preferences migrate only once after confirmed success',async()=>{
  const s=server(),d=device(s.fetcher,{avatar_42:'wolf',favs_42:JSON.stringify([{id:8}])});await d.sync.ready;
  assert.equal(d.sync.avatar(),'wolf');assert.equal(d.sync.has(8),true);assert.equal(d.storage.get('profile_migrated_A'),'1');
  await d.sync.refresh();assert.equal(s.calls.filter(b=>b?.action==='bootstrap').length,1);
  assert.equal(d.storage.get('avatar_42'),'wolf'); // Original browser data is preserved.
});
test('failed saves roll back optimistic changes and show an honest error',async()=>{
  const s=server(),d=device(s.fetcher);await d.sync.ready;s.fail();
  d.sync.select('fox');d.sync.toggle({id:10});assert.equal(d.sync.has(10),true);
  await d.sync.refresh();assert.equal(d.sync.has(10),false);assert.equal(d.sync.avatar(),'tg');assert.equal(d.sync.error,true);
  assert.match(d.sync.message,/Sin conexión/);
});
test('quick repeated taps retain the last requested state',async()=>{
  const s=server(),d=device(s.fetcher);await d.sync.ready;
  d.sync.toggle({id:10});d.sync.toggle({id:10});d.sync.select('fox');d.sync.select('cat');
  await d.sync.refresh();assert.equal(d.sync.has(10),false);assert.equal(d.sync.avatar(),'cat');
});
test('a delayed response cannot leak the previous account into a new session',async()=>{
  let release;
  const d=device(()=>new Promise(resolve=>{release=resolve}));await tick();
  d.root.AccountSession.state={authenticated:false,user:null};d.root.dispatchEvent(new Event('session-changed'));
  release({ok:true,json:async()=>({account_id:'A',avatar:'fox',items:[{id:10}],saved_ids:[10]})});await d.sync.ready;
  assert.equal(d.sync.enabled(),false);assert.equal(d.sync.avatar(),'tg');assert.equal(d.sync.saved().length,0);
});
test('an older refresh cannot overwrite a newer avatar selection',async()=>{
  const s=server();let hold=false,release;
  const d=device((p,o)=>hold&&!o?.body?new Promise(resolve=>{release=resolve}):s.fetcher(p,o));await d.sync.ready;
  hold=true;const refresh=d.sync.refresh();d.sync.select('fox');await tick();
  release({ok:true,json:async()=>({account_id:'A',avatar:'tg',items:[],saved_ids:[]})});await refresh;
  assert.equal(d.sync.avatar(),'fox');
});
test('a cookie changed in another tab refreshes identity before displaying its preferences',async()=>{
 let id='A';
 const d=device(async()=>({ok:true,json:async()=>({account_id:id,avatar:id==='A'?'fox':'cat',items:[{id:id==='A'?10:20}],saved_ids:[id==='A'?10:20]})}));
 await d.sync.ready;
 d.root.AccountSession.refresh=async()=>{d.root.AccountSession.state={authenticated:true,user:{id:'B'}};d.root.dispatchEvent(new Event('session-changed'));};
 id='B';await d.sync.refresh();await tick();
 assert.equal(d.sync.has(10),false);assert.equal(d.sync.has(20),true);assert.equal(d.sync.avatar(),'cat');
});
test('session expiration clears signed-in preferences instead of showing another session as current',async()=>{
 let expired=false;
 const d=device(async()=>expired?{ok:false,status:401,json:async()=>({error:'Inicia sesión'})}:{ok:true,json:async()=>({account_id:'A',avatar:'fox',items:[{id:10}],saved_ids:[10]})});
 await d.sync.ready;
 d.root.AccountSession.refresh=async()=>{d.root.AccountSession.state={authenticated:false,user:null};d.root.dispatchEvent(new Event('session-changed'));};
 expired=true;await d.sync.refresh();assert.equal(d.sync.enabled(),false);assert.equal(d.sync.saved().length,0);
});
