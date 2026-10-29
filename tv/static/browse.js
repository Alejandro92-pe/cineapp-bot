/* Dedicated collection layouts for remote navigation, never loaded by the web app. */
window.TVBrowse = {
  render(data, state, image, esc, card) {
    const themes={
      pelicula:{name:'Películas',headline:'Esta noche, una gran historia.',copy:'Del suspenso que atrapa a la comedia que alegra el día. Encuentra tu próxima película.',tone:'cinema'},
      serie:{name:'Series',headline:'Un capítulo más. Y otro mundo.',copy:'Historias que crecen contigo. Elige un género y encuentra tu próxima serie.',tone:'series'},
      anime:{name:'Anime',headline:'Imagina otros mundos.',copy:'Grandes aventuras, personajes inolvidables y universos por descubrir.',tone:'anime'},
      biblico:{name:'Bíblicos',headline:'Historias que dejan huella.',copy:'Un espacio para la fe, la historia y la reflexión. Descubre películas y relatos por episodios.',tone:'faith'},
      search:{name:'Buscar',headline:'Encuentra tu próxima historia.',copy:'Busca una película, serie o anime por su nombre.',tone:'cinema'}
    };
    const t=themes[state.kind]||themes.search, f=data.featured;
    const compact=Boolean(state.genre||state.q||state.format||data.page>1||!state.kind);
    const rows=[];const perRow=state.kind==='biblico'?3:6;
    function faithCard(item){return `<button data-nav class="faith-card" id="title-${item.id}" data-title="${item.id}"><div class="faith-art"><img loading="lazy" src="${image(item.backdrop_url||item.imagen_url,'w780')}" alt=""><span class="faith-badge">${item.format==='series'?'Por episodios':'Película'}</span><span class="faith-open" aria-hidden="true">↗</span></div><div class="faith-caption"><h3>${esc(item.titulo)}</h3><span>${esc(item.año||'')}${item.rating?' · ★ '+esc(Number(item.rating).toFixed(1)):''}</span></div></button>`;}
    for(let i=0;i<data.items.length;i+=perRow)rows.push(`<div class="collection-row ${state.kind==='biblico'?'faith-row':''}" data-row="collection-${i}">${data.items.slice(i,i+perRow).map(state.kind==='biblico'?faithCard:card).join('')}</div>`);
    const selectedGenre=data.genres.find(g=>g.id===state.genre)?.label;
    return `<section class="collection collection-${t.tone}">
      <div class="collection-hero ${compact?'is-compact':''}">
        ${f&&!compact?`<div class="collection-art"><img src="${image(f.backdrop_url||f.imagen_url,'w1280')}" alt=""></div>`:''}
        <div class="collection-intro"><p class="eyebrow">QUÉ HAY / ${esc(t.name.toUpperCase())}</p><h1>${compact?esc(t.name):esc(t.headline)}</h1><p class="collection-description">${esc(t.copy)}</p><span class="collection-count">${data.collection_total} historias para explorar</span>
        ${f&&!compact?`<div class="collection-feature-actions" data-row="collection-hero"><button data-nav class="primary" id="collection-feature" data-title="${f.id}">Ver ficha <span aria-hidden="true">↗</span></button><button data-nav id="collection-explore">Explorar ${esc(t.name.toLowerCase())} ↓</button></div>`:''}</div>
        ${f&&!compact?`<div class="collection-feature"><span>PARA DESCUBRIR</span><h2>${esc(f.titulo)}</h2><p>${esc(f.año||'')}${f.rating?' · ★ '+esc(Number(f.rating).toFixed(1)):''}</p></div>`:''}
      </div>
      <div class="collection-body">
        <div class="collection-tools"><div><p class="eyebrow">A TU MANERA</p><h2>${state.kind==='biblico'?'Elige una historia':'¿Qué te apetece ver?'}</h2></div><form id="search-form" class="collection-search" data-row="collection-search"><input data-nav id="search-input" aria-label="${state.kind?'Buscar en '+esc(t.name.toLowerCase()):'Buscar título'}" placeholder="${state.kind?'Buscar en '+esc(t.name.toLowerCase()):'Buscar por título'}" maxlength="80" value="${esc(state.q)}"><button data-nav id="collection-search-submit" aria-label="Buscar">⌕</button></form></div>
        ${state.kind==='biblico'?`<div class="filter-row format-filters" data-row="formats" aria-label="Formato"><button data-nav id="format-all" data-format="" aria-pressed="${!state.format}">Todas las historias <small>${data.collection_total}</small></button>${data.formats.filter(x=>x.count).map(x=>`<button data-nav id="format-${x.id}" data-format="${x.id}" aria-pressed="${state.format===x.id}">${esc(x.label)} <small>${x.count}</small></button>`).join('')}</div>`:''}
        <div class="filter-row genre-filters" data-row="genres" aria-label="Géneros"><button data-nav id="genre-all" data-genre="" aria-pressed="${!state.genre}">Todos los géneros</button>${data.genres.filter(g=>!(state.kind==='anime'&&g.id==='animacion')).map(g=>`<button data-nav id="genre-${g.id}" data-genre="${g.id}" aria-pressed="${state.genre===g.id}">${esc(g.label)} <small>${g.count}</small></button>`).join('')}</div>
        <div class="collection-order"><p role="status">${data.total} ${data.total===1?'título':'títulos'}${selectedGenre?' · '+esc(selectedGenre):''}${state.q?' para «'+esc(state.q)+'»':''}</p><div data-row="sort" aria-label="Ordenar">${[['recent','Recién añadidos'],['rating','Mejor valorados'],['az','A–Z']].map(([id,label])=>`<button data-nav id="sort-${id}" data-sort="${id}" aria-pressed="${state.sort===id}">${label}</button>`).join('')}</div></div>
        <div class="collection-results">${rows.join('')}</div>
        ${!data.items.length?'<div class="collection-empty"><h3>No encontramos títulos con esta combinación.</h3><p>Prueba otro género o vuelve a explorar la colección completa.</p><button data-nav class="primary" id="collection-reset">Quitar filtros</button></div>':''}
        ${data.items.length?`<div class="pages collection-pages" data-row="collection-pages"><button data-nav id="catalog-prev" ${data.page===1?'disabled':''}>← Anteriores</button><span>Página ${data.page} de ${data.pages}</span><button data-nav id="catalog-next" ${!data.has_next?'disabled':''}>Más títulos →</button></div>`:''}
      </div>
    </section>`;
  }
};
