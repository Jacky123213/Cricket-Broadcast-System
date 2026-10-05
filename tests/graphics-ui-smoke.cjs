/* Source-level DOM checks; no physical camera, browser session or match data. */
const {JSDOM}=require('jsdom'),fs=require('node:fs'),assert=require('node:assert/strict');
const read=path=>fs.readFileSync(path,'utf8'),wait=()=>new Promise(resolve=>setImmediate(resolve));
const innings={team:'Pavilion',opposition:'Creek',color:'#14b8a6',opposition_color:'#f6b342',logo:'',opposition_logo:'/creek.png',runs:94,wickets:4,balls:85,overs:'14.1',extras:null,run_rate:6.64,batters:[{name:'Ali',runs:14,balls:12,dismissal:'c Bo b Dee',active:false,dots:2,fours:1,sixes:0}],bowlers:[{name:'Dee',figures:'2–6',overs:'0.3',wickets:2,runs:6,economy:12},{name:'Bo',figures:'0–39',overs:'3.1',wickets:0,runs:39,economy:12.32}],chart:Array.from({length:20},(_,i)=>({over:i+1,runs:i<9?[1,6,11,13,2,4,4,12,8][i]:null,wickets:i===1?1:0})),last_wicket:{name:'Ali',runs:14,balls:12,dismissal:'c Bo b Dee',dots:2,scoring_shots:10,fours:1,sixes:0,strike_rate:117}};
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
 for(const kind of ['batting_card','bowling_card','run_chart','innings_break','match_summary']){
   const view={...graphics,active:{kind,innings:0,reason:'Manual',until:null},result:''};
   assert.equal(w.BackyardGraphics.render(view,{visible:true,bowler:'Dee'}),true,kind+' must open');
   assert.equal(d.getElementById(kind==='innings_break'?'breakGraphic':'statGraphic').hidden,false);
   if(kind==='batting_card'){assert.match(d.getElementById('statGraphic').textContent,/BATTERDISMISSALRUNSBALLS/);assert.equal(d.querySelectorAll('.batting-card tbody tr').length,1);}
   if(kind==='bowling_card'){
     assert.equal(d.querySelector('.graphic-heading h1').textContent,'Creek');
     assert.equal(d.querySelector('.graphic-heading img').getAttribute('src'),'/creek.png');
     assert.equal(d.getElementById('statGraphic').style.getPropertyValue('--graphic-team'),'#f6b342');
     assert.match(d.getElementById('statGraphic').textContent,/BOWLEROVERSWICKETS–RUNSECONOMYDee0.32–612.00Bo3.10–3912.32/);
     assert.equal(d.querySelector('.bowling-card .not-out .player-name').textContent,'Dee');
     w.BackyardGraphics.render(view,{visible:true,bowler:'Bo'});
     assert.equal(d.querySelector('.bowling-card .not-out .player-name').textContent,'Bo','bowler-only changes update the active-row highlight');
   }
   if(kind==='match_summary')assert.equal(d.querySelector('.summary-list:nth-child(2) .summary-player strong').textContent,'2–6');
 }
 const chaseBowling={...graphics,active:{kind:'bowling_card',innings:0,reason:'Manual',until:null},innings:[innings,{...innings,team:'Creek',opposition:'Pavilion',color:'#f6b342',opposition_color:'#14b8a6',opposition_logo:'/pavilion.png'}]};
 w.BackyardGraphics.render(chaseBowling,{visible:true});
 assert.equal(d.querySelector('.graphic-heading h1').textContent,'Pavilion','bowling card follows the current opposition even when held across an innings change');
 assert.equal(d.getElementById('statGraphic').style.getPropertyValue('--graphic-team'),'#14b8a6');
 assert.equal(d.querySelector('.graphic-heading img').getAttribute('src'),'/pavilion.png');
 const chartView={...graphics,active:{kind:'run_chart',innings:0,reason:'Manual',until:null},config:{...graphics.config,powerplay_overs:4}};
 w.BackyardGraphics.render(chartView,{visible:true});assert.equal(d.querySelector('.powerplay-label').textContent,'POWER PLAY');
 assert.equal(d.querySelectorAll('rect[fill="url(#powerplayFill)"]').length,4);assert.equal(d.querySelectorAll('rect[fill="var(--graphic-team)"]').length,5);
 chartView.config.powerplay_overs=0;w.BackyardGraphics.render(chartView,{visible:true});assert.equal(d.querySelector('.powerplay-bracket'),null,'config-only change redraws the chart');
 dom.window.close();

 const desk=new JSDOM(read('frontend/scoreboard/control.html'),{url:'http://local/scoreboard',runScripts:'outside-only'}),dw=desk.window,dd=dw.document,posts=[];
 const score={source:'manual',team1:'Pavilion',team2:'Creek',color1:'#14b8a6',color2:'#f6b342',visible:true,banner:'Backyard'};
 dw.AbortSignal.timeout=()=>undefined;dw.fetch=async(url,opts)=>{if(opts?.method==='POST')posts.push({url,data:JSON.parse(opts.body)});return {ok:true,json:async()=>url==='/api/server-info'?{overlay_urls:['http://local/overlay'],secure_context:false}:{score,graphics,team_appearance:[],logs:[],server_time:100,last_score:null,packet_count:0,status:'Ready'}};};
 dw.eval(read('frontend/assets/sections.js'));dw.CricketSections.init();
 dw.eval(read('frontend/scoreboard/control.js'));await wait();await wait();
 assert.equal(dd.getElementById('battingRows').querySelectorAll('input').length,7);
 dd.getElementById('wicketType').value='Caught';dd.getElementById('wicketBowler').value='Dee';dd.getElementById('wicketFielder').value='Bo';
 dd.querySelector('#dismissalForm button[name="show"]').click();await wait();assert.equal(posts.at(-1).data.dismissal,'c Bo b Dee');assert.equal(posts.at(-1).data.show,true);
 dd.getElementById('hideGraphic').click();await wait();assert.equal(posts.at(-1).data.action,'hide');
 dd.getElementById('powerSurgeToggle').click();await wait();assert.equal(posts.at(-1).data.action,'power_surge_off');
 dd.querySelector('[data-graphic="wicket_card"]').click();await wait();assert.equal(posts.at(-1).data.kind,'wicket_card');
 dd.getElementById('wicketType').value='Stumped';
 dd.getElementById('wicketFielder').value='Ignored keeper name';
 dd.querySelector('#dismissalForm button[name="show"]').click();await wait();assert.equal(posts.at(-1).data.dismissal,'st wk b Dee');
 dd.getElementById('wicketFielder').value='';
 dd.querySelector('#dismissalForm button[name="show"]').click();await wait();assert.equal(posts.at(-1).data.dismissal,'st wk b Dee');
 dd.getElementById('wicketType').value='6 and Out';
 dd.querySelector('#dismissalForm button[name="show"]').click();await wait();assert.equal(posts.at(-1).data.dismissal,'6 and Out');
 graphics.innings.push({...innings,team:'Creek',opposition:'Pavilion'});
 dd.getElementById('graphicInnings').value='0';
 dd.querySelector('[data-graphic="bowling_card"]').click();await wait();assert.equal(posts.at(-1).data.kind,'bowling_card');assert.equal(posts.at(-1).data.innings,1);
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
 console.log('Graphics DOM smoke passed: all seven graphics, batting/bowling cards, opposing team colours/logos, wickets–runs figures, st wk/6 and Out corrections, first-X-over chart, manual controls and delayed rendering');
})().catch(error=>{console.error(error);process.exitCode=1;});
