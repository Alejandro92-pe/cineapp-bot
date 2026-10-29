/* Choose the asset for the surface, never stretch a poster into a backdrop. */
(function(root){
  const pattern=/^https:\/\/(?:image\.tmdb\.org|media\.themoviedb\.org)\/t\/p\/(?:w\d+(?:_and_h\d+_face)?|original)\/(\w+\.(?:jpg|png|webp))$/i;
  function sized(url,width){const match=String(url||'').match(pattern);return match?`https://image.tmdb.org/t/p/w${width}/${match[1]}`:url||'';}
  function backdrop(item){
    const bg=item?.backdrop_url||'';const poster=item?.imagen_url||'';
    return bg && sized(bg,500)!==sized(poster,500)?bg:'';
  }
  function poster(img,url,sizes='(max-width:700px) 42vw, 180px'){
    img.src=sized(url,342)||'/static/placeholder.svg';
    img.sizes=sizes;
    img.srcset=pattern.test(String(url))?[185,342,500].map(w=>`${sized(url,w)} ${w}w`).join(', '):'';
  }
  function hero(img,item){
    const url=backdrop(item);img.classList.toggle('artwork-poster-fallback',!url);
    if(!url){poster(img,item?.imagen_url,'(max-width:700px) 70vw, 400px');return;}
    img.src=sized(url,1280);img.sizes='100vw';
    img.srcset=pattern.test(url)?[780,1280].map(w=>`${sized(url,w)} ${w}w`).join(', '):'';
  }
  function detail(node,item){
    let img=node.querySelector('img');if(!img){img=document.createElement('img');img.alt='';img.decoding='async';node.append(img);}
    node.style.backgroundImage='none';hero(img,item);
    img.onerror=()=>{img.onerror=null;img.removeAttribute('srcset');img.src='/static/placeholder.svg';};
  }
  root.CatalogArtwork={sized,backdrop,poster,hero,detail};
  if(typeof module!=='undefined')module.exports=root.CatalogArtwork;
})(typeof window==='undefined'?{}:window);
