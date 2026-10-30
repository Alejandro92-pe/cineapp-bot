const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm'),fs=require('node:fs');
const context={window:{}};
vm.runInNewContext(fs.readFileSync(require.resolve('../tv/static/synopsis.js'),'utf8'),context);
vm.runInNewContext(fs.readFileSync(require.resolve('../tv/static/detail.js'),'utf8'),context);
const detail=context.window.TVDetail;
const esc=s=>String(s??'').replaceAll('<','&lt;').replaceAll('"','&quot;');
function pending(fields){return detail.pending({titulo:'Historia',imagen_url:'poster',backdrop_url:'background',...fields},esc,esc,()=>'<div class="meta"></div>');}
for(const fields of [{tipo:'serie'},{tipo:'anime',format:'movies'},{tipo:'biblico',format:'series'},{tipo:'biblico',tmdb_media:'tv'}]){
  test('episodic pending layout has no movie poster: '+JSON.stringify(fields),()=>{
    const html=pending(fields);
    assert.match(html,/detail-pending detail-series/);
    assert.match(html,/series-atmosphere/);
    assert.doesNotMatch(html,/cinema-poster|id="detail-play"/);
    assert.match(html,/id="detail-back"/);
  });
}
for(const fields of [{tipo:'pelicula'},{tipo:'biblico',format:'movies'}]){
  test('movie pending layout preserves poster: '+JSON.stringify(fields),()=>{
    const html=pending(fields);
    assert.match(html,/detail-pending detail-movie/);
    assert.match(html,/cinema-poster/);
    assert.doesNotMatch(html,/series-atmosphere|id="detail-play"/);
  });
}
test('pending genre and title content stays escaped',()=>{
  const html=pending({tipo:'serie',titulo:'<script>',genero:'<img>'});
  assert.doesNotMatch(html,/<script>|<span><img>/);
  assert.match(html,/&lt;script>/);assert.match(html,/&lt;img>/);
});

test('ready series uses the same hero without a hidden movie poster',()=>{
  const item={tipo:'biblico',format:'series',titulo:'Una historia',sinopsis:'Texto completo',genero:'Drama'};
  const html=detail.render({item,episodic:true,seasons:[{id:1,numero:1,episodios:0,has_episodes:true}],related:[],playable:false},esc,esc,()=>'',()=> '');
  assert.match(html,/detail-series/);assert.doesNotMatch(html,/cinema-poster/);
  assert.match(html,/season-1/);assert.match(html,/detail-synopsis/);
  assert.equal((html.match(/Texto completo/g)||[]).length,1);
});

test('full synopsis and malicious text remain escaped, not truncated in the data',()=>{
  const text='<img src=x onerror=alert(1)> '+ 'Historia extensa. '.repeat(500);
  const html=detail.render({item:{tipo:'pelicula',titulo:'<script>',sinopsis:text},seasons:[],related:[],playable:true},esc,esc,()=>'',()=> '');
  assert(html.includes(esc(text)));assert.doesNotMatch(html,/<script>|<img src=x/);
  assert.match(html,/aria-haspopup="dialog"/);
});
