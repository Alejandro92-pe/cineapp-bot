/* Header presentation only; authorization stays on the server. */
(function(root){
  function model(session,active){
    const signedIn=Boolean(session?.authenticated && session.user);
    const fullName=String(session?.user?.name||'').trim();
    const name=fullName.split(/\s+/)[0]||'Qué gusto verte';
    return {signedIn,label:signedIn?(fullName?`Hola, ${name}`:name):'Mi cuenta',
      badge:signedIn?(active?'Acceso activo':'Mi cuenta'):'Iniciar sesión',
      showAccess:!signedIn||!active,accessLabel:signedIn?'Activar acceso':'Acceso mensual'};
  }
  function render(){
    const doc=root.document,session=root.AccountSession?.state;
    const active=Boolean(typeof membresiaActiva!=='undefined' && membresiaActiva);
    const value=model(session,active),chip=doc?.getElementById('userChip');
    if(!chip)return;
    chip.classList.toggle('is-signed-in',value.signedIn);
    const name=doc.getElementById('ucName'),badge=doc.getElementById('ucBadge');
    if(name){name.textContent=value.label;name.title=value.label;}
    if(badge){badge.textContent=value.badge;badge.className='uc-badge'+(value.signedIn&&active?' vip':'');}
    const link=doc.querySelector('.cine-header .cine-membership-link');
    if(link){link.hidden=!value.showAccess;link.textContent=value.accessLabel;}
  }
  if(typeof module!=='undefined')module.exports={model};
  if(!root.document || root.QueHayIdentity)return;
  root.QueHayIdentity={render};
  const original=root.inicializarUserChip;
  if(original)root.inicializarUserChip=function(){original();render();};
  root.AccountSession?.ready.then(render);
  root.addEventListener('session-changed',render);
  render();
})(typeof window==='undefined'?{}:window);
