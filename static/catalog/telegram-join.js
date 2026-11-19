/* Shows the header's "Únete a Telegram" on the web only: never in the Android app, never inside
   Telegram's own Mini App (the person is already in Telegram), and the TV has its own pages. */
(function(){
  'use strict';
  function insideTelegram(){
    const tg=window.Telegram?.WebApp;
    // initData is only filled inside Telegram; the launch hash covers a slow-loading Telegram script.
    return Boolean(tg?.initData)||/[#&]tgWebApp(Data|Platform)=/.test(location.hash)||Boolean(tg?.platform&&tg.platform!=='unknown');
  }
  function setup(){
    const link=document.getElementById('telegramJoin');
    if(!link)return;
    const android=/\bQueHayAndroid\//.test(navigator.userAgent)||document.documentElement.classList.contains('quehay-android');
    if(android||insideTelegram()){link.remove();return;}
    link.hidden=false;
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup,{once:true});else setup();
})();
