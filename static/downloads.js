/* A second explicit click opens the provider, preserving the user gesture on mobile. */
function mostrarEnlaceExterno(raw, label='Abrir sitio de descarga') {
  const url = new URL(raw);
  if (url.protocol !== 'https:') throw new Error('El enlace debe usar HTTPS.');
  document.getElementById('download-dialog')?.remove();
  const dialog = document.createElement('dialog');
  dialog.id='download-dialog';
  dialog.style.cssText='max-width:420px;width:calc(100% - 40px);padding:28px;border:1px solid #34455b;border-radius:16px;background:#111c2c;color:#edf3fa;margin:auto';
  const title=document.createElement('h2');title.textContent='Tu enlace está listo';title.style.fontSize='22px';
  const description=document.createElement('p');description.textContent=`Se abrirá ${url.hostname}. Completa la descarga en la página del proveedor.`;description.style.cssText='font-size:14px;color:#adbacb;margin:16px 0';
  const link=document.createElement('a');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';link.textContent=label;
  link.style.cssText='display:block;background:#77baff;color:#071321;padding:12px;border-radius:8px;text-align:center;font-weight:600;text-decoration:none';
  link.onclick=event=>{
    const webapp=window.Telegram?.WebApp;
    if (webapp?.initData && webapp.openLink) {
      event.preventDefault();
      try{webapp.openLink(url.href,{try_instant_view:false});}
      catch {window.open(url.href,'_blank','noopener,noreferrer');}
    }
  };
  const copy=document.createElement('button');copy.textContent='Copiar enlace';copy.style.cssText='margin:16px 14px 0 0;padding:8px;background:transparent;color:#bcd9f6;border:1px solid #34455b;border-radius:6px';
  copy.onclick=async()=>{try{await navigator.clipboard.writeText(url.href);copy.textContent='Copiado';}catch{description.textContent='Mantén pulsado el botón de descarga para copiar su enlace.';}};
  const close=document.createElement('button');close.textContent='Cerrar';close.style.cssText='padding:8px;background:transparent;color:#bcc8d7;border:0';close.onclick=()=>dialog.close();
  dialog.append(title,description,link,copy,close);document.body.append(dialog);dialog.showModal();
}
async function prepararDescarga(contentId) {
  try {
    const response=await fetch(`/api/download/${contentId}`);
    const payload=await response.json();
    if(window.AccessSupport.handle(response,payload))return;
    if(!response.ok)throw new Error(payload.error||'No se pudo preparar la descarga.');
    mostrarEnlaceExterno(payload.url);
  } catch(error) { alert(error.message); }
}
