/* Public, cached artwork only; no login cookies, API keys or video URLs. */
(function(){
  const root=document.documentElement,origin=root.dataset.appOrigin;
  const imagePattern=/^https:\/\/image\.tmdb\.org\/t\/p\/w\d+\/\w+\.(?:jpg|png|webp)$/i;
  function size(url,w){return url.replace(/\/w\d+\//,`/w${w}/`);}
  function valid(data){return Array.isArray(data?.items)&&data.items.length===3&&data.items.every(r=>
    Number.isInteger(r.id)&&r.id>0&&typeof r.title==='string'&&imagePattern.test(r.poster)&&imagePattern.test(r.backdrop));}
  function apply(data){
    if(!valid(data))return;
    if(data.items.map(r=>r.id).join(',')===root.dataset.selectionIds)return;
    document.querySelectorAll('[data-poster]').forEach(img=>{
      const item=data.items[Number(img.dataset.poster)];if(!item)return;
      const previous=img.src,previousSet=img.srcset;
      img.onerror=()=>{img.onerror=null;img.srcset=previousSet;img.src=previous;};
      img.sizes=img.closest('.poster-stack')?'(max-width:700px) 150px, 240px':'120px';
      img.srcset=[185,342,500].map(w=>`${size(item.poster,w)} ${w}w`).join(', ');img.src=item.poster;
      img.alt=img.closest('[aria-hidden="true"]')?'':item.title;
      const figure=img.closest('figure');if(figure){const caption=figure.querySelector('figcaption');caption.textContent=item.title;caption.title=item.title;}
    });
    const bg=document.querySelector('[data-backdrop]');
    if(bg){const previous=bg.src,previousSet=bg.srcset;bg.onerror=()=>{bg.onerror=null;bg.srcset=previousSet;bg.src=previous;};bg.sizes='100vw';bg.srcset=[780,1280].map(w=>`${size(data.items[0].backdrop,w)} ${w}w`).join(', ');bg.src=data.items[0].backdrop;}
    const note=document.querySelector('.stack-note');if(note)note.textContent=`Descubre el cine de ${data.year}.`;
    root.dataset.selectionIds=data.items.map(r=>r.id).join(',');
  }
  async function update(){
    if(!origin)return;
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),4500);
    try{const response=await fetch(origin+'/api/public/landing',{credentials:'omit',signal:controller.signal});if(response.ok)apply(await response.json());}
    catch(_){/* The optimized, locally bundled selection remains visible. */}
    finally{clearTimeout(timer);}
  }
  update();
})();
