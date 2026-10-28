const {test}=require('node:test');const assert=require('node:assert/strict');
const {selectTitles,rotation}=require('../static/catalog/hero.js');
test('hero selects three unique available movies, preserving server selection',()=>{
 const film=id=>({id,tipo:'pelicula'});
 assert.deepEqual(selectTitles([film(2),film(2),{id:8,tipo:'serie'},{...film(5),disponible:false}],[film(1),film(2),film(3),film(4),film(6)]).map(x=>x.id),[2,1,3]);
});
test('rotation wraps, pauses on interaction and cancels its interval on navigation',()=>{
 let tick,cancelled=false,last;const model=rotation(4,(index,paused)=>last={index,paused},{schedule:fn=>(tick=fn,22),cancel:id=>{assert.equal(id,22);cancelled=true;}});
 tick();assert.equal(last.index,1);model.go(3);assert.equal(last.paused,true);tick();assert.equal(last.index,3);
 model.toggle();tick();assert.equal(last.index,0);model.step(-1);assert.equal(last.index,3);
 model.dispose();tick();assert.equal(cancelled,true);assert.equal(last.index,3);
});
test('hidden tabs, open details and reduced motion do not auto-advance',()=>{
 let tick,blocked=true,calls=0;const model=rotation(4,()=>calls++,{schedule:fn=>(tick=fn,1),cancel:()=>{},blocked:()=>blocked,paused:true});
 tick();assert.equal(calls,0);model.toggle();const count=calls;tick();assert.equal(calls,count);
 blocked=false;tick();assert.equal(calls,count+1);model.dispose();
});
