/* TV presentation only; values and image URLs are escaped by the shared helpers. */
window.TVDetail = {
  render(data, image, esc, meta, card) {
    const item=data.item, first=data.first_episode;
    const seasons=data.seasons.filter(s=>s.episodios>0);
    const count=seasons.reduce((n,s)=>n+(Number(s.episodios)||0),0);
    const genres=(item.genero||'').split(',').map(s=>s.trim()).filter(Boolean).slice(0,4);
    const playLabel=first?`Empezar T${first.season} · E${first.numero}`:'Reproducir';
    const status=data.episodic&&!first?'Los episodios de este título aún no están disponibles en este catálogo.':!data.playable?'Este título aún no tiene reproducción disponible para TV.':'';
    return `<article class="detail detail-cinema">
      <section class="cinema-hero">
        <div class="cinema-background"><img src="${image(item.backdrop_url||item.imagen_url,'w1280')}" alt=""></div>
        <div class="detail-breadcrumb" data-row="detail-back"><button data-nav id="detail-back" aria-label="Volver al catálogo">← Volver</button><span>QUÉ HAY <i>/</i> ${data.episodic?'SERIES Y EPISODIOS':'PELÍCULAS'}</span></div>
        <div class="cinema-layout">
          <div class="cinema-copy"><p class="eyebrow">UNA HISTORIA PARA TU GRAN PANTALLA</p>
            <h1>${esc(item.titulo)}</h1>${meta(item)}
            ${data.episodic&&seasons.length?`<div class="series-count">${seasons.length} ${seasons.length===1?'temporada':'temporadas'} <span>·</span> ${count} episodios</div>`:''}
            <p class="cinema-synopsis">${esc(item.sinopsis||'Descubre esta historia en Qué Hay.')}</p>
            <div class="cinema-actions" data-row="hero-actions">
              <div class="play-group"><button data-nav id="detail-play" class="circle-play" aria-label="${esc(playLabel)}" ${!data.playable?'disabled':''}><svg aria-hidden="true" viewBox="0 0 32 32"><path d="M11 6 26 16 11 26Z"/></svg></button><span class="play-label">${data.playable?esc(playLabel):'No disponible'}<small>${first?esc(first.titulo||'Episodio '+first.numero):'Disfrútala en tu pantalla'}</small></span></div>
              ${seasons.length?'<button data-nav id="detail-episodes" class="detail-secondary">☷ Episodios</button>':''}
              <button data-nav id="detail-info" class="detail-secondary">ⓘ Sinopsis</button>
            </div>
            ${status?`<p class="availability-note" role="status">${esc(status)}</p>`:''}
          </div>
          <aside class="cinema-poster" aria-label="Afiche"><img src="${image(item.imagen_url,'w500')}" alt="Afiche de ${esc(item.titulo)}"><div class="poster-foot"><span>QUÉ HAY</span><span>${esc(item.año||'CINE')}</span></div></aside>
        </div>
      </section>
      ${data.episodic?`<section class="episode-section cinema-episodes"><div class="section-heading"><div><p class="eyebrow">LA HISTORIA CONTINÚA</p><h2>Temporadas y episodios</h2></div><span>Elige tu próximo capítulo</span></div>${seasons.length?`<div class="season-tabs" data-row="seasons">${seasons.map(s=>`<button data-nav data-season="${s.id}" id="season-${s.id}" aria-pressed="false">${s.numero===0?'Especiales':'Temporada '+s.numero}<small>${s.episodios} episodios</small></button>`).join('')}</div><div id="episode-results"><p class="loading">Cargando episodios…</p></div>`:'<div class="missing-episodes"><h3>Aún no hay capítulos disponibles</h3><p>Puedes explorar otras series mientras se completa este título.</p><button data-nav id="detail-other-series">Explorar series →</button></div>'}</section>`:''}
      <section class="cinema-story" id="detail-story"><div><p class="eyebrow">DETRÁS DEL TÍTULO</p><h2>La historia</h2></div><div><p>${esc(item.sinopsis||'Sinopsis no disponible.')}</p><div class="genre-chips">${genres.map(g=>`<span>${esc(g)}</span>`).join('')}</div><button data-nav id="story-back" class="detail-secondary">↑ Volver a la ficha</button></div></section>
      ${data.related?.length?`<section class="shelves detail-related"><div class="section-heading"><h2>Más para tu próxima sesión</h2><span>Sigue explorando</span></div><div class="rail" data-row="related">${data.related.map(card).join('')}</div></section>`:''}
    </article>`;
  }
};
