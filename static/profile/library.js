/* Per-account browser library, compatible with existing favourite keys. */
(function(root){
 const identity=()=>root.AccountSession?.state.user?.telegram_id||root.AccountSession?.state.user?.id||'guest';
 const key=kind=>`${kind}_${identity()}`;
 function read(kind){try{const rows=JSON.parse(localStorage.getItem(key(kind))||'[]');return Array.isArray(rows)?rows.filter(r=>r&&typeof r==='object'&&r.id!=null):[];}catch{return [];}}
 function write(kind,rows){try{localStorage.setItem(key(kind),JSON.stringify(rows));}catch{return false;}root.dispatchEvent(new Event('library-changed'));return true;}
 function saved(){return root.ProfileSync?.enabled()?root.ProfileSync.saved():read('favs');}
 function toggle(item){if(root.ProfileSync?.enabled())return root.ProfileSync.toggle(item);const rows=read('favs'),index=rows.findIndex(r=>String(r.id)===String(item.id));if(index>=0)rows.splice(index,1);else rows.unshift(item);write('favs',rows.slice(0,200));return index<0;}
 function opened(item,selection={}){const row={...item,opened_at:Date.now(),last_episode:selection.episode?.id||null,last_season:selection.season?.id||null};write('hist',[row,...read('hist').filter(r=>String(r.id)!==String(item.id))].slice(0,50));}
 root.AccountLibrary={saved,recent:()=>read('hist'),toggle,opened,has:id=>root.ProfileSync?.enabled()?root.ProfileSync.has(id):saved().some(r=>String(r.id)===String(id)),removeRecent:id=>write('hist',read('hist').filter(r=>String(r.id)!==String(id)))};
})(window);
