/* Directional navigation is isolated from the web and mobile application. */
(function(root){
 function pick(rows,current,key){
  let row=rows.findIndex(r=>r.some(e=>e.id===current));if(row<0)return rows[0]?.[0]?.id;
  const col=rows[row].findIndex(e=>e.id===current),item=rows[row][col];
  if(key==='ArrowLeft'||key==='ArrowRight')return rows[row][col+(key==='ArrowRight'?1:-1)]?.id||current;
  const target=rows[row+(key==='ArrowDown'?1:-1)];if(!target)return current;
  return target.reduce((best,e)=>Math.abs(e.x-item.x)<Math.abs(best.x-item.x)?e:best,target[0]).id;
 }
 if(typeof module==='object')module.exports={pick};
 if(!root.document)return;
 let uid=0;const doc=root.document;
 function scope(){return doc.querySelector('dialog[open]')||(!doc.getElementById('player').hidden?doc.getElementById('player'):doc.body);}
 function elements(){return [...scope().querySelectorAll('[data-nav]')].filter(e=>!e.disabled&&e.getClientRects().length&&!e.closest('[hidden]'));}
 function focus(e){if(!e)return;elements().forEach(x=>x.tabIndex=-1);e.tabIndex=0;e.focus({preventScroll:true});if(!e.closest('.topbar'))e.scrollIntoView({block:'nearest',inline:'nearest',behavior:'instant'});}
 root.TVFocus={focus,first:()=>focus(elements()[0])};
 doc.addEventListener('focusin',e=>{if(e.target.matches('[data-nav]')){elements().forEach(x=>x.tabIndex=x===e.target?0:-1);}});
 doc.addEventListener('keydown',e=>{
  if(e.altKey||e.ctrlKey||e.metaKey)return;
  const edit=e.target.matches('input,textarea');
  if(['Escape','BrowserBack','GoBack'].includes(e.key)||(e.key==='Backspace'&&!edit)){
   if(root.TVBack?.()){e.preventDefault();e.stopPropagation();}return;
  }
  if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;
  if(edit&&['ArrowLeft','ArrowRight'].includes(e.key))return;
  e.preventDefault();const els=elements();const rows=[];let last=null;
  els.forEach(el=>{if(!el.id)el.id='tv-focus-'+(++uid);const group=el.closest('[data-row]')||el.parentElement;
   if(group!==last){rows.push([]);last=group;}const r=el.getBoundingClientRect();rows.at(-1).push({id:el.id,x:r.x+r.width/2});});
  const id=pick(rows,doc.activeElement?.id,e.key);focus(els.find(x=>x.id===id));
 });
})(typeof window!=='undefined'?window:globalThis);
