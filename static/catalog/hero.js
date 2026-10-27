/* Four featured films with accessible controls and a disposable rotation timer. */
(function(root){
 function selectTitles(featured,latest){
  const seen=new Set();return [...featured,...latest].filter(item=>{
   if(item.tipo!=='pelicula'||item.disponible===false||seen.has(String(item.id)))return false;
   seen.add(String(item.id));return true;
  }).slice(0,4);
 }
 function rotation(count,render,{schedule=setInterval,cancel=clearInterval,blocked=()=>false,paused=false}={}){
  let index=0,stopped=false;
  const handle=count>1?schedule(()=>{if(!stopped&&!paused&&!blocked()){index=(index+1)%count;render(index,paused);}},7500):null;
  return {go(value,manual=true){if(stopped||!count)return;if(manual)paused=true;index=(value+count)%count;render(index,paused);},
   step(delta){this.go(index+delta);},toggle(){paused=!paused;render(index,paused);},
   dispose(){stopped=true;if(handle!==null)cancel(handle);},get index(){return index;}};
 }
 function create(items,onOpen,onBrowse){
  const el=(tag,cls,text)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(text)node.textContent=text;return node;};
  const button=(label,handler,cls)=>{const b=el('button',cls,label);b.type='button';b.onclick=handler;return b;};
  const hero=el('section','cine-hero cine-carousel');hero.setAttribute('aria-roledescription','carrusel');hero.setAttribute('aria-label','Películas destacadas');
  const art=el('img','cine-hero-art');art.alt='';art.loading='eager';art.fetchPriority='high';art.onerror=()=>{art.onerror=null;art.src='/static/placeholder.svg';};
  const copy=el('div','cine-hero-copy');const title=el('h1');title.id='cine-hero-title';
  const metadata=el('p','cine-hero-meta');const summary=el('p','cine-hero-summary');
  copy.append(el('p','cine-eyebrow','QUEHAY PRESENTA'),title,metadata,summary);
  const actions=el('div','cine-actions');let selected=items[0];
  actions.append(button('Ver detalles',()=>onOpen(selected),'cine-button primary'),button('Explorar catálogo',onBrowse,'cine-button secondary'));copy.append(actions);
  const controls=el('div','hero-controls');controls.setAttribute('aria-label','Controles del carrusel');
  const dots=el('div','hero-dots');const position=el('span','hero-position');
  const announcement=el('span','hero-announcement');announcement.setAttribute('aria-live','off');
  let model;
  const previous=button('‹',()=>model.step(-1),'hero-arrow');previous.setAttribute('aria-label','Película anterior');
  const next=button('›',()=>model.step(1),'hero-arrow');next.setAttribute('aria-label','Película siguiente');
  const pause=button('Ⅱ',()=>model.toggle(),'hero-pause');
  const choices=items.map((item,i)=>{const b=button('',()=>model.go(i),'hero-dot');b.setAttribute('aria-label',`Mostrar ${item.titulo}`);dots.append(b);return b;});
  controls.append(previous,dots,next,position,pause);hero.append(art,el('div','cine-hero-shade'),copy,controls,announcement);
  function render(index,paused){
   selected=items[index];art.src=safeImageSrc(selected.backdrop_url||selected.imagen_url);title.textContent=selected.titulo;
   metadata.textContent=[selected.año,selected.genero?.split(',')[0],Number(selected.rating)>0?'★ '+Number(selected.rating).toFixed(1):''].filter(Boolean).join(' · ');
   summary.textContent=selected.sinopsis||'Descubre esta historia en nuestro catálogo.';
   position.textContent=`${index+1} / ${items.length}`;pause.textContent=paused?'▷':'Ⅱ';pause.setAttribute('aria-label',paused?'Reanudar carrusel':'Pausar carrusel');
   choices.forEach((b,i)=>b.setAttribute('aria-pressed',String(i===index)));
   announcement.setAttribute('aria-live',paused?'polite':'off');announcement.textContent=`${index+1} de ${items.length}: ${selected.titulo}`;
  }
  const reduced=root.matchMedia('(prefers-reduced-motion: reduce)');
  model=rotation(items.length,render,{paused:reduced.matches,blocked:()=>!hero.isConnected||document.hidden||hero.matches(':hover')||hero.contains(document.activeElement)||document.querySelector('#modalDetalle.active')});
  render(0,reduced.matches);controls.hidden=items.length<2;
  let touch;
  hero.addEventListener('touchstart',event=>{touch=event.touches[0];},{passive:true});
  hero.addEventListener('touchend',event=>{if(!touch)return;const end=event.changedTouches[0],dx=end.clientX-touch.clientX,dy=end.clientY-touch.clientY;if(Math.abs(dx)>50&&Math.abs(dx)>Math.abs(dy))model.step(dx<0?1:-1);touch=null;},{passive:true});
  controls.addEventListener('keydown',event=>{if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();model.step(event.key==='ArrowRight'?1:-1);}});
  return {element:hero,dispose:()=>model.dispose()};
 }
 root.CatalogHero={selectTitles,create};
 if(typeof module!=='undefined')module.exports={selectTitles,rotation};
})(typeof window==='undefined'?{}:window);
