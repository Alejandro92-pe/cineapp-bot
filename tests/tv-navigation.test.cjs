const {test}=require('node:test');const assert=require('node:assert/strict');
const {pick}=require('../tv/static/navigation.js');
const rows=[[{id:'home',x:20},{id:'account',x:800}],[{id:'hero',x:80}],[{id:'card1',x:80},{id:'card2',x:220},{id:'card3',x:380}],[{id:'season',x:80}]];
test('remote keeps boundaries and chooses nearest item vertically',()=>{
 assert.equal(pick(rows,'card2','ArrowRight'),'card3');assert.equal(pick(rows,'card3','ArrowRight'),'card3');
 assert.equal(pick(rows,'card2','ArrowUp'),'hero');assert.equal(pick(rows,'hero','ArrowDown'),'card1');
 assert.equal(pick(rows,'card3','ArrowDown'),'season');assert.equal(pick(rows,'home','ArrowUp'),'home');
});
test('a disappeared focused item recovers to the first control',()=>{assert.equal(pick(rows,'deleted','ArrowDown'),'home');assert.equal(pick([],'deleted','ArrowDown'),undefined);});
