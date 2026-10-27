/* Provider import panel: plain DOM, no inline provider values in HTML. */
document.addEventListener('DOMContentLoaded', () => {
  const queueStatus=document.getElementById('catalog-queue-status'),queueToggle=document.getElementById('catalog-queue-toggle');
  let queueEnabled=false;
  async function queueState(change){
    queueToggle.disabled=true;
    try{
      const response=await fetch(change===undefined?'/api/admin/catalog/queue':'/api/admin/catalog/queue/settings',change===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:change})});
      const data=await response.json();if(!response.ok)throw Error('No pudimos consultar el avance. Verifica tu sesión de administrador.');
      queueEnabled=data.enabled;queueToggle.hidden=!data.configured;queueToggle.textContent=data.enabled?'Pausar importación':'Reanudar importación';
      const q=data.queue||{};queueStatus.textContent=`${data.enabled?'Activa':data.configured?'Pausada':'Desactivada'} · ${q.done||0} títulos importados · ${q.pending||0} pendientes · ${q.failed||0} para revisar.`;
    }catch(error){queueStatus.textContent=error.message;}finally{queueToggle.disabled=false;}
  }
  document.getElementById('catalog-queue-refresh').onclick=()=>queueState();
  queueToggle.onclick=()=>queueState(!queueEnabled);
  const form = document.getElementById('vimeus-import');
  const status = document.getElementById('vimeus-status');
  const kind = document.getElementById('vimeus-kind');
  const id = document.getElementById('vimeus-id');
  const submit = document.getElementById('vimeus-submit');
  let generation=0,loadingTargets=false;
  async function types(){
    const current=++generation;loadingTargets=false;status.textContent='';id.value='';
    const biblical=kind.value.startsWith('biblico');document.getElementById('import-target-wrap').hidden=!biblical;
    document.getElementById('import-help').textContent=biblical?'TMDB trae títulos, imágenes y capítulos. Los vídeos se agregan en Reproductores · OK.ru.':kind.value==='pelicula'?'TMDB aporta la ficha de la película. La reproducción depende de su disponibilidad en Vimeus.':'Se importan todas las temporadas y capítulos que Vimeus tenga disponibles.';
    if(biblical){
      loadingTargets=true;
      const select=document.getElementById('import-target');select.replaceChildren();const empty=document.createElement('option');empty.value='';empty.textContent='Crear ficha o buscar coincidencia por TMDB';select.append(empty);
      try{for(let page=1;page<=20;page++){const r=await fetch('/api/admin/okru?page='+page);const d=await r.json();if(current!==generation)return;if(!r.ok)throw Error(d.error);for(const item of d.data){const option=document.createElement('option');option.value=item.id;option.textContent=item.titulo;select.append(option);}if(!d.has_next)break;}}
      catch(error){if(current===generation)status.textContent='No pudimos cargar tus bíblicos. Vuelve a seleccionar el tipo antes de importar.';return;}
      if(current===generation)loadingTargets=false;
    }
  }
  kind.onchange=types;
  form.onsubmit = async event => {
    event.preventDefault(); if (!form.reportValidity()) return;
    if(loadingTargets){status.textContent='Espera a que se carguen tus bíblicos antes de importar.';return;}
    submit.disabled = true; kind.disabled = true; id.disabled = true;
    status.className = 'vimeus-status'; status.textContent = 'Leyendo todas las páginas y verificando capítulos. Espera a que termine…';
    status.setAttribute('aria-busy', 'true');
    try {
      const response = await fetch('/api/admin/catalog/import', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({tmdb_id: Number(id.value), tipo: kind.value,content_id:kind.value.startsWith('biblico')?document.getElementById('import-target').value:null}) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'No se pudo completar. Puedes reintentar sin duplicar capítulos.');
      status.textContent = `${data.titulo}: ${data.temporadas ? `${data.temporadas} ${data.temporadas===1?'temporada':'temporadas'} y ${data.episodios} capítulos.` : 'Ficha de película importada.'} Descargas conservadas.`;
      if(data.metadata_only)status.append(document.createTextNode(' Los capítulos sin vídeo quedarán pendientes hasta que añadas sus enlaces en Reproductores · OK.ru.'));
      const link = document.createElement('a'); link.href = `/?contenido=${data.contenido_id}`; link.textContent = 'Ver ficha en el catálogo'; status.append(document.createElement('br'), link);
      (data.warnings || []).forEach(warning => { const p = document.createElement('p'); p.textContent = warning; status.append(p); });
    } catch (error) { status.classList.add('error'); status.textContent = error.message; }
    finally { submit.disabled = false; kind.disabled = false; id.disabled = false; status.setAttribute('aria-busy', 'false'); }
  };
});
