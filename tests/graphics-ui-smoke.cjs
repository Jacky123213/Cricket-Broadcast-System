/* Source-level DOM checks; no physical camera, browser session or match data. */
const {JSDOM}=require('jsdom'),fs=require('node:fs'),assert=require('node:assert/strict');
const read=path=>fs.readFileSync(path,'utf8'),wait=()=>new Promise(resolve=>setImmediate(resolve));
const innings={team:'Pavilion',opposition:'Creek',color:'#14b8a6',logo:'',runs:94,wickets:4,balls:85,overs:'14.1',batters:[{name:'Ali',runs:14,balls:12,dismissal:'c Bo b Dee',active:false,dots:2,fours:1,sixes:0}],bowlers:[],chart:[],last_wicket:{name:'Ali',runs:14,balls:12,dismissal:'c Bo b Dee',dots:2,scoring_shots:10,fours:1,sixes:0,strike_rate:117}};
const graphics={active:{kind:'wicket_card',innings:0,reason:'Manual',until:null},power_surge:true,innings:[innings],config:{messages:[],match_title:'Backyard',venue:''},strip:{text:'PARTNERSHIP 21 (18)',kind:'partnership'},phase:'live'};
(async()=>{
 const dom=new JSDOM(read('frontend/scoreboard/overlay.html'),{url:'http://local/overlay',runScripts:'outside-only'}),w=dom.window,d=w.document;
 w.eval(read('frontend/scoreboard/graphic-renderer.js'));
 assert.equal(w.BackyardGraphics.render(graphics,{visible:true}),false,'wicket panel keeps the bottom scoreboard visible');
 assert.equal(d.getElementById('wicketGraphic').hidden,false);
 assert.match(d.getElementById('wicketGraphic').textContent,/Alic Bo b Dee1412DOTS2SCORING SHOTS10FOURS1SIXES0STRIKE RATE117/);
 assert.equal(d.getElementById('powerSurge').hidden,false);
 assert.equal(d.getElementById('powerSurge').style.backgroundColor,'rgb(20, 184, 166)');
 const switched=structuredClone(graphics);switched.innings.push({...innings,team:'Creek',color:'#f6b342'});
 w.BackyardGraphics.render(switched,{visible:true});assert.equal(d.getElementById('powerSurge').style.backgroundColor,'rgb(246, 179, 66)');
 w.BackyardGraphics.render({...switched,active:null,power_surge:false},{visible:true});assert.equal(d.getElementById('wicketGraphic').hidden,true);assert.equal(d.getElementById('powerSurge').hidden,true);
 dom.window.close();

 const desk=new JSDOM(read('frontend/scoreboard/control.html'),{url:'http://local/scoreboard',runScripts:'outside-only'}),dw=desk.window,dd=dw.document,posts=[];
 const score={source:'manual',team1:'Pavilion',team2:'Creek',color1:'#14b8a6',color2:'#f6b342',visible:true,banner:'Backyard'};
 dw.AbortSignal.timeout=()=>undefined;dw.fetch=async(url,opts)=>{if(opts?.method==='POST')posts.push({url,data:JSON.parse(opts.body)});return {ok:true,json:async()=>url==='/api/server-info'?{overlay_urls:['http://local/overlay'],secure_context:false}:{score,graphics,team_appearance:[],logs:[],server_time:100,last_score:null,packet_count:0,status:'Ready'}};};
 dw.eval(read('frontend/scoreboard/control.js'));await wait();await wait();
 assert.equal(dd.getElementById('battingRows').querySelectorAll('input').length,7);
 dd.getElementById('wicketType').value='Caught';dd.getElementById('wicketBowler').value='Dee';dd.getElementById('wicketFielder').value='Bo';
 dd.querySelector('#dismissalForm button[name="show"]').click();await wait();assert.equal(posts.at(-1).data.dismissal,'c Bo b Dee');assert.equal(posts.at(-1).data.show,true);
 dd.getElementById('hideGraphic').click();await wait();assert.equal(posts.at(-1).data.action,'hide');
 dd.getElementById('powerSurgeToggle').click();await wait();assert.equal(posts.at(-1).data.action,'power_surge_off');
 dd.querySelector('[data-graphic="wicket_card"]').click();await wait();assert.equal(posts.at(-1).data.kind,'wicket_card');
 assert.equal(dd.querySelector('[data-action="reopen"]').textContent,'Undo match finish');
 desk.window.close();

 const program=new JSDOM(read('frontend/scoreboard/overlay.html'),{url:'http://local/overlay?program=1',runScripts:'outside-only'}),pw=program.window,calls=[],polls=[];
 pw.AbortSignal.timeout=()=>undefined;pw.setTimeout=fn=>{polls.push(fn);return 1;};
 pw.fetch=async url=>{calls.push(url);return {ok:true,json:async()=>({score:{...score,runs:url.includes('program-state')?'10':'14',wickets:'1',overs:'1.0'},graphics:{...graphics,active:null},server_time:100,last_score:null})};};
 pw.eval(read('frontend/scoreboard/graphic-renderer.js'));pw.eval(read('frontend/scoreboard/overlay.js'));await wait();
 assert.equal(program.window.document.getElementById('scorebar').hidden,true,'no current-time graphics during initial camera buffer');
 pw.dispatchEvent(new pw.MessageEvent('message',{source:pw.parent,origin:'http://local',data:{type:'broadcast-time',at:95}}));
 polls.shift()();await wait();await wait();
 assert.ok(calls.includes('/api/scoreboard/program-state?at=95'));assert.equal(pw.document.getElementById('total').textContent,'1–10');
 pw.dispatchEvent(new pw.MessageEvent('message',{source:pw.parent,origin:'http://untrusted',data:{type:'broadcast-time',at:96}}));
 polls.shift()();await wait();assert.equal(calls.at(-1),'/api/scoreboard/program-state?at=95','foreign pages cannot change playout time');
 program.window.close();
 console.log('Graphics DOM smoke passed: wicket stats/dismissal, batting-team Power Surge, manual controls, seven-column stats editor, initial delayed overlay hidden');
})().catch(error=>{console.error(error);process.exitCode=1;});
