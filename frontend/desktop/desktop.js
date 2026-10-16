"use strict";
const views=[...document.querySelectorAll('.view')];
const byId=id=>document.getElementById(id);
const serverDot=byId('serverDot'),serverText=byId('serverText'),cameraCount=byId('cameraCount'),scoreCount=byId('scoreCount'),secureState=byId('secureState'),overlayUrl=byId('overlayUrl'),diagServer=byId('diagServer'),diagBluetooth=byId('diagBluetooth'),diagSleep=byId('diagSleep'),copyOverlay=byId('copyOverlay');
const localLiveSwitch=byId('localLiveViews'),liveFrames=[...document.querySelectorAll('iframe[data-live-src]')];
let studioConnection={name:'Studio PC',client:false,local_operator:false};
try{studioConnection=JSON.parse(byId('studioConnection')?.textContent||'{}');}catch{/* Source previews have no server substitution. */}
function studioIdentity(name){byId('studioMode').textContent=studioConnection.client?'Connected to':'Studio host';byId('studioName').textContent=name||studioConnection.name;byId('studioAddress').textContent=location.host;}
studioIdentity(studioConnection.name);
let hadConnection=false,connectionLost=false;
let localLiveEnabled=true;
try{localLiveEnabled=localStorage.getItem('cricket.local-live-views.v1')!=='off';}catch{/* Storage restrictions never prevent local control. */}
function localLiveViews(){
  localLiveSwitch.checked=localLiveEnabled;
  for(const frame of liveFrames){
    const view=frame.closest('.view');frame.hidden=!localLiveEnabled;view.querySelector('.local-live-paused').hidden=localLiveEnabled;
    if(!localLiveEnabled){if(frame.getAttribute('src')&&frame.getAttribute('src')!=='about:blank')frame.src='about:blank';}
    else if(view.classList.contains('active')&&frame.getAttribute('src')!==frame.dataset.liveSrc)frame.src=frame.dataset.liveSrc;
  }
}
localLiveSwitch.addEventListener('change',()=>{localLiveEnabled=localLiveSwitch.checked;try{localStorage.setItem('cricket.local-live-views.v1',localLiveEnabled?'on':'off');}catch{}localLiveViews();});
function show(name){if(!views.some(view=>view.id===`view-${name}`))name='match-day';views.forEach(view=>view.classList.toggle('active',view.id===`view-${name}`));document.querySelectorAll('.nav').forEach(button=>button.classList.toggle('active',button.dataset.view===name));history.replaceState(null,'',`#${name}`);localLiveViews();}
document.querySelectorAll('[data-view]').forEach(item=>item.addEventListener('click',event=>{event.preventDefault();show(item.dataset.view);}));
document.querySelectorAll('[data-score-section]').forEach(button=>button.addEventListener('click',()=>{show('scoreboard');const frame=byId('scoreboardFrame').contentWindow;frame.CricketSections?.open(button.dataset.scoreSection);frame.location.hash=button.dataset.scoreSection;frame.document.getElementById(button.dataset.scoreSection)?.scrollIntoView({block:'start'});}));
show(location.hash.slice(1)||'match-day');
window.addEventListener('message',event=>{if(event.source!==byId('matchDayFrame').contentWindow||event.origin!==location.origin||event.data?.type!=='match-day-navigate')return;const {view,section}=event.data;if(!['scoreboard','replay','help','settings'].includes(view))return;show(view);if(view==='scoreboard'&&['graphicControls','statsEditor'].includes(section)){const frame=byId('scoreboardFrame').contentWindow;frame.CricketSections?.open(section);frame.location.hash=section;frame.document.getElementById(section)?.scrollIntoView({block:'start'});}});
const fillLinks=(id,urls,label)=>{const box=document.getElementById(id);box.replaceChildren(...urls.map((url,index)=>{const a=document.createElement('a');a.href=url;a.target='_blank';a.rel='noopener';a.textContent=`${label}${urls.length>1?' '+(index+1):''}: ${url}`;return a;}));};
function outputAddress(){const url=byId('overlayAddress').value;if(!url)return;overlayUrl.textContent=url;byId('broadcastLink').href=url.replace(/\/overlay$/,'/broadcast');}
byId('overlayAddress').addEventListener('change',outputAddress);
function networkOutput(data){const select=byId('overlayAddress'),urls=data.overlay_urls||[data.overlay_url];const key=urls.join('|');if(select.dataset.urls!==key){const previous=select.value;select.dataset.urls=key;select.replaceChildren(...urls.map((url,n)=>Object.assign(document.createElement('option'),{value:url,textContent:new URL(url).host+(n===0?' · preferred LAN':' · alternative adapter')})));if(urls.includes(previous))select.value=previous;}outputAddress();byId('overlayCertificate').hidden=!data.certificate_url;}
async function status(){try{const response=await fetch('/api/app-status',{cache:'no-store',signal:AbortSignal.timeout(5000)});if(response.status===401)throw Error('Approval removed. Close and reconnect with a new code.');if(!response.ok)throw Error(`HTTP ${response.status}`);const data=await response.json();serverDot.classList.add('online');serverText.textContent=studioConnection.client?`Connected to ${data.studio_name||studioConnection.name}`:'Local server ready';studioIdentity(data.studio_name);cameraCount.textContent=data.connected_cameras;scoreCount.textContent=data.score_packets;secureState.textContent=data.secure_context?'Ready':'Not configured';fillLinks('cameraLinks',data.camera_urls,'Camera');fillLinks('umpireLinks',data.umpire_urls,'Umpire');networkOutput(data);diagServer.textContent=`Online · ${data.connected_cameras} camera(s)`;diagBluetooth.textContent=data.bluetooth_status;diagSleep.textContent=data.sleep_prevention||'Status unavailable';if(connectionLost&&hadConnection&&studioConnection.client&&localLiveEnabled){for(const frame of liveFrames){if(frame.closest('.view').classList.contains('active'))frame.src=frame.dataset.liveSrc;}}hadConnection=true;connectionLost=false;}catch(error){connectionLost=true;serverDot.classList.remove('online');serverText.textContent=studioConnection.client?'Studio unavailable · reconnecting…':'Server connection lost';diagServer.textContent=error.message;}finally{setTimeout(status,2500);}}
copyOverlay.addEventListener('click',async()=>{await navigator.clipboard.writeText(overlayUrl.textContent);copyOverlay.textContent='Copied';setTimeout(()=>copyOverlay.textContent='Copy overlay URL',1500);});
status();

async function studioCommand(path,options){const response=await fetch('/api/studio-network/'+path,{cache:'no-store',...options});const data=await response.json();if(!response.ok)throw Error(data.detail||'Could not update studio connections');return data;}
function paintStudioSettings(data){byId('studioHostName').value=data.name;byId('studioAllowJoin').checked=data.allow_join;byId('studioPairCode').textContent=data.code?`${data.code} · expires in ${Math.ceil(data.code_seconds/60)} min`:data.allow_join?'Code expired · press New code':'New connections off';byId('studioCAFingerprint').textContent=data.ca_sha256||'HTTPS not prepared';byId('studioDiscovery').textContent=data.discovery||'';byId('studioNewCode').disabled=!data.allow_join;const clients=byId('studioClients');clients.replaceChildren();for(const client of data.clients||[]){const row=document.createElement('p'),name=document.createElement('span'),remove=document.createElement('button');name.textContent=client.name+' ';remove.textContent='Remove approval';remove.addEventListener('click',()=>{if(!confirm(`Remove ${client.name}'s approval? Their installed app will need a new code.`))return;studioUpdate('clients/'+encodeURIComponent(client.id),{method:'DELETE'});});row.append(name,remove);clients.append(row);}if(!data.clients?.length)clients.textContent='No installed PCs approved yet.';studioIdentity(data.name);}
async function studioUpdate(path,options){try{paintStudioSettings(await studioCommand(path,options));byId('studioNetworkStatus').textContent='Connection settings updated.';}catch(error){byId('studioNetworkStatus').textContent=error.message;}}
byId('studioSaveNetwork').addEventListener('click',()=>studioUpdate('settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:byId('studioHostName').value,allow_join:byId('studioAllowJoin').checked})}));
byId('studioNewCode').addEventListener('click',()=>studioUpdate('new-code',{method:'POST'}));
async function refreshStudioSettings(){if(!studioConnection.local_operator){byId('studioNetworkHint').textContent=studioConnection.client?'You are controlling the host studio. New PC approvals and certificates are managed in Settings on the host PC.':'Open Settings in the desktop app on the host PC to approve installed PCs.';return;}try{paintStudioSettings(await studioCommand('settings'));byId('studioNetworkControls').hidden=false;}catch(error){byId('studioNetworkStatus').textContent=error.message;}finally{setTimeout(refreshStudioSettings,10000);}}
// Do not refresh editable fields while the operator is typing or unsaved.
let editingStudio=false;
for(const field of ['studioHostName','studioAllowJoin'])byId(field).addEventListener('input',()=>editingStudio=true);
byId('studioSaveNetwork').addEventListener('click',()=>editingStudio=false);
const initialStudioRefresh=refreshStudioSettings;
refreshStudioSettings=async function(){if(editingStudio){setTimeout(refreshStudioSettings,10000);return;}return initialStudioRefresh();};
refreshStudioSettings();
