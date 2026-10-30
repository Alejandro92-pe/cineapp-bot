const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm'),fs=require('node:fs');
const context={window:{}};
vm.runInNewContext(fs.readFileSync(require.resolve('../tv/static/detail.js'),'utf8'),context);
const detail=context.window.TVDetail;
const esc=s=>String(s??'').replaceAll('<','&lt;').replaceAll('"','&quot;');
function pending(fields){return detail.pending({titulo:'Historia',imagen_url:'poster',backdrop_url:'background',...fields},esc,esc,()=>'<div class="meta"></div>');}
for(const fields of [{tipo:'serie'},{tipo:'anime',format:'movies'},{tipo:'biblico',format:'series'}]){
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
