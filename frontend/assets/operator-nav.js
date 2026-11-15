/* Standalone iPad/PC controls use the same navigation as the desktop shell. */
window.CricketNavigation = (() => {
  'use strict';
  const groups = [
    ['LIVE', [['match-day','Match Day','/match-day','monitor'],['replay','Replay Studio','/umpire','film'],['scoreboard','Scoreboard','/scoreboard','score']]],
    ['PREPARE', [['match-setup','Match Setup','/match-setup','calendar'],['teams','Teams & Players','/teams','people']]],
    ['BROADCAST', [['graphics','Graphics','/graphics','layers'],['highlights','Highlights','/highlights','play']]],
    ['SYSTEM', [['connections','Connections','/connections','plug'],['settings','Settings','/settings','settings'],['help','Help','/help','help']]]
  ];
  const paths = {monitor:'M3 4h18v12H3z M8 20h8 M12 16v4', film:'M3 3h18v18H3z M7 3v18 M17 3v18 M3 8h4 M17 8h4 M3 16h4 M17 16h4',score:'M3 4h18v16H3z M7 8h2 M13 8h4 M7 12h2 M13 12h4 M7 16h10',calendar:'M4 5h16v16H4z M8 2v6 M16 2v6 M4 10h16 M8 14h2 M14 14h2 M8 18h2',people:'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M2 21v-3a7 7 0 0 1 14 0v3 M18 5a4 4 0 0 1 0 8 M19 16a5 5 0 0 1 3 5',layers:'M12 3 2 8l10 5 10-5z M2 12l10 5 10-5 M2 16l10 5 10-5',play:'M3 4h18v16H3z M10 8l6 4-6 4z',plug:'M7 3v6 M17 3v6 M5 9h14v5a7 7 0 0 1-14 0z M12 21v-5',settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z',help:'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18 M9 9a3 3 0 1 1 5 2c-2 1-2 2-2 3 M12 17h.01'};
  const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]}"/></svg>`;
  function render(host, active, desktop = false) {
    host.classList.add('operator-rail');
    host.innerHTML = `<a class="operator-brand" href="${desktop ? '#match-day' : '/match-day'}"><span>BC</span><strong>Cricket<br>Broadcast System</strong></a><nav aria-label="Application sections">${groups.map(([label, rows]) => `<div class="nav-group"><span>${label}</span>${rows.map(([id,text,url,img]) => `<${desktop ? 'button type="button"' : 'a href="'+url+'"'} class="nav${id===active?' active':''}" data-view="${id}"${id===active?' aria-current="page"':''}>${icon(img)}<span>${text}</span></${desktop?'button':'a'}>`).join('')}</div>`).join('')}</nav>`;
  }
  function standalone() {
    if (window.top !== window || document.body.classList.contains('desktop-ui') || document.body.classList.contains('broadcast-ui') || !document.body.hasAttribute('data-operator')) return;
    const rail = document.createElement('aside'); render(rail, document.body.dataset.operator); document.body.prepend(rail); document.body.classList.add('standalone-operator');
    const menu = document.createElement('button'); menu.type='button'; menu.className='operator-menu'; menu.textContent='Menu'; menu.setAttribute('aria-expanded','false'); menu.setAttribute('aria-label','Open application sections'); menu.onclick=()=>{const open=document.body.classList.toggle('nav-open');menu.setAttribute('aria-expanded',String(open));}; document.body.prepend(menu);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', standalone); else standalone();
  return {groups, render};
})();
