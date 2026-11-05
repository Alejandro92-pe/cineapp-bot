/* Shared web/landing measurement. No account data, forms, URLs or search text. */
(function (root) {
  'use strict';
  if (root.QueHayAnalytics) return;
  const ID='G-NQWW6WCBR2', KEY='qh_analytics_v1';
  const live=location.protocol==='https:' && ['quehay.live','www.quehay.live','app.quehay.live'].includes(location.hostname);
  const preview=location.protocol==='http:' && ['127.0.0.1','localhost'].includes(location.hostname) && location.pathname.endsWith('/consent-preview.html') && new URLSearchParams(location.search).get('qhAnalyticsPreview')==='1';
  const allowed=preview || (live && ['/', '/membresia', '/cuenta', '/instalar'].includes(location.pathname));
  let enabled=false, loaded=false, banner, lastView='', filterTimer;
  const surface=()=>/QueHayAndroid\//.test(navigator.userAgent)?'android':root.Telegram?.WebApp?.initData?'telegram':root.matchMedia?.('(display-mode: standalone)').matches?'pwa':'web';
  const section=location.hostname==='app.quehay.live'?'app':'landing';
  const page=location.origin+location.pathname;
  const referrer=(()=>{try{return new URL(document.referrer).origin+'/';}catch{return '';}})();
  const fields={
    catalog_view:['screen_name'], view_content:['content_id','content_name','content_type'],
    catalog_filter:['content_type','has_query','result_count'], open_catalog:['placement'],
    membership_click:['placement'], install_click:['placement','app_kind'],
    download_apk:['app_kind'], select_payment_method:['payment_method'],
    begin_checkout:['payment_method','value','currency'], checkout_redirect:['payment_method'],
    payment_submitted:['payment_method'], playback_open:['content_id','content_type']
  };
  function choice(){return document.cookie.split('; ').find(v=>v.startsWith(KEY+'='))?.split('=')[1]||'';}
  function event(name, data={}) {
    if(preview || !enabled || !fields[name])return;
    const clean={site_section:section,client_surface:surface(),page_location:page,page_referrer:referrer};
    for(const key of fields[name]){
      const value=data[key];
      if(typeof value==='number' && Number.isFinite(value))clean[key]=value;
      else if(typeof value==='boolean')clean[key]=value;
      else if(typeof value==='string' && value.length<=120 && !/[@\r\n]|https?:|<|>/.test(value))clean[key]=value;
    }
    root.gtag('event',name,clean);
  }
  function start(){
    if(preview)return;
    if(!allowed || enabled || navigator.globalPrivacyControl===true)return;
    enabled=true;root['ga-disable-'+ID]=false;
    if(!loaded){
      loaded=true;root.dataLayer=root.dataLayer||[];
      root.gtag=function(){root.dataLayer.push(arguments);};
      root.gtag('consent','default',{analytics_storage:'granted',ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied'});
      root.gtag('js',new Date());
      root.gtag('config',ID,{send_page_view:false,allow_google_signals:false,allow_ad_personalization_signals:false,
        cookie_domain:'quehay.live',page_location:page,page_referrer:referrer});
      const script=document.createElement('script');script.async=true;
      script.src='https://www.googletagmanager.com/gtag/js?id='+ID;document.head.append(script);
    }else root.gtag('consent','update',{analytics_storage:'granted'});
    root.gtag('event','page_view',{page_location:page,page_referrer:referrer,page_title:document.title,site_section:section,client_surface:surface()});
    if(lastView)event('catalog_view',{screen_name:lastView});
  }
  function choose(value){
    if(!preview)document.cookie=KEY+'='+value+'; Path=/; Domain=quehay.live; Max-Age=15552000; SameSite=Lax; Secure';
    banner?.remove();banner=null;
    if(value==='yes')start();
    else{
      enabled=false;root['ga-disable-'+ID]=true;
      if(loaded)root.gtag('consent','update',{analytics_storage:'denied'});
      for(const entry of document.cookie.split('; ')){
        const name=entry.split('=')[0];if(!/^_ga(?:_|$)/.test(name))continue;
        for(const domain of ['', '; Domain=quehay.live','; Domain='+location.hostname])document.cookie=name+'=; Max-Age=0; Path=/'+domain;
      }
    }
  }
  function preferences(){
    if(banner || !allowed)return;
    banner=document.createElement('section');banner.className='qh-measure-choice';banner.setAttribute('aria-label','Preferencias de cookies');
    const render=customizing=>{
      banner.replaceChildren();
      const title=document.createElement('strong');title.textContent=customizing?'Personalizar cookies':'Preferencias de cookies';
      const text=document.createElement('p');
      if(customizing){
        text.textContent='Elige si permites las estadísticas de Google Analytics. Puedes cambiar esta opción cuando quieras desde el pie de página.';
      }else{
        text.append(document.createTextNode('Este sitio utiliza cookies para ayudar a mejorar su experiencia de usuario. Obtenga más información sobre cómo usamos las cookies en nuestro '));
        const policy=document.createElement('a');policy.href='https://quehay.live/politicas-de-privacidad/';policy.textContent='Aviso sobre cookies';policy.rel='noopener noreferrer';
        text.append(policy,document.createTextNode('.'));
      }
      banner.append(title,text);
      const actions=document.createElement('div');
      if(customizing){
        const label=document.createElement('label');label.className='qh-measure-toggle';
        const checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.checked=choice()==='yes';
        label.append(checkbox,document.createTextNode('Permitir estadísticas de visitas y uso de botones'));
        banner.append(label);
        const save=document.createElement('button');save.type='button';save.textContent='Guardar preferencias';save.onclick=()=>choose(checkbox.checked?'yes':'no');actions.append(save);
        const back=document.createElement('button');back.type='button';back.textContent='Volver';back.onclick=()=>render(false);actions.append(back);
      }else{
        for(const [label,value] of [['OK','yes'],['Personalizar Cookies',null]]){
          const button=document.createElement('button');button.type='button';button.textContent=label;
          button.onclick=value?()=>choose(value):()=>render(true);actions.append(button);
        }
      }
      banner.append(actions);
    };
    render(false);document.body.append(banner);
  }  function view(name){
    if(!['inicio','explorar','buscar','guardados'].includes(name) || lastView===name)return;
    lastView=name;event('catalog_view',{screen_name:name});
  }
  function filter(data){clearTimeout(filterTimer);filterTimer=setTimeout(()=>event('catalog_filter',data),800);}
  root.QueHayAnalytics={event,view,filter,preferences};
  function init(){
    if(!allowed)return;
    const link=document.createElement('button');link.type='button';link.className='qh-measure-settings';link.textContent='Estadísticas';link.setAttribute('aria-label','Personalizar cookies y estadísticas');link.onclick=preferences;
    function installSettingsLink(){
      const footer=section==='app'
        ? (document.querySelector('.cine-page-footer') || (location.pathname!=='/' ? document.querySelector('footer:not(.qh-measure-footer)') : null))
        : (document.querySelector('footer.footer') || document.querySelector('footer:not(.qh-measure-footer)'));
      if(!footer)return false;
      if(footer.contains(link))return true;
      if(section==='app'){
        const membership=[...footer.querySelectorAll('a')].find(a=>a.textContent.trim().toLowerCase()==='descubre la membresía')
          || footer.querySelector('a[href="/membresia"]');
        if(membership)footer.insertBefore(link,membership);else footer.append(link);
      }else{
        const nav=footer.querySelector('nav[aria-label="Información"]');
        (nav||footer).append(link);
      }
      return true;
    }
    if(!installSettingsLink() && document.body){
      const observer=new MutationObserver(records=>{
        const hasFooter=records.some(record=>[...record.addedNodes].some(node=>
          node.nodeType===1 && (node.matches?.('.cine-page-footer') || node.querySelector?.('.cine-page-footer'))
        ));
        if(hasFooter)installSettingsLink();
      });
      observer.observe(document.body,{childList:true,subtree:true});
    }
    if(navigator.globalPrivacyControl===true)return;
    if(choice()==='yes')start();else if(choice()!=='no')preferences();
    document.addEventListener('click',e=>{
      const a=e.target.closest?.('a[href]');if(!a)return;
      let url;try{url=new URL(a.href,location.href);}catch{return;}
      if(url.protocol!=='https:' || !['app.quehay.live','quehay.live'].includes(url.hostname))return;
      const placement=a.closest('header')?'header':a.closest('footer')?'footer':a.closest('.hero')?'hero':'content';
      if(a.id==='apk-android'||a.id==='apk-tv')event('download_apk',{app_kind:a.id==='apk-tv'?'tv':'android'});
      else if(url.pathname==='/membresia')event('membership_click',{placement});
      else if(url.pathname==='/instalar')event('install_click',{placement,app_kind:['#android','#tv','#navegador'].includes(url.hash)?url.hash.slice(1):'all'});
      else if(section==='landing'&&url.hostname==='app.quehay.live'&&url.pathname==='/')event('open_catalog',{placement});
    },true);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})(window);
