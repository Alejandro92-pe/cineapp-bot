import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';

function setup(changeAccount=false){
 let reads=0,writes=0;const events=[];
 const identity=(id,token)=>({authenticated:true,user:{id},csrf_token:token,is_admin:false});
 const ctx={URL,Headers,Request,Event,location:{href:'https://cine.test/',origin:'https://cine.test'},
  document:{addEventListener(){}},dispatchEvent:e=>events.push(e.type),
  fetch:async(url,options)=>{
   if(url==='/api/auth/me')return Response.json(identity(reads++&&changeAccount?'B':'A',reads===1?'old':'new'));
   writes++;return options.headers.get('X-CSRF-Token')==='new'?Response.json({ok:true}):Response.json({code:'csrf_refresh_required'},{status:403});
  }};
 ctx.window=ctx;vm.createContext(ctx);vm.runInContext(fs.readFileSync('static/session.js','utf8'),ctx);
 return {ctx,counts:()=>({reads,writes}),events};
}
test('stale tab refreshes CSRF once and replays only a rejected action for the same account',async()=>{
 const {ctx,counts}=setup();await ctx.AccountSession.ready;
 const response=await ctx.fetch('/api/playback/1',{method:'POST',body:'{}'});
 assert.equal(response.status,200);assert.deepEqual(counts(),{reads:2,writes:2});
});
test('a change of account in another tab never replays the previous account action',async()=>{
 const {ctx,counts}=setup(true);await ctx.AccountSession.ready;
 assert.equal((await ctx.fetch('/api/playback/1',{method:'POST',body:'{}'})).status,403);
 assert.deepEqual(counts(),{reads:2,writes:1});assert.equal(ctx.AccountSession.state.user.id,'B');
});
