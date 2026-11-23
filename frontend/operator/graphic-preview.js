/* A private render receives copies of state. It never sends broadcast commands. */
(()=>{'use strict';const $=id=>document.getElementById(id),display=v=>v===null||v===undefined||v===''?'—':String(v);
 window.addEventListener('message',event=>{if(event.source!==window.parent||event.origin!==location.origin||event.data?.type!=='private-graphic-preview')return;const {score:s,graphics:g}=event.data.state;
  document.documentElement.style.setProperty('--team1',s.color1);document.documentElement.style.setProperty('--team2',s.color2);
  for(const id of ['team1','team2','overs','bowler','bowler_figures','bowler_overs','batter1_name','batter2_name','batter1_runs','batter2_runs','batter1_balls','batter2_balls'])$(id).textContent=display(s[id]);
  for(const slot of [1,2]){$('team'+slot).textContent=display(s['abbr'+slot]||s['team'+slot]);$('team'+slot).title=s['team'+slot]||'';}
  $('total').textContent=s.runs!==''&&s.wickets!==''?s.wickets+'–'+s.runs:'—';$('bannerText').textContent=g.strip?.text||s.banner||g.config.match_title;
  for(const n of [1,2]){$('logo'+n).hidden=!s['logo'+n];if(s['logo'+n])$('logo'+n).src=s['logo'+n];$('batter'+n).classList.toggle('striker',s.striker===String(n));}
  window.FoxODI?.apply(g,s);$('scorebar').hidden=window.BackyardGraphics.render(g,s);$('connection').hidden=true;
 });
})();
