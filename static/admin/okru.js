(function(root){
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
 const button=(text,fn)=>{const b=el('button',text);b.type='button';b.onclick=fn;return b;};
 async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.error||'No se pudo guardar.');return data;}
 function field(label,type,value=''){const l=el('label',label),i=el('input');i.type=type;i.value=value;l.append(i);return {label:l,input:i};}
 let mountVersion=0;
 root.OKAdmin={mount(container){
  const version=++mountVersion;let selected=null,selection=0,searchVersion=0,page=1,query='';
  container.replaceChildren();container.classList.add('okru-admin');
  const header=el('header');header.append(el('p','BIBLIOTECA · REPRODUCCIÓN','okru-eyebrow'),el('h2','Tus bíblicos, dentro de QueHay.'),el('p','Pega un enlace de OK.ru para el vídeo completo o para cada capítulo. Las descargas que ya tienes se conservan.'));
  const layout=el('div',null,'okru-layout'),aside=el('aside'),editor=el('section',null,'okru-editor');
  const search=el('form',null,'okru-search'),q=field('Buscar un bíblico','search');q.input.placeholder='Nombre de la película o serie';
  const searchButton=el('button','Buscar');searchButton.type='submit';search.append(q.label,searchButton);
  const list=el('div',null,'okru-titles');aside.append(search,list);layout.append(aside,editor);container.append(header,layout);
  editor.append(el('p','Selecciona un título para editar su reproducción.'));
  search.onsubmit=e=>{e.preventDefault();query=q.input.value.trim();load(1);};
  async function load(target){
   const token=++searchVersion;list.textContent='Buscando…';
   try{const data=await api(`/api/admin/okru?q=${encodeURIComponent(query)}&page=${target}`);if(version!==mountVersion||token!==searchVersion)return;page=target;list.replaceChildren();
    data.data.forEach(item=>{const b=button(item.titulo,()=>choose(item));b.className='okru-title';b.setAttribute('aria-pressed',String(selected?.id===item.id));b.dataset.id=item.id;list.append(b);});
    if(!data.data.length)list.append(el('p','No encontramos bíblicos con ese nombre.'));
    const nav=el('nav',null,'okru-pages');const prev=button('Anterior',()=>load(page-1)),next=button('Siguiente',()=>load(page+1));prev.disabled=page===1;next.disabled=!data.has_next;nav.append(prev,el('span',`Página ${page}`),next);list.append(nav);
   }catch(error){if(token===searchVersion)list.textContent=error.message;}
  }
  async function choose(item){
   selected=item;const token=++selection;editor.textContent='Cargando enlaces…';
   list.querySelectorAll('[data-id]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.id)===item.id)));
   const live=()=>version===mountVersion&&token===selection;
   try{const data=await api(`/api/admin/okru/${item.id}`);if(!live())return;editor.replaceChildren();editor.append(el('h3',item.titulo));
    const preview=el('a','Ver ficha ↗');preview.href='/?contenido='+item.id;preview.target='_blank';preview.rel='noopener';editor.append(preview);
    const full=el('form',null,'okru-form'),url=field('Enlace del vídeo completo','url',data.content.playback_url||'');url.input.required=true;url.input.maxLength=2048;url.input.placeholder='https://ok.ru/video/…';
    const saveFull=el('button','Guardar vídeo completo');saveFull.type='submit';const fullStatus=el('p',null,'okru-status');fullStatus.setAttribute('role','status');
    full.append(el('h4','Película o vídeo único'),url.label,saveFull,fullStatus);editor.append(full);
    full.onsubmit=async event=>{event.preventDefault();saveFull.disabled=true;try{const saved=await api(`/api/admin/okru/${item.id}`,{scope:'title',url:url.input.value});if(live()){url.input.value=saved.url;fullStatus.textContent='Vídeo guardado. Descargas conservadas.';}}catch(error){if(live())fullStatus.textContent=error.message;}finally{saveFull.disabled=false;}};
    const episodes=el('section',null,'okru-episodes');episodes.append(el('h4','Temporadas y capítulos'),el('p','El número identifica cada capítulo. Guardar el mismo número actualiza su enlace; si es nuevo, crea el capítulo y su temporada.'));
    const form=el('form',null,'okru-form'),season=field('Temporada','number',data.seasons.find(s=>s.numero>0)?.numero??1),number=field('Capítulo','number','1'),title=field('Nombre del capítulo (opcional)','text'),video=field('Enlace de OK.ru del capítulo','url');
    season.input.min='0';season.input.max='9999';number.input.min='1';number.input.max='99999';season.input.required=number.input.required=video.input.required=true;title.input.maxLength=300;video.input.maxLength=2048;video.input.placeholder='https://ok.ru/video/…';
    const pair=el('div',null,'okru-numbers');pair.append(season.label,number.label);const saveEpisode=el('button','Guardar capítulo');saveEpisode.type='submit';const status=el('p',null,'okru-status');status.setAttribute('role','status');
    form.append(pair,title.label,video.label,saveEpisode,status);const existing=el('div',null,'okru-chapters');episodes.append(form,el('h4','Capítulos guardados'),existing);editor.append(episodes);
    let chapterVersion=0;
    async function chapters(page=1){const t=++chapterVersion;existing.textContent='Cargando capítulos…';try{const d=await api(`/api/admin/okru/${item.id}?season=${encodeURIComponent(season.input.value)}&page=${page}`);if(!live()||t!==chapterVersion)return;existing.replaceChildren();
      if(!d.episodes.length)existing.append(el('p','Esta temporada aún no tiene capítulos. Puedes agregar el primero arriba.'));
      d.episodes.forEach(ep=>{const b=button(`${ep.numero}. ${ep.titulo} · ${ep.playback_url?'Con OK.ru':'Sin OK.ru'}${ep.disponible?'':' · Oculto'}`,()=>{number.input.value=ep.numero;title.input.value=ep.titulo;video.input.value=ep.playback_url||'';status.textContent=`Editando capítulo ${ep.numero}.`;video.input.focus();});existing.append(b);});
      const nav=el('nav',null,'okru-pages');const prev=button('Capítulos anteriores',()=>chapters(page-1)),next=button('Más capítulos',()=>chapters(page+1));prev.disabled=page===1;next.disabled=!d.has_next;nav.append(prev,next);existing.append(nav);
    }catch(error){if(live()&&t===chapterVersion)existing.textContent=error.message;}}
    season.input.onchange=()=>{number.input.value='1';title.input.value='';video.input.value='';status.textContent='';chapters();};
    const choices=el('div',null,'okru-season-shortcuts');data.seasons.forEach(s=>choices.append(button(s.numero===0?'Especiales':`Temporada ${s.numero}`,()=>{season.input.value=s.numero;season.input.onchange();})));episodes.insertBefore(choices,form);
    form.onsubmit=async event=>{event.preventDefault();const values={scope:'episode',season:Number(season.input.value),episode:Number(number.input.value),title:title.input.value,url:video.input.value};const controls=[...form.querySelectorAll('input,button')];controls.forEach(n=>n.disabled=true);status.textContent='Guardando…';try{const result=await api(`/api/admin/okru/${item.id}`,values);if(live()){video.input.value=result.url;status.textContent=`Temporada ${values.season}, capítulo ${values.episode}: guardado. Descargas conservadas.`;await chapters();}}catch(error){if(live())status.textContent=error.message;}finally{controls.forEach(n=>n.disabled=false);}};
    chapters();
   }catch(error){if(live())editor.textContent=error.message;}
  }
  load(1);
 }};
})(window);
