const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

function setup(telegram=false) {
  const elements=[];const calls=[];
  const document={getElementById:()=>null,body:{append(node){elements.push(node);}},createElement(tag){return {tag,style:{},children:[],append(...nodes){this.children.push(...nodes);},showModal(){this.open=true;},close(){this.open=false;}};}};
  const context={document,URL,location:{origin:'http://127.0.0.1:5010'},window:{AccessSupport:{handle:()=>false},Telegram:{WebApp:{initData:telegram?'signed-data':'',openLink(...args){calls.push(args);}}}},navigator:{clipboard:{writeText:async()=>{}}},alert:message=>calls.push(message)};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync('static/escape.js','utf8'),context);
  vm.runInContext(fs.readFileSync('static/downloads.js','utf8'),context);
  return {context,elements,calls};
}

test('MediaFire opens through Telegram openLink with instant view disabled',()=>{
  const {context,elements,calls}=setup(true);
  context.mostrarEnlaceExterno('https://www.mediafire.com/file/example/file');
  const link=elements[0].children[2];
  let prevented=false;
  link.onclick({preventDefault(){prevented=true;}});
  assert.equal(prevented,true);assert.equal(calls[0][0],link.href);assert.equal(calls[0][1].try_instant_view,false);
});
test('Normal browser receives an explicit HTTPS link with opener isolation',()=>{
  const {context,elements}=setup();
  context.mostrarEnlaceExterno('https://downloads.example.org/file');
  const link=elements[0].children[2];
  assert.equal(link.target,'_blank');assert.equal(link.rel,'noopener noreferrer');
  let prevented=false;link.onclick({preventDefault(){prevented=true;}});assert.equal(prevented,false);
});
test('Non-HTTPS downloads are rejected before creating UI',()=>{
  const {context,elements}=setup();
  assert.throws(()=>context.mostrarEnlaceExterno('javascript:alert(1)'));
  assert.equal(elements.length,0);
});
test('Expired session never opens a provider URL',async()=>{
  const {context,elements,calls}=setup();
  context.fetch=async()=>({ok:false,json:async()=>({error:'Acceso vencido'})});
  await context.prepararDescarga(1);
  assert.equal(elements.length,0);assert.equal(calls[0],'Acceso vencido');
});
test('HTML encoded JSON preserves malicious-looking text without executable injection',()=>{
  const {context}=setup();
  const title=`O'Brien </div><img src=x onerror="globalThis.pwned=true">`;
  const encoded=context.jsonAttr({titulo:title});
  assert(!encoded.includes("'"));assert(!encoded.includes('<'));assert(!encoded.includes('"'));
  const decoded=encoded.replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');
  context.capture=value=>assert.equal(value.titulo,title);
  vm.runInContext(`capture(${decoded})`,context);
  assert.equal(context.pwned,undefined);
});
test('Injected image attributes are encoded and script URLs are rejected',()=>{
  const {context}=setup();
  assert.equal(context.safeImageUrl('javascript:alert(1)'),'/static/placeholder.svg');
  assert(!context.safeImageUrl('https://example.org/a" onerror="bad').includes('"'));
});
test('DOM image source preserves query parameters while HTML attributes remain escaped',()=>{
  const {context}=setup();
  const url='https://images.example.org/poster?w=400&lang=es';
  assert.equal(context.safeImageSrc(url),url);
  assert.equal(context.safeImageUrl(url),'https://images.example.org/poster?w=400&amp;lang=es');
  assert.equal(context.safeImageSrc('javascript:alert(1)'),'/static/placeholder.svg');
});
