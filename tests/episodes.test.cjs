const test = require('node:test');
const assert = require('node:assert/strict');
const {EpisodeController} = require('../static/catalog/episodes.js');
const item = {id:3,tipo:'anime',fuente:'vimeus'};
const seasons = [{id:1,numero:0,episodios:1},{id:2,numero:1,episodios:60},{id:3,numero:2,episodios:12}];
const episode = (id, numero) => ({id,numero,titulo:`Episodio ${numero}`});
test('selects normal season, pages beyond 50, selects a distinct chapter', async () => {
  const calls=[];
  const controller=new EpisodeController(async url => {
    calls.push(url);
    if(url.includes('/temporadas/')) return {temporadas:seasons};
    return url.endsWith('page=1') ? {episodios:[episode(1,1)],page:1,total:60,has_next:true} : {episodios:[episode(60,60)],page:2,total:60,has_next:false};
  },()=>{});
  await controller.mount(item); await controller.more(); controller.select(60);
  assert.equal(controller.state.season.numero,1);
  assert.equal(controller.state.selected.numero,60);
  assert.equal(controller.state.episodes.length,2);
  assert.ok(calls.at(-1).includes('page=2'));
});
test('late old-season responses cannot overwrite a new selection', async () => {
  let resolveOld;
  const controller=new EpisodeController(async url => {
    if(url.includes('/temporadas/')) return {temporadas:seasons};
    if(url.includes('/3/2?')) return new Promise(resolve => {resolveOld=resolve;});
    return {episodios:[episode(99,1)],page:1,total:1,has_next:false};
  },()=>{});
  const pending=controller.mount(item);
  await new Promise(resolve=>setImmediate(resolve));
  await controller.season(3);
  resolveOld({episodios:[episode(22,2)],page:1,total:1,has_next:false});
  await pending;
  assert.equal(controller.state.season.id,3);
  assert.equal(controller.state.selected.id,99);
});
test('reset invalidates in-flight requests and discards the previous episode', async () => {
  let resolve;
  const controller=new EpisodeController(()=>new Promise(r=>{resolve=r;}),()=>{});
  const pending=controller.mount(item); controller.reset(); resolve({temporadas:seasons}); await pending;
  assert.equal(controller.state.selected,null); assert.equal(controller.state.item,undefined);
});
test('network failure is visible and can be retried', async () => {
  let fails=true;
  const controller=new EpisodeController(async url=>{
    if(url.includes('/temporadas/')) return {temporadas:seasons};
    if(fails) throw new Error('No disponible');
    return {episodios:[episode(1,1)],page:1,total:1,has_next:false};
  },()=>{});
  await controller.mount(item); assert.equal(controller.state.error,'No disponible');
  fails=false; await controller.more(); assert.equal(controller.state.selected.id,1); assert.equal(controller.state.error,'');
});

test('resume opens only its page and next loads the following block', async()=>{
 const calls=[];
 const c=new EpisodeController(async url=>{
  calls.push(url);
  if(url.includes('/temporadas/'))return {temporadas:seasons};
  if(url.includes('around=180'))return {episodios:[episode(180,180)],page:15,total:220,has_next:true};
  return {episodios:[episode(181,181)],page:16,total:220,has_next:true};
 },()=>{});
 await c.mount({...item,last_episode:180,last_season:2});
 assert.equal(calls.length,2);assert.equal(c.state.selected.id,180);
 assert.ok(calls[1].includes('page_size=12'));assert.equal(c.state.start_page,15);
 assert.equal((await c.next()).id,181);assert.ok(calls.at(-1).endsWith('page=16'));
});
