(function () {
  const $ = id => document.getElementById(id);
  let configuration, currentOrders = [], permanentAccess = false;
  const labels = {draft:'Falta registrar tu pago',pending_provider:'Esperando confirmación de Buy Me a Coffee',pending_review:'En revisión manual',approved:'Acceso activado',rejected:'No aprobado'};
  function amount(method) { return (method.currency === 'PEN' ? 'S/' : method.currency === 'USD' ? 'US$' : '') + (method.amount_minor/100).toFixed(2) + (method.currency === 'USDT' ? ' USDT' : ''); }
  async function api(path, body) {
    const response = await fetch(path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const result = await response.json(); if (!response.ok) throw new Error(result.error || 'No se pudo completar. Intenta otra vez.'); return result;
  }
  const node = (tag, text, cls) => { const element = document.createElement(tag); if(text)element.textContent=text; if(cls)element.className=cls;return element; };
  const icons = {
    bmc:'<path d="M5 8h12v7a5 5 0 0 1-5 5h-2a5 5 0 0 1-5-5V8Zm12 1h2a3 3 0 0 1 0 6h-2M8 3v2m4-2v2M3 22h17"/>',
    yape_plin:'<rect x="6" y="2" width="12" height="20" rx="3"/><path d="M10 5h4m-4 14h4m-5-9h6v5H9z"/>',
    binance:'<path d="m12 2 4 4-4 4-4-4 4-4Zm0 12 4 4-4 4-4-4 4-4ZM2 12l4-4 4 4-4 4-4-4Zm12 0 4-4 4 4-4 4-4-4Z"/>'
  };
  function methods() {
    const container = $('payment-methods'); container.replaceChildren();
    configuration.methods.forEach(method => {
      const card = node('article',null,'method-card'+(method.id === 'bmc'?' recommended':''));
      card.append(node('span',method.id === 'bmc'?'RECOMENDADO · CONFIRMACIÓN AUTOMÁTICA':'CONFIRMACIÓN MANUAL','method-label'));
      const heading = node('div',null,'method-heading'); const icon=node('span',null,'method-icon'); icon.setAttribute('aria-hidden','true');
      icon.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'+icons[method.id]+'</svg>';
      heading.append(icon,node('h3',method.label));card.append(heading,node('div',amount(method),'method-price'));
      card.append(node('p',method.id === 'bmc'?'Compra el acceso como un pago único. Al confirmar el pago, se activa en tu cuenta.':method.id === 'yape_plin'?'Escanea el QR con Yape o Plin y registra tu operación. Revisaremos el ingreso para activar tu acceso.':'Usa Binance Pay con USDT y registra el ID de la operación. Activamos el acceso después de revisar el ingreso.','method-desc'));
      const button=node('button',!method.available?'Pendiente de habilitar':method.id === 'bmc'?'Continuar con Buy Me a Coffee':'Pagar con '+method.label);button.type='button';button.disabled=!method.available;
      button.onclick=()=>start(method,button);card.append(button);container.append(card);
    });
    $('guest-note').hidden=AccountSession.state.authenticated;
  }
  async function start(method, button, existing=null) {
    if(!AccountSession.state.authenticated){location.href='/cuenta?next=membership';return;}
    if(permanentAccess){$('payment-feedback').textContent='Tu acceso de propietario es permanente. No necesitas comprar.';return;}
    button.disabled=true;$('payment-feedback').textContent='';
    try { const result=existing?{order:existing,local:configuration.local}:await api('/api/payments/orders',{method:method.id});showCheckout(method,result);await refresh(); }
    catch(error){$('payment-feedback').textContent=error.message;}finally{button.disabled=false;}
  }
  function showCheckout(method,result) {
    const order=result.order, content=$('checkout-content');content.replaceChildren();$('checkout-feedback').textContent='';
    $('checkout-feedback').className='';
    const title=node('h2',method.label);title.id='checkout-title';content.append(title,node('p',amount(method),'checkout-amount'),node('p','30 días · un solo pago · sin renovación automática'));
    if(order.status==='pending_review'){content.append(node('p','Tu operación ya está en revisión. No vuelvas a pagar; consulta el estado en Tus solicitudes.'));}
    else if(method.id==='bmc'){
      content.append(node('p','Copia este código y pégalo en la pregunta «Código de compra» al pagar. Así el acceso se activa en tu cuenta.'));
      content.append(node('code',order.code,'order-code'));
      const copy=node('button','Copiar código','outline-action');copy.type='button';copy.onclick=async()=>{try{await navigator.clipboard.writeText(order.code);copy.textContent='Código copiado';}catch{$('checkout-feedback').textContent='Selecciona y copia el código que aparece arriba.';}};content.append(copy);
      if(result.local){content.append(node('p','Vista previa de pago: esta operación no realiza ningún cobro.'));}
      else{
        if(!result.checkout_url)throw new Error('El enlace de compra todavía no está configurado.');
        const link=node('a','Ir al pago único de US$1.50','primary-action');link.href=result.checkout_url;link.target='_blank';link.rel='noopener noreferrer';
        link.onclick=event=>{if(window.Telegram?.WebApp?.initData){event.preventDefault();Telegram.WebApp.openLink(link.href,{try_instant_view:false});}};content.append(link);
      }
    }else{
      content.append(node('p','Destinatario: '+method.recipient));
      if(configuration.local)content.append(node('p','Vista previa de pago: no realices transferencias. La confirmación de esta operación es de demostración.'));
      const img=document.createElement('img');img.src=method.qr;img.alt='QR de '+method.label;img.className='payment-qr';content.append(img);
      const download=node('a','Guardar QR para abrirlo en mi billetera','qr-download');download.href=method.qr;download.download=method.id+'-qr';content.append(download);
      content.append(node('p',method.id==='binance'?'Escanea desde Binance Pay y comprueba el receptor, 1.50 USDT y el total antes de confirmar.':'Escanea desde Yape o Plin y comprueba el receptor y S/5.50 antes de confirmar.'));
      const form=document.createElement('form');
      [['reference','Número de operación / ID del pago','text'],['payer','Nombre del titular que pagó','text'],['paid_date','Fecha del pago','date']].forEach(([name,label,type])=>{const field=node('label',label);const input=document.createElement('input');input.name=name;input.type=type;input.required=true;input.maxLength=name==='payer'?80:100;if(type==='date')input.value=new Date().toLocaleDateString('en-CA');field.append(input);form.append(field);});
      const submit=node('button','Registrar pago para revisión','primary-action');submit.type='submit';form.append(submit);
      form.onsubmit=async event=>{event.preventDefault();submit.disabled=true;try{await api(`/api/payments/orders/${order.id}/report`,Object.fromEntries(new FormData(form)));$('checkout-feedback').textContent='Solicitud enviada. Verificaremos el ingreso antes de activar tus 30 días.';$('checkout-feedback').className='success';form.remove();await refresh();}catch(error){$('checkout-feedback').textContent=error.message;submit.disabled=false;}};
      content.append(form,node('p','Registrar la operación no activa el acceso inmediatamente. Espera la aprobación del administrador.'));
    }
    if(!$('payment-dialog').open)$('payment-dialog').showModal();
  }
  async function refresh(){
    if(!AccountSession.state.authenticated)return;
    try{
      const data=await api('/api/payments/mine');currentOrders=data.orders;permanentAccess=data.permanent===true;
      $('payment-methods').querySelectorAll('button').forEach((button,index)=>{button.disabled=permanentAccess||!configuration.methods[index].available;});
      $('access-state').hidden=!data.active;
      $('access-state').textContent=permanentAccess?'Tu cuenta de propietario tiene acceso permanente, sin vencimiento ni pagos.':data.active?'Tu acceso está activo hasta el '+new Date(data.expires_at).toLocaleString('es-PE',{dateStyle:'long',timeStyle:'short'})+'. Si vuelves a comprar, sumamos 30 días al tiempo restante.':'';
      $('payment-history').hidden=!data.orders.length;const list=$('order-list');list.replaceChildren();
      data.orders.forEach(order=>{const method=configuration.methods.find(m=>m.id===order.method);const card=node('article',null,'order-card');const info=node('div');info.append(node('strong',method.label+' · '+amount(order)),node('p',new Date(order.created_at*1000).toLocaleString('es-PE')));if(order.reference)info.append(node('p','Operación: '+order.reference));if(order.reason)info.append(node('p',order.reason));card.append(info,node('span',labels[order.status]||order.status,'order-status '+order.status));
        if(!permanentAccess&&['draft','pending_provider'].includes(order.status)){const button=node('button','Continuar','outline-action');button.type='button';button.onclick=()=>start(method,button);card.append(button);}list.append(card);});
    }catch(error){$('payment-feedback').textContent=error.message;}
  }
  $('close-payment').onclick=()=>$('payment-dialog').close();$('refresh-payments').onclick=refresh;
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
  setInterval(()=>{if(!document.hidden&&currentOrders.some(o=>o.status.startsWith('pending')))refresh();},15000);
  AccountSession.ready.then(async()=>{try{configuration=await api('/api/payments/config');methods();await refresh();}catch(error){$('payment-feedback').textContent=error.message;}});
})();
