(() => {
  let registering = false;
  const $ = id => document.getElementById(id);
  const feedback = (message, success=false) => { $('feedback').textContent=message; $('feedback').classList.toggle('success',success); };
  let membershipRevision=0;
  const date=value=>new Date(value).toLocaleString('es-PE',{dateStyle:'medium',timeStyle:'short'});
  async function membership(){
    const revision=++membershipRevision;
    $('membership-state').textContent='Comprobando membresía…';$('membership-expiry').textContent='';$('membership-orders').replaceChildren();
    try{
      const response=await fetch('/api/payments/mine');const info=await response.json();
      if(revision!==membershipRevision || !AccountSession.state.authenticated)return;
      if(!response.ok)throw new Error(info.error||'No pudimos consultar tu membresía.');
      const badge=$('membership-badge');badge.textContent=info.permanent?'Propietario':info.active?'Activo':info.expires_at?'Vencido':'Sin activar';badge.dataset.state=info.active?'active':'inactive';
      const pending=info.orders.filter(o=>['pending_review','pending_provider'].includes(o.status));
      $('orders-count').textContent=String(info.orders.length);$('membership-pending').hidden=info.permanent||!pending.length;
      $('membership-pending').textContent=pending.length?'Tienes '+pending.length+' '+(pending.length===1?'pago pendiente de confirmación.':'pagos pendientes de confirmación.')+' Revisa Mis compras antes de volver a pagar.':'';
      $('membership-state').textContent=info.permanent?'Acceso permanente':info.active?'Membresía activa':info.expires_at?'Tu acceso venció':'Aún no tienes membresía';
      $('membership-expiry').textContent=info.permanent?'Sin vencimiento ni pagos. Este acceso es exclusivo de tu cuenta de propietario.':info.expires_at?(info.active?'Disponible hasta ':'Venció el ')+date(info.expires_at):'Elige cómo apoyar y recibe 30 días de acceso.';
      $('membership-action').hidden=info.permanent;
      $('membership-terms').hidden=info.permanent;
      $('membership-action').textContent=info.active?'Añadir otros 30 días':'Conocer y comprar membresía';
      const statuses={draft:'Falta registrar tu pago',pending_provider:'Esperando confirmación de Buy Me a Coffee',pending_review:'En revisión manual',approved:'Acceso activado',rejected:'No aprobado'};
      const methods={bmc:'Buy Me a Coffee',yape_plin:'Yape / Plin',binance:'Binance Pay'};
      for(const order of info.orders){const row=document.createElement('div');row.className='profile-order';const heading=document.createElement('strong');heading.textContent=`${methods[order.method]||order.method} · ${order.currency} ${(order.amount_minor/100).toFixed(2)}`;const detail=document.createElement('p');detail.textContent=`${statuses[order.status]||order.status} · ${order.code}`;row.append(heading,detail);if(order.reason){const reason=document.createElement('p');reason.textContent=order.reason;row.append(reason);}$('membership-orders').append(row);}
      if(!info.orders.length)$('membership-orders').textContent='Todavía no tienes compras registradas.';
    }catch(error){if(revision===membershipRevision){$('membership-state').textContent=error.message;$('membership-badge').textContent='Sin conexión';$('membership-badge').dataset.state='unknown';}}
  }
  async function post(path, body) {
    const response = await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'No se pudo completar la solicitud.');
    return payload;
  }
  function render() {
    const state = AccountSession.state;
    $('account-loading').hidden=true;
    document.body.classList.toggle('account-authenticated',state.authenticated);
    $('forms').hidden=state.authenticated; $('signed-in').hidden=!state.authenticated;
    if (state.authenticated) {
      ProfileAvatars.picker($('profile-choices'),$('profile-avatar'));membership();
      const savedCount=AccountLibrary.saved().length;
      $('saved-count').textContent=`${savedCount} ${savedCount===1?'título guardado':'títulos guardados'} en tu cuenta`;
      $('welcome').textContent = `Hola, ${state.user.name}.`;
      $('identity').textContent = state.user.email || 'Cuenta vinculada con Telegram';
      $('telegram-status').textContent = state.user.telegram_id ? 'ID '+state.user.telegram_id+' · Verificado' : 'Sin vincular';
      $('link-telegram').hidden=!!state.user.telegram_id;
      $('role').textContent=state.is_admin?'Administrador':'Usuario';
      $('admin-link').hidden=!state.is_admin;
    }
  }
  function mode(register) {
    registering=register; $('name-field').hidden=!register; $('name').required=register;
    $('password-help').hidden=!register; $('password').minLength=register?12:1;
    $('password').autocomplete=register?'new-password':'current-password';
    $('tab-login').classList.toggle('selected',!register);$('tab-register').classList.toggle('selected',register);
    $('tab-login').setAttribute('aria-pressed',String(!register));$('tab-register').setAttribute('aria-pressed',String(register));
    $('form-title').textContent=register?'Tu próxima historia.':'Qué bueno verte.';
    $('form-description').textContent=register?'Crea tu cuenta para empezar.':'Inicia sesión para continuar.';
    $('submit').textContent=register?'Crear mi cuenta →':'Entrar a mi cuenta →'; feedback('');
  }
  $('tab-login').onclick=()=>mode(false);$('tab-register').onclick=()=>mode(true);
  $('show-password').onclick=()=>{const show=$('password').type==='password';$('password').type=show?'text':'password';$('show-password').textContent=show?'Ocultar':'Ver';$('show-password').setAttribute('aria-label',show?'Ocultar contraseña':'Mostrar contraseña');};
  $('account-form').onsubmit=async event=>{
    event.preventDefault();$('submit').disabled=true;feedback('');
    try{await post('/api/auth/'+(registering?'register':'login'),{name:$('name').value,email:$('email').value,password:$('password').value});$('password').value='';render();feedback(registering?'Tu cuenta está lista.':'Sesión iniciada.',true);if(new URLSearchParams(location.search).get('next')==='membership')location.href='/membresia';}
    catch(error){feedback(error.message);}finally{$('submit').disabled=false;}
  };
  $('logout').onclick=async()=>{try{await post('/api/auth/logout',{});render();feedback('Sesión cerrada.',true);}catch(error){feedback(error.message);}};
  $('refresh-membership').onclick=membership;
  window.addEventListener('focus',()=>{if(AccountSession.state.authenticated)membership();});
  async function link(){try{await AccountSession.telegram();render();feedback('Telegram verificado.',true);if(new URLSearchParams(location.search).get('next')==='membership')location.href='/membresia';}catch(error){feedback(error.message);}}
  $('telegram-login').onclick=link;$('link-telegram').onclick=link;
  $('password-form').onsubmit=async event=>{event.preventDefault();try{await post('/api/auth/password',Object.fromEntries(new FormData(event.target)));event.target.reset();feedback('Contraseña actualizada. Las otras sesiones se cerraron.',true);}catch(error){feedback(error.message);}};
  function updateProfile(){
    if(!AccountSession.state.authenticated)return;
    const count=AccountLibrary.saved().length;
    $('saved-count').textContent=`${count} ${count===1?'título guardado':'títulos guardados'} en tu cuenta`;
    const selected=ProfileAvatars.selected();
    if($('profile-avatar').dataset.selection!==selected){ProfileAvatars.picker($('profile-choices'),$('profile-avatar'));$('profile-avatar').dataset.selection=selected;}
  }
  window.addEventListener('profile-changed',updateProfile);
  window.addEventListener('session-changed',()=>{render();ProfileSync.refresh().then(updateProfile);});
  window.addEventListener('profile-status',()=>{$('profile-sync-status').textContent=ProfileSync.message;});
  ProfileSync.ready.then(()=>{
    render();
    const verified=AccountSession.state.user?.telegram_id;
    const opened=window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
    if(verified&&opened&&String(verified)!==String(opened))feedback('Esta sesión pertenece a otra cuenta de Telegram. Cierra sesión aquí y vuelve a abrir QueHay desde la cuenta que quieres usar.');
    else if(AccountSession.state.error)feedback(AccountSession.state.error);
  });
})();
