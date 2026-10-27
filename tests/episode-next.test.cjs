const {test}=require('node:test');const assert=require('node:assert/strict');const {EpisodeController}=require('../static/catalog/episodes.js');
test('next episode crosses pages then seasons without inventing episodes',async()=>{
const c=new EpisodeController(async url=>url.includes('/temporadas/')?{temporadas:[{id:1,numero:1,episodios:2},{id:2,numero:2,episodios:1}]}:url.includes('/9/2?')?{episodios:[{id:3,numero:1}],page:1,total:1,has_next:false}:url.endsWith('page=2')?{episodios:[{id:2,numero:2}],page:2,total:2,has_next:false}:{episodios:[{id:1,numero:1}],page:1,total:2,has_next:true},()=>{});
await c.mount({id:9,tipo:'serie'});assert.equal((await c.next()).id,2);assert.equal((await c.next()).id,3);assert.equal(c.state.season.numero,2);assert.equal(await c.next(),null);
});
test('remembers the last opened episode without claiming a playback timestamp',async()=>{
const c=new EpisodeController(async url=>url.includes('/temporadas/')?{temporadas:[{id:1,numero:1,episodios:1},{id:2,numero:2,episodios:1}]}:{episodios:[{id:22,numero:3}],page:1,total:1,has_next:false},()=>{});await c.mount({id:9,tipo:'serie',last_season:2,last_episode:22});assert.equal(c.state.season.id,2);assert.equal(c.state.selected.id,22);
});
