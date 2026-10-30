/* Reuses the web's verified login and cookie; never accepts a Telegram ID alone. */
(()=>{'use strict';const $=id=>document.getElementById(id);let csrf='',signed=false;
 async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.error||'No pudimos completar la solicitud.');return d;}
 const feedback=(text,ok=false)=>{$('phone-status').textContent=text;$('phone-status').className=ok?'success':'';};
 async function refresh(){const d=await api('/tv/api/phone/me');signed=Boolean(d.name);csrf=d.csrf||'';
  $('login').hidden=signed;$('confirm').hidden=!signed;$('revoke').hidden=!signed;$('account-help').hidden=signed;
  $('telegram-login').hidden=signed||!window.Telegram?.WebApp?.initData;
  $('welcome').textContent=signed?'Hola, '+d.name+'. Confirma el código que muestra tu TV.':'Usa la misma cuenta de Qué Hay. Tu contraseña nunca se escribe en el televisor.';
  return signed;
 }
 $('login').onsubmit=async e=>{e.preventDefault();try{await api('/api/auth/login',{email:$('email').value,password:$('password').value});$('password').value='';await refresh();feedback('Cuenta verificada. Introduce el código de tu TV.');$('code').focus();}catch(error){feedback(error.message);}};
 $('telegram-login').onclick=async()=>{try{const raw=window.Telegram?.WebApp?.initData;if(!raw)throw Error('Abre esta página desde tu Mini App de Qué Hay.');await api('/api/auth/telegram',{init_data:raw});await refresh();feedback('Telegram verificado. Introduce el código de tu TV.');}catch(error){feedback(error.message);}};
 $('confirm').onsubmit=async e=>{e.preventDefault();const button=e.submitter;button.disabled=true;try{await api('/tv/api/phone/confirm',{code:$('code').value});feedback('Listo. Tu TV recibirá la cuenta en unos segundos.',true);$('code').value='';}catch(error){feedback(error.message);}finally{button.disabled=false;}};
 $('revoke').onclick=async()=>{if(!confirm('¿Desvincular todos tus televisores? Tu sesión del celular seguirá abierta.'))return;try{await api('/tv/api/phone/revoke',{});feedback('Tus televisores se han desvinculado.',true);}catch(error){feedback(error.message);}};
 window.addEventListener('focus',()=>refresh().catch(error=>feedback(error.message)));
 window.Telegram?.WebApp?.ready();refresh().then(()=>feedback(signed?'Introduce el código de tu TV.':'')).catch(error=>feedback(error.message));
})();
