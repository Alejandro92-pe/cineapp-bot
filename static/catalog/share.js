/* One public title link for browser, Telegram and the Android shell. */
(function(root){
  'use strict';
  function payload(item){
    if(!item || !/^[1-9]\d*$/.test(String(item.id)))return null;
    const title=String(item.titulo||'Una historia para ti').replace(/[\u0000-\u001f\u007f]/g,' ').trim().slice(0,200);
    const year=/^\d{4}$/.test(String(item.año||item.anio||'')) ? ` (${item.año||item.anio})` : '';
    return {title,text:`🎬 Mira «${title}»${year} en Qué Hay Cine.`,url:`https://app.quehay.live/?contenido=${item.id}`};
  }
  function telegramLink(data){return `https://t.me/share/url?url=${encodeURIComponent(data.url)}&text=${encodeURIComponent(data.text)}`;}
  function fallback(data){
    const doc=root.document,previous=doc.activeElement;
    doc.getElementById('quehay-share')?.remove();
    const dialog=doc.createElement('dialog');dialog.id='quehay-share';dialog.setAttribute('aria-labelledby','quehay-share-title');
    dialog.style.cssText='box-sizing:border-box;width:min(420px,calc(100% - 32px));margin:auto;max-height:calc(100% - 32px);overflow:auto;padding:24px;border:1px solid #30465f;border-radius:22px;background:#101d2e;color:#f4f7fb;font:inherit;box-shadow:0 20px 80px #0009';
    const heading=doc.createElement('h2');heading.id='quehay-share-title';heading.textContent='Comparte una buena historia';heading.style.cssText='font-size:22px;margin:0 0 12px';
    const title=doc.createElement('p');title.textContent=data.title;title.style.cssText='margin:0 0 18px;color:#c6d7e9';
    const actions=doc.createElement('div');actions.style.cssText='display:grid;gap:10px';
    const style='box-sizing:border-box;display:block;text-align:center;padding:13px;border:1px solid #375371;border-radius:12px;background:#1b324e;color:#fff;text-decoration:none;font:inherit;cursor:pointer';
    for(const [label,url] of [['WhatsApp',`https://wa.me/?text=${encodeURIComponent(data.text+'\n'+data.url)}`],['Telegram',telegramLink(data)]]){
      const a=doc.createElement('a');a.textContent=label;a.href=url;a.target='_blank';a.rel='noopener noreferrer';a.style.cssText=style;actions.append(a);
    }
    const copy=doc.createElement('button');copy.type='button';copy.textContent='Copiar mensaje y enlace';copy.style.cssText=style;
    const status=doc.createElement('p');status.setAttribute('role','status');status.style.fontSize='14px';
    copy.onclick=async()=>{try{await root.navigator.clipboard.writeText(data.text+'\n'+data.url);status.textContent='Mensaje y enlace copiados.';}catch{status.textContent='Selecciona y copia este enlace:';const field=doc.createElement('input');field.readOnly=true;field.value=data.url;field.style.cssText='box-sizing:border-box;width:100%;padding:10px';status.append(field);field.select();}};
    const close=doc.createElement('button');close.type='button';close.textContent='Cerrar';close.style.cssText=style+';background:transparent';close.onclick=()=>dialog.close();
    dialog.addEventListener('close',()=>{dialog.remove();previous?.focus();});
    actions.append(copy,close);dialog.append(heading,title,actions,status);doc.body.append(dialog);dialog.showModal();
  }
  async function share(item,env=root){
    const data=payload(item);if(!data)return 'invalid';
    if(typeof env.QueHayAndroidUI?.share==='function'){env.QueHayAndroidUI.share(data);return 'android';}
    const tg=env.Telegram?.WebApp;
    if(tg?.initData && typeof tg.openTelegramLink==='function'){
      try{tg.openTelegramLink(telegramLink(data));return 'telegram';}catch{}
    }
    if(typeof env.navigator?.share==='function'){
      try{await env.navigator.share(data);return 'native';}catch(error){if(error.name==='AbortError')return 'cancelled';}
    }
    (env.shareFallback||fallback)(data);return 'fallback';
  }
  const api={payload,telegramLink,share};
  if(typeof module!=='undefined')module.exports=api;
  root.QueHayShare=api;
})(typeof window==='undefined'?{}:window);
