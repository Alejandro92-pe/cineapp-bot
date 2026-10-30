/* APK-only adaptation. No credentials, native JS bridge or iframe DOM access. */
(function(root){
  class PlaybackPolicy {
    constructor(fetch){this.fetch=fetch;this.revision=0;this.key='';this.tried=new Set();this.actual='';this.url='';this.force=false;}
    reset(key=''){this.revision++;this.key=key;this.tried=new Set();this.actual='';this.url='';this.force=false;}
    async request(input,options,eligible){
      const uri=new URL(input,'https://app.quehay.live');
      const key=uri.pathname+'?episode='+(uri.searchParams.get('episodio_id')||'');
      if(key!==this.key)this.reset(key);
      const revision=++this.revision;
      const send=async(fallback)=>{
        uri.searchParams.delete('provider');if(fallback)uri.searchParams.set('provider','vimeus');
        this.tried.add(fallback?'vimeus':'videoapi');
        const response=await this.fetch(uri.pathname+uri.search,options);
        let data={};try{data=await response.clone().json();}catch{}
        if(revision===this.revision && response.ok){this.actual=data.provider||'';this.url=data.url||'';if(this.actual)this.tried.add(this.actual);}
        return {response,data};
      };
      try{
        const result=await send(eligible&&this.force);
        if(revision===this.revision && eligible && !this.tried.has('vimeus') &&
           (result.response.status>=500 || (result.response.status===404 && result.data.code==='provider_unavailable'))){
          this.force=true;return (await send(true)).response;
        }
        return result.response;
      }catch(error){
        if(revision===this.revision && eligible && !this.tried.has('vimeus')){this.force=true;return (await send(true)).response;}
        throw error;
      }
    }
    fallback(url){
      if(!url || url!==this.url || this.actual!=='videoapi' || this.tried.has('vimeus'))return false;
      this.force=true;this.tried.add('vimeus');this.url='';return true;
    }
  }
  if(typeof module!=='undefined')module.exports={PlaybackPolicy};
  if(!root.document || root.QueHayAndroidUI)return;
  const doc=root.document,$=id=>doc.getElementById(id);
  doc.documentElement.classList.add('quehay-android');
  let installed=false,current=null,policy=null,pagerPage=0,pagerSeason='',lastSelected='',pendingPage=null;
  const ui={
    share(data){
      const url=new URL(data.url);
      root.location.href='quehay-app://share?id='+encodeURIComponent(url.searchParams.get('contenido'))+'&title='+encodeURIComponent(data.title);
    },
    fullscreen(value){
      doc.documentElement.classList.toggle('android-fullscreen',value);
      $('player-fullscreen')?.setAttribute('aria-pressed',String(value));
      $('player-fullscreen')?.setAttribute('aria-label',value?'Salir de pantalla completa':'Pantalla completa');
    },
    providerFailure(url){
      const frame=$('iframeReproductor');
      if(current?.videoapi_enabled && frame && !frame.hidden && frame.src===url && policy?.fallback(url))root.InlinePlayback.start(current);
    },
    back(){
      if($('inline-player') && !$('inline-player').hidden){root.InlinePlayback.close();return true;}
      const support=doc.querySelector('.access-support [aria-label="Cerrar invitación de apoyo"]');
      if(support && support.offsetParent){support.click();return true;}
      const detail=$('modalDetalle');if(detail?.classList.contains('active')){detail.querySelector('[aria-label="Volver al catálogo"]')?.click();return true;}
      return false;
    }
  };
  root.QueHayAndroidUI=ui;
  // Also works against the current deployed web until its sharing update is released.
  if(root.QueHayShare)root.compartirContenido=()=>root.QueHayShare.share(typeof contenidoSeleccionado==='undefined'?null:contenidoSeleccionado);
  // Detail modules are loaded on demand, possibly minutes after opening Home.
  if(root.DetailAssets){
    const detailReady=root.DetailAssets.ready;
    root.DetailAssets.ready=()=>detailReady().then(value=>{install();return value;});
  }
  const observer=new MutationObserver(()=>{compactEpisodes();bindScreen();});
  function watch(){const wrap=$('detalleTemporadasWrap');if(wrap)observer.observe(wrap,{childList:true,subtree:true});}
  function compactEpisodes(){
    const wrap=$('detalleTemporadasWrap');if(!wrap)return;
    observer.disconnect();
    try{
      const rows=[...wrap.querySelectorAll('.episode-row')];
      const season=wrap.querySelector('select')?.value||'';
      const selected=root.EpisodeBrowser?.selection()?.episode?.id;
      if(season!==pagerSeason){pagerSeason=season;pagerPage=0;pendingPage=null;lastSelected='';}
      if(pendingPage!==null && rows.length>pendingPage*6){pagerPage=pendingPage;pendingPage=null;}
      if(selected!==lastSelected){
        const index=rows.findIndex(r=>r.querySelector('[aria-pressed="true"]'));
        if(index>=0)pagerPage=Math.floor(index/6);lastSelected=selected;
      }
      pagerPage=Math.min(pagerPage,Math.max(0,Math.ceil(rows.length/6)-1));
      rows.forEach((row,index)=>{row.hidden=Math.floor(index/6)!==pagerPage;});
      wrap.querySelector('.android-episode-pages')?.remove();
      const more=[...wrap.querySelectorAll('.episodes-more')].find(b=>/Ver más capítulos|Cargando…|Reintentar/.test(b.textContent));
      if(more)more.hidden=!/Reintentar/.test(more.textContent);
      if(rows.length){
        const nav=doc.createElement('nav');nav.className='android-episode-pages';nav.setAttribute('aria-label','Páginas de episodios');
        const previous=doc.createElement('button');previous.type='button';previous.textContent='‹';previous.setAttribute('aria-label','Episodios anteriores');previous.disabled=pagerPage===0;
        previous.onclick=()=>{pagerPage--;compactEpisodes();};
        const label=doc.createElement('span');label.textContent=`${pagerPage*6+1}–${Math.min(rows.length,(pagerPage+1)*6)}`;label.setAttribute('aria-live','polite');
        const next=doc.createElement('button');next.type='button';next.textContent='›';next.setAttribute('aria-label','Episodios siguientes');
        next.disabled=(pagerPage+1)*6>=rows.length && (!more||more.disabled||/Reintentar/.test(more.textContent));
        next.onclick=()=>{if((pagerPage+1)*6<rows.length){pagerPage++;compactEpisodes();}else if(more){pendingPage=pagerPage+1;more.click();}};
        nav.append(previous,label,next);wrap.append(nav);
      }
    }finally{watch();}
  }
  function bindScreen(){
    const button=$('player-fullscreen');if(!button)return;
    button.hidden=false;button.onclick=()=>{root.location.href='quehay-app://fullscreen';};
    if(!$('android-player-retry')){
      const retry=doc.createElement('button');retry.id='android-player-retry';retry.type='button';retry.textContent='↻';retry.title='Reintentar reproducción';retry.setAttribute('aria-label','Reintentar reproducción');
      retry.onclick=()=>{if(!current)return;if(!policy.fallback(policy.url))policy.reset();root.InlinePlayback.start(current);};
      button.parentElement.prepend(retry);
    }
  }
  function install(){
    if(installed||!root.InlinePlayback||!root.EpisodeBrowser)return false;
    installed=true;
    const fetch=root.fetch.bind(root);policy=new PlaybackPolicy(fetch);
    root.fetch=(input,options={})=>{
      if(typeof input!=='string')return fetch(input,options);
      const url=new URL(input,root.location.href);
      if(url.origin!==root.location.origin || !/^\/api\/playback\/[1-9][0-9]*$/.test(url.pathname))return fetch(input,options);
      return policy.request(url.href,options,Boolean(current?.videoapi_enabled));
    };
    const start=root.InlinePlayback.start,close=root.InlinePlayback.close;
    root.InlinePlayback.start=async item=>{current=item;const result=await start(item);bindScreen();return result;};
    root.InlinePlayback.close=()=>{policy.reset();current=null;ui.fullscreen(false);return close();};
    $('player-close').onclick=root.InlinePlayback.close;
    $('player-retry').onclick=()=>{if(!current)return;policy.fallback(policy.url);root.InlinePlayback.start(current);};
    const mount=root.EpisodeBrowser.mount;
    root.EpisodeBrowser.mount=async item=>{pagerSeason='';pagerPage=0;return mount(item);};
    watch();compactEpisodes();bindScreen();
    return true;
  }
  let attempts=0;
  function ready(){if(!install() && ++attempts<80)setTimeout(ready,250);}
  ready();
})(typeof window==='undefined'?{}:window);
