const {test}=require('node:test');const assert=require('node:assert/strict');
const {source}=require('../tv/static/images.js');
test('legacy TMDB posters and modern backgrounds use the same optimized CDN',()=>{
 const file='cQuuBjG78j4b2r1dFpAjnjbUplv.jpg';
 for(const size of ['w342','w500','w780','w1280']){
  assert.equal(source('https://media.themoviedb.org/t/p/w300_and_h450_face/'+file,size),'https://image.tmdb.org/t/p/'+size+'/'+file);
  assert.equal(source('https://image.tmdb.org/t/p/original/'+file+'?old=1',size),'https://image.tmdb.org/t/p/'+size+'/'+file);
 }
});
test('existing biblical artwork remains available without arbitrary image domains',()=>{
 const url='https://static.wixstatic.com/media/859174_dae68737adf0429d906c00ccd6312b48~mv2.jpg';
 assert.equal(source(url),url);
 for(const value of [null,'','javascript:alert(1)','data:image/svg+xml,test','http://image.tmdb.org/t/p/w500/a.jpg','https://media.themoviedb.org.evil.test/t/p/w500/a.jpg','https://user:secret@image.tmdb.org/t/p/w500/a.jpg','https://image.tmdb.org:8443/t/p/w500/a.jpg','https://image.tmdb.org/t/p/w500/a.svg','https://image.tmdb.org/t/p/w500/a.jpg/extra','https://static.wixstatic.com/other/a.jpg','https://example.test/a.jpg'])assert.equal(source(value),'/tv/brand',String(value));
 assert.equal(source('https://image.tmdb.org/t/p/w500/a.jpg','original'),'/tv/brand');
});
