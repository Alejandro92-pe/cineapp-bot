/* TV-only reading panel. Text stays complete; the collapsed height is visual. */
window.TVSynopsis = (()=>{
  let current=null,dialog=null,opener=null;
  function markup(text,esc,{id,title='',className='cinema-synopsis',pending=false}={}){
    return `<div class="synopsis-block" data-row="synopsis" data-reader-title="${esc(title)}"><p id="${id}" class="${className} synopsis-excerpt">${esc(text)}</p>${pending?'':`<button data-nav type="button" class="synopsis-more" aria-haspopup="dialog" aria-controls="synopsis-dialog" aria-expanded="false" hidden>Ver más <span aria-hidden="true">＋</span></button>`}</div>`;
  }
  function close(restore=true){
    if(!dialog?.open)return false;
    dialog.close();opener?.setAttribute('aria-expanded','false');
    // Roving tabindex is updated by navigation's focusin listener. Avoid its
    // scrollIntoView here: returning from reading must not shift the ficha.
    if(restore&&opener?.isConnected){opener.tabIndex=0;opener.focus({preventScroll:true});}
    opener=null;return true;
  }
  function open(block,button){
    if(!dialog){
      dialog=document.createElement('dialog');dialog.id='synopsis-dialog';
      dialog.setAttribute('aria-labelledby','synopsis-reader-title');
      dialog.innerHTML='<p class="eyebrow">LA HISTORIA</p><h2 id="synopsis-reader-title"></h2><div data-row="reader-text"><div id="synopsis-reader-copy" data-nav tabindex="0" role="region" aria-label="Sinopsis completa"></div></div><div class="reader-actions" data-row="reader-actions"><button data-nav id="synopsis-reader-close">Volver a la ficha</button><span>↑ ↓ Leer · Volver para cerrar</span></div>';
      document.body.append(dialog);
      dialog.querySelector('button').onclick=()=>close();
      dialog.addEventListener('cancel',e=>{e.preventDefault();close();});
      dialog.addEventListener('keydown',e=>{
        if(!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.key))return;
        e.preventDefault();e.stopPropagation();
        const copy=dialog.querySelector('#synopsis-reader-copy'),back=dialog.querySelector('button');
        if(document.activeElement===copy){
          if(e.key==='ArrowLeft'||e.key==='ArrowRight')window.TVFocus.focus(back);
          else copy.scrollBy({top:(e.key==='ArrowDown'?1:-1)*copy.clientHeight*.65,behavior:'instant'});
        }else window.TVFocus.focus(copy);
      });
    }
    opener=button;button.setAttribute('aria-expanded','true');
    dialog.querySelector('h2').textContent=block.dataset.readerTitle||'Sinopsis';
    const copy=dialog.querySelector('#synopsis-reader-copy');
    copy.textContent=block.querySelector('.synopsis-excerpt').textContent;
    dialog.showModal();copy.scrollTop=0;window.TVFocus.focus(dialog.querySelector('button'));
  }
  function mount(scope){
    current?.dispose();
    let frame=0,disposed=false;
    const observed=new Set();
    const observer=typeof ResizeObserver==='function'?new ResizeObserver(refresh):null;
    function refresh(){
      if(disposed)return;
      cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{
        observed.forEach(el=>{if(!scope.contains(el)){observer?.unobserve(el);observed.delete(el);}});
        scope.querySelectorAll('.synopsis-block').forEach(block=>{
          const text=block.querySelector('.synopsis-excerpt'),button=block.querySelector('.synopsis-more');
          if(!button||!text)return;
          if(!observed.has(text)){observed.add(text);observer?.observe(text);}
          if(!text.getClientRects().length)return;
          const overflow=text.scrollHeight>text.clientHeight+1;
          // Keep a focused control reachable if resizing removes the overflow.
          button.hidden=!overflow&&document.activeElement!==button;
        });
      });
    }
    function click(e){const button=e.target.closest('.synopsis-more');if(button&&scope.contains(button))open(button.closest('.synopsis-block'),button);}
    scope.addEventListener('click',click);window.addEventListener('resize',refresh);
    function dispose(){disposed=true;cancelAnimationFrame(frame);observer?.disconnect();observed.clear();scope.removeEventListener('click',click);window.removeEventListener('resize',refresh);close(false);if(current?.dispose===dispose)current=null;}
    current={refresh,dispose};refresh();return dispose;
  }
  function update(block,text,title){
    if(!block)return;
    block.querySelector('.synopsis-excerpt').textContent=text;
    block.dataset.readerTitle=title;
    current?.refresh();
  }
  return {markup,mount,update,refresh:()=>current?.refresh(),close};
})();
