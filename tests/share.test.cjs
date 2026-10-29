const {test}=require('node:test');
const assert=require('node:assert/strict');
const {payload,telegramLink,share}=require('../static/catalog/share.js');
const item={id:675,titulo:'La casa del dragón',año:2022};
test('shares exact public title URL, without session or bot parameters',()=>{
  assert.deepEqual(payload(item),{title:item.titulo,text:'🎬 Mira «La casa del dragón» (2022) en Qué Hay Cine.',url:'https://app.quehay.live/?contenido=675'});
  assert.equal(payload({...item,id:'675&token=secret'}),null);
  assert.equal(payload(null),null);
});
test('Telegram encodes accented titles, ampersands and the URL once',()=>{
  const data=payload({...item,titulo:'Tú & yo #1'}),url=new URL(telegramLink(data));
  assert.equal(url.searchParams.get('url'),data.url);assert.equal(url.searchParams.get('text'),data.text);
});
test('APK uses native adapter before browser sharing',async()=>{
  let sent;assert.equal(await share(item,{QueHayAndroidUI:{share:d=>sent=d},navigator:{share:()=>assert.fail('browser called')}}),'android');
  assert.equal(sent.url,payload(item).url);
});
test('Telegram opens chat selection, without copying or sending automatically',async()=>{
  let sent;assert.equal(await share(item,{Telegram:{WebApp:{initData:'signed',openTelegramLink:url=>sent=url}}}),'telegram');
  assert.equal(sent,telegramLink(payload(item)));
});
test('browser receives name, promotional text and deep link',async()=>{
  let sent;assert.equal(await share(item,{navigator:{share:async data=>sent=data}}),'native');assert.deepEqual(sent,payload(item));
});
test('cancelling native share does not copy or show another dialog',async()=>{
  assert.equal(await share(item,{navigator:{share:async()=>{throw {name:'AbortError'};}},shareFallback:()=>assert.fail('fallback called')}),'cancelled');
});
test('unsupported or denied native sharing offers explicit alternatives',async()=>{
  for(const navigator of [{},{share:async()=>{throw {name:'NotAllowedError'};}}]){
    let shown;assert.equal(await share(item,{navigator,shareFallback:d=>shown=d}),'fallback');assert.deepEqual(shown,payload(item));
  }
});
