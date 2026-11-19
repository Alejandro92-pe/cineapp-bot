/* The provider iframe stays inside the title detail. No guessed progress events. */
(function(root){
 let revision=0,current=null,nextBusy=false,provider='videoapi',manualProvider=false;
 const $=id=>document.getElementById(id);
 // Skin to try on this device: ?skin=netflix in the address remembers it; ?skin=default clears it.
 const SKINS=['netflix','disney','prime','cinematic','vidzilla'];
 function playerSkin(){let value=null;try{const asked=new URLSearchParams(location.search).get('skin');if(asked!==null){value=asked.toLowerCase();if(SKINS.includes(value))localStorage.setItem('qh-player-skin',value);else localStorage.removeItem('qh-player-skin');}return localStorage.getItem('qh-player-skin');}catch{return SKINS.includes(value)?value:null;}}
 // A provider that is down or lacks the title gets our own notice, never its broken page.
 const UNAVAILABLE=new Set(['provider_down','provider_unavailable']);
 const tried=new Set();
 let notice=null;
 function clearNotice(){if(notice){notice.remove();notice=null;}}
 function unavailable(item,error){
  $('player-status').textContent='';$('player-status').hidden=true;$('player-retry').hidden=true;$('player-next').hidden=true;
  const frame=$('iframeReproductor');frame.removeAttribute('src');frame.hidden=true;
  clearNotice();
  if(!document.getElementById('player-unavailable-style')){const css=document.createElement('style');css.id='player-unavailable-style';css.textContent='.player-unavailable{display:grid;justify-items:center;gap:12px;text-align:center;padding:48px 24px;margin:0;aspect-ratio:16/9;align-content:center;background:radial-gradient(ellipse at 50% 40%,#13233a,#03070d 70%);color:#edf3fc}.player-unavailable svg{width:46px;height:46px;color:#e8c581}.player-unavailable h3{margin:0;font-size:clamp(18px,3vw,24px)}.player-unavailable p{margin:0!important;max-width:460px;color:#9daec5!important;font-size:14px!important;line-height:1.6}.player-unavailable-actions{display:flex;flex-wrap:wrap;justify-content:center;gap:10px;margin-top:6px}.player-unavailable-actions button{min-height:44px;padding:10px 18px;border-radius:10px;border:1px solid #3c526e;background:#16263a;color:#edf3fc;font:inherit;font-size:14px;cursor:pointer}.player-unavailable-actions button.primary{background:#e8c581;border-color:#e8c581;color:#1a1408;font-weight:700}@media(max-width:600px){.player-unavailable{aspect-ratio:auto;min-height:260px;padding:36px 18px}}';document.head.append(css);}
  const box=document.createElement('div');box.id='player-unavailable';box.className='player-unavailable';box.setAttribute('role','status');
  box.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="5" width="20" height="14" rx="3"/><path d="m9 9 6 6m0-6-6 6"/></svg>';
  const title=document.createElement('h3');title.textContent='Este título no está disponible por ahora';
  const text=document.createElement('p');text.textContent=error.code==='provider_down'?'El servidor de vídeo no responde en este momento. Estamos trabajando para recuperarlo; vuelve a intentarlo más tarde.':error.message;
  const actions=document.createElement('div');actions.className='player-unavailable-actions';
  const add=(label,fn,primary)=>{const b=document.createElement('button');b.type='button';b.textContent=label;if(primary)b.className='primary';b.onclick=fn;actions.append(b);};
  const other=error.provider==='vimeus'?'videoapi':'vimeus';
  tried.add(error.provider);
  if(item.videoapi_enabled&&!tried.has(other))add('Probar el otro servidor',()=>{provider=other;manualProvider=true;return start(item);},true);
  const download=document.getElementById('btnDescargar');
  if(download&&download.style.display!=='none'&&!['serie','anime'].includes(item.tipo))add('Descargar',()=>download.click(),!item.videoapi_enabled);
  add('Volver a la ficha',close);
  box.append(title,text,actions);frame.before(box);notice=box;
 }
 function close(){clearNotice();++revision;current=null;root.PlayerScreen?.close();const frame=$('iframeReproductor');frame.onload=null;frame.removeAttribute('src');$('inline-player').hidden=true;$('modalDetalle').classList.remove('has-player');}
 async function start(item){
  if(current?.id!==item.id){provider='videoapi';manualProvider=false;tried.clear();}
  const token=++revision;current=item;
  $('player-provider-label').hidden=!item.videoapi_enabled;
  $('player-provider').value=provider;
  const expanded=Boolean(root.PlayerScreen?.expanded());
  $('inline-player').hidden=!expanded;if(!expanded)$('modalDetalle').classList.remove('has-player');
  $('player-title').textContent=item.titulo;
  $('player-status').textContent='Preparando el reproductor…';
  $('player-status').hidden=false;
  $('iframeReproductor').removeAttribute('src');$('iframeReproductor').hidden=true;clearNotice();
  $('player-next').hidden=!['serie','anime'].includes(item.tipo);$('player-retry').hidden=true;
  $('player-next').disabled=true;$('player-download').hidden=true;
  try{
   const selection=EpisodeBrowser.selection();
   $('player-next').hidden=!selection.episode;
   const params=new URLSearchParams();
   if(selection.episode)params.set('episodio_id',selection.episode.id);
   if(item.videoapi_enabled&&manualProvider)params.set('provider',provider);
   const skin=playerSkin();if(skin)params.set('skin',skin);
   const query=params.toString()?'?'+params.toString():'';
   const response=await fetch(`/api/playback/${item.id}${query}`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});const payload=await response.json();
   if(token!==revision)return;
   if(root.AccessSupport.handle(response,payload)){close();return;}
   if(!response.ok){const failure=Error(payload.error||'No pudimos autorizar la reproducción.');failure.code=payload.code;failure.provider=payload.provider||(item.videoapi_enabled?provider:'vimeus');throw failure;}
   if(!payload.embed)throw Error('Este título todavía no tiene reproducción integrada. Sus enlaces de descarga se conservan.');
   const url=new URL(payload.url);const okru=url.origin==='https://ok.ru'&&/^\/videoembed\/[1-9][0-9]{0,19}$/.test(url.pathname);
   const videoapi=item.videoapi_enabled&&provider==='videoapi'&&payload.provider==='videoapi'&&url.origin==='https://videoapi.la'&&/^\/e\/(movie\/[1-9][0-9]*|(tv|anime)\/[1-9][0-9]*\/[0-9]+\/[1-9][0-9]*)$/.test(url.pathname)&&[...url.searchParams].every(([key,value])=>(['primary_color','secondary_color','icon_color'].includes(key)&&/^[0-9a-f]{6}$/i.test(value))||(key==='skin'&&SKINS.includes(value)))&&!url.hash;
   if(!okru&&!videoapi&&!['https://vimeus.com','https://www.vimeus.com'].includes(url.origin))throw Error('Reproductor no permitido.');
   if(url.username||url.password)throw Error('Reproductor no permitido.');
   if(item.videoapi_enabled)$('player-provider').value=videoapi?'videoapi':'vimeus';
   $('inline-player').hidden=false;$('modalDetalle').classList.add('has-player');
   root.PlayerScreen?.open();
   $('inline-player').scrollIntoView({block:'start',behavior:'smooth'});
   const frame=$('iframeReproductor');
   frame.onload=()=>{if(token===revision){$('player-status').textContent='';$('player-status').hidden=true;}};
   frame.hidden=false;frame.src=url.href;
   $('player-next').disabled=selection.episode ? !EpisodeBrowser.hasNext() : true;
   $('player-next-label').textContent=selection.episode && !EpisodeBrowser.hasNext()?'Último episodio':'Siguiente episodio';
   $('player-download').hidden=!selection.episode?.has_download;
   $('player-download').onclick=()=>selection.episode&&EpisodeDownloads.download(item.id,selection.episode.id);
   $('player-retry').hidden=true;
   $('player-title').textContent=item.titulo+(selection.episode?` · T${selection.season.numero} E${selection.episode.numero}`:'');
   AccountLibrary.opened(item,selection);
   root.QueHayAnalytics?.event('playback_open',{content_id:String(item.id),content_type:item.tipo});
  }catch(error){if(token!==revision)return;$('inline-player').hidden=false;$('modalDetalle').classList.add('has-player');if(UNAVAILABLE.has(error.code)){unavailable(item,error);return;}$('player-status').textContent=error.message;$('player-retry').hidden=false;$('player-next').hidden=true;}
 }
 async function next(){const item=current,token=revision;if(!item||nextBusy)return;nextBusy=true;const button=$('player-next');button.disabled=true;try{const selected=await EpisodeBrowser.next();if(current!==item||revision!==token)return;if(selected)await start(item);else{$('player-status').textContent='Llegaste al último episodio disponible.';$('player-status').hidden=false;}}catch(error){if(revision===token){$('player-status').textContent=error.message;$('player-status').hidden=false;button.disabled=false;}}finally{nextBusy=false;}}
 function bindControls(){
  $('player-close').onclick=close;$('player-retry').onclick=()=>current&&start(current);$('player-next').onclick=next;
  $('player-provider').onchange=event=>{provider=event.target.value;manualProvider=true;if(current)start(current);};
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bindControls,{once:true});
 else bindControls();
 root.InlinePlayback={start,close};
})(window);
