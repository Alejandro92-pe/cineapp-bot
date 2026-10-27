/* Download URLs are released only by an authenticated server route. */
(function(root){
 async function download(contentId,episodeId){try{const r=await fetch(`/api/episode-download/${contentId}/${episodeId}`);const data=await r.json();if(root.AccessSupport.handle(r,data))return;if(!r.ok)throw Error(data.error||'Descarga no disponible.');mostrarEnlaceExterno(data.url);}catch(error){alert(error.message);}}
 async function edit(contentId,episode,onSave){
  const dialog=document.createElement('dialog');dialog.className='episode-download-editor';
  const title=document.createElement('h2');title.textContent=`Descarga · Episodio ${episode.numero}`;
  const form=document.createElement('form');const label=document.createElement('label');label.textContent='Enlace de este episodio';
  const input=document.createElement('input');input.type='url';input.placeholder='https://www.mediafire.com/…';input.maxLength=4096;label.append(input);
  const hint=document.createElement('p');hint.textContent='Tu enlace tiene prioridad. Déjalo vacío para usar la descarga del catálogo, si existe.';
  const status=document.createElement('p');status.setAttribute('role','status');
  const save=document.createElement('button');save.type='submit';save.textContent='Guardar enlace';save.disabled=true;
  const cancel=document.createElement('button');cancel.type='button';cancel.textContent='Cancelar';cancel.onclick=()=>dialog.close();
  form.append(label,hint,save,cancel,status);dialog.append(title,form);dialog.onclose=()=>dialog.remove();document.body.append(dialog);dialog.showModal();
  const endpoint=`/api/admin/episode-download/${contentId}/${episode.id}`;
  try{const r=await fetch(endpoint);const data=await r.json();if(!r.ok)throw Error(data.error);input.value=data.url||'';save.disabled=false;}catch(error){status.textContent=error.message;}
  form.onsubmit=async event=>{event.preventDefault();save.disabled=true;try{const r=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:input.value})});const data=await r.json();if(!r.ok)throw Error(data.error);episode.has_download=data.has_download;onSave();dialog.close();}catch(error){status.textContent=error.message;}finally{save.disabled=false;}};
 }
 root.EpisodeDownloads={download,edit};
})(window);
