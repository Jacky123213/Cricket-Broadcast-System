window.CricketPackMenu=(()=>{'use strict';const $=id=>document.getElementById(id);let state=null;
 function choices(select,rows){const signature=JSON.stringify(rows);if(select.dataset.rows===signature)return;const old=select.value;select.replaceChildren(...rows.map(([value,textContent])=>Object.assign(document.createElement('option'),{value,textContent})));select.dataset.rows=signature;if(rows.some(([v])=>v===old))select.value=old;}
 async function post(url,data){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),signal:AbortSignal.timeout(6000)}),body=await r.json();if(!r.ok)throw Error(typeof body.detail==='string'?body.detail:'Command unavailable');return body;}
 async function run(url,data){try{await post(url,data);$('quickPackStatus').textContent='Applied · shared broadcast follows after the normal delay';}catch(e){$('quickPackStatus').textContent=e.message;}}
 function players(){const team=state?.graphics.presentation?.teams.find(t=>t.team===$('quickCardTeam').value);choices($('quickCardPlayer'),(team?.players||[]).map(p=>[p.name,p.name]));}
 $('quickPack').onchange=()=>run('/api/scoreboard/broadcast/settings',{pack:$('quickPack').value});$('quickCardTeam').onchange=players;
 document.querySelectorAll('[data-quick-pack]').forEach(b=>b.onclick=()=>run('/api/scoreboard/broadcast/action',{action:'show',kind:b.dataset.quickPack,...(['lineup','player_batting','player_bowling'].includes(b.dataset.quickPack)?{team:$('quickCardTeam').value,player:$('quickCardPlayer').value}:{})}));
 $('quickFieldingHighlights').onclick=()=>run('/api/live/fielding-highlights',{});
 function update(s){state=s;if(document.activeElement!==$('quickPack'))$('quickPack').value=s.graphics.config.pack||'bbl';choices($('quickCardTeam'),[[s.score.team1,s.score.team1+' · batting'],[s.score.team2,s.score.team2+' · fielding']]);players();document.querySelectorAll('[data-quick-pack],#quickFieldingHighlights').forEach(b=>b.disabled=!['blank','coming_up','sponsor'].includes(b.dataset.quickPack)&&s.graphics.config.pack!=='fox_odi');}
 return {update};
})();
