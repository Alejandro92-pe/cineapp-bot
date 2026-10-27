const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const {reason}=require('../static/support/access.js');
test('membership gate distinguishes guests, inactive members and real technical failures',()=>{
 assert.equal(reason({status:401},{}),'guest');assert.equal(reason({status:403},{code:'membership_required'}),'member');
 assert.equal(reason({status:403},{error:'CSRF'}),null);assert.equal(reason({status:503},{}),null);assert.equal(reason({status:200},{}),null);
});
for(const episode of [false,true])for(const status of [401,403,200])test(`${episode?'episode':'movie'} download ${status} uses shared support gate or authorized link`,async()=>{
 const supports=[],links=[],alerts=[];const window={AccessSupport:{handle:(r,p)=>{const kind=reason(r,p);if(kind)supports.push(kind);return !!kind;}}};
 const context={window,fetch:async()=>({status,ok:status===200,json:async()=>({code:'membership_required',url:'https://www.mediafire.com/file/manual/file'})}),alert:m=>alerts.push(m),mostrarEnlaceExterno:u=>links.push(u)};
 vm.createContext(context);vm.runInContext(fs.readFileSync(episode?'static/catalog/episode-downloads.js':'static/downloads.js','utf8'),context);
 if(!episode)context.mostrarEnlaceExterno=u=>links.push(u);
 if(episode)await window.EpisodeDownloads.download(1,2);else await context.prepararDescarga(1);
 assert.equal(alerts.length,0);assert.equal(links.length,status===200?1:0);assert.equal(supports.length,status===200?0:1);
});
