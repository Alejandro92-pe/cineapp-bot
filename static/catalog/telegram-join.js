/* Shows the header's "Únete a Telegram" on the web; never in the Android app (or TV, which has its own pages). */
(function(){
  'use strict';
  function setup(){
    const link=document.getElementById('telegramJoin');
    if(!link)return;
    const android=/\bQueHayAndroid\//.test(navigator.userAgent)||document.documentElement.classList.contains('quehay-android');
    if(android){link.remove();return;}
    link.hidden=false;
    // Inside the Telegram Mini App, open the channel natively instead of a browser tab.
    link.addEventListener('click',event=>{
      const tg=window.Telegram?.WebApp;
      if(tg?.initData&&typeof tg.openTelegramLink==='function'){event.preventDefault();tg.openTelegramLink(link.href);}
    });
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup,{once:true});else setup();
})();
