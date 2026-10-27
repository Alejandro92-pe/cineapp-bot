/* The server owns signed-in preferences. Browser storage is only a one-time
 * migration source; it is never used as a second authenticated database. */
(function(root){
  let current=null;
  const account=()=>root.AccountSession?.state.authenticated?root.AccountSession.state.user?.id:null;
  const emit=()=>{for(const type of ['profile-changed','avatar-changed','library-changed'])root.dispatchEvent(new Event(type));};
  function status(message,error=false){
    root.ProfileSync.message=message;root.ProfileSync.error=error;
    root.dispatchEvent(new Event('profile-status'));
    if(error&&root.document){
      let notice=document.getElementById('profile-sync-notice');
      if(!notice){notice=document.createElement('p');notice.id='profile-sync-notice';notice.className='profile-sync-notice';notice.setAttribute('role','alert');document.body.append(notice);}
      notice.textContent=message;notice.hidden=false;clearTimeout(notice.hideTimer);notice.hideTimer=setTimeout(()=>notice.hidden=true,8000);
    }
  }
  async function request(body,expected){
    const response=await fetch('/api/profile',body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{cache:'no-store'});
    const result=await response.json();
    if(response.status===401)await root.AccountSession.refresh();
    if(!response.ok)throw Error(result.error||'No pudimos sincronizar. Comprueba tu conexión y vuelve a intentarlo.');
    if(result.account_id!==expected){await root.AccountSession.refresh();throw Error('La cuenta cambió. Actualizamos tu sesión.');}
    return result;
  }
  const active=c=>current===c&&account()===c.id;
  function legacy(c){
    try{
      if(localStorage.getItem('profile_migrated_'+c.id))return null;
      const user=root.AccountSession.state.user,key=user.telegram_id||user.id;
      const avatar=localStorage.getItem('avatar_'+key),stored=JSON.parse(localStorage.getItem('favs_'+key)||'[]');
      const ids=Array.isArray(stored)?[...new Set(stored.map(r=>Number(r?.id)).filter(i=>Number.isSafeInteger(i)&&i>0))].slice(0,200):[];
      const valid=['tg','fox','wolf','dragon','ghost','cat','alien','robot','ninja'].includes(avatar);
      return ids.length||valid?{action:'bootstrap',avatar:valid?avatar:'tg',saved_ids:ids}:null;
    }catch{return null;}
  }
  async function refresh(){
    const id=account();
    if(!id){current=null;status('');emit();return;}
    if(current?.id!==id){current={id,data:{avatar:'tg',items:[],saved_ids:[]},loaded:false,pending:new Map(),avatar:null,queue:Promise.resolve(),flight:null,sequence:0};emit();}
    const c=current;
    if(c.flight)return c.flight;
    if(c.pending.size||c.avatar)return c.queue;
    if(!c.loaded)status('Sincronizando tu cuenta…');
    c.flight=(async()=>{
      try{
        const sequence=c.sequence,body=!c.loaded?legacy(c):null,result=await request(body,c.id);
        if(!active(c)||sequence!==c.sequence)return;
        const changed=!c.loaded||JSON.stringify(c.data)!==JSON.stringify(result);
        c.data=result;c.loaded=true;
        if(body)try{localStorage.setItem('profile_migrated_'+c.id,'1');}catch{}
        status('Avatar y Mi lista sincronizados con tu cuenta.');if(changed)emit();
      }catch(error){if(active(c))status(error.message,true);}
      finally{c.flight=null;}
    })();
    return c.flight;
  }
  function change(body,overlay){
    const c=current;
    if(!c||!active(c)||!c.loaded){status('Espera a que se sincronice tu cuenta y vuelve a intentarlo.',true);refresh();return false;}
    const token=++c.sequence;
    if(body.action==='avatar')c.avatar={value:body.avatar,token};
    else c.pending.set(body.content_id,{...overlay,token});
    status('Guardando en tu cuenta…');emit();
    c.queue=c.queue.then(async()=>{
      if(!active(c))return;
      let failure=null;
      try{const data=await request(body,c.id);if(active(c))c.data=data;}catch(error){failure=error;}
      if(!active(c))return;
      if(body.action==='avatar'){if(c.avatar?.token===token)c.avatar=null;}
      else if(c.pending.get(body.content_id)?.token===token)c.pending.delete(body.content_id);
      status(failure?failure.message:c.pending.size||c.avatar?'Guardando en tu cuenta…':'Avatar y Mi lista sincronizados con tu cuenta.',!!failure);emit();
    });
    return true;
  }
  function saved(){
    if(!current||!active(current))return [];
    const rows=[...current.data.items];
    for(const [id,p] of current.pending){const index=rows.findIndex(r=>Number(r.id)===id);if(index>=0)rows.splice(index,1);if(p.saved)rows.unshift(p.item);}
    return rows;
  }
  function has(id){
    if(!current||!active(current))return false;
    return current.pending.get(Number(id))?.saved??current.data.saved_ids.includes(Number(id));
  }
  root.ProfileSync={message:'',error:false,enabled:()=>!!account(),refresh,saved,has,
    avatar:()=>current&&active(current)?current.avatar?.value||current.data.avatar:'tg',
    select:avatar=>change({action:'avatar',avatar}),
    toggle(item){const selected=!has(item.id);return change({action:'saved',content_id:Number(item.id),saved:selected},{item,saved:selected})?selected:has(item.id);}
  };
  root.ProfileSync.ready=root.AccountSession.ready.then(refresh);
  root.addEventListener('session-changed',()=>{if(current?.id!==account())refresh();});
  root.addEventListener('focus',refresh);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
  setInterval(()=>{if(!document.hidden&&account())refresh();},30000);
})(window);
