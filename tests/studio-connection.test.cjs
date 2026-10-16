const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{JSDOM}=require('jsdom');
const root=path.join(__dirname,'..'),read=p=>fs.readFileSync(path.join(root,p),'utf8');
async function harness(connection){
 const dom=new JSDOM(read('frontend/desktop/index.html'),{url:'https://192.168.1.68:8765/',runScripts:'outside-only'}),w=dom.window,d=w.document,requests=[],timers=[];
 d.getElementById('studioConnection').textContent=JSON.stringify(connection);
 w.AbortSignal.timeout=()=>undefined;w.setTimeout=(fn,delay)=>{timers.push({fn,delay});return timers.length;};w.confirm=()=>true;
 let online=true,removed=false;
 const studio={name:"Jack's PC",allow_join:true,code:'ABCD1234',code_seconds:1000,ca_sha256:'FP',discovery:'Ready',clients:[{id:'approved',name:'OBS PC'}]};
 w.fetch=async(url,opts)=>{requests.push({url,opts});if(url==='/api/app-status'){if(!online)throw Error('offline');return {ok:!removed,status:removed?401:200,json:async()=>({studio_name:studio.name,connected_cameras:2,score_packets:5,secure_context:true,camera_urls:['https://192.168.1.68:8765/camera'],umpire_urls:['https://192.168.1.68:8765/umpire'],overlay_urls:['https://192.168.1.68:8765/overlay'],certificate_url:'/local-ca.crt'})};}if(url.startsWith('/api/studio-network'))return {ok:true,status:200,json:async()=>studio};throw Error(url);};
 w.eval(read('frontend/desktop/desktop.js'));await new Promise(r=>setImmediate(r));
 return {dom,w,d,requests,timers,poll:()=>timers.find(t=>t.delay===2500).fn(),offline:()=>online=false,online:()=>online=true,revoke:()=>removed=true,close:()=>w.close()};
}
test('host identity and approvals appear only on the host; codes and removal send scoped commands',async()=>{
 const h=await harness({name:"Jack's PC",client:false,local_operator:true});try{
  assert.equal(h.d.getElementById('studioMode').textContent,'Studio host');assert.equal(h.d.getElementById('studioNetworkControls').hidden,false);
  assert.match(h.d.getElementById('studioPairCode').textContent,/ABCD1234/);
  h.d.getElementById('studioNewCode').click();await new Promise(r=>setImmediate(r));
  assert.ok(h.requests.some(r=>r.url==='/api/studio-network/new-code'&&r.opts.method==='POST'));
  h.d.querySelector('#studioClients button').click();await new Promise(r=>setImmediate(r));
  assert.ok(h.requests.some(r=>r.url==='/api/studio-network/clients/approved'&&r.opts.method==='DELETE'));
 }finally{h.close();}
});
test('connected PC has a clear host indicator, no approval controls, and recovers its live preview without resetting scoreboard drafts',async()=>{
 const h=await harness({name:"Jack's PC",client:true,local_operator:false});try{
  assert.equal(h.d.getElementById('serverText').textContent,"Connected to Jack's PC");assert.equal(h.d.getElementById('studioNetworkControls').hidden,true);
  assert.ok(!h.requests.some(r=>r.url==='/api/studio-network/settings'));
  const scoreFrame=h.d.getElementById('scoreboardFrame'),scoreSrc=scoreFrame.getAttribute('src'),scoreDoc=scoreFrame.contentDocument;
  if(!scoreDoc.body){const html=scoreDoc.createElement('html');html.append(scoreDoc.createElement('body'));scoreDoc.append(html);}scoreDoc.body.textContent='Unsaved score draft';
  h.offline();await h.poll();assert.match(h.d.getElementById('serverText').textContent,/reconnecting/);
  h.online();await h.poll();assert.equal(h.d.getElementById('serverText').textContent,"Connected to Jack's PC");assert.equal(scoreFrame.getAttribute('src'),scoreSrc);assert.equal(scoreFrame.contentDocument.body.textContent,'Unsaved score draft');
  h.revoke();await h.poll();assert.match(h.d.getElementById('diagServer').textContent,/Approval removed/);
 }finally{h.close();}
});
