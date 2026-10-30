/* Catalogue presentation. Playback and downloads keep their authenticated routes. */
(function(root){
  const LIMIT=24;
  const types={todo:'Todo',pelicula:'Películas',serie:'Series',anime:'Anime',biblico:'Bíblico','Peliculas anime':'Películas anime'};
  const state={type:'todo',query:'',genre:'',year:'',download:false};
  let revision=0, currentView='inicio', timer;
  let disposeHero=()=>{};
  // Short-lived public metadata only. Access, payments and downloads never use it.
  const publicCache=new Map();
  async function cachedPublic(key,load){
    const now=Date.now(), stored=publicCache.get(key);
    if(stored && now-stored.at<60000)return stored.value;
    const value=Promise.resolve().then(load);
    publicCache.set(key,{at:now,value});
    if(publicCache.size>24)publicCache.delete(publicCache.keys().next().value);
    try{return await value;}catch(error){if(publicCache.get(key)?.value===value)publicCache.delete(key);throw error;}
  }
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
  function button(text,handler,cls='cine-button'){const n=el('button',text,cls);n.type='button';n.onclick=handler;return n;}
  function image(item,cls){const n=el('img',null,cls);CatalogArtwork.poster(n,safeImageSrc(item.imagen_url));n.alt='';n.loading='lazy';n.onerror=()=>{n.onerror=null;n.srcset='';n.src='/static/placeholder.svg';};return n;}
  function metadata(item){return [types[item.tipo]||item.tipo,item.año,item.genero?.split(',')[0]].filter(Boolean).join(' · ');}
  async function request(filters={}){
    return cachedPublic(JSON.stringify(filters),async()=>{
    const response=await fetch('/api/contenido',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tipo:'todo',limit:LIMIT,offset:0,...filters})});
    if(!response.ok)throw new Error('No pudimos cargar el catálogo. Inténtalo de nuevo.');
    return response.json();
    });
  }
  function payload(offset=0){return {tipo:state.type,busqueda:state.query.trim(),genero:state.genre,año:state.year||null,descarga:state.download,limit:LIMIT,offset};}
  function card(item){
    const article=el('article',null,'cine-card');
    const open=button('',()=>abrirModalContenido(item),'cine-poster');open.setAttribute('aria-label','Ver detalles de '+item.titulo);
    open.append(image(item));
    const score=Number(item.rating);if(Number.isFinite(score)&&score>0&&score<=10){const rating=el('span','★ '+score.toFixed(1),'cine-rating '+(score>=7?'green':score>=5?'yellow':'red'));rating.setAttribute('aria-label',`Puntuación ${score.toFixed(1)} de 10`);open.append(rating);}
    if(item.has_download&&!['serie','anime'].includes(item.tipo)){const tag=el('span',null,'cine-download-tag');tag.setAttribute('aria-label','Descarga disponible');tag.title='Descarga disponible';open.append(tag);}
    const mark=el('span','Ver detalles','cine-card-hover');open.append(mark);
    const save=button(esFavorito(item.id)?'✓':'+',()=>{const active=toggleFavorito(item);save.textContent=active?'✓':'+';save.setAttribute('aria-pressed',String(active));if(currentView==='guardados')mount('guardados');},'cine-save');
    save.dataset.contentId=String(item.id);save.setAttribute('aria-label','Guardar '+item.titulo);save.setAttribute('aria-pressed',String(esFavorito(item.id)));
    const title=button(item.titulo,()=>abrirModalContenido(item),'cine-card-title');
    article.append(open,save,title,el('p',metadata(item),'cine-card-meta'));return article;
  }
  function empty(title,description,action){const wrap=el('div',null,'cine-empty');wrap.append(el('h2',title),el('p',description));if(action)wrap.append(action);return wrap;}
  function section(title,description,items,kind){
    const wrap=el('section',null,'cine-section');const header=el('div',null,'cine-section-heading');const copy=el('div');copy.append(el('h2',title),el('p',description));header.append(copy);
    if(kind)header.append(button('Ver todo →',()=>{state.type=kind;state.query='';state.genre='';state.year='';state.download=false;root.cambiarVista('explorar');},'cine-text-button'));
    const rail=el('div',null,'cine-rail');rail.setAttribute('aria-label',title);rail.tabIndex=0;rail.append(...items.map(card));
    const arrows=el('div',null,'cine-rail-arrows');
    for(const [symbol,direction,label] of [['‹',-1,'Anterior'],['›',1,'Siguiente']]){
      const arrow=button(symbol,()=>rail.scrollBy({left:direction*rail.clientWidth*.85,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'}),'cine-rail-arrow');
      arrow.setAttribute('aria-label',label+' en '+title);arrows.append(arrow);
    }
    header.append(arrows);wrap.append(header,rail);return wrap;
  }
  async function home(container,token){
    let heroVisible=false;
    const featuredRequest=fetch('/api/tendencias').then(r=>{if(!r.ok)throw new Error('No pudimos cargar los destacados.');return r.json();}).then(items=>{
      if(token===revision){
        const slides=CatalogHero.selectTitles(items,[]);
        if(slides.length){const hero=CatalogHero.create(slides,item=>abrirModalContenido(item),()=>root.cambiarVista('explorar'));disposeHero=hero.dispose;container.replaceChildren(hero.element);heroVisible=true;}
      }
      return items;
    });
    const [featured,latest,movies,series,anime,top,biblical]=await Promise.all([
      featuredRequest,
      request({limit:12}),request({tipo:'pelicula',limit:8}),request({tipo:'serie',limit:8}),request({tipo:'anime',limit:8}),
      cachedPublic('top10',()=>fetch('/api/top10').then(r=>{if(!r.ok)throw Error('Ranking no disponible');return r.json();})).catch(()=>({data:[]})),request({tipo:'biblico',limit:8})]);
    if(token!==revision)return;
    if(!heroVisible)container.replaceChildren();
    const slides=CatalogHero.selectTitles(featured,movies.data);
    if(slides.length){if(!heroVisible){const hero=CatalogHero.create(slides,item=>abrirModalContenido(item),()=>root.cambiarVista('explorar'));disposeHero=hero.dispose;container.append(hero.element);}}
    else if(!latest.data.length){container.append(empty('Las próximas historias están en camino.','El catálogo aparecerá aquí cuando haya títulos disponibles.'));return;}
    const intro=el('div',null,'cine-intro');intro.append(el('p','Tu siguiente historia, a un toque.'),el('a','Conoce el acceso de 30 días →'));intro.lastChild.href='/membresia';container.append(intro);
    if(top.data?.length){
      const ranked=top.mode==='ranked';const ranking=section(ranked?'Top 10 de la semana':'10 para descubrir',ranked?'Lo más visto por nuestra comunidad.':'Diez historias para tu próxima sesión de cine.',top.data);
      ranking.classList.add('cine-top10');ranking.querySelectorAll('.cine-card').forEach((node,i)=>{const rank=el('span',String(i+1),'cine-rank');rank.setAttribute('aria-hidden','true');node.prepend(rank);node.querySelector('.cine-poster').setAttribute('aria-label',`${ranked?'Puesto':'Selección'} ${i+1}: ${top.data[i].titulo}`);});container.append(ranking);
    }
    const fresh=new Map([...latest.data,...movies.data,...series.data,...anime.data,...biblical.data,...(top.data||[])].map(item=>[String(item.id),item]));
    const recent=AccountLibrary.recent().slice(0,12).map(item=>({...item,...fresh.get(String(item.id))}));if(recent.length)container.append(section('Vuelve a tus historias','Títulos abiertos recientemente en este navegador. La posición del vídeo depende del reproductor.',recent));
    if(latest.data.length)container.append(section('Recién llegados','Lo último que se sumó al catálogo.',latest.data,'todo'));
    for(const [title,description,result,kind] of [['Una noche de películas','Encuentra algo que te atrape.',movies,'pelicula'],['Una historia, muchos capítulos','Explora temporadas y episodios.',series,'serie'],['El universo del anime','Nuevos mundos por descubrir.',anime,'anime'],['Historias que inspiran','Explora nuestra sección de bíblicos.',biblical,'biblico']]){
      if(result.data.length)container.append(section(title,description,result.data,kind));
    }
    const promo=el('aside',null,'cine-install-promo qh-apps');promo.id='tus-pantallas';promo.setAttribute('aria-labelledby','apps-title');
    promo.append(el('p','QUÉ HAY VA CONTIGO','app-kicker'));
    const appTitle=el('h2',null,'app-heading');appTitle.id='apps-title';appTitle.append(document.createTextNode('Tu pantalla. Tu momento.'),el('br'),el('em','Tu Qué Hay.'));promo.append(appTitle,el('p','Del celular al sofá, con tu misma cuenta. Elige dónde empieza tu próxima historia.','app-intro'));
    const platforms=el('div',null,'app-grid');
    for(const [key,label,hint,shape,title,description,cta] of [
      ['android','APK MÓVIL','Para llevar','mobile','Android','Tu próxima maratón va contigo. Entra con tu cuenta y sigue explorando.','Instalar en Android'],
      ['tv','APK TV','Para el sofá','television','Android TV / Google TV','Pantalla grande, control remoto y tu cuenta vinculada desde el celular.','Instalar en mi TV'],
      ['navegador','DESDE TU NAVEGADOR','Sin archivo APK','browser','A un toque','Añade Qué Hay a tu pantalla de inicio. Menos vueltas para volver a tus historias.','Cómo añadirla']]){
      const tile=el('article',null,'app-card '+key),labelRow=el('div',null,'app-label');labelRow.append(el('span',label),el('span',hint));
      const stage=el('div',null,'app-device-stage');stage.setAttribute('aria-hidden','true');const device=el('div',null,'app-device '+shape),face=el('img');face.src='/static/logo-que-hay-live.png';face.alt='';face.width=42;face.height=42;face.loading='lazy';device.append(face);stage.append(device);
      const link=el('a',cta,'app-link');link.href='/instalar#'+key;const arrow=el('span','↗');arrow.setAttribute('aria-hidden','true');link.append(arrow);
      tile.append(labelRow,stage,el('h3',title),el('p',description),link);platforms.append(tile);
    }
    const appNote=el('p',null,'app-footnote');appNote.append(el('strong','La misma cuenta. Tus favoritos contigo.'),el('span','Instalar no activa ni renueva una membresía.'));promo.append(platforms,appNote);container.append(promo);
    const foot=el('footer',null,'cine-page-footer');foot.append(el('strong','QUEHAY CINE'),el('span','Historias que nos acompañan.'),el('a','Descubre la membresía'));foot.lastChild.href='/membresia';container.append(foot);
  }
  function browse(container,token,focus){
    container.replaceChildren();
    const heading=el('header',null,'cine-browse-heading');heading.append(el('p','EXPLORA A TU MANERA','cine-eyebrow'),el('h1','Encuentra tu próxima historia.'),el('p','Películas, series y anime. Elige qué quieres ver hoy.'));container.append(heading);
    const controls=el('section',null,'cine-controls');controls.setAttribute('aria-label','Buscar y filtrar catálogo');
    const label=el('label','Buscar por título','cine-search');const search=el('input');search.type='search';search.placeholder='¿Qué te gustaría ver?';search.value=state.query;search.autocomplete='off';search.id='cine-search';label.append(search);controls.append(label);
    const tabs=el('div',null,'cine-type-tabs');tabs.setAttribute('aria-label','Tipo de contenido');
    for(const [id,name] of Object.entries(types)){const b=button(name,()=>{state.type=id;tabs.querySelectorAll('button').forEach(n=>n.setAttribute('aria-pressed',String(n===b)));load();},'cine-filter');b.setAttribute('aria-pressed',String(state.type===id));tabs.append(b);}controls.append(tabs);
    const filters=el('div',null,'cine-filter-row');
    const genreLabel=el('label','Género');const genre=el('select');
    for(const g of ['', 'Acción','Aventura','Animación','Ciencia ficción','Comedia','Documental','Drama','Familia','Fantasía','Misterio','Romance','Suspense','Terror']){const o=el('option',g||'Todos los géneros');o.value=g;genre.append(o);}genre.value=state.genre;genreLabel.append(genre);
    const yearLabel=el('label','Año');const year=el('input');year.type='number';year.min='1888';year.max=String(new Date().getFullYear()+2);year.placeholder='Cualquier año';year.value=state.year;year.inputMode='numeric';yearLabel.append(year);
    const downloadLabel=el('label',null,'cine-download-filter');const download=el('input');download.type='checkbox';download.checked=state.download;downloadLabel.append(download,document.createTextNode('Con descarga'));
    const clear=button('Limpiar filtros',()=>{Object.assign(state,{type:'todo',query:'',genre:'',year:'',download:false});mount('explorar');},'cine-text-button');filters.append(genreLabel,yearLabel,downloadLabel,clear);controls.append(filters);container.append(controls);
    const status=el('p',null,'cine-result-count');status.setAttribute('role','status');const grid=el('div',null,'cine-grid');grid.setAttribute('aria-label','Resultados del catálogo');const more=button('Cargar más',()=>load(true),'cine-button secondary cine-more');more.hidden=true;container.append(status,grid,more);
    let requestId=0, offset=0, loading=false;
    async function load(append=false){
      if(append&&loading)return;
      clearTimeout(timer);const id=++requestId;loading=true;more.disabled=true;status.textContent='Buscando historias…';grid.setAttribute('aria-busy','true');
      if(!append){offset=0;grid.replaceChildren();more.hidden=true;}
      try{
        const result=await request(payload(offset));if(token!==revision||id!==requestId)return;
        offset+=result.data.length;grid.append(...result.data.map(card));status.textContent=`${result.total} ${result.total===1?'título encontrado':'títulos encontrados'}`;
        if(!offset)grid.append(empty('No encontramos ese título.','Prueba otro nombre o limpia los filtros.'));
        more.hidden=offset>=result.total||result.data.length===0;
      }catch(error){if(token!==revision||id!==requestId)return;status.textContent=error.message;const retry=button('Reintentar',()=>{retry.remove();load(append);});grid.append(retry);}
      finally{if(id===requestId){loading=false;more.disabled=false;grid.setAttribute('aria-busy','false');}}
    }
    search.oninput=()=>{state.query=search.value;++requestId;more.hidden=true;timer&&clearTimeout(timer);timer=setTimeout(()=>load(),250);};
    genre.onchange=()=>{state.genre=genre.value;load();};year.oninput=()=>{++requestId;more.hidden=true;clearTimeout(timer);if(year.checkValidity()){state.year=year.value;timer=setTimeout(()=>load(),250);}else status.textContent='Introduce un año entre 1888 y '+year.max+'.';};download.onchange=()=>{state.download=download.checked;load();};
    load();if(focus)search.focus();
  }
  async function mount(view,options={}){
    disposeHero();disposeHero=()=>{};
    clearTimeout(timer);const token=++revision;currentView=view;
    if(options.type)state.type=options.type;
    const container=document.getElementById('contenido');container.className='cine-main';
    document.querySelectorAll('[data-cine-view]').forEach(n=>{const active=n.dataset.cineView===(view==='buscar'?'explorar':view);n.classList.toggle('active',active);if(active)n.setAttribute('aria-current','page');else n.removeAttribute('aria-current');});
    container.replaceChildren(el('p','Preparando tus próximas historias…','cine-loading'));window.scrollTo({top:0,behavior:'instant'});
    try{
      if(view==='inicio')await home(container,token);
      else if(view==='guardados'){
        container.replaceChildren();const heading=el('header',null,'cine-browse-heading');heading.append(el('p','TU SELECCIÓN','cine-eyebrow'),el('h1','Mi lista'),el('p','Tus historias favoritas, listas para ver desde tu cuenta.'));container.append(heading);
        const items=getFavoritos();const grid=el('div',null,'cine-grid');grid.append(...items.map(card));container.append(items.length?grid:empty('Aquí empieza tu próxima maratón.','Pulsa + en un título para guardarlo.',button('Explorar catálogo',()=>root.cambiarVista('explorar'))));
      }else browse(container,token,view==='buscar');
    }catch(error){if(token===revision)container.replaceChildren(empty('No pudimos abrir el catálogo.',error.message,button('Reintentar',()=>mount(view,options))));}
  }
  root.CatalogBrowse={mount,card,cancel(){++revision;clearTimeout(timer);disposeHero();},refreshSaved(){if(currentView==='guardados')mount('guardados');else document.querySelectorAll('.cine-save').forEach(n=>{const active=getFavoritos().some(item=>String(item.id)===n.dataset.contentId);n.textContent=active?'✓':'+';n.setAttribute('aria-pressed',String(active));});}};
})(window);
