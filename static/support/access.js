/* Shared membership gate. The server alone decides whether access is active. */
(function(root){
 function reason(response,payload){
  if(response.status===401)return 'guest';
  if(response.status===403&&payload.code==='membership_required')return 'member';
  return null;
 }
 function show(kind){
  document.getElementById('support-dialog')?.close();document.getElementById('support-dialog')?.remove();
  const dialog=document.createElement('dialog');dialog.id='support-dialog';dialog.className='support-dialog';
  dialog.setAttribute('aria-labelledby','support-title');dialog.setAttribute('aria-describedby','support-description');
  const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
  const close=node('button','×','support-close');close.type='button';close.setAttribute('aria-label','Cerrar invitación de apoyo');close.onclick=()=>dialog.close();
  const mascot=node('picture'),still=node('source');still.media='(prefers-reduced-motion: reduce)';still.srcset='/static/support/porcon-critico-still.webp';
  const animation=node('img',null,'support-mascot');animation.src='/static/support/porcon-critico.webp';animation.alt='Porcón Crítico con ojitos tristes';animation.width=121;animation.height=220;animation.decoding='async';mascot.append(still,animation);
  const eyebrow=node('p','CONTIGO, LA FUNCIÓN CONTINÚA','support-eyebrow');
  const title=node('h2','Nos falta un protagonista: tú.');title.id='support-title';
  const description=node('p',kind==='guest'?'Crea tu cuenta gratis o inicia sesión. Para ver y descargar, necesitas un acceso activo. Tu apoyo nos ayuda a seguir compartiendo historias.':'Tu cuenta sigue aquí. Activa o renueva tu acceso y vuelve a disfrutar de las historias que te gustan. Tu apoyo nos ayuda a mantener QueHay.');description.id='support-description';
  const price=node('p','US$1.50 · 30 días · sin renovación automática','support-price');
  const support=node('a','Quiero apoyar y ver','support-primary');support.href='/membresia';
  const account=node('a',kind==='guest'?'Iniciar sesión o crear mi cuenta':'Ya apoyé · Revisar mi cuenta','support-secondary');account.href=kind==='guest'?'/cuenta?next=membership':'/cuenta';
  const later=node('button','Seguir explorando','support-later');later.type='button';later.onclick=()=>dialog.close();
  dialog.append(close,mascot,eyebrow,title,description,price,support,account,later);document.body.append(dialog);dialog.showModal();
  dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});
  dialog.addEventListener('close',()=>dialog.remove(),{once:true});
 }
 root.AccessSupport={reason,show,handle(response,payload){const kind=reason(response,payload);if(!kind)return false;show(kind);return true;}};
 if(typeof module!=='undefined')module.exports={reason};
})(typeof window==='undefined'?{}:window);
