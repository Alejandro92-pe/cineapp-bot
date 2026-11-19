/* Admin · people: web accounts with their access, payments, BMC events and playback. */
(function(root){
  'use strict';
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined&&text!==null)n.textContent=String(text);if(cls)n.className=cls;return n;};
  async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.error||'No se pudo completar.');return d;}
  const PE={timeZone:'America/Lima'};
  const day=ts=>ts?new Date(ts*1000).toLocaleDateString('es-PE',{...PE,day:'2-digit',month:'short',year:'numeric'}):'—';
  const moment=ts=>ts?new Date(ts*1000).toLocaleString('es-PE',{...PE,day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}):'—';
  const ago=iso=>{if(!iso)return 'nunca';const d=Math.round((Date.now()-new Date(iso+'T12:00:00-05:00'))/86400000);return d<=0?'hoy':d===1?'ayer':`hace ${d} días`;};
  const ACCESS={activo:['Activo','ok'],vencido:['Vencido','warn'],sin_pago:['Sin pago','muted'],propietario:['Propietario','info']};
  const METHOD={bmc:'Buy Me a Coffee',yape_plin:'Yape / Plin',binance:'Binance Pay'};
  const ORDER={draft:'No registró el pago',pending_provider:'Esperando pago en BMC',pending_review:'Por revisar',approved:'Aprobado',rejected:'Rechazado'};
  const OUTCOME={activado:['Activado','ok'],esperando:['Esperando código','info'],sin_vincular:['Sin vincular','warn'],revisar:['Revisar','bad'],cancelada:['Cancelada','muted'],duplicado:['Repetido','muted'],prueba:['Prueba','muted'],ignorado:['Ignorado','muted'],rechazado:['Rechazado','bad']};
  const badge=(map,key)=>{const [label,tone]=map[key]||[key||'—','muted'];return el('span',label,'pp-badge '+tone);};
  const money=o=>(o.currency==='PEN'?'S/':o.currency==='USD'?'US$':'')+(o.amount_minor/100).toFixed(2)+(o.currency==='USDT'?' USDT':'');
  let state={filter:'todos',query:'',data:null};

  function kpi(label,value,tone,hint){const c=el('div',null,'pp-kpi '+(tone||''));c.append(el('span',label,'pp-kpi-label'),el('strong',value,'pp-kpi-value'));if(hint)c.append(el('span',hint,'pp-kpi-hint'));return c;}

  async function load(container){
    const list=container.querySelector('.pp-list');list.replaceChildren(el('p','Cargando cuentas…','pp-empty'));
    try{state.data=await api('/api/admin/accounts'+(state.query?'?q='+encodeURIComponent(state.query):''));render(container);}
    catch(error){list.replaceChildren(el('p',error.message,'pp-empty'));}
  }

  function render(container){
    const data=state.data,c=data.counts||{};
    const kpis=container.querySelector('.pp-kpis');kpis.replaceChildren(
      kpi('Cuentas web',data.total),kpi('Con acceso',(c.activo||0)+(c.propietario||0),'ok'),
      kpi('Vencidos',c.vencido||0,'warn','Pagaron antes, hoy sin acceso'),kpi('Nunca pagaron',c.sin_pago||0,'muted'));
    const pending=data.accounts.filter(a=>a.last_order&&['pending_provider','pending_review','draft'].includes(a.last_order.status)).length;
    kpis.append(kpi('Pago a medias',pending,pending?'bad':'muted','Empezaron a pagar y no terminó'));
    const rows=data.accounts.filter(a=>state.filter==='todos'||(state.filter==='pendiente'?a.last_order&&['pending_provider','pending_review','draft'].includes(a.last_order.status):a.access===state.filter));
    const list=container.querySelector('.pp-list');list.replaceChildren();
    if(data.shown<data.total&&!state.query)list.append(el('p',`Mostrando las ${data.shown} cuentas más recientes de ${data.total}. Usa el buscador para encontrar otras.`,'pp-note'));
    if(!rows.length){list.append(el('p','Ninguna cuenta con este filtro.','pp-empty'));return;}
    const table=el('div',null,'pp-table');
    const head=el('div',null,'pp-row pp-head');['Persona','Acceso','Último pago','Actividad','Registro'].forEach(t=>head.append(el('span',t)));table.append(head);
    rows.forEach(a=>{
      const row=el('button',null,'pp-row');row.type='button';
      const who=el('span',null,'pp-who');const avatar=el('span',(a.name||'?').trim().charAt(0).toUpperCase(),'pp-avatar');
      const names=el('span');names.append(el('strong',a.name||'Sin nombre'),el('small',a.email||(a.telegram_id?'Telegram '+a.telegram_id:'Sin email')));who.append(avatar,names);
      const acc=el('span',null,'pp-cell');acc.append(badge(ACCESS,a.access));if(a.access_until&&a.access!=='propietario')acc.append(el('small',(a.access==='activo'?'hasta ':'venció ')+day(a.access_until)));
      const pay=el('span',null,'pp-cell');if(a.last_order){pay.append(el('span',ORDER[a.last_order.status]||a.last_order.status,'pp-order '+a.last_order.status),el('small',METHOD[a.last_order.method]||a.last_order.method));}else pay.append(el('small','Sin solicitudes'));
      const act=el('span',null,'pp-cell');act.append(el('span',a.titles?`${a.titles} títulos`:'Sin reproducir'),el('small','Último: '+ago(a.last_play_day)));
      row.append(who,acc,pay,act,el('span',day(a.created_at),'pp-cell pp-date'));
      row.onclick=()=>detail(container,a.id);table.append(row);
    });
    list.append(table);
  }

  async function detail(container,id){
    const drawer=container.querySelector('.pp-drawer');drawer.hidden=false;const body=drawer.querySelector('.pp-drawer-body');body.replaceChildren(el('p','Cargando…','pp-empty'));
    try{
      const d=await api('/api/admin/accounts/'+encodeURIComponent(id));const a=d.account;body.replaceChildren();
      const top=el('div',null,'pp-detail-top');top.append(el('span',(a.name||'?').charAt(0).toUpperCase(),'pp-avatar big'));const t=el('div');t.append(el('h3',a.name||'Sin nombre'),el('p',[a.email,a.telegram_id&&('Telegram '+a.telegram_id)].filter(Boolean).join(' · ')||'Sin datos de contacto'),el('p','Registrado el '+day(a.created_at),'pp-muted'));top.append(t);body.append(top);
      const now=Date.now()/1000,until=Math.max(d.expires_at||0,d.legacy_until||0);
      const access=el('section',null,'pp-box');access.append(el('h4','Acceso'));
      access.append(el('p',d.owner?'Propietario: acceso permanente.':until>now?`Activo hasta el ${moment(until)}.`:until?`Venció el ${moment(until)}.`:'Nunca tuvo acceso pagado.'));
      if(d.legacy_until)access.append(el('p',`Incluye tiempo del bot antiguo hasta el ${day(d.legacy_until)}.`,'pp-muted'));body.append(access);
      if(d.memberships.length){const box=el('section',null,'pp-box');box.append(el('h4','Membresía IMAX'));d.memberships.forEach(m=>box.append(el('p',`${m.status==='active'&&!m.canceled?'Activa':'Cancelada'} · ${m.email||'sin email'} · mes pagado hasta ${day(m.period_end)} · vinculada por ${m.link_method==='admin'?'el admin':'email'}`)));body.append(box);}
      const orders=el('section',null,'pp-box');orders.append(el('h4',`Pagos y solicitudes · ${d.orders.length}`));
      if(!d.orders.length)orders.append(el('p','Todavía no empezó ningún pago.','pp-muted'));
      d.orders.forEach(o=>{const line=el('div',null,'pp-line');line.append(el('span',moment(o.created_at),'pp-date'),el('span',`${METHOD[o.method]||o.method} · ${money(o)}`),el('span',ORDER[o.status]||o.status,'pp-order '+o.status));
        const extra=[o.payer&&('Email/titular: '+o.payer),o.reference&&('Operación: '+o.reference),o.reason,o.expires_at&&('Acceso hasta '+day(o.expires_at))].filter(Boolean);if(extra.length)line.append(el('small',extra.join(' · ')));orders.append(line);});
      body.append(orders);
      const ev=el('section',null,'pp-box');ev.append(el('h4',`Avisos de Buy Me a Coffee · ${d.events.length}`));
      if(!d.events.length)ev.append(el('p','Ningún aviso de BMC vinculado a esta cuenta.','pp-muted'));
      d.events.forEach(e=>ev.append(root.PeopleAdmin.eventLine(e)));body.append(ev);
      const plays=el('section',null,'pp-box');plays.append(el('h4','Últimas reproducciones'));
      if(!d.plays.length)plays.append(el('p','No ha abierto ningún título.','pp-muted'));
      else{const ul=el('ul',null,'pp-plays');d.plays.slice(0,15).forEach(p=>{const li=el('li');const link=el('a',p.title||('Título #'+p.content_id));link.href='/?contenido='+p.content_id;link.target='_blank';link.rel='noopener';li.append(link,el('small',' · '+ago(p.day)));ul.append(li);});plays.append(ul);}
      body.append(plays);
    }catch(error){body.replaceChildren(el('p',error.message,'pp-empty'));}
  }

  function eventLine(e){
    const TYPES={'membership.started':'Se unió a IMAX','membership.updated':'Membresía actualizada / renovada','membership.cancelled':'Canceló la membresía','extra_purchase.created':'Compra en la tienda','extra_purchase.updated':'Compra en la tienda (respuesta)','extra_purchase.refunded':'Reembolso','admin.link':'Vinculada a mano'};
    const line=el('div',null,'pp-event');
    const head=el('div',null,'pp-event-head');head.append(badge(OUTCOME,e.outcome),el('strong',TYPES[e.type]||e.type),el('span',moment(e.received_at),'pp-date'));
    line.append(head);
    const who=[e.name,e.email,e.amount&&(e.amount+' '+(e.currency||''))].filter(Boolean).join(' · ');if(who)line.append(el('small',who));
    if(e.detail)line.append(el('p',e.detail));
    if(!String(e.id).startsWith('link-')){const more=el('button','Ver aviso completo','pp-link');more.type='button';more.onclick=async()=>{more.disabled=true;try{const r=await api('/api/admin/bmc/events/'+encodeURIComponent(e.id));const pre=el('pre',JSON.stringify(r.payload,null,2),'pp-json');more.replaceWith(pre);}catch(err){more.textContent=err.message;}};line.append(more);}
    return line;
  }

  root.PeopleAdmin={eventLine,
    mount(container){
      container.replaceChildren();
      const intro=el('section',null,'pp-intro');intro.append(el('h2','Usuarios de la web'),el('p','Cuentas creadas en app.quehay.live con su acceso, pagos, avisos de Buy Me a Coffee y lo que han visto. Toca una persona para ver su ficha.'));container.append(intro);
      container.append(el('div',null,'pp-kpis'));
      const tools=el('div',null,'pp-tools');const search=document.createElement('input');search.type='search';search.placeholder='Buscar por nombre, email o Telegram';search.setAttribute('aria-label','Buscar usuarios');
      let timer;search.oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{state.query=search.value.trim();load(container);},300);};tools.append(search);
      const chips=el('div',null,'pp-chips');[['todos','Todos'],['activo','Con acceso'],['vencido','Vencidos'],['sin_pago','Nunca pagaron'],['pendiente','Pago a medias']].forEach(([key,label])=>{const b=el('button',label,'pp-chip'+(state.filter===key?' on':''));b.type='button';b.onclick=()=>{state.filter=key;chips.querySelectorAll('.pp-chip').forEach(x=>x.classList.toggle('on',x===b));if(state.data)render(container);};chips.append(b);});
      const refresh=el('button','Actualizar','pp-chip');refresh.type='button';refresh.onclick=()=>load(container);chips.append(refresh);tools.append(chips);container.append(tools);
      container.append(el('div',null,'pp-list'));
      const drawer=el('aside',null,'pp-drawer');drawer.hidden=true;const close=el('button','×','pp-close');close.type='button';close.setAttribute('aria-label','Cerrar ficha');close.onclick=()=>{drawer.hidden=true;};drawer.append(close,el('div',null,'pp-drawer-body'));container.append(drawer);
      load(container);
    }};
})(window);
