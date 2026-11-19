/* A second explicit click opens the provider, preserving the user gesture on mobile. */
function mostrarEnlaceExterno(raw, label='Abrir sitio de descarga', password='') {
  const url = new URL(raw);
  if (url.protocol !== 'https:') throw new Error('El enlace debe usar HTTPS.');
  document.getElementById('download-dialog')?.remove();
  const dialog = document.createElement('dialog');
  dialog.id='download-dialog';
  dialog.style.cssText='max-width:420px;width:calc(100% - 40px);padding:28px;border:1px solid #34455b;border-radius:16px;background:#111c2c;color:#edf3fa;margin:auto';
  const title=document.createElement('h2');title.textContent='Tu enlace está listo';title.style.fontSize='22px';
  const description=document.createElement('p');description.textContent=`Se abrirá ${url.hostname}. Completa la descarga en la página del proveedor.`;description.style.cssText='font-size:14px;color:#adbacb;margin:16px 0';
  // Archive password, shown before leaving: the file asks for it when it is extracted.
  const secret=document.createElement('div');
  if(password){
    secret.style.cssText='margin:0 0 18px;padding:14px;border:1px solid #e8c581;border-radius:10px;background:#1a2536';
    const label2=document.createElement('p');label2.textContent='Contraseña para abrir el archivo';label2.style.cssText='margin:0 0 8px;font-size:12px;color:#e8c581;font-weight:700';
    const row=document.createElement('div');row.style.cssText='display:flex;gap:10px;align-items:center;flex-wrap:wrap';
    const value=document.createElement('code');value.textContent=password;value.style.cssText='font-size:20px;font-weight:700;color:#fff;letter-spacing:.5px;user-select:all;overflow-wrap:anywhere';
    const copyPass=document.createElement('button');copyPass.type='button';copyPass.textContent='Copiar contraseña';copyPass.style.cssText='padding:8px 12px;background:#e8c581;color:#1a1408;border:0;border-radius:6px;font-weight:700;cursor:pointer';
    copyPass.onclick=async()=>{try{await navigator.clipboard.writeText(password);copyPass.textContent='Copiada';}catch{copyPass.textContent='Mantén pulsada la contraseña para copiarla';}};
    const hint=document.createElement('p');hint.textContent='Guárdala: la pedirá el archivo al descomprimirlo.';hint.style.cssText='margin:8px 0 0;font-size:12px;color:#adbacb';
    row.append(value,copyPass);secret.append(label2,row,hint);
  }
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
  dialog.append(title,description,...(password?[secret]:[]),link,copy,close);document.body.append(dialog);dialog.showModal();
}
async function prepararDescarga(contentId) {
  try {
    const response=await fetch(`/api/download/${contentId}`);
    const payload=await response.json();
    if(window.AccessSupport.handle(response,payload))return;
    if(!response.ok)throw new Error(payload.error||'No se pudo preparar la descarga.');
    mostrarEnlaceExterno(payload.url, undefined, payload.password||'');
  } catch(error) { alert(error.message); }
}
