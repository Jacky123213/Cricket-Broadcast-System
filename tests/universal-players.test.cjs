const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),{JSDOM}=require('jsdom');
const {harness,settle}=require('./helpers/operator-harness.cjs'),read=p=>fs.readFileSync(p,'utf8');
const player={id:'c'.repeat(32),name:'Ali',universal:true,teams:[],roster_teams:[],matches:2,runs:40};
test('same universal record can be added to two rosters without creating another player',async()=>{
 const h=await harness('teams',undefined,({state,careerPlayers})=>{careerPlayers.push(structuredClone(player));state.graphics.presentation.teams=[{team:'HOME',featured:'',players:[]},{team:'AWAY',featured:'',players:[]}];});
 try{for(const name of ['HOME','AWAY']){h.d.getElementById('teamPicker').value=name;h.d.getElementById('teamPicker').dispatchEvent(new h.w.Event('change'));h.d.getElementById('universalRosterPlayer').value=player.id;h.d.getElementById('addUniversalPlayer').click();assert.equal(h.d.getElementById('rosterPlayerRecord').value,player.id);h.submit('teamEditor');await h.settle();}
  const saves=h.requests.filter(r=>r.url==='/api/graphics-packs'&&r.options?.body).map(r=>JSON.parse(r.options.body));assert.equal(saves.length,2);assert.ok(saves.every(r=>r.team.players.length===1&&r.team.players[0].player_id===player.id));assert.equal(h.requests.filter(r=>r.url==='/api/statistics/players'&&r.options?.body).length,0);
 }finally{h.close();}
});
test('link an existing roster row to a universal record without duplicating its name or losing details',async()=>{
 const h=await harness('teams',undefined,({state,careerPlayers})=>{careerPlayers.push(structuredClone(player));state.graphics.presentation.teams[0].players=[{name:'Ali',role:'keeper',captain:true,photo:'',runs:'120'}];});
 try{h.d.getElementById('universalRosterPlayer').value=player.id;h.d.getElementById('addUniversalPlayer').click();assert.match(h.d.getElementById('workspaceError').textContent,/already in the roster/);h.d.getElementById('rosterPlayerRecord').value=player.id;h.d.getElementById('rosterPlayerRecord').dispatchEvent(new h.w.Event('change'));h.submit('teamEditor');await h.settle();const body=JSON.parse(h.requests.find(r=>r.url==='/api/graphics-packs'&&r.options?.body).options.body);assert.equal(body.team.players.length,1);assert.equal(body.team.players[0].player_id,player.id);assert.equal(body.team.players[0].role,'keeper');assert.equal(body.team.players[0].captain,true);assert.equal(body.team.players[0].runs,'120');
 }finally{h.close();}
});
function statistics(){const dom=new JSDOM(read('frontend/operator/statistics.html'),{url:'https://local/statistics',runScripts:'outside-only',pretendToBeVisual:true}),w=dom.window;const intervals=[];w.AbortSignal.timeout=()=>undefined;w.setInterval=fn=>{intervals.push(fn);return intervals.length;};return {w,d:w.document,intervals,close:()=>w.close()};}
test('mark an existing player universal, preserve the selection while polling and never recreate the record',async()=>{
 const h=statistics(),{w,d}=h,posts=[];let record={...structuredClone(player),universal:false};
 try{w.fetch=async(url,options={})=>{if(options.body){const body=JSON.parse(options.body);posts.push({url,body});record.universal=body.universal;return {ok:true,json:async()=>record};}return {ok:true,json:async()=>url==='/api/statistics'?{players:[record],teams:[],matches:[]}:url.endsWith('/archive')?[]:{addresses:['https://192.168.1.68:8765']}};};w.eval(read('frontend/operator/statistics.js'));await settle();d.getElementById('universalPlayerPicker').value=record.id;d.getElementById('universalPlayerPicker').dispatchEvent(new w.Event('change'));d.getElementById('isUniversalPlayer').click();await h.intervals[0]();await settle();assert.equal(d.getElementById('isUniversalPlayer').checked,true,'background refresh preserves unsaved option');d.getElementById('universalPlayerOptions').dispatchEvent(new w.Event('submit',{cancelable:true}));await settle();assert.deepEqual(posts,[{url:'/api/statistics/players/'+record.id+'/options',body:{universal:true}}]);assert.equal(record.runs,40);assert.equal(d.getElementById('universalPlayerPicker').value,record.id);
 }finally{h.close();}
});
test('new player registration includes the explicit universal checkbox',async()=>{
 const h=statistics(),{w,d}=h;let created=null;
 try{w.fetch=async(url,options={})=>{if(options.body){created=JSON.parse(options.body);return {ok:true,json:async()=>({...player,...created})};}return {ok:true,json:async()=>url==='/api/statistics'?{players:created?[{...player,...created}]:[],teams:[],matches:[]}:url.endsWith('/archive')?[]:{addresses:[]}};};w.eval(read('frontend/operator/statistics.js'));await settle();const form=d.getElementById('addCareerPlayer');form.elements.name.value='Ali';form.elements.universal.checked=true;form.dispatchEvent(new w.Event('submit',{cancelable:true}));await settle();assert.deepEqual(created,{name:'Ali',team:'',universal:true});assert.equal(d.getElementById('universalPlayerPicker').value,player.id);
 }finally{h.close();}
});
