/* Public APK distribution only. No account tokens, entitlements or auto-downloads. */
(function(){
  const manifest=document.currentScript?.dataset.manifest||'/static/pwa/apk-releases.json';
  const local=['127.0.0.1','localhost'].includes(location.hostname);
  function valid(item,kind){
    if(!item||!/^\d+\.\d+\.\d+$/.test(item.version)||!Number.isSafeInteger(item.bytes)||item.bytes<=0||!/^\d+$/.test(String(item.minAndroid))||!/^[a-f0-9]{64}$/.test(item.sha256))return false;
    try{
      const url=new URL(item.url),name=`QueHay-${kind==='android'?'Android':'TV'}-${item.version}.apk`;
      const official=url.origin==='https://quehay.live'&&url.pathname===`/apps/${name}`;
      const preview=local&&url.origin===location.origin&&url.pathname===`/static/_design-preview/distribution/apps/${name}`;
      return (official||preview)&&!url.search&&!url.hash&&!url.username&&!url.password;
    }catch{return false;}
  }
  function render(item,kind){
    const button=document.getElementById(`apk-${kind}`),info=document.getElementById(`apk-${kind}-info`);
    if(!button||!info||!valid(item,kind))return;
    button.href=item.url;button.hidden=false;
    info.textContent=`Versión ${item.version} · ${Math.ceil(item.bytes/1024)} KB · Android ${item.minAndroid} o superior`;
    const hash=document.getElementById(`apk-${kind}-hash`);if(hash)hash.textContent=item.sha256;
    const details=document.getElementById(`apk-${kind}-details`);if(details)details.hidden=false;
    const placeholder=document.getElementById(`apk-${kind}-pending`);if(placeholder)placeholder.hidden=true;
    button.addEventListener('click',event=>{
      const tg=window.Telegram?.WebApp;
      if(tg?.initData&&typeof tg.openLink==='function'){
        try{tg.openLink(item.url,{try_instant_view:false});event.preventDefault();}
        catch{/* The normal HTTPS link remains usable if Telegram declines. */}
      }
    });
  }
  async function start(){
    try{
      const response=await fetch(manifest,{credentials:'omit',cache:'no-store'});
      if(!response.ok)return;
      const data=await response.json();if(data.schema!==1||data.published!==true)return;
      for(const kind of ['android','tv'])render(data.releases?.[kind],kind);
    }catch{/* Keep honest availability copy; never invent a download URL. */}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
