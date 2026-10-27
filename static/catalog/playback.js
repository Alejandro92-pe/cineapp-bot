/* The provider iframe stays inside the title detail. No guessed progress events. */
(function(root){
 let revision=0,current=null,nextBusy=false;
 const $=id=>document.getElementById(id);
 function close(){++revision;current=null;const frame=$('iframeReproductor');frame.onload=null;frame.removeAttribute('src');$('inline-player').hidden=true;$('modalDetalle').classList.remove('has-player');}
 async function start(item){
  const token=++revision;current=item;
  $('inline-player').hidden=true;$('modalDetalle').classList.remove('has-player');
  $('player-title').textContent=item.titulo;
  $('player-status').textContent='Preparando el reproductor…';
  $('player-status').hidden=false;
  $('iframeReproductor').removeAttribute('src');$('iframeReproductor').hidden=true;
  $('player-next').hidden=!['serie','anime'].includes(item.tipo);$('player-retry').hidden=true;
  $('player-next').disabled=true;$('player-download').hidden=true;
  try{
   const selection=EpisodeBrowser.selection();
   $('player-next').hidden=!selection.episode;
   const query=selection.episode?'?episodio_id='+selection.episode.id:'';
   const response=await fetch(`/api/playback/${item.id}${query}`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});const payload=await response.json();
   if(token!==revision)return;
   if(root.AccessSupport.handle(response,payload)){current=null;return;}
   if(!response.ok)throw Error(payload.error||'No pudimos autorizar la reproducción.');
   if(!payload.embed)throw Error('Este título todavía no tiene reproducción integrada. Sus enlaces de descarga se conservan.');
   const url=new URL(payload.url);const okru=url.origin==='https://ok.ru'&&/^\/videoembed\/[1-9][0-9]{0,19}$/.test(url.pathname);
   if(!okru&&!['https://vimeus.com','https://www.vimeus.com'].includes(url.origin))throw Error('Reproductor no permitido.');
   if(url.username||url.password)throw Error('Reproductor no permitido.');
   $('inline-player').hidden=false;$('modalDetalle').classList.add('has-player');
   $('inline-player').scrollIntoView({block:'start',behavior:'smooth'});
   const frame=$('iframeReproductor');
   frame.onload=()=>{if(token===revision){$('player-status').textContent='';$('player-status').hidden=true;}};
   frame.hidden=false;frame.src=url.href;
   $('player-next').disabled=selection.episode ? !EpisodeBrowser.hasNext() : true;
   $('player-next').textContent=selection.episode && !EpisodeBrowser.hasNext()?'Último episodio':'Siguiente episodio →';
   $('player-download').hidden=!selection.episode?.has_download;
   $('player-download').onclick=()=>selection.episode&&EpisodeDownloads.download(item.id,selection.episode.id);
   $('player-retry').hidden=true;
   $('player-title').textContent=item.titulo+(selection.episode?` · T${selection.season.numero} E${selection.episode.numero}`:'');
   AccountLibrary.opened(item,selection);
  }catch(error){if(token!==revision)return;$('inline-player').hidden=false;$('modalDetalle').classList.add('has-player');$('player-status').textContent=error.message;$('player-retry').hidden=false;$('player-next').hidden=true;}
 }
 async function next(){const item=current,token=revision;if(!item||nextBusy)return;nextBusy=true;const button=$('player-next');button.disabled=true;try{const selected=await EpisodeBrowser.next();if(current!==item||revision!==token)return;if(selected)await start(item);else{$('player-status').textContent='Llegaste al último episodio disponible.';$('player-status').hidden=false;}}catch(error){if(revision===token){$('player-status').textContent=error.message;$('player-status').hidden=false;button.disabled=false;}}finally{nextBusy=false;}}
 document.addEventListener('DOMContentLoaded',()=>{
  $('player-close').onclick=close;$('player-retry').onclick=()=>current&&start(current);$('player-next').onclick=next;
 });
 root.InlinePlayback={start,close};
})(window);
