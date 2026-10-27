/* Progressive enhancement: an install button appears only after a real browser
 * offer. Registration never caches a login, a payment or an access decision. */
(function(){
  const $=id=>document.getElementById(id);
  let offer=null,installed=false,accepted=false,registration=null,reloadForUpdate=false;
  const standalone=window.matchMedia('(display-mode: standalone)');
  const inTelegram=()=>!!window.Telegram?.WebApp?.initData;
  const local=['127.0.0.1','localhost','[::1]'].includes(location.hostname);
  function render(){
    const button=$('install-button'),status=$('install-status');if(!status)return;
    const running=standalone.matches||navigator.standalone===true;
    button.hidden=!offer||running||installed||inTelegram();
    $('install-local-help').hidden=!local;
    $('install-guide').hidden=running||installed;
    status.textContent=running?'Estás usando QueHay como aplicación.':installed?'El navegador confirmó la instalación. Busca QueHay en tu dispositivo.':accepted?'Solicitud aceptada. Espera la confirmación de tu dispositivo.':inTelegram()?'Abre esta página en Chrome para instalarla en Android.':!window.isSecureContext?'Abre QueHay mediante su dirección HTTPS para instalarla.':offer?'Tu navegador ofrece instalar QueHay. Pulsa el botón para continuar.':'Si no aparece un botón, revisa el menú de tu navegador y sigue los pasos de abajo.';
  }
  window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();offer=event;accepted=false;render();});
  window.addEventListener('appinstalled',()=>{installed=true;offer=null;render();});
  standalone.addEventListener?.('change',render);
  function updateNotice(){
    if(!registration?.waiting||document.getElementById('pwa-update'))return;
    const notice=document.createElement('aside');notice.id='pwa-update';notice.setAttribute('aria-label','Actualización disponible');
    const text=document.createElement('p');text.textContent='Hay una actualización de QueHay. Actualiza cuando termines lo que estás haciendo.';
    const update=document.createElement('button');update.textContent='Actualizar ahora';update.type='button';
    update.onclick=()=>{if(registration.waiting){reloadForUpdate=true;update.disabled=true;registration.waiting.postMessage({type:'ACTIVATE_UPDATE'});}};
    const dismiss=document.createElement('button');dismiss.textContent='Más tarde';dismiss.type='button';dismiss.onclick=()=>notice.remove();
    notice.append(text,update,dismiss);document.body.append(notice);
  }
  async function start(){
    render();
    if($('install-copy'))$('install-copy').onclick=async()=>{try{await navigator.clipboard.writeText(location.origin+'/instalar');$('install-copy').textContent='Dirección copiada';}catch{$('install-status').textContent='Copia la dirección desde la barra de tu navegador.';}};
    if($('install-button'))$('install-button').onclick=async()=>{
      if(!offer)return;const event=offer;offer=null;$('install-button').disabled=true;
      try{await event.prompt();const choice=await event.userChoice;accepted=choice.outcome==='accepted';render();if(!accepted)$('install-status').textContent='Puedes instalarla más adelante desde el menú del navegador.';}
      catch{render();$('install-status').textContent='No se pudo abrir la instalación. Prueba desde el menú de Chrome.';}
      finally{$('install-button').disabled=false;}
    };
    if(!window.isSecureContext||!('serviceWorker' in navigator)){if($('install-runtime'))$('install-runtime').textContent='Puedes seguir usando QueHay desde el navegador.';return;}
    try{
      registration=await navigator.serviceWorker.register('/sw.js',{scope:'/',updateViaCache:'none'});
      await navigator.serviceWorker.ready;
      if($('install-runtime'))$('install-runtime').textContent='Tu catálogo, a un toque desde la pantalla de inicio.';
      updateNotice();registration.addEventListener('updatefound',()=>{const worker=registration.installing;worker?.addEventListener('statechange',()=>{if(worker.state==='installed'&&navigator.serviceWorker.controller)updateNotice();});});
      navigator.serviceWorker.addEventListener('controllerchange',()=>{if(reloadForUpdate){reloadForUpdate=false;location.reload();}});
    }catch{if($('install-runtime'))$('install-runtime').textContent='No pudimos preparar la pantalla sin conexión. Puedes seguir usando el catálogo y volver a intentarlo.';}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
