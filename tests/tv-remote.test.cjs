const {test}=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('android-tv/app/src/main/assets/remote.js','utf8');
function setup(tag='BUTTON'){
 let clicked=0,focused=0,events=[];const el={tagName:tag,disabled:false,matches:s=>s==='[data-nav]'?tag==='BUTTON':tag==='INPUT',click:()=>clicked++,dispatchEvent:e=>{events.push(e.key);e.defaultPrevented=true;}};
 const ctx={window:{TVFocus:{first:()=>focused++}},document:{activeElement:el},KeyboardEvent:class{constructor(_,props){Object.assign(this,props);}}};vm.runInNewContext(source,ctx);
 return {handle:ctx.window.QueHayTVRemote,state:()=>({clicked,focused,events}),el};
}
test('native arrows and OK activate once without swallowing provider or keyboard events',()=>{
 const a=setup();assert(a.handle('ArrowDown',false));assert(a.handle('Enter',false));assert(a.handle('Enter',true));assert.deepEqual(a.state(),{clicked:1,focused:0,events:['ArrowDown']});
 assert.equal(setup('IFRAME').handle('Enter',false),false);assert.equal(setup('INPUT').handle('ArrowLeft',false),false);
});
test('OK does not activate a disabled button',()=>{const a=setup();a.el.disabled=true;a.handle('Enter',false);assert.equal(a.state().clicked,0);});
