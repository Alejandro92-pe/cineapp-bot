(()=>{const $=id=>document.getElementById(id);let csrf='';
 async function api(path,body){const r=await fetch('/tv/api/phone/'+path,body?{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body)}:{});const d=await r.json();if(!r.ok)throw Error(d.error);return d;}
 function signed(d){csrf=d.csrf;$('login').hidden=true;$('confirm').hidden=false;$('revoke').hidden=false;$('welcome').textContent='Hola, '+d.name+'. Escribe el código que aparece en la TV.';}
 $('login').onsubmit=async e=>{e.preventDefault();try{signed(await api('login',{email:$('email').value,password:$('password').value}));$('password').value='';$('phone-status').textContent='';$('code').focus();}catch(e){$('phone-status').textContent=e.message;}};
 $('confirm').onsubmit=async e=>{e.preventDefault();try{await api('confirm',{code:$('code').value});$('phone-status').textContent='Listo. Tu televisor recibirá la cuenta en unos segundos.';$('phone-status').className='success';$('code').value='';}catch(e){$('phone-status').textContent=e.message;$('phone-status').className='';}};
 $('revoke').onclick=async()=>{try{await api('revoke',{});$('phone-status').textContent='Televisores desvinculados.';}catch(e){$('phone-status').textContent=e.message;}};
 api('me').then(d=>{if(d.name)signed(d);}).catch(()=>{});
})();
