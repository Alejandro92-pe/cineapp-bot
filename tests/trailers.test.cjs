const {test}=require('node:test');const assert=require('node:assert/strict');
const {embed}=require('../static/catalog/trailers.js');
test('trailer accepts real YouTube URLs and uses the allowlisted embed origin',()=>{
 for(const value of ['https://www.youtube.com/watch?v=abcdefghijk','https://youtu.be/abcdefghijk','https://www.youtube.com/embed/abcdefghijk'])assert.match(embed(value),/^https:\/\/www.youtube-nocookie.com\/embed\/abcdefghijk\?/);
});
test('trailer rejects lookalike hosts, credentials, unsafe schemes and malformed ids',()=>{
 for(const value of ['https://evil.example/youtube.com/watch?v=abcdefghijk','http://youtube.com/watch?v=abcdefghijk','https://user@youtube.com/watch?v=abcdefghijk','https://youtube.com/watch?v=short','javascript:alert(1)'])assert.equal(embed(value),null);
});
