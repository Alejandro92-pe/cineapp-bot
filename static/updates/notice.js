/* Never reload or touch the provider iframe without a deliberate user action. */
(()=>{'use strict';
 const meta=document.querySelector('meta[name="qh-release"]');if(!meta)return;
 const endpoint=new URL(meta.dataset.endpoint,location.href);if(endpoint.origin!==location.origin)return;
 const tv=!!document.querySelector('.topbar[data-row="navigation"]');
 let pending='',dismissed='',lastCheck=0,inflight=false,wasBusy=false;
 const notice=document.createElement('aside');notice.id='qh-update';notice.hidden=true;notice.setAttribute('aria-label','Actualización disponible');notice.dataset.row='update';
 const text=document.createElement('p');text.setAttribute('role','status');text.textContent='Hay una nueva versión de Qué Hay.';
 const update=document.createElement('button');update.id='qh-update-now';update.textContent='Actualizar ahora';update.dataset.nav='';
 const later=document.createElement('button');later.id='qh-update-later';later.textContent='Más tarde';later.dataset.nav='';
 notice.append(text,update,later);if(tv)document.querySelector('.topbar').after(notice);else document.body.append(notice);
 function busy(){
  return ['player','inline-player'].some(id=>{const el=document.getElementById(id);return el&&!el.hidden&&el.getClientRects().length>0;}) ||
   !!document.querySelector('#modalTrailer iframe[src]:not([src=""])') || !!document.fullscreenElement || !!document.querySelector('dialog[open]');
 }
 function hide(){
  if(notice.contains(document.activeElement)&&tv)window.TVFocus?.focus(document.getElementById('account-nav'));
  if(!notice.hidden)notice.hidden=true;
 }
 function render(){if(pending&&pending!==dismissed&&!busy()&&!document.hidden){if(notice.hidden)notice.hidden=false;}else hide();}
 async function check(force=false){
  if(inflight||document.hidden||busy()||(!force&&Date.now()-lastCheck<60000))return;
  inflight=true;lastCheck=Date.now();const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),8000);
  try{const r=await fetch(endpoint.href,{cache:'no-store',credentials:'omit',signal:controller.signal});if(!r.ok)return;
   const data=await r.json();if(/^[a-f0-9]{20}$/.test(data.version))pending=data.version!==meta.content?data.version:'';
  }catch(_){/* Offline and deploy transitions must not disturb viewing. */}
  finally{clearTimeout(timeout);inflight=false;render();}
 }
 update.onclick=()=>{if(busy()||document.hidden){render();return;}location.reload();};
 later.onclick=()=>{dismissed=pending;hide();};
 function state(){const active=busy();render();if(wasBusy&&!active)check();wasBusy=active;}
 new MutationObserver(state).observe(document.body,{subtree:true,attributes:true,attributeFilter:['hidden','open','src','style']});
 document.addEventListener('fullscreenchange',state);document.addEventListener('visibilitychange',()=>{state();if(!document.hidden)check();});
 // At most one lightweight request per five minutes while this page is visible.
 setInterval(check,300000);setTimeout(check,30000);wasBusy=busy();
 window.QHUpdates={check:()=>check(true)};
})();
