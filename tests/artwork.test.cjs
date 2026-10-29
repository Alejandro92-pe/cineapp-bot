const {test}=require('node:test');const assert=require('node:assert/strict');
const {sized,backdrop,hero,poster}=require('../static/catalog/artwork.js');
const image=()=>({classList:{toggle(name,on){this[name]=on;}}});
test('legacy thumbnail gets real CDN variants without changing unknown hosts',()=>{
 assert.equal(sized('https://media.themoviedb.org/t/p/w300_and_h450_face/abc.jpg',1280),'https://image.tmdb.org/t/p/w1280/abc.jpg');
 assert.equal(sized('https://example.com/w500/photo.jpg',780),'https://example.com/w500/photo.jpg');
});
test('poster fallback is contained and never pretends to be a horizontal image',()=>{
 const img=image(),url='https://image.tmdb.org/t/p/w500/abc.jpg';hero(img,{imagen_url:url});
 assert.equal(img.classList['artwork-poster-fallback'],true);assert.ok(!img.srcset.includes('1280'));
 assert.equal(backdrop({imagen_url:url,backdrop_url:sized(url,1280)}),'');
});
test('backdrops use responsive capped sizes, not original',()=>{
 const img=image();hero(img,{backdrop_url:'https://image.tmdb.org/t/p/original/wide.jpg'});
 assert.equal(img.classList['artwork-poster-fallback'],false);
 assert.match(img.srcset,/w780/);assert.match(img.srcset,/w1280/);assert.ok(!img.srcset.includes('original'));assert.equal(img.sizes,'100vw');
});
test('switch to non-TMDB art clears the former responsive URLs',()=>{
 const img=image();hero(img,{backdrop_url:'https://image.tmdb.org/t/p/w1280/wide.jpg'});poster(img,'/static/placeholder.svg');
 assert.equal(img.srcset,'');assert.equal(img.src,'/static/placeholder.svg');
});
