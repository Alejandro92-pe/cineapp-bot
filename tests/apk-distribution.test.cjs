const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const script=fs.readFileSync('static/pwa/apks.js','utf8');
const release=(kind='android')=>({version:'0.5.0',bytes:36907,minAndroid:8,sha256:'a'.repeat(64),url:`https://quehay.live/apps/QueHay-${kind==='android'?'Android':'TV'}-0.5.0.apk`});
const manifest=()=>({schema:1,published:true,releases:{android:release(),tv:release('tv')}});
async function load(data,{telegram=false,fail=false,origin='https://app.quehay.live'}={}){
  const elements={},calls={fetch:[],open:[]};
  for(const kind of ['android','tv'])for(const part of ['', '-info','-hash','-details','-pending'])elements[`apk-${kind}${part}`]={hidden:part!=='-pending',textContent:'',href:'',events:{},addEventListener(n,f){this.events[n]=f;}};
  const location=new URL(origin);
  const context={URL,location,document:{readyState:'complete',currentScript:{dataset:{}},getElementById:id=>elements[id]},window:{Telegram:{WebApp:{initData:telegram?'verified-context':'',openLink:(...args)=>calls.open.push(args)}}},fetch:async(...args)=>{calls.fetch.push(args);if(fail)throw Error('offline');return{ok:true,json:async()=>data};}};
  vm.runInNewContext(script,context);await new Promise(resolve=>setImmediate(resolve));return{elements,calls};
}
test('published manifest exposes two distinct downloads without downloading automatically',async()=>{
  const {elements:e,calls}=await load(manifest());
  assert.equal(e['apk-android'].hidden,false);assert.match(e['apk-android'].href,/Android/);
  assert.match(e['apk-tv'].href,/TV/);assert.equal(e['apk-android-pending'].hidden,true);
  assert.match(e['apk-android-info'].textContent,/37 KB/);assert.equal(e['apk-android-hash'].textContent,'a'.repeat(64));
  assert.equal(calls.fetch.length,1);assert.equal(calls.fetch[0][1].credentials,'omit');assert.equal(calls.fetch[0][1].cache,'no-store');assert.equal(calls.open.length,0);
});
test('unpublished, unsupported, broken and offline manifests keep honest unavailable state',async()=>{
  for(const data of [{...manifest(),published:false},{...manifest(),published:'true'},{...manifest(),schema:2},null]){
    const {elements:e}=await load(data);assert.equal(e['apk-android'].hidden,true);assert.equal(e['apk-android-pending'].hidden,false);
  }
  const {elements:e}=await load(manifest(),{fail:true});assert.equal(e['apk-tv'].hidden,true);
});
test('arbitrary hosts, local URLs in production, credentials, queries and wrong packages are rejected',async()=>{
  for(const url of ['javascript:alert(1)','https://evil.example/apps/QueHay-Android-0.5.0.apk','http://quehay.live/apps/QueHay-Android-0.5.0.apk','https://quehay.live.evil.example/apps/QueHay-Android-0.5.0.apk','https://user@quehay.live/apps/QueHay-Android-0.5.0.apk',release().url+'?token=x',release().url+'#x','https://quehay.live/apps/QueHay-TV-0.5.0.apk','http://127.0.0.1:5031/static/_design-preview/distribution/apps/QueHay-Android-0.5.0.apk']){
    const data=manifest();data.releases.android.url=url;const {elements:e}=await load(data);assert.equal(e['apk-android'].hidden,true,url);assert.equal(e['apk-tv'].hidden,false);
  }
});
test('invalid versions, hash and sizes never become HTML or download links',async()=>{
  for(const patch of [{version:'<img onerror=alert(1)>'},{sha256:'invalid'},{bytes:-1},{bytes:NaN},{minAndroid:'<b>8</b>'}]){
    const data=manifest();Object.assign(data.releases.android,patch);const {elements:e}=await load(data);assert.equal(e['apk-android'].hidden,true);
  }
});
test('Telegram opens the official file only on click; ordinary browser retains its anchor',async()=>{
  const {elements:e,calls}=await load(manifest(),{telegram:true});let prevented=false;
  e['apk-android'].events.click({preventDefault(){prevented=true;}});
  assert.equal(prevented,true);assert.equal(calls.open[0][0],release().url);assert.equal(calls.open[0][1].try_instant_view,false);
  const browser=await load(manifest());browser.elements['apk-tv'].events.click({preventDefault(){throw Error('should retain normal link');}});assert.equal(browser.calls.open.length,0);
});
test('a local preview may use only its own exact APK path',async()=>{
  const data=manifest();data.releases.android.url='http://127.0.0.1:5031/static/_design-preview/distribution/apps/QueHay-Android-0.5.0.apk';
  const {elements:e}=await load(data,{origin:'http://127.0.0.1:5031'});assert.equal(e['apk-android'].hidden,false);
  data.releases.android.url=data.releases.android.url.replace('5031','5010');assert.equal((await load(data,{origin:'http://127.0.0.1:5031'})).elements['apk-android'].hidden,true);
});
