/* Progressive enhancement: an install button appears only after a real browser
 * offer. Registration never caches a login, a payment or an access decision. */
(function(){
  const $=id=>document.getElementById(id);
  let offer=null,installed=false,accepted=false;
  const standalone=window.matchMedia('(display-mode: standalone)');
  const inTelegram=()=>!!window.Telegram?.WebApp?.initData;
  const local=['127.0.0.1','localhost','[::1]'].includes(location.hostname);
  function render(){
    const button=$('install-button'),status=$('install-status');if(!status)return;
    const running=standalone.matches||navigator.standalone===true;
    button.hidden=!offer||running||installed||inTelegram();
    $('install-local-help').hidden=!local;
    $('install-guide').hidden=running||installed;
    const apple=/iPhone|iPad|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
    status.textContent=running?'Ya estás usando Qué Hay desde tu pantalla de inicio.':installed?'El navegador confirmó la instalación. Busca Qué Hay en tu dispositivo.':accepted?'Solicitud aceptada. Espera la confirmación de tu dispositivo.':inTelegram()?'Abre esta página en un navegador externo: Chrome en Android o Safari en iPhone.':!window.isSecureContext?'Abre Qué Hay mediante su dirección HTTPS para instalarla.':offer?'Tu navegador permite añadir Qué Hay. Pulsa el botón para continuar.':apple?'En Safari, abre Compartir y elige «Añadir a pantalla de inicio».':'Busca la opción de instalar en el menú de tu navegador. También puedes seguir usando la web.';
  }
  window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();offer=event;accepted=false;render();});
  window.addEventListener('appinstalled',()=>{installed=true;offer=null;render();});
  standalone.addEventListener?.('change',render);
  async function start(){
    render();
    if($('install-copy'))$('install-copy').onclick=async()=>{try{await navigator.clipboard.writeText(location.origin+'/instalar#navegador');$('install-copy').textContent='Dirección copiada';}catch{$('install-status').textContent='Copia la dirección desde la barra de tu navegador.';}};
    if($('install-button'))$('install-button').onclick=async()=>{
      if(!offer)return;const event=offer;offer=null;$('install-button').disabled=true;
      try{await event.prompt();const choice=await event.userChoice;accepted=choice.outcome==='accepted';render();if(!accepted)$('install-status').textContent='Puedes instalarla más adelante desde el menú del navegador.';}
      catch{render();$('install-status').textContent='No se pudo abrir la instalación. Prueba desde el menú de Chrome.';}
      finally{$('install-button').disabled=false;}
    };
    if(!window.isSecureContext||!('serviceWorker' in navigator)){if($('install-runtime'))$('install-runtime').textContent='Puedes seguir usando QueHay desde el navegador.';return;}
    try{
      await navigator.serviceWorker.register('/sw.js',{scope:'/',updateViaCache:'none'});
      await navigator.serviceWorker.ready;
      if($('install-runtime'))$('install-runtime').textContent='Tu catálogo, a un toque desde la pantalla de inicio.';
      // Let the browser activate waiting workers after old clients close.
      // No prompt, skipWaiting or reload while someone may be watching.
    }catch{if($('install-runtime'))$('install-runtime').textContent='No pudimos preparar la pantalla sin conexión. Puedes seguir usando el catálogo y volver a intentarlo.';}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
