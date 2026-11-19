/* Admin · OK.ru players for biblical titles. Same save endpoints; faster to use. */
(function(root){
 'use strict';
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined&&text!==null)n.textContent=String(text);if(cls)n.className=cls;return n;};
 const button=(text,fn,cls)=>{const b=el('button',text,cls);b.type='button';b.onclick=fn;return b;};
 async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json().catch(()=>({}));if(!r.ok)throw Error(data.error||'No se pudo guardar.');return data;}
 // Mirrors providers/okru.py: only https://ok.ru/video/<id> or /videoembed/<id>.
 function okId(value){try{const u=new URL(String(value||'').trim());if(u.protocol!=='https:'||!['ok.ru','www.ok.ru'].includes(u.hostname))return null;const m=u.pathname.match(/^\/video(?:embed)?\/([1-9][0-9]{0,19})\/?$/);return m?m[1]:null;}catch{return null;}}
 const embed=id=>`https://ok.ru/videoembed/${id}?nochat=1`;
 function linkField(label,value){
  const wrap=el('label',null,'okx-field');wrap.append(el('span',label));
  const row=el('div',null,'okx-link-row');const input=document.createElement('input');input.type='url';input.maxLength=2048;input.placeholder='https://ok.ru/video/…';input.value=value||'';input.autocomplete='off';
  const state=el('span',null,'okx-check');row.append(input,state);wrap.append(row);
  const check=()=>{const v=input.value.trim();const id=okId(v);state.textContent=!v?'':id?'✓ Enlace válido':'✗ No es un enlace de vídeo de OK.ru';state.className='okx-check '+(!v?'':id?'ok':'bad');return id;};
  input.addEventListener('input',check);check();
  return {wrap,input,check};
 }
 function previewBox(){const box=el('div',null,'okx-preview');box.hidden=true;return {box,show(id){box.replaceChildren();if(!id){box.hidden=true;return;}const f=document.createElement('iframe');f.src=embed(id);f.title='Vista previa de OK.ru';f.allow='autoplay; fullscreen';f.setAttribute('allowfullscreen','');f.loading='lazy';f.referrerPolicy='origin';const close=button('Cerrar vista previa',()=>{box.hidden=true;box.replaceChildren();},'okx-ghost');box.append(f,close);box.hidden=false;}};}

 let mountVersion=0;
 root.OKAdmin={mount(container){
  const version=++mountVersion;let selected=null,selection=0,searchVersion=0,page=1,query='',state='';
  container.replaceChildren();container.classList.add('okru-admin');
  const header=el('header',null,'okx-header');header.append(el('p','BIBLIOTECA · REPRODUCCIÓN','okru-eyebrow'),el('h2','Reproductores OK.ru'),el('p','Elige un bíblico y pega el enlace de OK.ru del vídeo completo o de cada capítulo. Las descargas que ya tienes se conservan.'));
  const layout=el('div',null,'okru-layout'),aside=el('aside',null,'okx-aside'),editor=el('section',null,'okru-editor');
  const search=document.createElement('input');search.type='search';search.placeholder='Buscar bíblico por nombre';search.setAttribute('aria-label','Buscar bíblico');search.className='okx-search';
  const chips=el('div',null,'okx-chips');const summary=el('p',null,'okx-summary');
  [['','Todos'],['sin','Falta vídeo'],['con','Con vídeo']].forEach(([key,label])=>{const b=button(label,()=>{state=key;chips.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===b));load(1);},'okx-chip'+(key===state?' on':''));chips.append(b);});
  const list=el('div',null,'okru-titles');aside.append(search,chips,summary,list);layout.append(aside,editor);container.append(header,layout);
  editor.append(el('p','Selecciona un título de la lista para editar su reproducción.','okx-empty'));
  let timer;search.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(()=>{query=search.value.trim();load(1);},300);});

  async function load(target){
   const token=++searchVersion;list.replaceChildren(el('p','Buscando…','okx-empty'));
   try{const data=await api(`/api/admin/okru?q=${encodeURIComponent(query)}&page=${target}${state?'&estado='+state:''}`);if(version!==mountVersion||token!==searchVersion)return;page=target;list.replaceChildren();
    summary.textContent=data.total!==undefined?`${data.total} ${data.total===1?'título':'títulos'}${state==='sin'?' sin vídeo':state==='con'?' con vídeo':''}`:'';
    data.data.forEach(item=>{const b=el('button',null,'okru-title');b.type='button';b.dataset.id=item.id;b.setAttribute('aria-pressed',String(selected?.id===item.id));
      b.append(el('span',item.titulo,'okx-title-name'));const tags=el('span',null,'okx-tags');
      if(item.has_video!==undefined)tags.append(el('span',item.has_video?'▶ Con vídeo':'Falta vídeo','okx-tag '+(item.has_video?'ok':'warn')));
      if(item.disponible===false)tags.append(el('span','Oculto','okx-tag muted'));b.append(tags);b.onclick=()=>choose(item);list.append(b);});
    if(!data.data.length)list.append(el('p','No hay bíblicos con ese filtro.','okx-empty'));
    if(page>1||data.has_next){const nav=el('nav',null,'okru-pages');const prev=button('← Anterior',()=>load(page-1)),next=button('Siguiente →',()=>load(page+1));prev.disabled=page===1;next.disabled=!data.has_next;nav.append(prev,el('span',`Página ${page}`),next);list.append(nav);}
   }catch(error){if(token===searchVersion)list.replaceChildren(el('p',error.message,'okx-empty'));}
  }

  async function choose(item){
   selected=item;const token=++selection;editor.replaceChildren(el('p','Cargando enlaces…','okx-empty'));
   list.querySelectorAll('[data-id]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.id)===item.id)));
   const live=()=>version===mountVersion&&token===selection;
   try{const data=await api(`/api/admin/okru/${item.id}`);if(!live())return;editor.replaceChildren();
    const head=el('div',null,'okx-editor-head');head.append(el('h3',item.titulo));const preview=el('a','Ver ficha ↗');preview.href='/?contenido='+item.id;preview.target='_blank';preview.rel='noopener';head.append(preview);editor.append(head);
    if(window.matchMedia('(max-width:700px)').matches)editor.scrollIntoView({behavior:'smooth',block:'start'});

    // ---- Whole video
    const full=el('form',null,'okx-card'),url=linkField('Enlace del vídeo completo',data.content.playback_url||'');url.input.required=true;
    const fullPreview=previewBox();const fullActions=el('div',null,'okx-actions');const saveFull=el('button','Guardar vídeo completo','okx-primary');saveFull.type='submit';
    fullActions.append(saveFull,button('Probar enlace',()=>fullPreview.show(url.check()),'okx-ghost'));
    const fullStatus=el('p',null,'okru-status');fullStatus.setAttribute('role','status');
    full.append(el('h4','Película o vídeo único'),url.wrap,fullActions,fullStatus,fullPreview.box);editor.append(full);
    full.onsubmit=async event=>{event.preventDefault();if(!url.check()){fullStatus.textContent='Revisa el enlace: debe ser https://ok.ru/video/…';return;}saveFull.disabled=true;fullStatus.textContent='Guardando…';
     try{const saved=await api(`/api/admin/okru/${item.id}`,{scope:'title',url:url.input.value.trim()});if(live()){url.input.value=saved.url;url.check();fullStatus.textContent='✓ Vídeo guardado. Descargas conservadas.';const b=list.querySelector(`[data-id="${item.id}"] .okx-tag`);if(b){b.textContent='▶ Con vídeo';b.className='okx-tag ok';}}}
     catch(error){if(live())fullStatus.textContent=error.message;}finally{saveFull.disabled=false;}};

    // ---- Seasons and chapters
    const episodes=el('section',null,'okx-card');episodes.append(el('h4','Temporadas y capítulos'));
    const seasonBar=el('div',null,'okx-chips');const progress=el('p',null,'okx-summary');const grid=el('div',null,'okx-grid');
    let season=data.seasons.find(s=>s.numero>0)?.numero??data.seasons[0]?.numero??1;
    const seasonInput=document.createElement('input');seasonInput.type='number';seasonInput.min='0';seasonInput.max='9999';seasonInput.className='okx-season-input';seasonInput.setAttribute('aria-label','Número de temporada');seasonInput.placeholder='Nº';
    function renderSeasons(){seasonBar.replaceChildren();const numbers=[...new Set([...data.seasons.map(s=>s.numero),season])].sort((a,b)=>a-b);
     numbers.forEach(n=>seasonBar.append(button(n===0?'Especiales':`Temporada ${n}`,()=>{season=n;renderSeasons();reset();chapters();},'okx-chip'+(n===season?' on':''))));
     const add=el('span',null,'okx-add-season');add.append(seasonInput,button('+ Temporada',()=>{const n=Number(seasonInput.value);if(!Number.isInteger(n)||n<0||n>9999){seasonInput.focus();return;}season=n;seasonInput.value='';renderSeasons();reset();chapters();},'okx-ghost'));seasonBar.append(add);}
    const form=el('form',null,'okx-form');
    const numberLabel=el('label',null,'okx-field okx-number');numberLabel.append(el('span','Capítulo'));const number=document.createElement('input');number.type='number';number.min='1';number.max='99999';number.required=true;number.value='1';numberLabel.append(number);
    const titleLabel=el('label',null,'okx-field');titleLabel.append(el('span','Nombre del capítulo (opcional)'));const title=document.createElement('input');title.type='text';title.maxLength=300;titleLabel.append(title);
    const video=linkField('Enlace de OK.ru del capítulo','');video.input.required=true;
    const epPreview=previewBox();
    const actions=el('div',null,'okx-actions');const saveNext=el('button','Guardar y pasar al siguiente','okx-primary');saveNext.type='submit';const saveOnly=button('Solo guardar',()=>save(false),'okx-ghost');
    actions.append(saveNext,saveOnly,button('Probar enlace',()=>epPreview.show(video.check()),'okx-ghost'));
    const status=el('p',null,'okru-status');status.setAttribute('role','status');
    const top=el('div',null,'okx-row');top.append(numberLabel,titleLabel);form.append(top,video.wrap,actions,status,epPreview.box);
    let known=[];
    // Suggest the first chapter still missing its link; otherwise the next new number.
    function reset(){const gap=known.find(e=>!e.playback_url);number.value=String(gap?gap.numero:(known.length?Math.max(...known.map(e=>e.numero)):0)+1);title.value=gap?.titulo||'';video.input.value='';video.check();status.textContent='';epPreview.show(null);}
    function pick(ep){number.value=ep.numero;title.value=ep.titulo||'';video.input.value=ep.playback_url||'';video.check();status.textContent=`Editando el capítulo ${ep.numero}.`;grid.querySelectorAll('button').forEach(b=>b.classList.toggle('on',Number(b.dataset.n)===ep.numero));video.input.focus();}
    let chapterVersion=0;
    async function chapters(){const t=++chapterVersion;grid.replaceChildren(el('p','Cargando capítulos…','okx-empty'));progress.textContent='';
     try{known=[];let p=1,more=true;while(more&&p<=20){const d=await api(`/api/admin/okru/${item.id}?season=${encodeURIComponent(season)}&page=${p}`);if(!live()||t!==chapterVersion)return;known.push(...d.episodes);more=d.has_next;p++;}
      grid.replaceChildren();const withLink=known.filter(e=>e.playback_url).length;
      progress.textContent=known.length?`${withLink} de ${known.length} capítulos con OK.ru en ${season===0?'Especiales':'la temporada '+season}.`:'Esta temporada aún no tiene capítulos: agrega el primero abajo.';
      known.forEach(ep=>{const b=el('button',String(ep.numero),'okx-ep '+(ep.playback_url?'ok':'missing')+(ep.disponible?'':' hidden'));b.type='button';b.dataset.n=ep.numero;b.title=`${ep.numero}. ${ep.titulo||'Sin nombre'} · ${ep.playback_url?'Con OK.ru':'Sin OK.ru'}${ep.disponible?'':' · Oculto'}`;b.onclick=()=>pick(ep);grid.append(b);});
      if(!video.input.value)reset();
     }catch(error){if(live()&&t===chapterVersion)grid.replaceChildren(el('p',error.message,'okx-empty'));}}
    async function save(advance){
     if(!form.reportValidity())return;if(!video.check()){status.textContent='Revisa el enlace: debe ser https://ok.ru/video/…';return;}
     const values={scope:'episode',season,episode:Number(number.value),title:title.value,url:video.input.value.trim()};
     const controls=[...form.querySelectorAll('input,button')];controls.forEach(n=>n.disabled=true);status.textContent='Guardando…';
     try{await api(`/api/admin/okru/${item.id}`,values);if(!live())return;
      if(!data.seasons.some(s=>s.numero===season)){data.seasons.push({numero:season});renderSeasons();}
      await chapters();status.textContent=`✓ Temporada ${values.season}, capítulo ${values.episode} guardado.`;
      if(advance){const next=known.find(e=>e.numero>values.episode&&!e.playback_url)||known.find(e=>!e.playback_url);const n=next?next.numero:Math.max(values.episode,...known.map(e=>e.numero))+1;
       number.value=String(n);title.value=next?.titulo||'';video.input.value='';video.check();epPreview.show(null);video.input.focus();}
     }catch(error){if(live())status.textContent=error.message;}finally{controls.forEach(n=>n.disabled=false);}}
    form.onsubmit=event=>{event.preventDefault();save(true);};

    // ---- Paste many links at once
    const bulk=el('details',null,'okx-bulk');bulk.append(el('summary','Pegar varios enlaces a la vez'));
    const bulkText=document.createElement('textarea');bulkText.rows=6;bulkText.placeholder='Un enlace por línea, en orden.\nhttps://ok.ru/video/111\nhttps://ok.ru/video/222';bulkText.setAttribute('aria-label','Enlaces de OK.ru, uno por línea');
    const fromLabel=el('label',null,'okx-field okx-number');fromLabel.append(el('span','Empezar en el capítulo'));const from=document.createElement('input');from.type='number';from.min='1';from.value='1';fromLabel.append(from);
    const bulkStatus=el('div',null,'okx-bulk-log');const bulkGo=button('Guardar todos',async()=>{
     const lines=bulkText.value.split(/\s+/).map(s=>s.trim()).filter(Boolean);if(!lines.length){bulkText.focus();return;}
     const bad=lines.map((l,i)=>[i+1,l]).filter(([,l])=>!okId(l));if(bad.length){bulkStatus.replaceChildren(el('p',`Revisa ${bad.length===1?'la línea':'las líneas'} ${bad.map(b=>b[0]).join(', ')}: no ${bad.length===1?'es un enlace':'son enlaces'} de vídeo de OK.ru.`,'bad'));return;}
     bulkGo.disabled=true;bulkStatus.replaceChildren();let n=Number(from.value)||1;
     for(const line of lines){const row=el('p',`Capítulo ${n}: guardando…`);bulkStatus.append(row);
      try{await api(`/api/admin/okru/${item.id}`,{scope:'episode',season,episode:n,title:'',url:line});if(!live())return;row.textContent=`✓ Capítulo ${n} guardado.`;row.className='ok';}
      catch(error){row.textContent=`✗ Capítulo ${n}: ${error.message} Se detuvo aquí.`;row.className='bad';break;}n++;}
     bulkGo.disabled=false;if(!data.seasons.some(s=>s.numero===season)){data.seasons.push({numero:season});renderSeasons();}await chapters();from.value=String(n);
    },'okx-primary');
    const bulkHelp=el('p','Se guardan en la temporada elegida arriba, un capítulo por enlace. Si un capítulo ya tenía enlace, se reemplaza.','okx-summary');
    const bulkRow=el('div',null,'okx-row');bulkRow.append(fromLabel);bulk.append(bulkHelp,bulkText,bulkRow,bulkGo,bulkStatus);

    episodes.append(seasonBar,progress,grid,form,bulk);editor.append(episodes);
    const legend=el('p',null,'okx-legend');legend.append(el('span','● Con OK.ru','ok'),el('span','● Falta enlace','missing'),el('span','● Oculto','hidden'));episodes.insertBefore(legend,grid.nextSibling);
    renderSeasons();chapters();
   }catch(error){if(live())editor.replaceChildren(el('p',error.message,'okx-empty'));}
  }
  load(1);
 }};
})(window);
