/* FOX ODI is a preset renderer, not a user-authored template interpreter. */
window.FoxODI=(()=>{'use strict';
 const $=id=>document.getElementById(id),n=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;},show=v=>v===null||v===undefined||v===''?'—':String(v),total=i=>i.runs===null||i.runs===undefined?'—':`${show(i.wickets)}–${i.runs}`,key=t=>(t||'').trim().replace(/\s+/g,' ').toLowerCase();
 const colour=c=>/^#[\da-f]{6}$/i.test(c)?c:'#b8e34b';let last='',lastFull=false;
 function image(src,cls,alt){const e=n('img',cls);e.src=src;e.alt=alt||'';return e;}
 function ink(c){return parseInt(c.slice(1,3),16)*.2126+parseInt(c.slice(3,5),16)*.7152+parseInt(c.slice(5,7),16)*.0722>150?'#101216':'#fff';}
 function appearance(g,s,team){for(const i of g.innings||[]){if(key(i.team)===key(team))return {team:i.team,color:colour(i.color),logo:i.logo};if(key(i.opposition)===key(team))return {team:i.opposition,color:colour(i.opposition_color),logo:i.opposition_logo};}const slot=key(team)===key(s.team2)?2:1;return {team:team||s['team'+slot],color:colour(s['color'+slot]),logo:s['logo'+slot]};}
 function theme(e,a){e.style.setProperty('--graphic-team',colour(a.color));e.style.setProperty('--graphic-ink',ink(colour(a.color)));}
 function header(g,a,title=a.team){const e=n('header','fox-heading');if(a.logo)e.append(image(a.logo,'fox-team-logo',a.team));const text=n('div');text.append(n('h1','',title),n('p','',g.config.match_title),n('p','',g.config.venue));e.append(text);return e;}
 function footer(i,bowling=false){const e=n('footer','fox-footer');e.append(n('span','',bowling?'AGAINST '+i.team:'EXTRAS '+show(i.extras)),n('span','',`OVERS ${i.overs}`),n('span','',bowling?'TOTAL AGAINST':'TOTAL'),n('strong','',total(i)));return e;}
 function table(columns,rows){const t=n('table','fox-table'),head=n('thead'),h=n('tr'),body=n('tbody');for(const c of columns)h.append(n('th','',c));head.append(h);t.append(head,body);for(const row of rows){const tr=n('tr',row.active?'fox-active':'');row.values.forEach((v,j)=>tr.append(n('td',j?'':'fox-name',show(v))));body.append(tr);}t.style.setProperty('--rows',Math.max(5,rows.length));return t;}
 function mini(a,label,main,sub){const e=n('div','fox-mini');if(a.logo)e.append(image(a.logo,'fox-mini-logo',a.team));const copy=n('div');copy.append(n('small','',label),n('strong','',main),n('span','',sub));e.append(copy);return e;}
 function summary(g){const e=n('div','fox-summary');for(const i of g.innings.slice(0,2)){const part=n('section','fox-summary-innings');theme(part,i);const title=n('header');if(i.logo)title.append(image(i.logo,'fox-mini-logo',i.team));title.append(n('h2','',i.team),n('b','',total(i)),n('span','',i.overs+' OVERS'));part.append(title);const lists=n('div','fox-leaders');for(const kind of ['batters','bowlers']){const list=n('div','fox-leader-list'),rows=i[kind].filter(r=>kind==='batters'?r.runs!==null:r.figures).slice().sort((a,b)=>kind==='batters'?b.runs-a.runs:(b.wickets??0)-(a.wickets??0)||(a.runs??9999)-(b.runs??9999)).slice(0,4);if(!rows.length)list.append(n('p','','Details unavailable'));for(const row of rows){const line=n('div','fox-leader');line.append(n('span','',row.name));if(kind==='batters')line.append(n('b','',show(row.runs)+(row.active?'*':'')),n('small','',show(row.balls)));else line.append(n('b','',row.wickets!==null&&row.wickets!==undefined?row.wickets+'–'+row.runs:show(row.figures)));list.append(line);}lists.append(list);}part.append(lists);e.append(part);}return e;}
 function apply(g,s){const pack=g?.config.pack==='fox_odi'?'fox_odi':'bbl';document.body.dataset.pack=pack;let target=$('targetLabel');if(!target){target=n('span','score-target');target.id='targetLabel';$('total').parentElement.insertBefore(target,$('total').nextSibling);}target.hidden=pack!=='fox_odi'||g.target===null||g.target===undefined;target.textContent='TARGET '+g.target;}
 function render(g,s,helpers){
  const active=g.active,full=$('statGraphic'),small=$('breakGraphic'),wicket=$('wicketGraphic'),surge=$('powerSurge'),signature=JSON.stringify([g,s.bowler,s.team1,s.team2,s.logo1,s.logo2]);if(signature===last)return lastFull;last=signature;lastFull=false;
  for(const e of [full,small,wicket,surge])if(e)e.hidden=true;
  if(!s.visible)return false;
  if(g.power_surge&&g.innings.length){const current=g.innings.at(-1);surge.textContent='POWER SURGE';surge.style.backgroundColor=current.color;surge.style.color=ink(colour(current.color));surge.hidden=false;}
  if(!active)return false;
  const kind=active.kind,i=(['batting_card','bowling_card'].includes(kind)?g.innings.at(-1):g.innings[active.innings])||g.innings.at(-1),p=g.presentation||{details:{},teams:[]},d=p.details||{},team=active.team||(kind==='bowling_card'?i?.opposition:i?.team)||s.team1,a=appearance(g,s,team),profile=p.teams?.find(t=>key(t.team)===key(a.team));
  theme(full,a);theme(small,a);theme(wicket,a);full.replaceChildren();small.replaceChildren();wicket.replaceChildren();full.className='stat-graphic fox-panel fox-'+kind;small.className='break-graphic fox-small fox-'+kind;wicket.className='wicket-graphic fox-player';
  if(kind==='innings_break'||kind==='toss'||kind==='win'||kind==='coming_up'){
   let badge;
   if(kind==='innings_break'&&i)badge=mini(a,'INNINGS BREAK',i.team,total(i));
   if(kind==='toss'){const toss=appearance(g,s,d.toss_team);theme(small,toss);badge=mini(toss,'TOSS',d.toss_team||'Toss details unavailable',d.toss_team?'WINS & '+(d.toss_choice==='field'?'FIELDS':'BATS'):'');}
   if(kind==='win'){const winning=g.innings.find(v=>(g.result||'').startsWith(v.team+' wins')),win=winning?appearance(g,s,winning.team):a;theme(small,win);badge=mini(win,'MATCH RESULT',g.result||'Result unavailable','');}
   if(kind==='coming_up'){badge=mini(a,'COMING UP',d.coming_title||`${s.team1} v ${s.team2}`,d.coming_subtitle||'');if(d.coming_image)small.append(image(d.coming_image,'fox-coming-image','Coming up'));}
   if(badge){small.append(badge);small.hidden=false;}surge.hidden=true;lastFull=true;return true;
  }
  if(kind==='sponsor'){const e=n('div','fox-sponsor-content');if(d.sponsor_image)e.append(image(d.sponsor_image,'fox-sponsor-logo',d.sponsor_name));e.append(n('strong','',d.sponsor_name||'Sponsor'),n('span','',d.sponsor_caption||''));small.append(e);small.hidden=false;return false;}
  if(kind==='player_batting'||kind==='player_bowling'||kind==='wicket_card'){
   const isWicket=kind==='wicket_card',name=active.player||profile?.featured||profile?.players?.[0]?.name||(kind==='player_bowling'?s.bowler:s.batter1_name),row=isWicket?i?.last_wicket:profile?.players.find(r=>r.name===name);
   if(isWicket&&!row)return false;const title=n('header','fox-player-heading');if(a.logo)title.append(image(a.logo,'fox-mini-logo',a.team));const copy=n('div');copy.append(n('strong','',isWicket?row.name:name||'Player details unavailable'),n('small','',isWicket?row.dismissal||'Out':d.career_label||'ODI CAREER'));title.append(copy);
   if(isWicket){const figures=n('div','fox-player-figures');figures.append(n('b','',show(row.runs)),n('span','',show(row.balls)));title.append(figures);}wicket.append(title);
   const stats=n('div','fox-player-stats'),fields=isWicket?[['DOTS','dots'],['SCORING SHOTS','scoring_shots'],['FOURS','fours'],['SIXES','sixes'],['STRIKE RATE','strike_rate']]:kind==='player_batting'?[['AGE','age'],['MATCHES','matches'],['RUNS','runs'],['STRIKE RATE','strike_rate'],['AVERAGE','average'],['BEST','best']]:[['AGE','age'],['MATCHES','matches'],['WICKETS','wickets'],['AVERAGE','average'],['ECONOMY','economy'],['BEST','best']];for(const [label,field]of fields){const cell=n('div');cell.append(n('small','',label),n('b','',show(row?.[field])));stats.append(cell);}wicket.append(stats);wicket.hidden=false;return !isWicket&&(s.runs===''||s.runs===null);
  }
  full.append(header(g,a,kind==='match_summary'?'MATCH SUMMARY':kind==='run_chart'?a.team:a.team));
  if(kind==='lineup'){
   const selection=p.lineups?.find(t=>t.match_id===g.match_id&&key(t.team)===key(a.team)),roster=selection?(profile?.players||[]).filter(r=>selection.players.includes(r.name)):profile?.players;
   const body=n('div','fox-lineup-body'),observed=g.innings.find(v=>key(v.team)===key(a.team))?.batters||[],players=selection?roster:roster?.length?roster:observed,featured=players.find(r=>r.name===profile?.featured)||players.find(r=>r.captain)||players[0],list=n('div','fox-lineup-list');
   if(!players.length)list.append(n('p','','Add this team’s lineup in Graphics pack setup.'));
   for(const row of players.slice(0,24)){const line=n('div',row===featured?'fox-lineup-row fox-active':'fox-lineup-row');line.append(n('span','',row.name+(row.captain?' (c)':'')));const role=n('span','fox-role',({batter:'╱',bowler:'●',allrounder:'╱ ●',keeper:'WK'})[row.role]||'');role.setAttribute('aria-label',row.role||'Role unavailable');line.append(role);list.append(line);}body.append(list);
   if(featured?.photo)body.append(image(featured.photo,'fox-portrait',featured.name));else if(a.logo)body.append(image(a.logo,'fox-lineup-logo',a.team));if(!profile?.players?.length)list.append(n('small','','Observed players · full lineup not provided'));full.append(body);lastFull=true;
  }else if(kind==='match_summary'){
   full.append(summary(g));const result=n('footer','fox-result',g.result||'MATCH IN PROGRESS'),win=g.innings.find(v=>(g.result||'').startsWith(v.team+' wins'))||i;if(win)theme(result,win);full.append(result);lastFull=true;
  }else if(i){
   const body=n('div','fox-card-body');
   if(kind==='run_chart')body.append(helpers.chart(i,g.config,active.innings));
   else if(kind==='bowling_card'){
    body.append(table(['BOWLER','OVERS','MAIDENS','RUNS','WICKETS','ECONOMY'],(i.bowlers.length?i.bowlers:[{name:'Waiting for bowling details'}]).slice(0,15).map(r=>({active:r.name===s.bowler,values:[r.name,r.overs,r.maidens,r.runs,r.wickets,r.economy?.toFixed(2)]}))));
    const fow=n('div','fox-fow');fow.append(n('small','','FALL OF WICKET'));for(const event of i.wicket_events||[]){const cell=n('span');cell.append(n('small','',event.number),n('b','',event.runs));fow.append(cell);}body.append(fow);
   }else body.append(table(['BATTER','DISMISSAL','RUNS','BALLS'],(i.batters.length?i.batters:[{name:'Waiting for batting details',runs:null}]).slice(0,15).map(r=>({active:r.active,values:[r.name,r.dismissal||(r.active?'not out':''),r.runs,r.balls]}))));
   full.append(body,footer(i,kind==='bowling_card'));lastFull=true;
  }
  full.hidden=!lastFull;if(lastFull)surge.hidden=true;return lastFull;
 }
 function reset(){if(last){$('wicketGraphic').className='wicket-graphic';$('breakGraphic').className='break-graphic';$('statGraphic').className='stat-graphic';}last='';lastFull=false;}
 return {apply,render,reset};
})();

window.FoxEvents=(()=>{'use strict';let current=null,seen=new Set(),box=null,until=0;
 function hide(){if(box)box.hidden=true;document.body.classList.remove('fox-animating');current=null;}
 function render(g,time,allowed){if(!box){box=document.createElement('aside');box.id='packEvent';box.hidden=true;box.setAttribute('aria-label','Scoring event animation');document.body.append(box);}if(!allowed||g.config.pack!=='fox_odi'||!g.config.event_animations){hide();return;}const event=g.event;if(!event){hide();return;}
  if(seen.size>300)seen=new Set([...seen].slice(-200));
  if(current===event.id){if(time>=until)hide();return;}if(seen.has(event.id)||time-event.at>5||time<event.at)return;seen.add(event.id);current=event.id;until=event.at+(event.kind==='wide'?3:4.5);
  const i=g.innings.at(-1),c=event.kind==='wicket'?i?.opposition_color:i?.color;box.style.setProperty('--event-team',/^#[\da-f]{6}$/i.test(c)?c:'#b8e34b');box.className='fox-event fox-event-'+event.kind;box.replaceChildren();const trail=document.createElement('div');trail.className='fox-event-trail';trail.textContent=Array(12).fill(event.kind.toUpperCase()).join('   ');const bars=document.createElement('div');bars.className='fox-event-bars';for(let n=0;n<9;n++)bars.append(document.createElement('i'));const title=document.createElement('strong');title.textContent=event.kind.toUpperCase();box.append(trail,bars,title);box.hidden=false;document.body.classList.add('fox-animating');
 }
 return {render,hide};
})();
