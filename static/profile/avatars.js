/* Original avatars shared by account and catalogue. */
(() => {
const options = [
  { id: 'fox',    emoji: null, svg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4 2l2 4H2L4 2zm16 0l2 4h-4l2-4zM12 4C7 4 3 8 3 13c0 3.3 1.8 6.2 4.5 7.8L7 23h10l-.5-2.2C19.2 19.2 21 16.3 21 13c0-5-4-9-9-9zm-3 8a1.5 1.5 0 110 3 1.5 1.5 0 010-3zm6 0a1.5 1.5 0 110 3 1.5 1.5 0 010-3zm-3 4c-1.1 0-2-.4-2.7-1h5.4c-.7.6-1.6 1-2.7 1z"/></svg>' },
  { id: 'wolf',   emoji: null, svg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M2 3l3 6H2l4 5v3c2 1 4 1.5 6 1.5s4-.5 6-1.5v-3l4-5h-3l3-6-5 3c-1-.3-2-.5-5-.5s-4 .2-5 .5L2 3zm10 10a1 1 0 110 2 1 1 0 010-2z"/></svg>' },
  { id: 'dragon', emoji: null, svg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M16.5 6.5C15.8 4.2 14 2 12 2 9 2 7 4.5 7 7c0 1 .3 2 .7 2.8C6 11 5 13 5 15c0 3.9 3.1 7 7 7s7-3.1 7-7c0-2-.8-3.8-2-5.1l-.5-.4zM12 19c-2.2 0-4-1.8-4-4 0-1 .4-2 1-2.7.6.4 1.3.7 2 .7s1.4-.3 2-.7c.6.7 1 1.7 1 2.7 0 2.2-1.8 4-4 4z"/></svg>' },
  { id: 'ghost',  emoji: null, svg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a9 9 0 00-9 9v11l3-3 3 3 3-3 3 3 3-3v-11a9 9 0 00-9-9zm-3 9a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm6 0a1.5 1.5 0 110-3 1.5 1.5 0 010 3z"/></svg>' },
  { id: 'cat',    emoji: null, svg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M2 4v5l2 2c0 5 4 9 8 9s8-4 8-9l2-2V4l-4 3c-1-.5-2-.8-3-1l-1-2h-4l-1 2c-1 .2-2 .5-3 1L2 4zm7 7a1 1 0 110 2 1 1 0 010-2zm6 0a1 1 0 110 2 1 1 0 010-2zm-3 3c-1 0-1.7-.4-2.2-1h4.4c-.5.6-1.2 1-2.2 1z"/></svg>' },
  { id: 'alien',  emoji: null, svg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C8.1 2 5 5.8 5 10.5c0 2.1.7 4 1.8 5.5L8 22h8l1.2-6c1.1-1.5 1.8-3.4 1.8-5.5C19 5.8 15.9 2 12 2zm-2.5 8a1.5 1.5 0 110 3 1.5 1.5 0 010-3zm5 0a1.5 1.5 0 110 3 1.5 1.5 0 010-3zm-2.5 5c-2 0-3-.8-3-.8s1-.2 3-.2 3 .2 3 .2-1 .8-3 .8z"/></svg>' },
  { id: 'robot',  emoji: null, svg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a2 2 0 012 2v1h3a2 2 0 012 2v10a2 2 0 01-2 2H7a2 2 0 01-2-2V7a2 2 0 012-2h3V4a2 2 0 012-2zM9 9a1.5 1.5 0 100 3 1.5 1.5 0 000-3zm6 0a1.5 1.5 0 100 3 1.5 1.5 0 000-3zm-5 5h4v1H10v-1z"/></svg>' },
  { id: 'ninja',  emoji: null, svg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C8 2 5 5 5 9c0 2.4 1.2 4.5 3 5.7V22h8v-7.3C17.8 13.5 19 11.4 19 9c0-4-3-7-7-7zm-2 8a1 1 0 110 2 1 1 0 010-2zm4 0a1 1 0 110 2 1 1 0 010-2zm-2 3c-.8 0-1.5-.3-2-.7h4c-.5.4-1.2.7-2 .7z"/></svg>' },
];

const labels={tg:'Mi foto o inicial',fox:'Zorro',wolf:'Lobo',dragon:'Dragón',ghost:'Fantasma',cat:'Gato',alien:'Alien',robot:'Robot',ninja:'Ninja'};
const key=()=>`avatar_${AccountSession.state.user?.telegram_id || AccountSession.state.user?.id || 'guest'}`;
function selected(){if(window.ProfileSync?.enabled())return window.ProfileSync.avatar();try{return localStorage.getItem(key())||'tg';}catch{return 'tg';}}
function select(id){if(id!=='tg'&&!options.some(o=>o.id===id))return;if(window.ProfileSync?.enabled()){window.ProfileSync.select(id);return;}try{localStorage.setItem(key(),id);}catch{}window.dispatchEvent(new Event('avatar-changed'));}
function render(container,id=selected()){
 if(!container)return;container.replaceChildren();const option=options.find(o=>o.id===id);
 if(option){container.innerHTML=option.svg;return;}
 const user=AccountSession.state.user;
 const tg=window.Telegram?.WebApp?.initDataUnsafe?.user;
 if(user?.telegram_id===tg?.id && tg?.photo_url){try{const url=new URL(tg.photo_url);if(url.protocol==='https:'){const img=document.createElement('img');img.src=url.href;img.alt='Mi avatar';container.append(img);return;}}catch{}}
 container.textContent=(user?.name||'U')[0].toUpperCase();
}
function picker(container,preview){
 container.replaceChildren();for(const id of ['tg',...options.map(o=>o.id)]){
 const b=document.createElement('button');b.type='button';b.className='profile-choice';b.title=labels[id];b.setAttribute('aria-label',labels[id]);b.setAttribute('aria-pressed',String(selected()===id));render(b,id);
 b.onclick=()=>{select(id);picker(container,preview);};container.append(b);
 }render(preview);
}
window.ProfileAvatars={options,key,selected,select,render,picker};
})();
