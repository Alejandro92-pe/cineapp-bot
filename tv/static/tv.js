/* TV-only views. All content is escaped; playback URLs are allowlisted twice. */
(()=>{'use strict';
 const $=id=>document.getElementById(id),screen=$('screen');
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const labels={pelicula:'Películas',serie:'Series',anime:'Anime',biblico:'Bíblicos'};
 let me={},revision=0,seasonRevision=0,detail=null,season=null,episodePage=1,homeData=null,pollTimer=null,pairRevision=0,lastFocus=null,returnHash="",playing=null,next=null,playRevision=0;
 async function api(path,body,csrf){const options=body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json',...(csrf?{'X-CSRF-Token':csrf}:{})},body:JSON.stringify(body)};
  const r=await fetch('/tv/api/'+path,options),d=await r.json();if(!r.ok)throw Error(d.error||'No pudimos completar la solicitud.');return d;}
 function toast(text){$('toast').textContent=text;clearTimeout(toast.timer);toast.timer=setTimeout(()=>{$('toast').textContent='';},6000);}
 function image(url,size='w780'){
  try{const u=new URL(url);if(u.origin==='https://image.tmdb.org'&&u.pathname.startsWith('/t/p/')){u.pathname=u.pathname.replace(/\/t\/p\/[^/]+\//,'/t/p/'+size+'/');return esc(u.href);}}catch(_){}return '/tv/brand';
 }
 function meta(item){return `<div class="meta">${item.rating?`<span class="rating">★ ${esc(Number(item.rating).toFixed(1))}</span>`:''}<span>${esc(item.año||'')}</span><span>${esc(labels[item.tipo]||'')}</span><span>${esc((item.genero||'').split(',')[0])}</span></div>`;}
 function card(item){return `<button data-nav class="poster" id="title-${item.id}" data-title="${item.id}"><img loading="lazy" src="${image(item.imagen_url,'w342')}" alt=""><span class="caption">${esc(item.titulo)}</span><small>${esc(item.año||labels[item.tipo]||'')} ${item.rating?' · ★ '+esc(Number(item.rating).toFixed(1)):''}</small></button>`;}
 function topTen(data){if(!data?.items.length)return '';const ranked=data.mode==='ranked';return `<section class="shelf top-ten"><div class="section-heading"><h2>${ranked?'Top 10 películas de la semana':'10 películas para descubrir'}</h2><span>${ranked?'Las más vistas por nuestra comunidad':'Tu próxima noche de cine'}</span></div><div class="rail" data-row="top10">${data.items.map((item,i)=>`<button data-nav class="poster ranked-poster" id="top-title-${item.id}" data-title="${item.id}" aria-label="${ranked?'Puesto':'Selección'} ${i+1}: ${esc(item.titulo)}"><span class="rank-number" aria-hidden="true">${i+1}</span><div class="rank-cover"><img loading="lazy" src="${image(item.imagen_url,'w342')}" alt=""><span class="caption">${esc(item.titulo)}</span></div></button>`).join('')}</div></section>`;}
 function hero(item,full=false){return `<section class="hero"><div class="hero-art"><img src="${image(item.backdrop_url||item.imagen_url,'w1280')}" alt=""></div><div class="hero-copy"><p class="eyebrow">${full?'QUÉ HAY · '+esc(labels[item.tipo]):'UNA GRAN HISTORIA. TU MEJOR PANTALLA.'}</p><h1>${esc(item.titulo)}</h1>${meta(item)}<p class="synopsis">${esc(item.sinopsis||'Encuentra tu próxima historia en Qué Hay.')}</p><div class="actions" data-row="hero-actions">${full?`<button data-nav class="primary" id="detail-play">▶ ${detail.seasons.length?'Ver episodios':'Reproducir'}</button><button data-nav id="detail-back" class="secondary">Volver</button>`:`<button data-nav class="primary" id="hero-open" data-title="${item.id}">Descubrir película →</button><button data-nav class="secondary" id="hero-browse">Explorar catálogo</button>`}</div></div></section>`;}
 function activateNav(kind){document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',kind==='home'?b.dataset.view==='home':b.dataset.kind===kind));}
 function go(hash){history.pushState(null,'',hash?'#'+hash:location.pathname);render();}
 function bindCards(){screen.querySelectorAll('[data-title]').forEach(b=>b.onclick=()=>{lastFocus=b.id;returnHash=location.hash.slice(1);go('title='+b.dataset.title);});}
 async function refreshMe(){me=await api('me');$('account-nav').textContent=me.linked?'Hola, '+me.name.split(' ')[0]+'  ☺':'Vincular cuenta  ☺';}
 async function home(rev){activateNav('home');homeData=homeData||await api('home');if(rev!==revision)return;
  const film=homeData.rows.find(r=>r.kind==='pelicula')?.items.find(x=>x.backdrop_url)||homeData.rows[0]?.items[0];
  screen.innerHTML=(film?hero(film):'')+'<div class="shelves">'+topTen(homeData.top10)+homeData.rows.filter(r=>r.items.length).map(r=>`<section class="shelf"><div class="section-heading"><h2>${esc(r.title)}</h2><span>Desliza con el control →</span></div><div class="rail" data-row="${r.kind}">${r.items.map(card).join('')}</div></section>`).join('')+'</div>';
  bindCards();if($('hero-browse'))$('hero-browse').onclick=()=>go('kind=pelicula');TVFocus.focus($(lastFocus)||$('hero-open')||$('account-nav'));
 }
 async function browse(params,rev){const kind=params.get('kind')||'',q=params.get('q')||'',page=Number(params.get('page'))||1;activateNav(kind);
  const data=await api('catalog?'+new URLSearchParams({kind,q,page}));if(rev!==revision)return;
  const heading=params.has('search')?'Tu próxima historia empieza aquí':labels[kind]||'Explorar catálogo';
  screen.innerHTML=`<section class="browse"><p class="eyebrow">ENCUENTRA ALGO QUE TE ATRAPE</p><h1>${esc(heading)}</h1><form class="search-form" id="search-form" data-row="search"><input data-nav id="search-input" aria-label="Buscar título" placeholder="Busca una película, serie o anime" maxlength="80" value="${esc(q)}"><button data-nav class="primary">Buscar</button></form><div class="browse-grid">${data.items.map(card).join('')}</div><div class="pages" data-row="pages"><button data-nav id="catalog-prev" ${page===1?'disabled':''}>← Anteriores</button><span>Página ${page}</span><button data-nav id="catalog-next" ${!data.has_next?'disabled':''}>Más títulos →</button></div>${data.items.length?'':'<p class="empty">No encontramos ese título. Prueba con otro nombre.</p>'}</section>`;
  // Grid rows are explicit so Up/Down retain the nearest column with a remote.
  const grid=screen.querySelector('.browse-grid');const cards=[...grid.querySelectorAll('.poster')];grid.replaceChildren();
  for(let i=0;i<cards.length;i+=6){const row=document.createElement('div');row.className='result-row';row.dataset.row='results';cards.slice(i,i+6).forEach(c=>row.append(c));grid.append(row);}
  $('search-form').onsubmit=e=>{e.preventDefault();go(new URLSearchParams({search:'1',q:$('search-input').value.trim()}).toString());};
  $('catalog-prev').onclick=()=>go(new URLSearchParams({kind,q,page:page-1}).toString());$('catalog-next').onclick=()=>go(new URLSearchParams({kind,q,page:page+1}).toString());bindCards();TVFocus.focus(params.has('search')&&!q?$('search-input'):cards[0]||$('search-input'));
 }
 async function titleView(cid,rev){const data=await api('title/'+cid);if(rev!==revision)return;detail=data;season=data.seasons.find(s=>s.numero>0)||data.seasons[0];episodePage=1;
  screen.innerHTML=`<article class="detail">${hero(data.item,true)}${data.seasons.length?`<section class="episode-section"><div class="section-heading"><h2>Elige dónde empieza tu historia</h2><span>Temporadas y episodios</span></div><div class="season-tabs" data-row="seasons">${data.seasons.map(s=>`<button data-nav data-season="${s.id}" id="season-${s.id}" aria-pressed="${s===season}">${s.numero===0?'Especiales':'Temporada '+s.numero}</button>`).join('')}</div><div id="episode-results"><p class="loading">Cargando episodios…</p></div></section>`:''}</article>`;
  $('detail-back').onclick=()=>go(returnHash);$('detail-play').onclick=()=>data.seasons.length?TVFocus.focus($('season-'+season.id)):play(data.item,null);
  screen.querySelectorAll('[data-season]').forEach(b=>b.onclick=()=>{season=data.seasons.find(s=>s.id===Number(b.dataset.season));episodePage=1;loadEpisodes(rev,true).catch(e=>toast(e.message));});
  if(season)await loadEpisodes(rev,false);if(rev===revision)TVFocus.focus($('detail-play'));
 }
 async function loadEpisodes(rev,focus){const seq=++seasonRevision,sid=season.id,cid=detail.item.id,p=episodePage;
  const data=await api(`episodes/${cid}/${sid}?page=${p}`);if(rev!==revision||seq!==seasonRevision)return;
  screen.querySelectorAll('[data-season]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.season)===sid)));
  $('episode-results').innerHTML=`<div class="episodes" data-row="episodes">${data.items.map(ep=>`<button data-nav class="episode" id="episode-${ep.id}" data-episode="${ep.id}"><div class="episode-image"><img loading="lazy" alt="" src="${image(ep.imagen_url||detail.item.backdrop_url,'w500')}"><b>EPISODIO ${ep.numero}</b></div><div class="episode-content"><small>${esc(ep.duracion?ep.duracion+' min':'')}</small><h3>${esc(ep.titulo||'Episodio '+ep.numero)}</h3><p>${esc(ep.sinopsis||'Continúa la historia con este episodio.')}</p></div></button>`).join('')}</div><div class="pages" data-row="episode-pages"><button data-nav id="episode-prev" ${p===1?'disabled':''}>← Anteriores</button><span>${data.total?((p-1)*6+1)+'–'+Math.min(p*6,data.total)+' de '+data.total+' episodios':'Sin episodios disponibles'}</span><button data-nav id="episode-more" ${!data.has_next?'disabled':''}>Más episodios →</button></div>`;
  screen.querySelectorAll('[data-episode]').forEach(b=>b.onclick=()=>play(detail.item,data.items.find(e=>e.id===Number(b.dataset.episode))));
  $('episode-prev').onclick=()=>{episodePage--;loadEpisodes(rev,true).catch(e=>toast(e.message));};$('episode-more').onclick=()=>{episodePage++;loadEpisodes(rev,true).catch(e=>toast(e.message));};
  if(focus)TVFocus.focus(screen.querySelector('[data-episode]')||$('season-'+sid));
 }
 async function render(){const rev=++revision;seasonRevision++;window.scrollTo({top:0,behavior:'instant'});screen.innerHTML='<p class="loading">Preparando tus historias…</p>';
  try{const params=new URLSearchParams(location.hash.slice(1));if(params.has('title'))await titleView(Number(params.get('title')),rev);else if(params.has('kind')||params.has('search')||params.has('q'))await browse(params,rev);else await home(rev);}
  catch(e){if(rev===revision){screen.innerHTML='<div class="empty"><h1>No pudimos cargar esta pantalla.</h1><p>'+esc(e.message)+'</p><div data-row="retry"><button data-nav id="retry-view">Volver a intentar</button></div></div>';$('retry-view').onclick=render;TVFocus.focus($('retry-view'));}}
 }
 function closeAccount(){pairRevision++;clearTimeout(pollTimer);$('account-dialog').close();TVFocus.focus($('account-nav'));}
 async function openAccount(){const rev=++pairRevision;clearTimeout(pollTimer);$('account-body').innerHTML='<p>Comprobando tu cuenta…</p>';$('account-dialog').showModal();TVFocus.focus($('account-close'));
  try{await refreshMe();if(rev!==pairRevision)return;
   if(me.linked){$('account-body').innerHTML=`<p class="eyebrow">TU CUENTA EN ESTA PANTALLA</p><h2>Hola, ${esc(me.name.split(' ')[0])}.</h2><p class="account-state">${me.active?'Tu acceso está activo. Elige algo y disfruta.':'Tu cuenta no tiene acceso activo. Revísala desde tu celular.'}</p><div data-row="account-actions"><button data-nav id="unlink-tv">Desvincular este televisor</button></div>`;$('unlink-tv').onclick=async()=>{try{await api('unlink',{},me.csrf);closeAccount();await refreshMe();toast('Televisor desvinculado.');}catch(e){toast(e.message);}};TVFocus.focus($('account-close'));return;}
   const pair=await api('pair/start',{});if(rev!==pairRevision)return;
   $('account-body').innerHTML=`<p class="eyebrow">TUS HISTORIAS, EN UNA PANTALLA MÁS GRANDE</p><h2>Vincula desde tu celular.</h2><p>Abre esta dirección, inicia sesión y confirma el código que ves aquí.</p><p class="pair-url">${esc(pair.url)}</p><div class="pair-code">${esc(pair.code)}</div><p id="pair-state">Este código vence en 10 minutos.</p><p class="pair-note">Vista local: puedes comprobar la pantalla del celular en otra pestaña de esta computadora.</p>`;
   const poll=async()=>{if(rev!==pairRevision)return;try{const d=await api('pair/poll',{});if(rev!==pairRevision)return;if(d.state==='linked'){await refreshMe();closeAccount();toast('Cuenta vinculada. Bienvenido a Qué Hay.');return;}if(d.state==='expired'){expired();return;}pollTimer=setTimeout(poll,3000);}catch(e){if(rev!==pairRevision)return;$('pair-state').textContent=e.message;pollTimer=setTimeout(poll,10000);}};
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
 function closePlayer(){playRevision++;$('player-frame').src='about:blank';$('player').hidden=true;document.querySelector('.topbar').inert=false;screen.inert=false;TVFocus.focus(playing?.ep?$('episode-'+playing.ep.id):$('detail-play'));playing=null;next=null;}
 rootBack();function rootBack(){window.TVBack=()=>{if($('account-dialog').open){closeAccount();return true;}if(!$('player').hidden){closePlayer();return true;}if(location.hash){go(location.hash.includes('title=')?returnHash:'');return true;}TVFocus.focus(document.querySelector('[data-view="home"]'));return false;};}
 window.addEventListener('popstate',()=>{if(!$('player').hidden)closePlayer();render();});
 document.querySelectorAll('[data-kind]').forEach(b=>b.onclick=()=>go('kind='+b.dataset.kind));document.querySelector('[data-view="home"]').onclick=()=>go('');$('search-nav').onclick=()=>go('search=1');$('account-nav').onclick=openAccount;$('account-close').onclick=closeAccount;$('account-dialog').addEventListener('cancel',e=>{e.preventDefault();closeAccount();});
 $('player-close').onclick=closePlayer;$('player-enter').onclick=()=>{$('player-message').textContent='';$('player-frame').focus();};$('player-next').onclick=()=>{if(next&&playing)play(playing.item,next);};
 refreshMe().catch(()=>{});render();
})();
