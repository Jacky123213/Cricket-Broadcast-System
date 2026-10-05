'use strict';
const $=id=>document.getElementById(id);
let latest=null,chosenReport='',userChoseReport=false,scrubbing=false,pending=false;
const names={scorebar:'Scoreboard',hidden:'Hidden',run_chart:'Runs per over',batting_card:'Batting card',bowling_card:'Bowling card',wicket_card:'Last wicket',innings_break:'Innings break',match_summary:'Match summary'};
const seconds=v=>Number.isFinite(v)?v.toFixed(1)+' s':'Unavailable';
function error(message){$('deskError').textContent=message;}
async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(6000)});const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'Command rejected');return data;}
async function command(body){if(pending)return;pending=true;try{const data=await post('/api/broadcast/program',body);if(latest){latest.program=data;renderProgram();}error('');}catch(e){error(e.message);}finally{pending=false;}}
$('programCamera').onchange=()=>command({action:'camera',camera_id:$('programCamera').value});
$('returnProgramLive').onclick=()=>command({action:'live'});
$('retryProgram').onclick=()=>command({action:'retry'});
document.querySelectorAll('[data-program-replay]').forEach(button=>button.onclick=()=>command({action:'replay',seconds:Number(button.dataset.programReplay)}));
$('programPlay').onclick=()=>command({action:'play'});$('programPause').onclick=()=>command({action:'pause'});
$('programSpeed').onchange=()=>command({action:'speed',speed:Number($('programSpeed').value)});
$('programPosition').oninput=()=>{scrubbing=true;};$('programPosition').onchange=()=>{scrubbing=false;command({action:'seek',position_ms:Number($('programPosition').value)});};
$('programAudio').onclick=()=>command({action:'audio',muted:!latest?.program.program.muted});
$('previewMeter').onclick=async()=>{try{const result=await $('programPreview').contentWindow.CricketProgram?.enableMeter();$('previewMeterStatus').textContent=result?'Silent preview meter started. The OBS output needs its own audio/meter permission.':'Meter unavailable or blocked. Wait for decoded footage, then try again.';}catch{$('previewMeterStatus').textContent='Preview is not ready. Restart Studio after upgrading.';}};
async function graphics(body){try{await post('/api/scoreboard/broadcast/action',body);error('');}catch(e){error(e.message);}}
document.querySelectorAll('[data-graphic]').forEach(button=>button.onclick=()=>graphics({action:'show',kind:button.dataset.graphic,innings:button.dataset.graphic==='bowling_card'?Math.max(0,(latest?.score.graphics.innings.length||1)-1):Number($('graphicInnings').value)}));
$('reopenProgramScore').onclick=()=>graphics({action:'hide'});
$('surgeProgram').onclick=()=>graphics(latest?.score.graphics.power_surge?{action:'power_surge_off'}:{action:'show',kind:'power_surge',innings:Math.max(0,(latest?.score.graphics.innings.length||1)-1)});
$('graphicsVisible').onchange=async()=>{try{await post('/api/scoreboard/settings',{visible:$('graphicsVisible').checked});error('');}catch(e){error(e.message);}};
function options(select,rows,value){const key=JSON.stringify(rows);if(select.dataset.rows!==key){select.dataset.rows=key;select.replaceChildren(...rows.map(([value,textContent])=>Object.assign(document.createElement('option'),{value,textContent})));}if(value!==undefined)select.value=value;}
function renderProgram(){const {program:p,devices}=latest.program,g=latest.score.graphics,s=latest.score.score;
  const sourceRows=p.mode==='replay'?[...new Set(p.review?.clips.map(c=>c.device_id)||[])].map(id=>[id,devices.find(d=>d.device_id===id)?.name||id]):devices.map(d=>[d.device_id,d.name+' · '+d.role.replaceAll('_',' ')]);
  if(!sourceRows.some(([id])=>id===p.camera_id))sourceRows.unshift([p.camera_id||'',p.camera_id?'Selected camera offline':'Waiting for cameras…']);
  options($('programCamera'),sourceRows,p.camera_id||'');$('programCamera').disabled=!sourceRows.some(([id])=>id);
  const cameraOnline=devices.some(d=>d.device_id===p.camera_id);
  $('programTally').textContent=p.mode==='replay'?'REPLAY · '+(p.playing?'PLAY':'PAUSED'):!p.camera_id?'NO CAMERA':cameraOnline?'LIVE · DELAYED':'CAMERA OFFLINE';$('programTally').classList.toggle('replay',p.mode==='replay');$('programTally').classList.toggle('warning',p.mode==='live'&&!cameraOnline);
  $('programTransport').hidden=p.mode!=='replay';const duration=p.review?p.review.end_ms-p.review.start_ms:0;
  $('programPosition').max=Math.max(0,duration-1);if(!scrubbing)$('programPosition').value=p.position_ms;
  if(document.activeElement!==$('programSpeed'))$('programSpeed').value=String(p.speed);$('programTime').textContent=(p.position_ms/1000).toFixed(1)+' / '+(duration/1000).toFixed(1)+' s';
  $('programAudio').textContent=p.muted?'Unmute program audio':'Mute program audio';
  $('battingTeam').textContent=s.team1||'Waiting for score';$('liveScore').textContent=s.runs!==''&&s.wickets!==''?s.wickets+'–'+s.runs:'—';$('liveOvers').textContent='OVERS '+(s.overs||'—');
  const age=latest.score.last_score===null?null:Math.max(0,latest.score.server_time-latest.score.last_score);$('scoreAge').textContent=s.source==='manual'?'Manual score · update age unavailable':age===null?'Bluetooth · no recognised score received':'Bluetooth score update '+Math.floor(age)+' s ago'+(age>30?' · check scoring device':'');
  const innings=g.innings,selector=$('graphicInnings'),rows=innings.map((i,n)=>[String(n),(n+1)+'. '+i.team]),old=selector.value;
  options(selector,rows.length?rows:[['0','Waiting for innings']],rows.some(([id])=>id===old)?old:String(Math.max(0,rows.length-1)));
  document.querySelectorAll('[data-graphic],#surgeProgram').forEach(b=>b.disabled=!innings.length);
  $('requestedGraphic').textContent=p.mode==='replay'?'Hidden during replay':'Requested: '+(names[g.active?.kind]||'Scoreboard')+(g.power_surge?' + Surge':'');
  $('surgeProgram').textContent=g.power_surge?'Power Surge off':'Power Surge on';$('surgeProgram').setAttribute('aria-pressed',String(g.power_surge));
  if(document.activeElement!==$('graphicsVisible'))$('graphicsVisible').checked=s.visible;
}
function renderHealth(){const p=latest.program.program,clients=[...latest.health.clients].sort((a,b)=>(a.role==='obs'?0:1)-(b.role==='obs'?0:1)||a.report_age_ms-b.report_age_ms);
  if(!userChoseReport)chosenReport=clients.find(c=>c.role==='obs')?.client_id||clients.find(c=>c.role==='preview')?.client_id||clients[0]?.client_id||'';
  const rows=clients.map(c=>[c.client_id,(c.role==='obs'?'OBS browser':c.role==='preview'?'Local preview':'Browser')+' · '+c.client_id.slice(-8)+(c.report_age_ms>3500?' · stale':'')]);
  if(chosenReport&&!clients.some(c=>c.client_id===chosenReport))rows.unshift([chosenReport,'Selected output stopped reporting']);
  options($('outputClient'),rows.length?rows:[['','No output reports yet']],chosenReport);
  const report=clients.find(c=>c.client_id===chosenReport),stale=!report||report.report_age_ms>3500,matching=report&&report.revision===p.revision&&report.camera_id===(p.camera_id||'')&&report.mode===p.mode;
  $('healthSummary').textContent=stale?'OUTPUT STALE / OFFLINE':!matching?'APPLYING COMMAND':report.role!=='obs'?(report.state==='playing'?'LOCAL PREVIEW ONLY':'LOCAL · '+report.state.toUpperCase()):report.state==='playing'?'OBS PLAYING':report.state.toUpperCase();
  $('healthSummary').classList.toggle('warning',stale||!matching||report?.role!=='obs'||report?.state!=='playing');
  $('outputIdentity').textContent=!report?'No report from this output. OBS must use the shared link.':(report.role==='obs'?'OBS-labelled browser report':'Local/browser report · not proof of OBS playback')+' · heartbeat '+seconds(report.report_age_ms/1000)+' ago'+(!matching?' · awaiting current program command':'');
  const current=!stale&&matching?report:null;
  $('healthPlayback').textContent=current?current.state:stale?'Unavailable · no recent report':'Awaiting command';
  $('healthDelay').textContent=current?seconds(current.delay_seconds):'—';$('healthFootage').textContent=current?seconds(current.available_seconds):'—';$('healthHeadroom').textContent=current?seconds(current.headroom_seconds):'—';
  $('healthDropped').textContent=current&&current.dropped_frames!==null?current.dropped_frames+' / '+current.total_frames:'Unavailable';
  for(const [id,key] of [['healthLate','late_clips'],['healthDecode','decode_errors'],['healthRequests','poll_errors']])$(id).textContent=current?String(current[key]):'—';
  $('healthFrame').textContent=current&&Number.isFinite(current.last_frame_age_ms)?seconds(current.last_frame_age_ms/1000)+(current.state==='paused'?' · intentionally paused':' ago'):current?'Unavailable':'—';
  $('healthGraphic').textContent=current?((names[current.graphics_kind]||'Awaiting graphics report')+(current.graphics_surge?' + Power Surge':'')):'—';
  const measured=current?.meter_state==='active'&&Number.isFinite(current.meter_dbfs);
  $('programAudioMeter').value=measured?Math.max(-60,current.meter_dbfs):-60;
  $('programAudioLevel').textContent=measured?current.meter_dbfs.toFixed(1)+' dBFS RMS'+(current.meter_dbfs<=-60?' · silence / very quiet':''):current?.meter_state==='no_audio'?'No audio track in displayed clip':current?.meter_state==='suspended'?'Meter suspended · enable audio in that output':'Meter unavailable · enable audio/meter in that output';
  $('programAudioState').textContent=!current?'No fresh player audio report':(current.muted?'Playback muted here. ':'Playback unmuted here. ')+(measured?'Decoded samples measured; OBS recording still needs checking.':'Audio presence/permission alone does not prove audible sound.');
}
$('outputClient').onchange=()=>{chosenReport=$('outputClient').value;userChoseReport=true;if(latest)renderHealth();};
async function read(url){const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(3500)});if(!r.ok)throw Error('Server HTTP '+r.status);return r.json();}
async function poll(){try{const [program,score,health]=await Promise.all(['/api/broadcast/program','/api/scoreboard/state','/api/broadcast/health'].map(read));latest={program,score,health};renderProgram();renderHealth();}catch(e){$('healthSummary').textContent='SERVER UNAVAILABLE';$('healthSummary').classList.add('warning');$('programTally').textContent='CONTROL LINK LOST';$('outputIdentity').textContent='No fresh server report. Previously displayed readings are unavailable.';for(const id of ['healthDelay','healthFootage','healthHeadroom','healthLate','healthDecode','healthRequests','healthFrame','healthGraphic'])$(id).textContent='—';$('healthPlayback').textContent='Unavailable';$('healthDropped').textContent='Unavailable';$('programAudioMeter').value=-60;$('programAudioLevel').textContent='Meter unavailable · server disconnected';$('programAudioState').textContent='No fresh player audio report';error(e.message);}finally{setTimeout(poll,1000);}}
function outputAddress(){const base=$('programAddress').value;if(!base)return;const url=new URL('/broadcast',base);url.search='?follow=1&clean=1&client=obs&audio=1';$('sharedOutputUrl').textContent=url.href;}
$('programAddress').onchange=outputAddress;
read('/api/server-info').then(info=>{options($('programAddress'),(info.addresses||[]).map((url,n)=>[url,new URL(url).host+(n===0?' · preferred LAN':'')]));outputAddress();}).catch(e=>{$('sharedOutputUrl').textContent='Network address unavailable: '+e.message;});
$('copySharedOutput').onclick=async()=>{try{const text=$('sharedOutputUrl').textContent;if(!/^https?:\/\//.test(text))throw Error('Wait for a valid Studio address');await navigator.clipboard.writeText(text);$('copySharedOutput').textContent='Copied';setTimeout(()=>$('copySharedOutput').textContent='Copy shared OBS link',1500);}catch(e){error(e.message+' · select and copy the link manually.');}};
$('downloadHealth').onclick=()=>{if(!latest)return;const report={exported_at:new Date().toISOString(),program:{camera_id:latest.program.program.camera_id,mode:latest.program.program.mode,revision:latest.program.program.revision},score_source:latest.score.score.source,last_score:latest.score.last_score,health:latest.health};const blob=new Blob([JSON.stringify(report,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='broadcast-health-'+Date.now()+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
document.querySelectorAll('[data-section],[data-view]').forEach(link=>link.onclick=event=>{if(window.parent===window)return;event.preventDefault();window.parent.postMessage({type:'match-day-navigate',section:link.dataset.section||null,view:link.dataset.view||'scoreboard'},location.origin);});
poll();
