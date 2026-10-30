/* TV-only views. All content is escaped; playback URLs are allowlisted twice. */
(()=>{'use strict';
 const $=id=>document.getElementById(id),screen=$('screen');
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 let cleanups=[],episodeStream=null,savedCache=null;const browseCache=new Map(),knownTitles=new Map();
 function rememberTitles(data){
  const items=[data.item,data.featured,...(data.items||[]),...(data.related||[]),...(data.top10?.items||[]),...(data.rows||[]).flatMap(r=>r.items||[])];
  for(const item of items){if(!item?.tipo||!item.titulo)continue;knownTitles.delete(item.id);knownTitles.set(item.id,item);if(knownTitles.size>200)knownTitles.delete(knownTitles.keys().next().value);}
 }
 const labels={pelicula:'Películas',serie:'Series',anime:'Anime',biblico:'Bíblicos'};
 let me={},revision=0,seasonRevision=0,detail=null,season=null,episodePage=1,homeData=null,pollTimer=null,pairRevision=0,lastFocus=null,returnHash="",playing=null,next=null,playRevision=0;
 async function api(path,body,csrf){const options=body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json',...(csrf?{'X-CSRF-Token':csrf}:{})},body:JSON.stringify(body)};
  const r=await fetch('/tv/api/'+path,options),d=await r.json();if(!r.ok)throw Error(d.error||'No pudimos completar la solicitud.');rememberTitles(d);return d;}
 screen.addEventListener('error',e=>{if(e.target.tagName==='IMG'&&!e.target.src.endsWith('/tv/brand')){e.target.src='/tv/brand';e.target.classList.add('poster-fallback');}},true);
 function toast(text){$('toast').textContent=text;clearTimeout(toast.timer);toast.timer=setTimeout(()=>{$('toast').textContent='';},6000);}
 function image(url,size='w780'){
  return esc(TVImages.source(url,size));
 }
 function meta(item,includeGenre=true){return `<div class="meta">${item.rating?`<span class="rating">★ ${esc(Number(item.rating).toFixed(1))}</span>`:''}<span>${esc(item.año||'')}</span><span>${esc(labels[item.tipo]||'')}</span>${includeGenre?`<span>${esc((item.genero||'').split(',')[0])}</span>`:''}</div>`;}
 function card(item){return `<button data-nav class="poster" id="title-${item.id}" data-title="${item.id}"><img loading="lazy" decoding="async" src="${image(item.imagen_url,'w342')}" alt=""><span class="caption">${esc(item.titulo)}</span><small>${esc(item.año||labels[item.tipo]||'')} ${item.rating?' · ★ '+esc(Number(item.rating).toFixed(1)):''}</small></button>`;}
 function topTen(data){if(!data?.items.length)return '';const ranked=data.mode==='ranked';return `<section class="shelf top-ten"><div class="section-heading"><h2>${ranked?'Top 10 películas de la semana':'10 películas para descubrir'}</h2><span>${ranked?'Las más vistas por nuestra comunidad':'Tu próxima noche de cine'}</span></div><div class="rail" data-row="top10">${data.items.map((item,i)=>`<button data-nav class="poster ranked-poster" id="top-title-${item.id}" data-title="${item.id}" aria-label="${ranked?'Puesto':'Selección'} ${i+1}: ${esc(item.titulo)}"><span class="rank-number" aria-hidden="true">${i+1}</span><div class="rank-cover"><img loading="lazy" decoding="async" src="${image(item.imagen_url,'w342')}" alt=""><span class="caption">${esc(item.titulo)}</span></div></button>`).join('')}</div></section>`;}
 function activateNav(kind){document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',kind==='home'?b.dataset.view==='home':b.dataset.kind===kind));}
 function go(hash){history.pushState(null,'',hash?'#'+hash:location.pathname);render();}
 function bindCards(scope=screen){scope.querySelectorAll('[data-title]').forEach(b=>b.onclick=()=>{lastFocus=b.id;returnHash=location.hash.slice(1);go('title='+b.dataset.title);});}
 async function refreshMe(){me=await api('me');$('account-nav').textContent=me.linked?'Hola, '+me.name.split(' ')[0]+'  ☺':'Vincular cuenta  ☺';}
 async function home(rev){activateNav('home');homeData=homeData||await api('home');if(rev!==revision)return;
  const bucket=Math.floor(Date.now()/(3*86400000));if(homeData.featureBucket!==bucket){homeData.featured=TVHome.choose(homeData.rows);homeData.featureBucket=bucket;}
  screen.innerHTML=TVHome.render(homeData.featured,image,esc,meta)+'<div class="shelves home-shelves">'+topTen(homeData.top10)+homeData.rows.filter(r=>r.items.length).map(r=>`<section class="shelf"><div class="section-heading"><h2>${esc(r.title)}</h2><span>Explora con el control →</span></div><div class="rail" id="home-rail-${r.kind}" data-row="${r.kind}">${r.items.map(card).join('')}</div></section>`).join('')+'</div>';
  bindCards();cleanups.push(TVHome.mount({items:homeData.featured,image,esc,meta,valid:()=>rev===revision,
   open:item=>{lastFocus='hero-open';returnHash='';go('title='+item.id);},explore:()=>TVFocus.focus(screen.querySelector('.home-shelves [data-nav]'))}));
  homeData.rows.filter(r=>r.items.length).forEach(row=>{const container=$('home-rail-'+row.kind);const stream=TVStream.mount({container,initial:row,horizontal:true,valid:()=>rev===revision,
   load:page=>api('catalog?kind='+row.kind+'&page='+page),append:(items,marker)=>{marker.insertAdjacentHTML('beforebegin',items.map(card).join(''));bindCards(container);},onChange:data=>Object.assign(row,data)});cleanups.push(()=>stream.dispose());});
  TVFocus.focus($(lastFocus)||$('hero-open')||$('account-nav'));
 }
 let browseFocus=null;
 async function browse(params,rev){
  const state={kind:params.get('kind')||'',q:params.get('q')||'',page:Number(params.get('page'))||1,genre:params.get('genre')||'',sort:params.get('sort')||'recent',format:params.get('format')||''};
  activateNav(state.kind);
  const key=new URLSearchParams({...state,page:1}).toString();const cached=browseCache.get(key);
  const data=cached&&cached.expires>Date.now()?cached.data:await api('catalog?'+key);if(rev!==revision)return;
  const remember=value=>{browseCache.delete(key);browseCache.set(key,{data:value,expires:Date.now()+300000});if(browseCache.size>6)browseCache.delete(browseCache.keys().next().value);};remember(data);
  state.page=data.page;screen.innerHTML=TVBrowse.render(data,state,image,esc,card);
  const navigate=(changes,focus)=>{browseFocus=focus;const updated={...state,...changes};const query=new URLSearchParams(updated);query.delete('page');if(!updated.kind)query.set('search','1');go(query.toString());};
  bindCards();
  if($('collection-explore'))$('collection-explore').onclick=()=>TVFocus.focus($('format-all')||$('genre-all'));
  screen.querySelectorAll('[data-genre]').forEach(b=>b.onclick=()=>navigate({genre:b.dataset.genre,page:1},b.id));
  screen.querySelectorAll('[data-format]').forEach(b=>b.onclick=()=>navigate({format:b.dataset.format,page:1},b.id));
  screen.querySelectorAll('[data-sort]').forEach(b=>b.onclick=()=>navigate({sort:b.dataset.sort,page:1},b.id));
  $('search-form').onsubmit=e=>{e.preventDefault();navigate({q:$('search-input').value.trim(),page:1},'results');};
  if($('collection-reset'))$('collection-reset').onclick=()=>navigate({genre:'',format:'',q:'',page:1},'genre-all');
  const container=screen.querySelector('.collection-results');let offset=data.items.length;
  const stream=TVStream.mount({container,initial:data,columns:state.kind==='biblico'?3:6,valid:()=>rev===revision,
   load:page=>api('catalog?'+new URLSearchParams({...state,page})),append:(items,marker)=>{marker.insertAdjacentHTML('beforebegin',TVBrowse.rows(items,state.kind,image,esc,card,offset));offset+=items.length;bindCards(container);},onChange:remember});cleanups.push(()=>stream.dispose());
  const focus=browseFocus==='results'?screen.querySelector('.collection-results [data-nav]'):$(browseFocus);
  TVFocus.focus(focus||(lastFocus?$(lastFocus):null)||(!state.kind?$('search-input'):$('collection-feature'))||$('genre-all'));browseFocus=null;
 }
 async function saveTitle(data,rev){
  const button=$('detail-save');if(button.getAttribute('aria-busy')==='true')return;button.setAttribute('aria-busy','true');
  try{await refreshMe();if(rev!==revision)return;if(!me.linked){openAccount();return;}
   const result=await api('list',{id:data.item.id,saved:!data.saved},me.csrf);if(rev!==revision)return;
   savedCache=null;data.saved=result.saved;button.setAttribute('aria-pressed',String(result.saved));button.setAttribute('aria-label',result.saved?'Quitar de Mi lista':'Añadir a Mi lista');
   button.innerHTML='<span aria-hidden="true">'+(result.saved?'✓':'＋')+'</span> Mi lista';toast(result.saved?'Añadido a Mi lista.':'Quitado de Mi lista.');
  }catch(e){if(rev===revision)toast(e.message);}finally{button.removeAttribute('aria-busy');}
 }
 async function savedView(params,rev){
  activateNav('list');$('list-nav').classList.add('active');await refreshMe();if(rev!==revision)return;
  if(!me.linked){screen.innerHTML='<section class="saved-library"><p class="eyebrow">TUS HISTORIAS</p><h1>Mi lista</h1><p>Vincula tu cuenta desde el celular para guardar lo que quieres ver.</p><button data-nav id="list-link" class="primary">Vincular cuenta</button></section>';$('list-link').onclick=openAccount;TVFocus.focus($('list-link'));return;}
  const data=savedCache&&savedCache.csrf===me.csrf&&savedCache.expires>Date.now()?savedCache.data:await api('list?page=1');if(rev!==revision)return;
  const remember=value=>{savedCache={data:value,csrf:me.csrf,expires:Date.now()+60000};};remember(data);
  screen.innerHTML='<section class="saved-library"><p class="eyebrow">TUS HISTORIAS, A TU RITMO</p><h1>Mi lista</h1><p>'+ (data.total?data.total+(data.total===1?' título':' títulos')+' para volver cuando quieras.':'Tu próxima historia empieza aquí. Guarda películas y series con ＋ Mi lista.')+'</p><div class="saved-results">'+TVBrowse.rows(data.items,'',image,esc,card)+'</div>'+(!data.total?'<button data-nav id="list-explore" class="primary">Explorar catálogo</button>':'')+'</section>';
  bindCards();if($('list-explore'))$('list-explore').onclick=()=>go('kind=pelicula');
  const container=screen.querySelector('.saved-results');let offset=data.items.length;
  const stream=TVStream.mount({container,initial:data,valid:()=>rev===revision,load:page=>api('list?page='+page),append:(items,marker)=>{marker.insertAdjacentHTML('beforebegin',TVBrowse.rows(items,'',image,esc,card,offset));offset+=items.length;bindCards(container);},onChange:remember});cleanups.push(()=>stream.dispose());
  TVFocus.focus($(lastFocus)||screen.querySelector('.saved-results [data-nav]')||$('list-explore'));
 }

 async function titleView(cid,rev){
  const known=knownTitles.get(cid)||[...(homeData?.top10?.items||[]),...(homeData?.rows||[]).flatMap(r=>r.items),...[...browseCache.values()].flatMap(x=>x.data.items),...(savedCache?.data.items||[])].find(x=>x.id===cid);
  if(known){screen.innerHTML=TVDetail.pending(known,image,esc,meta);$('detail-back').onclick=()=>go(returnHash);TVFocus.focus($('detail-back'));}
  const data=await api('title/'+cid);if(rev!==revision)return;detail=data;activateNav(data.item.tipo);season=data.seasons.find(s=>s.id===data.first_episode?.temporada_id)||data.seasons.find(s=>s.episodios>0);episodePage=1;
  screen.innerHTML=TVDetail.render(data,image,esc,meta,card);
  $('detail-back').onclick=()=>go(returnHash);
  $('detail-play').onclick=()=>play(data.item,data.first_episode);
  const showEpisodes=()=>TVFocus.focus($('season-'+season?.id)||$('detail-other-series'));
  if($('detail-episodes'))$('detail-episodes').onclick=showEpisodes;
  if($('series-tab-episodes'))$('series-tab-episodes').onclick=showEpisodes;
  if($('series-tab-related'))$('series-tab-related').onclick=()=>TVFocus.focus(screen.querySelector('#detail-related [data-nav]'));
  const seriesPanel=screen.querySelector('.cinema-episodes'),seriesDetail=screen.querySelector('.detail-series');
  if(seriesPanel){seriesPanel.addEventListener('focusin',e=>{if(!seriesDetail.classList.contains('episodes-focused')){seriesDetail.classList.add('episodes-focused');TVFocus.focus(e.target);requestAnimationFrame(()=>{if(rev===revision&&seriesDetail.classList.contains('episodes-focused')){window.scrollTo({top:0,behavior:'instant'});}});}});
   screen.querySelector('.series-section-tabs').addEventListener('keydown',e=>{if(e.key==='ArrowUp'){e.preventDefault();e.stopPropagation();seriesDetail.classList.remove('episodes-focused');TVFocus.focus(data.playable?$('detail-play'):$('detail-save'));}});
  }

  $('detail-save').onclick=()=>saveTitle(data,rev);
  if($('detail-other-series'))$('detail-other-series').onclick=()=>go('kind=serie');
  screen.querySelectorAll('[data-title]').forEach(b=>b.onclick=()=>{returnHash='kind='+data.item.tipo;go('title='+b.dataset.title);});
  screen.querySelectorAll('[data-season]').forEach(b=>b.onclick=()=>{season=data.seasons.find(s=>s.id===Number(b.dataset.season));episodePage=1;loadEpisodes(rev,true).catch(e=>toast(e.message));});
  if(season)loadEpisodes(rev,false,data.initial_episodes).catch(e=>{if(rev===revision)toast(e.message);});if(rev===revision)TVFocus.focus(data.playable?$('detail-play'):$('detail-back'));
 }
 function episodeCard(ep){return `<button data-nav class="episode" id="episode-${ep.id}" data-episode="${ep.id}" aria-disabled="${!ep.playable}"><div class="episode-image"><img loading="lazy" decoding="async" alt="" src="${image(ep.imagen_url||detail.item.backdrop_url,'w500')}"><b>${ep.numero}${!ep.playable?' · Sin video':''}</b></div><div class="episode-content"><h3>${esc(ep.titulo||'Episodio '+ep.numero)}</h3><small>${esc(ep.duracion?ep.duracion+' min':'Episodio '+ep.numero)}</small></div></button>`;}
 async function loadEpisodes(rev,focus,initial){episodeStream?.dispose();episodeStream=null;const seq=++seasonRevision,sid=season.id,cid=detail.item.id;
  const valid=()=>rev===revision&&seq===seasonRevision;const data=initial?.season_id===sid?initial:await api(`episodes/${cid}/${sid}?page=1`);if(!valid())return;
  const episodes=new Map(data.items.map(ep=>[ep.id,ep]));
  screen.querySelectorAll('[data-season]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.season)===sid)));
  $('episode-results').innerHTML=`<div class="episodes" data-row="episodes">${data.items.map(episodeCard).join('')}</div><div class="episode-peek" aria-live="off"><span id="episode-peek-title"></span><p id="episode-peek-copy">Elige un episodio para ver su descripción.</p></div>`;
  const container=screen.querySelector('.episodes');
  const bind=()=>container.querySelectorAll('[data-episode]').forEach(b=>b.onclick=()=>{const ep=episodes.get(Number(b.dataset.episode));if(ep.playable)play(detail.item,ep);else toast('Este episodio todavía no tiene video disponible para TV.');});bind();
  container.addEventListener('focusin',e=>{const ep=episodes.get(Number(e.target.dataset.episode));if(ep){$('episode-peek-title').textContent='Episodio '+ep.numero+' · '+(ep.titulo||'');$('episode-peek-copy').textContent=ep.sinopsis||'Continúa la historia con este episodio.';}});
  episodeStream=TVStream.mount({container,initial:data,horizontal:true,valid,load:page=>api(`episodes/${cid}/${sid}?page=${page}`),append:(items,marker)=>{items.forEach(ep=>episodes.set(ep.id,ep));marker.insertAdjacentHTML('beforebegin',items.map(episodeCard).join(''));bind();}});
  if(focus)TVFocus.focus(container.querySelector('[data-episode]')||$('season-'+sid));
 }
 async function render(){cleanups.forEach(fn=>fn());cleanups=[];episodeStream?.dispose();episodeStream=null;const rev=++revision;seasonRevision++;window.scrollTo({top:0,behavior:'instant'});screen.innerHTML='<p class="loading">Preparando tus historias…</p>';
  try{const params=new URLSearchParams(location.hash.slice(1));if(params.has('title'))await titleView(Number(params.get('title')),rev);else if(params.has('list'))await savedView(params,rev);else if(params.has('kind')||params.has('search')||params.has('q'))await browse(params,rev);else await home(rev);}
  catch(e){if(rev===revision){screen.innerHTML='<div class="empty"><h1>No pudimos cargar esta pantalla.</h1><p>'+esc(e.message)+'</p><div data-row="retry"><button data-nav id="retry-view">Volver a intentar</button></div></div>';$('retry-view').onclick=render;TVFocus.focus($('retry-view'));}}
 }
 function closeAccount(){pairRevision++;clearTimeout(pollTimer);$('account-dialog').close();TVFocus.focus($('account-nav'));}
 async function openAccount(){const rev=++pairRevision;clearTimeout(pollTimer);$('account-body').innerHTML='<p>Comprobando tu cuenta…</p>';$('account-dialog').showModal();TVFocus.focus($('account-close'));
  try{await refreshMe();if(rev!==pairRevision)return;
   if(me.linked){$('account-body').innerHTML=`<p class="eyebrow">TU CUENTA EN ESTA PANTALLA</p><h2>Hola, ${esc(me.name.split(' ')[0])}.</h2><p class="account-state">${me.permanent?'Tienes acceso permanente como propietario.':me.active?'Tu acceso está activo. Elige algo y disfruta.':'Tu cuenta no tiene acceso activo. Revísala desde tu celular.'}</p><div data-row="account-actions"><button data-nav id="unlink-tv">Desvincular este televisor</button></div>`;$('unlink-tv').onclick=async()=>{try{await api('unlink',{},me.csrf);closeAccount();await refreshMe();if(new URLSearchParams(location.hash.slice(1)).has('list')||new URLSearchParams(location.hash.slice(1)).has('title'))render();toast('Televisor desvinculado.');}catch(e){toast(e.message);}};TVFocus.focus($('account-close'));return;}
   const pair=await api('pair/start',{});if(rev!==pairRevision)return;
   $('account-body').innerHTML=`<p class="eyebrow">TUS HISTORIAS, EN UNA PANTALLA MÁS GRANDE</p><h2>Vincula desde tu celular.</h2><p>Abre esta dirección, inicia sesión y confirma el código que ves aquí.</p><p class="pair-url">${esc(pair.url)}</p><div class="pair-code">${esc(pair.code)}</div><p id="pair-state">Este código vence en 10 minutos.</p>${pair.demo?'<p class="pair-note">Vista local: puedes comprobar la pantalla del celular en otra pestaña de esta computadora.</p>':'<p class="pair-note">Tu cuenta se conserva. Puedes desvincular la TV desde el celular.</p>'}`;
   const poll=async()=>{if(rev!==pairRevision)return;try{const d=await api('pair/poll',{});if(rev!==pairRevision)return;if(d.state==='linked'){await refreshMe();closeAccount();if(new URLSearchParams(location.hash.slice(1)).has('list')||new URLSearchParams(location.hash.slice(1)).has('title'))render();toast('Cuenta vinculada. Bienvenido a Qué Hay.');return;}if(d.state==='expired'){expired();return;}pollTimer=setTimeout(poll,3000);}catch(e){if(rev!==pairRevision)return;$('pair-state').textContent=e.message;pollTimer=setTimeout(poll,10000);}};
   function expired(){$('pair-state').textContent='El código venció. Genera otro para continuar.';const b=document.createElement('button');b.dataset.nav='';b.textContent='Generar otro código';b.onclick=()=>{closeAccount();openAccount();};$('account-body').append(b);TVFocus.focus(b);}
   pollTimer=setTimeout(poll,3000);TVFocus.focus($('account-close'));
  }catch(e){$('account-body').innerHTML='<h2>No pudimos vincular la cuenta.</h2><p>'+esc(e.message)+'</p>';}
 }
 function safePlayer(url){try{const u=new URL(url);return u.protocol==='https:'&&!u.username&&!u.password&&((u.origin==='https://videoapi.la'&&/^\/e\/(movie\/\d+|(tv|anime)\/\d+\/\d+\/\d+)$/.test(u.pathname))||(u.origin==='https://ok.ru'&&/^\/videoembed\/\d+$/.test(u.pathname)));}catch(_){return false;}}
 async function play(item,ep){const rev=++playRevision;try{await refreshMe();}catch(e){toast(e.message);return;}if(rev!==playRevision)return;if(!me.linked){openAccount();return;}if(!me.active){toast('Tu cuenta no tiene acceso activo. Revísala desde tu celular.');return;}
  try{const d=await api('play',{id:item.id,episode:ep?.id||null},me.csrf);if(rev!==playRevision)return;if(!safePlayer(d.url))throw Error('Reproductor no permitido.');playing={item,ep};next=d.next;$('player-title').textContent=item.titulo+(ep?' · Episodio '+ep.numero:'');$('player-next').hidden=!next;
   $('player-message').textContent='Pulsa OK en «Controles del video» para entrar al reproductor.';
   $('player-frame').src=d.url;$('player').hidden=false;document.querySelector('.topbar').inert=true;screen.inert=true;TVFocus.focus($('player-enter'));
  }catch(e){toast(e.message);}
 }
 function closePlayer(){playRevision++;$('player-frame').src='about:blank';$('player').hidden=true;document.querySelector('.topbar').inert=false;screen.inert=false;TVFocus.focus((playing?.ep?$('episode-'+playing.ep.id):null)||$('detail-play'));playing=null;next=null;}
 rootBack();function rootBack(){window.TVBack=()=>{if($('account-dialog').open){closeAccount();return true;}if(!$('player').hidden){closePlayer();return true;}const compact=screen.querySelector('.detail-series.episodes-focused');if(compact){compact.classList.remove('episodes-focused');TVFocus.focus($('detail-play').disabled?$('detail-save'):$('detail-play'));return true;}if(location.hash){go(location.hash.includes('title=')?returnHash:'');return true;}TVFocus.focus(document.querySelector('[data-view="home"]'));return false;};}
 window.addEventListener('popstate',()=>{if(!$('player').hidden)closePlayer();render();});
 document.querySelectorAll('[data-kind]').forEach(b=>b.onclick=()=>{lastFocus=null;browseFocus=null;go('kind='+b.dataset.kind);});document.querySelector('[data-view="home"]').onclick=()=>{lastFocus=null;go('');};$('list-nav').onclick=()=>{lastFocus=null;go('list=1');};$('search-nav').onclick=()=>go('search=1');$('account-nav').onclick=openAccount;$('account-close').onclick=closeAccount;$('account-dialog').addEventListener('cancel',e=>{e.preventDefault();closeAccount();});
 $('player-close').onclick=closePlayer;$('player-enter').onclick=()=>{$('player-message').textContent='';$('player-frame').focus();};$('player-next').onclick=()=>{if(next&&playing)play(playing.item,next);};
 refreshMe().catch(()=>{});render();
})();
