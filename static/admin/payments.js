(function(root){
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
  async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw new Error(d.error||'No se pudo completar.');return d;}
  const names={bmc:'Buy Me a Coffee',yape_plin:'Yape / Plin',binance:'Binance Pay'};
  const statuses={draft:'Todavía no registró el pago',pending_review:'Revisión pendiente',pending_provider:'Esperando confirmación BMC',approved:'Aprobado',rejected:'Rechazado'};
  const day=ts=>ts?new Date(ts*1000).toLocaleDateString('es-PE',{timeZone:'America/Lima',day:'2-digit',month:'short',year:'numeric'}):'—';
  async function linkForm(card,membership,onDone){
    const form=el('div',null,'pp-link-form');const search=document.createElement('input');search.type='search';search.placeholder='Busca la cuenta por nombre, email o Telegram';search.setAttribute('aria-label','Buscar cuenta para vincular');
    const pick=el('div',null,'pp-pick');let chosen=null;const msg=el('p',null,'billing-message');
    const label=el('label',null,'billing-confirm');const check=document.createElement('input');check.type='checkbox';label.append(check,document.createTextNode('Confirmo que este pago de Buy Me a Coffee es de la cuenta elegida.'));
    const go=el('button','Vincular y activar acceso','btn-import');go.type='button';go.disabled=true;
    let timer;search.oninput=()=>{clearTimeout(timer);timer=setTimeout(async()=>{const q=search.value.trim();pick.replaceChildren();chosen=null;go.disabled=true;if(q.length<2)return;
      try{const r=await api('/api/admin/accounts?q='+encodeURIComponent(q));r.accounts.slice(0,8).forEach(a=>{const b=el('button',`${a.name||'Sin nombre'} · ${a.email||('Telegram '+(a.telegram_id||'—'))}`);b.type='button';b.onclick=()=>{chosen=a.id;pick.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===b));go.disabled=false;};pick.append(b);});if(!r.accounts.length)pick.append(el('p','Sin resultados.','pp-empty'));}catch(e){msg.textContent=e.message;}},300);};
    if(membership.email){search.value=membership.email;setTimeout(()=>search.oninput(),0);}
    go.onclick=async()=>{go.disabled=true;msg.textContent='';try{await api(`/api/admin/bmc/memberships/${encodeURIComponent(membership.id)}/link`,{account_id:chosen,confirmed:check.checked});onDone();}catch(e){msg.textContent=e.message;go.disabled=false;}};
    form.append(search,pick,label,go,msg);card.append(form);
  }
  root.PaymentAdmin={
  async bmc(section){
    section.replaceChildren(el('p','Cargando Buy Me a Coffee…','pp-empty'));
    try{
      const data=await api('/api/admin/bmc');section.replaceChildren();
      const now=Date.now()/1000;
      const active=data.memberships.filter(m=>m.status==='active'&&!m.canceled&&(m.period_end||0)>now&&String(m.level_id)===String(data.level_id));
      const unlinked=active.filter(m=>!m.account_id);
      const problems=data.events.filter(e=>['revisar','sin_vincular','rechazado'].includes(e.outcome)&&e.received_at>now-30*86400);
      const kpis=el('div',null,'pp-kpis');
      const k=(label,value,tone,hint)=>{const c=el('div',null,'pp-kpi '+(tone||''));c.append(el('span',label,'pp-kpi-label'),el('strong',String(value),'pp-kpi-value'));if(hint)c.append(el('span',hint,'pp-kpi-hint'));return c;};
      kpis.append(k('Miembros IMAX activos',active.length,'ok',`US$${(active.length*2).toFixed(2)} al mes`),k('Sin vincular',unlinked.length,unlinked.length?'bad':'muted','Pagaron y aún no tienen cuenta'),k('Avisos con problema (30 días)',problems.length,problems.length?'warn':'muted'),k('Avisos recibidos',data.events.length,'muted'));
      section.append(el('h3','Buy Me a Coffee · membresía IMAX','pp-section-title'),kpis);
      const link=el('p',null,'pp-note');link.append(document.createTextNode('Enlace que ven los usuarios: '));const a=el('a',data.checkout_url);a.href=data.checkout_url;a.target='_blank';a.rel='noopener';link.append(a);section.append(link);
      if(unlinked.length){section.append(el('h3',`Membresías sin vincular · ${unlinked.length}`,'pp-section-title'));
        unlinked.forEach(m=>{const card=el('article',null,'billing-review-card');card.append(el('h3',`${m.name||'Sin nombre'} · ${m.email||'sin email'}`),el('p',`Pagó US$${m.amount} · mes pagado hasta ${day(m.period_end)}. Ninguna cuenta coincide con su email: búscala y vincúlala.`));linkForm(card,m,()=>root.PaymentAdmin.bmc(section));section.append(card);});}
      const members=el('details',null,'billing-settings');members.append(el('summary',`Todas las membresías · ${data.memberships.length}`));
      data.memberships.forEach(m=>{const line=el('div',null,'pp-line');const state=m.status==='active'&&!m.canceled?'Activa':'Cancelada';line.append(el('span',state,'pp-order '+(state==='Activa'?'approved':'rejected')),el('span',`${m.name||'Sin nombre'} · ${m.email||'sin email'}`),el('span','hasta '+day(m.period_end),'pp-date'));
        line.append(el('small',m.account_id?`Cuenta: ${m.account_name||''} ${m.account_email||''} · vinculada por ${m.link_method==='admin'?'el admin':'email'}`:'Sin cuenta vinculada'));members.append(line);});
      if(!data.memberships.length)members.append(el('p','Todavía no llegó ninguna membresía.'));
      section.append(members);
      const events=el('details',null,'billing-settings');events.open=problems.length>0;events.append(el('summary',`Avisos de Buy Me a Coffee · ${data.events.length}`));
      events.append(el('p','Cada aviso que manda BMC, con lo que hizo la web y por qué. «Esperando código» en la tienda es normal: el código llega en el aviso siguiente.'));
      data.events.forEach(e=>events.append(root.PeopleAdmin?root.PeopleAdmin.eventLine(e):el('p',`${e.type} · ${e.outcome} · ${e.detail}`)));
      section.append(events);
    }catch(error){section.replaceChildren(el('p','Buy Me a Coffee: '+error.message,'billing-message'));}
  },
  async mount(container){
    container.replaceChildren(el('p','Cargando solicitudes…'));
    try{
      const data=await api('/api/admin/payments');container.replaceChildren();
      const top=el('section',null,'billing-admin-intro');top.append(el('h2','Pagos y acceso mensual'),el('p','Membresía IMAX en Buy Me a Coffee a US$2 al mes (se activa y renueva sola), o pago único de 30 días: S/7.50 en Yape/Plin o 2 USDT en Binance Pay. La tienda antigua de US$1.50 sigue activando a quien use su código.'));
      const refresh=el('button','Actualizar solicitudes','btn-import');refresh.onclick=()=>root.PaymentAdmin.mount(container);top.append(refresh);container.append(top);
      const bmc=el('section',null,'pp-bmc');container.append(bmc);root.PaymentAdmin.bmc(bmc);
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
      if(data.reviews.length){const reviews=el('details',null,'billing-settings');reviews.append(el('summary',`Registro antiguo de conciliación BMC · ${data.reviews.length}`));data.reviews.forEach(r=>reviews.append(el('p',`Pago ${r.payment_id}: ${r.reason}`)));container.append(reviews);}
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
