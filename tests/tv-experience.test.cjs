const {test}=require('node:test');const assert=require('node:assert/strict');
const {Pager}=require('../tv/static/stream.js');const {choose,INTERVAL}=require('../tv/static/home.js');
test('progressive loader serializes requests and deduplicates records',async()=>{
 let calls=0,release;const p=new Pager({items:[{id:1}],page:1,has_next:true},page=>{calls++;assert.equal(page,2);return new Promise(r=>release=r);});
 const a=p.more(),b=p.more();assert.equal(a,b);assert.equal(calls,1);
 release({items:[{id:1},{id:2},{id:2}],page:2,has_next:true});assert.deepEqual(await a,[{id:2}]);assert.deepEqual(p.data.items.map(x=>x.id),[1,2]);
});
test('failed load retries the same page and discarded views cannot append',async()=>{
 let calls=0,live=true;const p=new Pager({items:[{id:1}],page:1,has_next:true},async page=>{calls++;assert.equal(page,2);if(calls===1)throw Error('offline');live=false;return {items:[{id:2}],page:2,has_next:false};},()=>live);
 await assert.rejects(p.more(),/offline/);assert.equal(p.data.page,1);assert.deepEqual(await p.more(),[]);assert.equal(p.data.items.length,1);
});
test('empty/duplicate-only responses stop loading without an endless loop',async()=>{
 const p=new Pager({items:[{id:1}],page:1,has_next:true},async()=>({items:[{id:1}],page:2,has_next:true}));await p.more();assert.equal(p.data.has_next,false);assert.deepEqual(await p.more(),[]);
});
test('home selection stays stable for three days, uses artwork and three categories',()=>{
 const rows=['pelicula','serie','anime'].map((kind,k)=>({kind,items:Array.from({length:12},(_,i)=>({id:k*100+i,backdrop_url:'test'}))}));
 const start=3*86400000*6000;const a=choose(rows,start),b=choose(rows,start+2*86400000);assert.deepEqual(a,b);assert.equal(a.length,3);assert.equal(INTERVAL,20000);
 assert.notDeepEqual(a,choose(rows,start+3*86400000));assert.equal(choose([{kind:'pelicula',items:[{id:1}]}]).length,0);
});
