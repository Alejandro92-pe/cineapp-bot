(function(root){
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
  async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw new Error(d.error||'No se pudo completar.');return d;}
  const names={bmc:'Buy Me a Coffee',yape_plin:'Yape / Plin',binance:'Binance Pay'};
  const statuses={draft:'Todavía no registró el pago',pending_review:'Revisión pendiente',pending_provider:'Esperando confirmación BMC',approved:'Aprobado',rejected:'Rechazado'};
  root.PaymentAdmin={async mount(container){
    container.replaceChildren(el('p','Cargando solicitudes…'));
    try{
      const data=await api('/api/admin/payments');container.replaceChildren();
      const top=el('section',null,'billing-admin-intro');top.append(el('h2','Pagos y acceso mensual'),el('p','Un solo acceso de 30 días: US$1.50 en Buy Me a Coffee, S/5.50 en Yape/Plin o 1.50 USDT en Binance Pay.'));
      const refresh=el('button','Actualizar solicitudes','btn-import');refresh.onclick=()=>root.PaymentAdmin.mount(container);top.append(refresh);container.append(top);
      const pending=data.orders.filter(o=>o.status==='pending_review'||o.status==='pending_provider');
      container.append(el('h3',`Por revisar · ${pending.length}`));
      if(!pending.length)container.append(el('p','No hay solicitudes de pago pendientes.'));
      pending.forEach(order=>{
        const card=el('article',null,'billing-review-card');card.append(el('h3',`${order.name} · ${names[order.method]}`),el('p',`${(order.amount_minor/100).toFixed(2)} ${order.currency} · ${statuses[order.status]}`),el('p',order.email||'Cuenta vinculada por Telegram'));
        if(order.reference)card.append(el('p','Operación: '+order.reference,'billing-reference'));
        if(order.payer)card.append(el('p','Titular: '+order.payer+' · Fecha: '+order.paid_date));
        const message=el('p',null,'billing-message');
        if(order.method==='bmc'){
          card.append(el('p','Código: '+order.code));
          if(data.local){const simulate=el('button','Simular confirmación BMC · solo local','btn-import');simulate.onclick=async()=>{simulate.disabled=true;try{await api(`/api/admin/payments/${order.id}/simulate`,{});await root.PaymentAdmin.mount(container);}catch(e){message.textContent=e.message;simulate.disabled=false;}};card.append(simulate);}
          else card.append(el('p','La activación se realizará con el webhook firmado y el código de compra. Si falta el código, concilia el pago antes de conceder acceso.'));
        }else{
          const label=el('label',null,'billing-confirm');const check=document.createElement('input');check.type='checkbox';label.append(check,document.createTextNode(`Comprobé en mi billetera el ingreso de ${(order.amount_minor/100).toFixed(2)} ${order.currency}, el titular y este número de operación.`));card.append(label);
          const reason=document.createElement('input');reason.type='text';reason.placeholder='Motivo si rechazas la solicitud';reason.setAttribute('aria-label','Motivo del rechazo');reason.maxLength=300;card.append(reason);
          const buttons=el('div',null,'billing-actions');
          ['approve','reject'].forEach(decision=>{const button=el('button',decision==='approve'?'Aprobar y activar 30 días':'Rechazar',decision==='approve'?'btn-import':'billing-reject');button.onclick=async()=>{button.disabled=true;message.textContent='';try{await api(`/api/admin/payments/${order.id}/decide`,{decision,confirmed:check.checked,reason:reason.value});await root.PaymentAdmin.mount(container);}catch(error){message.textContent=error.message;button.disabled=false;}};buttons.append(button);});card.append(buttons);
        }
        card.append(message);container.append(card);
      });
      const history=el('details',null,'billing-settings');history.append(el('summary','Historial de solicitudes'));
      data.orders.filter(o=>!pending.includes(o)).forEach(order=>history.append(el('p',`${order.name} · ${names[order.method]} · ${(order.amount_minor/100).toFixed(2)} ${order.currency} · ${statuses[order.status]}`)));container.append(history);
      if(data.reviews.length){const reviews=el('details',null,'billing-settings');reviews.append(el('summary',`Eventos BMC para conciliación · ${data.reviews.length}`));data.reviews.forEach(r=>reviews.append(el('p',`Pago ${r.payment_id}: ${r.reason}`)));container.append(reviews);}
      const settings=el('details',null,'billing-settings');settings.append(el('summary','Configurar QR oficiales de Yape/Plin y Binance Pay'));
      settings.append(el('p','Sube una imagen oficial de tu billetera. Se conserva en la base privada para que sobreviva a reinicios de Render. El QR no se genera ni se modifica aquí.'));
      const form=document.createElement('form');form.className='billing-qr-form';
      const methodLabel=el('label','Método');const method=document.createElement('select');for(const id of ['binance','yape_plin']){const option=el('option',names[id]);option.value=id;method.append(option);}methodLabel.append(method);form.append(methodLabel);
      const recipientLabel=el('label','Nombre del receptor que muestra la billetera');const recipient=document.createElement('input');recipient.required=true;recipient.maxLength=100;recipientLabel.append(recipient);form.append(recipientLabel);
      const fileLabel=el('label','QR oficial · PNG o JPG · hasta 1 MB');const file=document.createElement('input');file.type='file';file.accept='image/png,image/jpeg';file.required=true;fileLabel.append(file);form.append(fileLabel);
      const confirmLabel=el('label',null,'billing-confirm');const confirmed=document.createElement('input');confirmed.type='checkbox';confirmed.required=true;confirmLabel.append(confirmed,document.createTextNode('Verifiqué que este QR pertenece al receptor indicado. Para Binance Pay está preparado para recibir USDT.'));form.append(confirmLabel);
      const submit=el('button','Guardar QR oficial','btn-import');submit.type='submit';form.append(submit);const feedback=el('p',null,'billing-message');feedback.setAttribute('role','status');form.append(feedback);
      form.onsubmit=async event=>{event.preventDefault();submit.disabled=true;try{const chosen=file.files[0];if(chosen.size>1024*1024)throw new Error('La imagen debe pesar como máximo 1 MB.');const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(chosen);});await api('/api/admin/payments/qr',{method:method.value,recipient:recipient.value,confirmed:confirmed.checked,data:encoded});feedback.textContent='QR guardado. El método ya aparece disponible en la página de acceso.';form.reset();}catch(error){feedback.textContent=error.message;}finally{submit.disabled=false;}};
      settings.append(form);container.append(settings);
      const legacy=el('details',null,'billing-settings');legacy.append(el('summary','Solicitudes anteriores al plan único'));const oldList=el('div');oldList.id='legacy-pagos-list';legacy.append(oldList);legacy.addEventListener('toggle',()=>{if(legacy.open&&typeof cargarPagosAnteriores==='function')cargarPagosAnteriores();});container.append(legacy);
    }catch(error){container.replaceChildren(el('p',error.message));}
  }};
})(window);
