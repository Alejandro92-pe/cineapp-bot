/* One hero renderer for provisional and ready TV details. */
window.TVDetail = (()=>{
  function hero(item,episodic,image,esc,meta,{pending=false,count=0,seasons=[],actions='',status=''}={}){
    const genres=(item.genero||'').split(',').map(s=>s.trim()).filter(Boolean).slice(0,4);
    return `<section class="cinema-hero">
      <div class="cinema-background"><img src="${image(item.backdrop_url||item.imagen_url,'w1280')}" alt=""></div>
      <div class="detail-breadcrumb" data-row="detail-back"><button data-nav id="detail-back" aria-label="Volver al catálogo">← Volver</button><span>QUÉ HAY <i>/</i> ${episodic?'SERIES Y EPISODIOS':item.tipo==='biblico'&&item.format!=='movies'?'BÍBLICOS':'PELÍCULAS'}</span></div>
      <div class="cinema-layout"><div class="cinema-copy"><p class="eyebrow">UNA HISTORIA PARA TU GRAN PANTALLA</p>
        <h1>${esc(item.titulo)}</h1>${meta(item,false)}
        <div class="genre-chips">${genres.map(g=>`<span>${esc(g)}</span>`).join('')}</div>
        ${episodic&&seasons.length?`<div class="series-count">${seasons.length} ${seasons.length===1?'temporada':'temporadas'} <span>·</span> ${count} episodios</div>`:''}
        ${window.TVSynopsis.markup(item.sinopsis||'Descubre esta historia en Qué Hay.',esc,{id:'detail-synopsis',title:item.titulo,pending})}
        ${pending?'<p role="status">Cargando opciones de reproducción…</p>':actions}
        ${status?`<p class="availability-note" role="status">${esc(status)}</p>`:''}
      </div>${episodic?'':`<aside class="cinema-poster" aria-label="Afiche"><img src="${image(item.imagen_url,'w500')}" alt="Afiche de ${esc(item.titulo)}"><div class="poster-foot"><span>QUÉ HAY</span><span>${esc(item.año||'CINE')}</span></div></aside>`}</div>
    </section>`;
  }
  function article(item,episodic,body,image,pending=false){
    return `<article class="detail detail-cinema ${pending?'detail-pending ':''}${episodic?'detail-series':'detail-movie'}"${pending?' aria-busy="true"':''}>
      ${episodic?`<div class="series-atmosphere"><img src="${image(item.backdrop_url||item.imagen_url,'w1280')}" alt=""></div>`:''}${body}</article>`;
  }
  return {
    pending(item,image,esc,meta){
      const episodic=['serie','anime'].includes(item.tipo)||item.format==='series'||item.tmdb_media==='tv';
      return article(item,episodic,hero(item,episodic,image,esc,meta,{pending:true}),image,true);
    },
    render(data,image,esc,meta,card){
      const item=data.item,first=data.first_episode;
      const seasons=data.seasons.filter(s=>s.has_episodes??(s.episodios>0));
      const count=seasons.reduce((n,s)=>n+(Number(s.episodios)||0),0);
      const playLabel=first?`Empezar T${first.season} · E${first.numero}`:'Reproducir';
      const status=data.episodic&&!first?'Los episodios de este título aún no están disponibles en este catálogo.':!data.playable?'Este título aún no tiene reproducción disponible para TV.':'';
      const actions=`<div class="cinema-actions" data-row="hero-actions">
        <div class="play-group"><button data-nav id="detail-play" class="circle-play" aria-label="${esc(playLabel)}" ${!data.playable?'disabled':''}><svg aria-hidden="true" viewBox="0 0 32 32"><path d="M11 6 26 16 11 26Z"/></svg></button><span class="play-label">${data.playable?esc(playLabel):'No disponible'}<small>${first?esc(first.titulo||'Episodio '+first.numero):'Disfrútala en tu pantalla'}</small></span></div>
        <button data-nav id="detail-save" class="detail-secondary save-title" aria-pressed="${Boolean(data.saved)}" aria-label="${data.saved?'Quitar de Mi lista':'Añadir a Mi lista'}"><span aria-hidden="true">${data.saved?'✓':'＋'}</span> Mi lista</button>
      </div>`;
      const body=hero(item,data.episodic,image,esc,meta,{count,seasons,actions,status})+`
      ${data.episodic?`<section class="episode-section cinema-episodes"><div class="series-section-tabs" data-row="series-sections"><button data-nav id="series-tab-episodes" aria-pressed="true">Episodios</button><button data-nav id="series-tab-related">También te puede gustar</button></div>${seasons.length?`<div class="season-tabs" data-row="seasons">${seasons.map(s=>`<button data-nav data-season="${s.id}" id="season-${s.id}" aria-pressed="false">${s.numero===0?'Especiales':'Temporada '+s.numero}</button>`).join('')}</div><div id="episode-results"><p class="loading">Cargando episodios…</p></div>`:'<div class="missing-episodes"><h3>Aún no hay capítulos disponibles</h3><p>Puedes explorar otras series mientras se completa este título.</p><button data-nav id="detail-other-series">Explorar series →</button></div>'}</section>`:''}
      ${data.related?.length?`<section class="shelves detail-related" id="detail-related"><div class="section-heading"><h2>Más para tu próxima sesión</h2><span>Sigue explorando</span></div><div class="rail" data-row="related">${data.related.map(card).join('')}</div></section>`:''}
`;
      return article(item,data.episodic,body,image);
    }
  };
})();
