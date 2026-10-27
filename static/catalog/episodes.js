/* Season/episode UI, isolated from the legacy catalogue. */
(function (root) {
  class EpisodeController {
    constructor(load, render) { this.load = load; this.render = render; this.version = 0; this.state = {}; }
    reset() { this.version++; this.state = { seasons: [], episodes: [], selected: null }; this.render(this.state); }
    async mount(item) {
      this.reset();
      if (!['serie', 'anime', 'biblico'].includes(item.tipo)) return;
      const version = this.version;
      this.state = { ...this.state, item, loading: true }; this.render(this.state);
      try {
        const result = await this.load(`/api/temporadas/${item.id}`);
        if (version !== this.version) return;
        this.state.seasons = result.temporadas || [];
        const first = this.state.seasons.find(s=>s.numero===item.start_season) || this.state.seasons.find(s=>s.id===item.last_season) || this.state.seasons.find(s => s.numero > 0 && s.episodios > 0) || this.state.seasons[0];
        if (first) {
          await this.season(first.id);
          const resumeVersion=this.version;
          while(item.last_episode && this.state.item===item && !this.state.episodes.some(e=>e.id===item.last_episode) && this.state.has_next && !this.state.error){await this.more();if(this.version!==resumeVersion)return;}
          if(this.state.item===item && this.state.episodes.some(e=>e.id===item.last_episode))this.select(item.last_episode);
          return;
        }
        this.state.loading = false; this.render(this.state);
      } catch (error) { if (version === this.version) this.fail(error); }
    }
    async season(id) {
      const season = this.state.seasons.find(s => s.id === Number(id));
      if (!season) return;
      const version = ++this.version;
      this.state = { ...this.state, season, selected: null, episodes: [], loading: true, fetching: false, error: '', page: 0, has_next: false };
      this.render(this.state);
      await this.more(version);
    }
    async more(version = this.version) {
      if (!this.state.season || this.state.fetching) return;
      this.state.fetching = true; this.render(this.state);
      try {
        const result = await this.load(`/api/episodios/${this.state.item.id}/${this.state.season.id}?page=${(this.state.page || 0)+1}`);
        if (version !== this.version) return;
        this.state = { ...this.state, episodes: [...this.state.episodes, ...result.episodios], page: result.page,
          has_next: result.has_next, total: result.total, fetching: false, loading: false, error: '' };
        this.state.selected ||= this.state.episodes[0] || null;
        this.render(this.state);
      } catch (error) { if (version === this.version) this.fail(error); }
    }
    select(id) { this.state.selected = this.state.episodes.find(e => e.id === Number(id)) || null; this.render(this.state); }
    hasNext() {
      const s=this.state,index=s.episodes?.findIndex(e=>e.id===s.selected?.id);
      return index>=0 && (index<s.episodes.length-1 || s.has_next || s.seasons.slice(s.seasons.findIndex(x=>x.id===s.season?.id)+1).some(x=>x.episodios>0));
    }
    async next() {
      if(this.state.loading||this.state.fetching)return null;
      const selected=this.state.selected?.id, seasonId=this.state.season?.id;
      let index=this.state.episodes.findIndex(e=>e.id===selected);
      if(index<0)return null;
      if(index===this.state.episodes.length-1 && this.state.has_next){await this.more();if(this.state.error)throw Error(this.state.error);if(this.state.season?.id!==seasonId)return null;}
      const next=this.state.episodes[index+1];
      if(next){this.select(next.id);return next;}
      const seasonIndex=this.state.seasons.findIndex(s=>s.id===seasonId);
      const upcoming=this.state.seasons.slice(seasonIndex+1).find(s=>s.episodios>0);
      if(upcoming){await this.season(upcoming.id);if(this.state.error)throw Error(this.state.error);return this.state.selected;}
      return null;
    }
    fail(error) { this.state = { ...this.state, error: error.message, loading: false, fetching: false }; this.render(this.state); }
  }
  if (typeof module !== 'undefined') module.exports = { EpisodeController };
  if (!root.document) return;
  function actionButton(label,path){
    const button=document.createElement('button');button.type='button';button.title=label;button.setAttribute('aria-label',label);
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');
    const shape=document.createElementNS('http://www.w3.org/2000/svg','path');shape.setAttribute('d',path);svg.append(shape);button.append(svg);return button;
  }
  const fetchData = async url => {
    const response = await fetch(url); const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'No se pudieron cargar los capítulos.');
    return data;
  };
  const controller = new EpisodeController(fetchData, state => {
    const wrap = document.getElementById('detalleTemporadasWrap');
    const play = document.getElementById('btnVerAhora');
    if (!wrap || !play) return;
    wrap.replaceChildren(); wrap.style.display = state.item && !(state.item.tipo==='biblico'&&!state.loading&&!state.seasons.length) ? 'block' : 'none';
    play.disabled = Boolean(state.item && (state.loading || state.selected?.has_playback===false || (!state.selected && !['vimeus','okru'].includes(state.item.fuente))));
    const download=document.getElementById('btnDescargar');if(download&&state.item?.tipo==='biblico')download.style.display=state.seasons.length?'none':state.item.has_download?'inline-flex':'none';
    play.setAttribute('aria-label',state.selected ? `Reproducir temporada ${state.season.numero}, episodio ${state.selected.numero}` : 'Reproducir');
    play.querySelector('.action-label').textContent='Reproducir';
    if (!state.item) return;
    const top = document.createElement('div'); top.className = 'episodes-toolbar';
    const heading = document.createElement('h2'); heading.textContent = 'Episodios'; top.append(heading);
    if (state.seasons.length) {
      const label = document.createElement('label'); label.textContent = 'Temporada';
      const select = document.createElement('select'); select.setAttribute('aria-label', 'Seleccionar temporada');
      state.seasons.forEach(s => { const option = document.createElement('option'); option.value = s.id;
        option.textContent = `${s.numero===0?'Especiales':'Temporada '+s.numero} · ${s.episodios || 0} cap.`; select.append(option); });
      if (state.season) select.value = state.season.id;
      select.onchange = () => controller.season(select.value); label.append(select); top.append(label);
    }
    wrap.append(top);
    const status = document.createElement('p'); status.className = 'episodes-status'; status.setAttribute('role', 'status');
    status.textContent = state.error || (state.loading ? 'Cargando capítulos…' : state.episodes.length ?
      `${state.total} episodios` : 'Los episodios de este título aún no están disponibles.');
    wrap.append(status);
    const grid = document.createElement('div'); grid.className = 'episodes-grid';
    state.episodes.forEach(ep => {
      const row = document.createElement('article');row.className='episode-row';
      const button = document.createElement('button'); button.type = 'button'; button.className = 'episode-card';
      button.setAttribute('aria-label',`Reproducir episodio ${ep.numero}: ${ep.titulo}`);
      button.title=ep.has_playback===false?'Vídeo pendiente':ep.sinopsis||ep.titulo;button.disabled=ep.has_playback===false;
      button.setAttribute('aria-pressed', String(state.selected?.id === ep.id)); button.onclick = () => {controller.select(ep.id);root.InlinePlayback.start(state.item);};
      const number = document.createElement('span'); number.className = 'episode-number'; number.textContent = String(ep.numero).padStart(2, '0');
      const thumb=document.createElement('span');thumb.className='episode-thumb';
      const image=document.createElement('img');image.src=safeImageSrc(ep.imagen_url||state.item.imagen_url);image.alt='';image.loading='lazy';image.onerror=()=>{image.onerror=null;image.src='/static/placeholder.svg';};thumb.append(image,number);
      const info = document.createElement('span'); info.className = 'episode-info';
      const title = document.createElement('strong'); title.textContent = ep.titulo; info.append(title);
      const small = document.createElement('span'); small.textContent = ep.has_playback===false ? 'Vídeo pendiente' : ep.duracion ? `${ep.duracion} min` : `Temporada ${state.season.numero}`; info.append(small);
      if (ep.sinopsis) { const synopsis = document.createElement('span'); synopsis.className = 'episode-synopsis'; synopsis.textContent = ep.sinopsis; info.append(synopsis); }
      const icon = document.createElement('span'); icon.textContent = state.selected?.id === ep.id ? '✓' : '▷'; icon.setAttribute('aria-hidden', 'true');
      button.append(thumb, info, icon); row.append(button);
      const actions=document.createElement('div');actions.className='episode-actions';
      if(ep.has_download){const download=actionButton(`Descargar episodio ${ep.numero}`,'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5');download.onclick=()=>root.EpisodeDownloads.download(state.item.id,ep.id);actions.append(download);}
      if(root.AccountSession?.state.is_admin){const edit=actionButton(`Editar descarga del episodio ${ep.numero}`,'m14 5 5 5M4 20l4-1L20 7a2 2 0 0 0-4-4L4 15z');edit.onclick=()=>root.EpisodeDownloads.edit(state.item.id,ep,()=>controller.render(controller.state));actions.append(edit);}
      if(actions.children.length)row.append(actions);grid.append(row);
    });
    wrap.append(grid);
    if (state.has_next || state.error) {
      const more = document.createElement('button'); more.type = 'button'; more.className = 'episodes-more'; more.disabled = state.fetching;
      more.textContent = state.fetching ? 'Cargando…' : state.error ? 'Reintentar' : 'Ver más capítulos';
      more.onclick = () => state.season ? controller.more() : controller.mount(state.item); wrap.append(more);
    }
  });
  root.EpisodeBrowser = { mount: item => controller.mount(item), reset: () => controller.reset(),next:()=>controller.next(),hasNext:()=>controller.hasNext(),
    selection: () => ({ episode: controller.state.selected, season: controller.state.season }) };
})(typeof window === 'undefined' ? {} : window);
