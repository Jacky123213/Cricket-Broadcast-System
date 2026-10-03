'use strict';
const $=id=>document.getElementById(id);
function render(s){
 const d=s.score;
 const graphicShown=window.BackyardGraphics?.render(s.graphics,d)||false;
 $('scorebar').hidden=!d.visible||graphicShown;
 document.documentElement.style.setProperty('--team1',d.color1);
 document.documentElement.style.setProperty('--team2',d.color2);
 for(const k of ['team1','team2','overs','batter1_name','batter2_name','batter1_runs','batter2_runs','batter1_balls','batter2_balls','bowler','bowler_figures','bowler_overs'])$(k).textContent=d[k]||'—';
 $('total').textContent=d.runs!==''&&d.wickets!==''?`${d.wickets}–${d.runs}`:'—';
 const banner=s.graphics?.strip.text||d.banner||'BACKYARD CRICKET';
 const bannerText=$('bannerText');
 $('banner').classList.toggle('projection',s.graphics?.strip.kind==='projection');
 if(bannerText.textContent!==banner){bannerText.textContent=banner;$('banner').classList.remove('changed','long');void $('banner').offsetWidth;$('banner').classList.add('changed');}
 const overflow=bannerText.scrollWidth-$('banner').clientWidth;
 $('banner').classList.toggle('long',overflow>1);
 $('banner').style.setProperty('--strip-shift',`${-Math.max(0,overflow)}px`);
 $('banner').style.setProperty('--strip-time',`${Math.max(4,(s.graphics?.config.interval_seconds||10)-1)}s`);
 for(const n of [1,2]){
  const logo=$('logo'+n);logo.hidden=!d['logo'+n];if(d['logo'+n]&&logo.getAttribute('src')!==d['logo'+n])logo.src=d['logo'+n];
  $('batter'+n).classList.toggle('striker',d.striker===String(n));
 }
 const tokens=d.deliveries.trim().split(/\s+/).filter(Boolean);
 const recent=tokens.slice(-12),omitted=Math.max(0,tokens.length-recent.length);
 const circles=Array.from({length:Math.max(6,recent.length)},(_,i)=>{
  const el=document.createElement('span'),t=recent[i];
  el.textContent=t===undefined?'':t==='0'?'·':t;
  el.className=t===undefined?'pending':/^w$/i.test(t)?'wicket':/^[46]$/.test(t)?'boundary':'played';
  el.title=t===undefined?'Not yet bowled':'Delivery: '+t;
  el.setAttribute('aria-label',el.title);return el;
 });
 $('deliveries').replaceChildren(...circles);
 $('deliveries').title=omitted?`Current over: ${tokens.join(' ')} (${omitted} earlier entries not shown)`:'Current over';
 $('overLabel').textContent=omitted?`THIS OVER · +${omitted} earlier`:'THIS OVER';

 const age=s.last_score===null?Infinity:s.server_time-s.last_score;
 $('connection').hidden=!d.visible||graphicShown||s.graphics?.phase==='complete'||s.graphics?.phase==='innings_break'||d.source==='manual'||age<=30;
 $('connection').textContent=s.last_score===null?'WAITING FOR SCORE':'NO SCORE UPDATE · '+Math.floor(age)+'s';
}
async function poll(){try{const r=await fetch('/api/state',{cache:'no-store',signal:AbortSignal.timeout(3000)});if(!r.ok)throw Error();render(await r.json());}catch{$('connection').hidden=false;$('connection').textContent='SCORE SERVER OFFLINE';}finally{setTimeout(poll,500);}}poll();
