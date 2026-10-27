const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
function setup(){
 const saved=new Map([['avatar_5824989040','cat']]);
 const state={user:{id:'account-a',telegram_id:5824989040,name:'Ale'}};
 const window={dispatchEvent(){},Telegram:{WebApp:{initDataUnsafe:{user:{id:5824989040,photo_url:'https://example.org/photo.jpg'}}}}};
 const document={createElement:tag=>({tag})};
 const context={AccountSession:{state},window,document,URL,Event:class {},localStorage:{getItem:k=>saved.get(k),setItem:(k,v)=>saved.set(k,v)}};
 vm.runInNewContext(fs.readFileSync('static/profile/avatars.js','utf8'),context);
 const container={children:[],replaceChildren(){this.children=[];this.innerHTML='';this.textContent='';},append(node){this.children.push(node);}};
 return {profile:window.ProfileAvatars,state,window,container};
}
test('restores existing Telegram avatar key and all eight original choices',()=>{
 const {profile}=setup();assert.equal(profile.selected(),'cat');assert.equal(profile.options.length,8);
});
test('avatar choices remain isolated between accounts',()=>{
 const {profile,state}=setup();profile.select('fox');state.user={id:'account-b',name:'B'};assert.equal(profile.selected(),'tg');profile.select('robot');state.user={id:'account-a',telegram_id:5824989040};assert.equal(profile.selected(),'fox');
});
test('unknown avatar never reaches local storage or markup',()=>{
 const {profile}=setup();profile.select('<img onerror=alert(1)>');assert.equal(profile.selected(),'cat');
});
test('Telegram photo requires matching verified account and HTTPS',()=>{
 const {profile,state,window,container}=setup();profile.render(container,'tg');assert.equal(container.children[0].src,'https://example.org/photo.jpg');
 window.Telegram.WebApp.initDataUnsafe.user.photo_url='javascript:alert(1)';profile.render(container,'tg');assert.equal(container.children.length,0);assert.equal(container.textContent,'A');
 state.user.telegram_id=111;window.Telegram.WebApp.initDataUnsafe.user.photo_url='https://example.org/photo.jpg';profile.render(container,'tg');assert.equal(container.children.length,0);
});
