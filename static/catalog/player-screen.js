/* Fullscreen belongs to our shell, never to an untrusted iframe message. */
(function(root){
 const doc=document,$=id=>doc.getElementById(id);
 let active=false,owned=false,pending=false,timer=null,previousLock=null;
 const tg=root.Telegram?.WebApp;
 const native=Boolean(tg?.initData&&tg.isVersionAtLeast?.('8.0')&&tg.requestFullscreen&&tg.exitFullscreen);
 const shell=()=>$('inline-player');
 const browserFull=()=>doc.fullscreenElement===shell();
 const full=()=>native?Boolean(tg.isFullscreen):browserFull();
 function notice(message=''){$('player-screen-status').textContent=message;$('player-screen-status').hidden=!message;}
 function waiting(value){pending=value;clearTimeout(timer);$('player-fullscreen').disabled=value;
  if(value)timer=setTimeout(()=>{waiting(false);if(!full())notice('No se pudo ampliar la pantalla. Puedes volver a intentarlo.');},6000);
 }
 function safeArea(){
  for(const side of ['top','bottom','left','right'])shell().style.setProperty('--player-safe-'+side,`${native?Math.max(0,tg.safeAreaInset?.[side]||0,tg.contentSafeAreaInset?.[side]||0):0}px`);
 }
 function sync(){
  waiting(false);
  if(!active&&owned&&full()){leave();return;}
  if(!full())owned=false;
  const expanded=active&&full();shell().classList.toggle('is-screen-full',expanded);
  const button=$('player-fullscreen');button.setAttribute('aria-pressed',String(expanded));
  button.setAttribute('aria-label',expanded?'Salir de pantalla completa':'Pantalla completa');button.title=button.getAttribute('aria-label');
  safeArea();if(expanded)notice();
 }
 function leave(){
  try{if(native){if(tg.isFullscreen)tg.exitFullscreen();}else if(browserFull())Promise.resolve(doc.exitFullscreen()).catch(()=>notice('No se pudo salir de pantalla completa.'));}catch{notice('No se pudo salir de pantalla completa.');}
 }
 function open(){
  if(!active){previousLock=native?Boolean(tg.isOrientationLocked):null;active=true;}
  if(native)try{tg.unlockOrientation();}catch{/* Device support varies. */}
  notice();sync();
 }
 async function toggle(){
  if(!active||pending)return;
  notice();
  if(full()){leave();return;}
  if(!native&&!shell().requestFullscreen){notice('La pantalla completa no está disponible en este navegador.');return;}
  owned=true;waiting(true);
  try{
   if(native){tg.unlockOrientation();tg.requestFullscreen();}
   else {await shell().requestFullscreen();sync();}
  }catch{owned=false;waiting(false);notice('No se pudo ampliar la pantalla en este dispositivo.');}
 }
 function close(){
  active=false;waiting(false);shell().classList.remove('is-screen-full');notice();
  if(owned&&full())leave();
  // Keep ownership until a late native event arrives, so it cannot reopen a closed player.
  if(native&&previousLock===true)try{tg.lockOrientation();}catch{}
  previousLock=null;
 }
 function bind(){
  $('player-fullscreen').onclick=toggle;
  doc.addEventListener('fullscreenchange',sync);
  if(native){
   tg.onEvent('fullscreenChanged',sync);
   tg.onEvent('fullscreenFailed',event=>{if(event.error==='ALREADY_FULLSCREEN'){sync();return;}owned=false;waiting(false);if(active)notice('Tu versión de Telegram no permite pantalla completa en este dispositivo.');});
   tg.onEvent('safeAreaChanged',safeArea);tg.onEvent('contentSafeAreaChanged',safeArea);
  }
 }
 if(doc.readyState==='loading')doc.addEventListener('DOMContentLoaded',bind,{once:true});else bind();
 root.PlayerScreen={open,close,expanded:()=>active&&full()};
})(window);
