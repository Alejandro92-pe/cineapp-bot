// The "Únete a Telegram" header link shows on the web only.
const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function run({ua='Mozilla/5.0 Chrome',hash='',webapp=null,android=false}={}){
 const link={hidden:true,removed:false,remove(){this.removed=true;}};
 const window={Telegram:webapp?{WebApp:webapp}:undefined};
 const context={window,navigator:{userAgent:ua},location:{hash},document:{readyState:'complete',getElementById:id=>id==='telegramJoin'?link:null,
  documentElement:{classList:{contains:c=>android&&c==='quehay-android'}}}};
 vm.runInNewContext(fs.readFileSync('static/catalog/telegram-join.js','utf8'),context);
 return link;
}
test('shows in a normal browser, even with the Telegram script loaded but outside Telegram',()=>{
 assert.equal(run().hidden,false);
 assert.equal(run({webapp:{initData:'',platform:'unknown'}}).hidden,false);
});
test('removed inside the Telegram Mini App',()=>{
 assert.equal(run({webapp:{initData:'query_id=1&user=%7B%7D',platform:'android'}}).removed,true);
 assert.equal(run({hash:'#tgWebAppData=abc&tgWebAppPlatform=ios'}).removed,true);
 assert.equal(run({webapp:{initData:'',platform:'tdesktop'}}).removed,true);
});
test('removed in the Android app',()=>{
 assert.equal(run({ua:'Mozilla/5.0 Chrome QueHayAndroid/0.5.1'}).removed,true);
 assert.equal(run({android:true}).removed,true);
});
