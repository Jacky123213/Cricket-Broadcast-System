/* Window-local live-view control. No server, camera or user data is touched. */
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),{JSDOM}=require('jsdom');
const read=path=>fs.readFileSync(path,'utf8'),settle=()=>new Promise(r=>setImmediate(r));
async function desktop(saved){
 const dom=new JSDOM(read('frontend/desktop/index.html'),{url:'https://local/',runScripts:'outside-only'}),w=dom.window,requests=[];
 w.setTimeout=()=>1;
 w.fetch=async url=>{requests.push(url);return {ok:true,json:async()=>({connected_cameras:1,score_packets:4,secure_context:true,camera_urls:['https://local/camera'],umpire_urls:['https://local/umpire'],overlay_urls:['https://local/overlay'],bluetooth_status:'Connected',sleep_prevention:'Active'})};};
 if(saved)w.localStorage.setItem('cricket.local-live-views.v1',saved);
 w.eval(read('frontend/desktop/desktop.js'));await settle();return {dom,w,d:w.document,requests,close:()=>w.close()};
}
test('hidden Replay Studio does not connect at launch; loaded sections and scoreboard drafts survive navigation',async()=>{
 const h=await desktop();try{
  const match=h.d.getElementById('matchDayFrame'),replay=h.d.getElementById('replayFrame'),score=h.d.getElementById('scoreboardFrame'),scoreWindow=score.contentWindow;
  assert.equal(match.getAttribute('src'),'/match-day');assert.equal(replay.getAttribute('src'),null);
  const scoreDoc=score.contentDocument;if(!scoreDoc.body){const html=scoreDoc.createElement('html');html.append(scoreDoc.createElement('body'));scoreDoc.append(html);}
  const draft=scoreDoc.createElement('input');draft.value='Unsaved team';scoreDoc.body.append(draft);
  h.d.querySelector('button[data-view="replay"]').click();assert.equal(replay.getAttribute('src'),'/umpire');
  h.d.querySelector('button[data-view="match-day"]').click();assert.equal(replay.getAttribute('src'),'/umpire','ordinary navigation does not discard a local review');
  assert.equal(score.contentWindow,scoreWindow);assert.equal(draft.value,'Unsaved team');
 }finally{h.close();}
});
test('local off unloads both live viewers, preserves scoreboard edits, and does not send a global command',async()=>{
 const h=await desktop();try{
  const match=h.d.getElementById('matchDayFrame'),replay=h.d.getElementById('replayFrame'),score=h.d.getElementById('scoreboardFrame'),scoreWindow=score.contentWindow,toggle=h.d.getElementById('localLiveViews');
  h.d.querySelector('button[data-view="replay"]').click();toggle.click();
  assert.equal(match.getAttribute('src'),'about:blank');assert.equal(replay.getAttribute('src'),'about:blank');assert.equal(match.hidden,true);assert.equal(replay.hidden,true);
  assert.equal(h.d.querySelector('#view-replay .local-live-paused').hidden,false);assert.equal(score.contentWindow,scoreWindow);assert.equal(score.hidden,false);
  assert.equal(h.w.localStorage.getItem('cricket.local-live-views.v1'),'off');assert.deepEqual(h.requests,['/api/app-status']);
  h.d.querySelector('button[data-view="match-day"]').click();assert.equal(match.getAttribute('src'),'about:blank','navigation cannot silently re-enable local video');
  toggle.click();assert.equal(match.getAttribute('src'),'/match-day');assert.equal(match.hidden,false);assert.equal(replay.getAttribute('src'),'about:blank','only the selected viewer restarts');
  h.d.querySelector('button[data-view="replay"]').click();assert.equal(replay.getAttribute('src'),'/umpire');
 }finally{h.close();}
});
test('saved local off starts without any live viewers and leaves server status available',async()=>{
 const h=await desktop('off');try{
  assert.equal(h.d.getElementById('localLiveViews').checked,false);assert.equal(h.d.getElementById('matchDayFrame').getAttribute('src'),null);assert.equal(h.d.getElementById('replayFrame').getAttribute('src'),null);
  assert.equal(h.d.getElementById('serverText').textContent,'Local server ready');
 }finally{h.close();}
 const ipad=await desktop();try{assert.equal(ipad.d.getElementById('localLiveViews').checked,true,'another browser/device has its own preference');}finally{ipad.close();}
});
