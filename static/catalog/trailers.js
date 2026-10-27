/* Only recognized YouTube URLs may become privacy-enhanced embeds. */
(function(root){
 function embed(value){
  try{
   const url=new URL(value);
   if(url.protocol!=='https:'||url.username||url.password||url.port)return null;
   const hosts=['youtube.com','www.youtube.com','m.youtube.com','youtu.be','www.youtube-nocookie.com'];
   if(!hosts.includes(url.hostname))return null;
   const id=url.hostname==='youtu.be'?url.pathname.slice(1):url.pathname==='/watch'?url.searchParams.get('v'):url.pathname.startsWith('/embed/')?url.pathname.slice(7):null;
   return /^[A-Za-z0-9_-]{11}$/.test(id||'')?`https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0`:null;
  }catch{return null;}
 }
 root.TrailerURL={embed};
 if(typeof module!=='undefined')module.exports={embed};
})(typeof window==='undefined'?{}:window);
