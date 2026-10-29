/* Progressive, remote-friendly loading. Requests remain bounded by the server. */
(function(root){
 class Pager {
  constructor(initial,load,valid=()=>true){this.data={...initial,items:[...initial.items]};this.load=load;this.valid=valid;this.pending=null;}
  more(){
   if(this.pending)return this.pending;
   if(!this.data.has_next||!this.valid())return Promise.resolve([]);
   this.pending=(async()=>{const next=await this.load(this.data.page+1);if(!this.valid())return [];
    const ids=new Set(this.data.items.map(x=>x.id));const added=next.items.filter(x=>!ids.has(x.id)&&ids.add(x.id));
    this.data={...next,items:[...this.data.items,...added],has_next:Boolean(next.has_next&&added.length)};return added;
   })().finally(()=>{this.pending=null;});return this.pending;
  }
 }
 let uid=0;
 function mount({container,initial,load,append,valid=()=>true,horizontal=false,columns=6,onChange=()=>{}}){
  const pager=new Pager(initial,load,valid),marker=document.createElement('div');
  marker.className='stream-status';marker.setAttribute('role','status');container.append(marker);
  let disposed=false,failed=false,intent=null;
  const live=()=>!disposed&&container.isConnected&&valid();pager.valid=live;
  const cards=()=>[...container.querySelectorAll('[data-title],[data-episode]')];
  async function more(manual=false){
   if(!live()||!pager.data.has_next||(failed&&!manual))return;
   const retryFocused=manual&&marker.contains(document.activeElement),previousCount=cards().length;
   marker.textContent='Cargando…';marker.setAttribute('aria-busy','true');
   try{const added=await pager.more();if(!live())return;
    if(added.length){append(added,marker);onChange(pager.data);}failed=false;marker.replaceChildren();
    if(retryFocused){const all=cards();root.TVFocus.focus(all[previousCount]||all.at(-1));}
    if(intent){const wanted=intent;intent=null;if(document.activeElement===wanted.anchor){const all=cards();root.TVFocus.focus(all[wanted.index]||all.at(-1));}}
   }catch(e){if(!live())return;failed=true;marker.replaceChildren();const b=document.createElement('button');b.dataset.nav='';b.id='stream-retry-'+(++uid);b.textContent='Reintentar carga';b.onclick=()=>request(true);marker.append(b);if(intent&&document.activeElement===intent.anchor){root.TVFocus.focus(b);}intent=null;
   }finally{marker.removeAttribute('aria-busy');}
  }
  // A shared in-flight promise must be rendered only once even under rapid keys.
  let running=null;const request=(manual=false)=>{if(running)return running;running=more(manual).finally(()=>{running=null;});return running;};
  function focused(e){const all=cards(),i=all.indexOf(e.target);if(i>=Math.max(0,all.length-(horizontal?2:columns)))request();}
  function keyed(e){if(e.key!==(horizontal?'ArrowRight':'ArrowDown'))return;const all=cards(),i=all.indexOf(e.target);
   if(i<0||!pager.data.has_next)return;
   if(horizontal?i===all.length-1:i>=all.length-columns){e.preventDefault();e.stopPropagation();intent={anchor:e.target,index:horizontal?i+1:i+columns};request(true);}
  }
  container.addEventListener('focusin',focused);container.addEventListener('keydown',keyed,true);
  const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting))request();},{root:horizontal?container:null,rootMargin:horizontal?'0px 120px':'180px 0px'});
  if(pager.data.has_next)observer.observe(marker);
  return {pager,dispose(){disposed=true;observer.disconnect();container.removeEventListener('focusin',focused);container.removeEventListener('keydown',keyed,true);}};
 }
 const api={Pager,mount};if(typeof module==='object')module.exports=api;if(root.document)root.TVStream=api;
})(typeof window!=='undefined'?window:globalThis);
