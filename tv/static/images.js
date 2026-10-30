/* TV artwork: accept existing TMDB catalog URLs, serve bounded CDN sizes. */
(function(root){
 const sizes=new Set(['w342','w500','w780','w1280']);
 function source(value,size='w780'){
  if(!sizes.has(size))return '/tv/brand';
  try{
   const url=new URL(value);
   if(url.protocol!=='https:'||url.username||url.password||url.port)return '/tv/brand';
   if(['image.tmdb.org','media.themoviedb.org'].includes(url.hostname)){
    const path=url.pathname.match(/^\/t\/p\/[^/]+\/([a-zA-Z0-9_-]+\.(?:jpg|jpeg|png|webp))$/i);
    return path?'https://image.tmdb.org/t/p/'+size+'/'+path[1]:'/tv/brand';
   }
   // One existing biblical poster is hosted here; never accept arbitrary hosts.
   if(url.hostname==='static.wixstatic.com'&&/^\/media\/[a-zA-Z0-9_~.-]+\.(?:jpg|jpeg|png|webp)$/i.test(url.pathname))return url.origin+url.pathname;
  }catch(_){}
  return '/tv/brand';
 }
 const api={source};if(typeof module==='object')module.exports=api;if(root.document)root.TVImages=api;
})(typeof window!=='undefined'?window:globalThis);
