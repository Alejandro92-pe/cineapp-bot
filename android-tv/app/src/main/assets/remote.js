/* Native D-pad events are handled only in our document, never inside providers. */
(function(){
 window.QueHayTVRemote=function(key,up){
  const el=document.activeElement;
  if(!el || el.tagName==='IFRAME' || el.matches('input,textarea,[contenteditable=true]'))return false;
  if(up)return true;
  if(key==='Enter'){
   if(el.matches('[data-nav]')&&!el.disabled){el.click();return true;}
   window.TVFocus?.first();return true;
  }
  const event=new KeyboardEvent('keydown',{key,bubbles:true,cancelable:true});el.dispatchEvent(event);
  return event.defaultPrevented;
 };
})();
