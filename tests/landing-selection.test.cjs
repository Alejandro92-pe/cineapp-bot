const {test}=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');
const code=fs.readFileSync(require.resolve('../landing/assets/selection.js'),'utf8');
function sample(){return {year:2026,items:[1,2,3].map(id=>({id,title:'Película '+id,poster:`https://image.tmdb.org/t/p/w342/p${id}.jpg`,backdrop:`https://image.tmdb.org/t/p/w1280/b${id}.jpg`}))};}
async function render(payload,ids='4,5,6',fail=false){
 const captions=[];const images=[0,1,2,0,1,2,0].map((index,i)=>{const caption={};captions.push(caption);return {dataset:{poster:String(index)},src:'bundled.webp',srcset:'bundled.webp 342w',closest:s=>s==='figure'&&i<3?{querySelector:()=>caption}:s==='.poster-stack'&&i<3?{}:null};});
 const bg={src:'cover.webp',srcset:'cover.webp 1280w'},note={},root={dataset:{appOrigin:'https://app.quehay.live',selectionIds:ids}};
 let request;
 vm.runInNewContext(code,{document:{documentElement:root,querySelectorAll:()=>images,querySelector:s=>s==='[data-backdrop]'?bg:note},
  AbortController,setTimeout,clearTimeout,fetch:async(url,options)=>{request={url,options};if(fail)throw Error('offline');return {ok:true,json:async()=>payload};}});
 await new Promise(resolve=>setImmediate(resolve));return {images,captions,bg,note,root,request};
}
test('a renewed selection updates all seven poster surfaces and backdrop without credentials',async()=>{
 const r=await render(sample());assert.equal(r.request.options.credentials,'omit');
 assert.ok(r.images.every(img=>img.src.startsWith('https://image.tmdb.org/')));assert.match(r.bg.src,/b1.jpg$/);
 assert.equal(r.captions[1].textContent,'Película 2');assert.equal(r.root.dataset.selectionIds,'1,2,3');
});
test('same selection does not download the already bundled images a second time',async()=>{
 const r=await render(sample(),'1,2,3');assert.ok(r.images.every(img=>img.src==='bundled.webp'));assert.equal(r.bg.src,'cover.webp');
});
test('failure or malicious image host preserves last bundled selection',async()=>{
 const payload=sample();payload.items[1].poster='https://attacker.test/p.jpg';
 for(const r of [await render(payload),await render(sample(),'4,5,6',true)])assert.ok(r.images.every(img=>img.src==='bundled.webp'));
});
test('unavailable images restore both original src and srcset',async()=>{
 const r=await render(sample());r.images[0].onerror();r.bg.onerror();
 assert.equal(r.images[0].src,'bundled.webp');assert.equal(r.images[0].srcset,'bundled.webp 342w');assert.equal(r.bg.src,'cover.webp');
});
