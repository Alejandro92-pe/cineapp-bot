/* Slow editorial carousel; never moves remote focus. */
(function(root){
 const INTERVAL=20000;
 function choose(rows,now=Date.now()){
  const bucket=Math.floor(now/(3*86400000));
  const score=x=>{let h=2166136261;for(const c of bucket+':'+x.id)h=Math.imul(h^c.charCodeAt(0),16777619);return h>>>0;};
  const result=[];for(const kind of ['pelicula','serie','anime']){const pool=(rows.find(r=>r.kind===kind)?.items||[]).filter(x=>x.backdrop_url);pool.sort((a,b)=>score(a)-score(b));if(pool[0])result.push(pool[0]);}
  return result;
 }
 function render(items,image,esc,meta){if(!items.length)return '';const x=items[0];
  return `<section class="home-feature" aria-label="Historias destacadas"><div class="home-feature-art"><img id="feature-image" src="${image(x.backdrop_url,'w1280')}" alt=""></div><div class="home-feature-content"><p class="eyebrow">TU PRÓXIMA GRAN HISTORIA</p><div id="feature-copy"><h1>${esc(x.titulo)}</h1>${meta(x)}<p class="synopsis">${esc(x.sinopsis||'Descubre esta historia en Qué Hay.')}</p></div><div class="actions" data-row="hero-actions"><button data-nav class="primary" id="hero-open">Ver ficha <span aria-hidden="true">↗</span></button><button data-nav class="secondary" id="hero-browse">Explorar catálogo ↓</button></div></div><div class="feature-bottom"><div class="feature-indicators" data-row="hero-slides">${items.map((x,i)=>`<button data-nav id="feature-dot-${i}" data-slide="${i}" aria-label="Destacado ${i+1}: ${esc(x.titulo)}" aria-pressed="${i===0}"><span></span></button>`).join('')}<button data-nav id="feature-pause" aria-label="Pausar destacados" aria-pressed="false">Ⅱ</button></div><span>BAJA Y DESCUBRE MÁS ↓</span></div></section>`;
 }
 function mount({items,image,esc,meta,open,explore,valid}){
  let transition=0,index=0,paused=matchMedia('(prefers-reduced-motion: reduce)').matches,last=Date.now();const hero=document.querySelector('.home-feature');if(!hero)return()=>{};
  const dots=[...hero.querySelectorAll('[data-slide]')],pause=hero.querySelector('#feature-pause');
  function reflect(){pause.textContent=paused?'▷':'Ⅱ';pause.setAttribute('aria-pressed',String(paused));pause.setAttribute('aria-label',paused?'Reanudar destacados':'Pausar destacados');}
  async function change(i){const attempt=++transition;last=Date.now();const x=items[i],url=image(x.backdrop_url,'w1280'),preload=new Image();preload.src=url;await preload.decode().catch(()=>{});if(!valid()||attempt!==transition)return;index=i;hero.querySelector('#feature-image').src=url;hero.querySelector('#feature-copy').innerHTML=`<h1>${esc(x.titulo)}</h1>${meta(x)}<p class="synopsis">${esc(x.sinopsis||'Descubre esta historia en Qué Hay.')}</p>`;dots.forEach((b,n)=>b.setAttribute('aria-pressed',String(n===i)));}
  dots.forEach((b,i)=>b.onclick=()=>change(i));pause.onclick=()=>{paused=!paused;last=Date.now();reflect();};reflect();
  hero.querySelector('#hero-open').onclick=()=>open(items[index]);hero.querySelector('#hero-browse').onclick=explore;
  const touched=()=>{last=Date.now();};hero.addEventListener('keydown',touched);hero.addEventListener('pointerdown',touched);
  const timer=setInterval(()=>{if(!valid()||paused||document.hidden||document.querySelector('dialog[open]')||!document.getElementById('player').hidden)return;
   const r=hero.getBoundingClientRect();if(r.top < -innerHeight*.3||r.bottom<innerHeight*.5){last=Date.now();return;}if(Date.now()-last>=INTERVAL)change((index+1)%items.length);
  },1000);
  return()=>{transition++;clearInterval(timer);hero.removeEventListener('keydown',touched);hero.removeEventListener('pointerdown',touched);};
 }
 const api={choose,render,mount,INTERVAL};if(typeof module==='object')module.exports=api;if(root.document)root.TVHome=api;
})(typeof window!=='undefined'?window:globalThis);
