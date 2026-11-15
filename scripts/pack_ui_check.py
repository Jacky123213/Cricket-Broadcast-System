"""Real browser preset/layout/reel checks with disposable synthetic match data."""
import base64
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from unittest.mock import patch


def check(output):
    import uvicorn
    from websockets.sync.client import connect
    from server.config import Settings
    from server.main import create_app
    from server.broadcast_graphics import new_innings
    from run import wait_for_server

    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    app=create_app(Settings(data_root=output/'data',ssl_certfile=None,ssl_keyfile=None))
    score=app.state.scoreboard
    score.save(dict(source='manual',team1='Pavilion XI',team2='Creek XI',color1='#35a7df',color2='#00e76c',runs='94',wickets='4',overs='14.1',striker='1',batter1_name='A. Player',batter2_name='B. Player',batter1_runs='14',batter2_runs='24',batter1_balls='12',batter2_balls='26',bowler='C. Bowler',bowler_figures='2–7',bowler_overs='2.1',deliveries='W'))
    score.flush()
    first=new_innings(score.data)
    first.update(runs=94,wickets=4,balls=85,extras=5,tracked_from_start=True,
        batters=[dict(name=('Very long player name for overflow checking' if i==10 else 'Player '+str(i+1)),runs=14 if i==0 else 10-i if i<10 else 0,balls=12+i,active=i in (4,5),dismissal='not out' if i in (4,5) else 'c Fielder b Bowler',shots={},fours=0,sixes=0,dots=3) for i in range(11)],
        bowlers=[dict(name='Bowler '+str(i+1),figures=f'{i}–{12+i*4}',overs='3.0',maidens=0) for i in range(5)],
        samples={str(i*6):i*6 for i in range(15)},
        wicket_events=[dict(number=i+1,runs=(i+1)*12,balls=(i+1)*15,at=time.time()-60) for i in range(4)])
    first['last_wicket']={**copy.deepcopy(first['batters'][0]),'out_number':4}
    score.graphics.innings=[first];score.graphics.previous=copy.deepcopy(score.data)
    app.state.devices.connected_snapshot=lambda:[dict(device_id='camera1',name='Synthetic camera',role='UMPIRE_POV')]
    score.packs.save({'team':dict(team='Pavilion XI',featured='Player 1',players=[dict(name='Player '+str(i+1),role='allrounder' if i<5 else 'bowler',captain=i==0,age='25',matches='12',runs='140',wickets='8',average='28.0',strike_rate='115.2',economy='5.3',best='40*') for i in range(11)]),
                      'details':dict(career_label='ODI CAREER',toss_team='Creek XI',toss_choice='field',coming_title='Pavilion XI v Creek XI',coming_subtitle='Tomorrow · Backyard Oval',sponsor_name='Local Club',sponsor_caption='Supporting backyard cricket')})
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=0,log_config=None))
    thread=threading.Thread(target=server.run,daemon=True)
    edge=Path(os.environ.get('PROGRAMFILES(X86)',r'C:\Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe'
    with patch('server.main.start_receiver'):
        thread.start()
        try:
            wait_for_server(server,thread)
            origin='http://127.0.0.1:'+str(server.servers[0].sockets[0].getsockname()[1])
            profile=Path(tempfile.mkdtemp(prefix='edge-packs-',dir=output))
            process=subprocess.Popen([str(edge),'--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--no-proxy-server','--disable-extensions','--hide-scrollbars','--autoplay-policy=no-user-gesture-required','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',f'--user-data-dir={profile}','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            deadline=time.monotonic()+15
            while not (profile/'DevToolsActivePort').exists() and time.monotonic()<deadline:time.sleep(.1)
            port=(profile/'DevToolsActivePort').read_text().splitlines()[0]
            targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list'))
            socket=connect(next(t['webSocketDebuggerUrl'] for t in targets if t['type']=='page'),open_timeout=5,legacy=True)
            sequence=0

            def call(method,params=None):
                nonlocal sequence
                sequence+=1;own=sequence;socket.send(json.dumps(dict(id=own,method=method,params=params or {})))
                while True:
                    msg=json.loads(socket.recv(timeout=15))
                    if msg.get('id')==own:
                        if 'error' in msg:raise RuntimeError(str(msg['error']))
                        return msg.get('result',{})

            def js(expression):
                result=call('Runtime.evaluate',dict(expression=expression,returnByValue=True,awaitPromise=True))
                if result.get('exceptionDetails'):raise AssertionError(str(result['exceptionDetails']))
                return result.get('result',{}).get('value')

            def wait(expression,seconds=15):
                until=time.monotonic()+seconds
                while time.monotonic()<until:
                    if js(expression):return
                    time.sleep(.1)
                raise AssertionError('Browser wait: '+expression+'; '+str(js("({error:document.getElementById('error')?.textContent,status:document.getElementById('status')?.textContent,processing:document.querySelector('.fielding-processing')?.textContent})")))

            def size(width,height):call('Emulation.setDeviceMetricsOverride',dict(width=width,height=height,deviceScaleFactor=1,mobile=False))
            def navigate(path):call('Page.navigate',dict(url=origin+path))
            def shot(name):(output/name).write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['data']))

            call('Page.enable');size(1280,720);navigate('/scoreboard?legacy=1')
            wait("document.getElementById('foxTeam')?.value==='Pavilion XI'")
            portrait=js("(()=>{const c=document.createElement('canvas');c.width=400;c.height=600;const g=c.getContext('2d');g.fillStyle='#35a7df';g.beginPath();g.ellipse(200,530,170,190,0,0,7);g.fill();g.fillStyle='#c6cbd0';g.beginPath();g.arc(200,200,100,0,7);g.fill();return c.toDataURL('image/png')})()")
            art=score.packs.upload(portrait)
            team=copy.deepcopy(score.packs.snapshot()['teams'][0]);team['players'][0]['photo']=art
            score.packs.save({'team':team,'details':{**score.packs.snapshot()['details'],'sponsor_image':art}})
            js("document.getElementById('graphicPack').value='fox_odi';document.getElementById('packSettings').dispatchEvent(new Event('input',{bubbles:true}));document.getElementById('packSettings').requestSubmit()")
            wait("document.getElementById('packStatus').textContent.includes('saved')")
            assert score.graphics.config['pack']=='fox_odi'
            results=[dict(preset_saved_from_real_control=True)]
            size(390,844);shot('mobile-setup.png')
            assert js('document.documentElement.scrollWidth<=innerWidth')
            size(1280,720);navigate('/overlay');wait("document.body.dataset.pack==='fox_odi'")
            # Synthetic test background, kept out of the shipped app assets.
            js("document.body.style.background='linear-gradient(120deg,#314c3b,#22362e)'")
            shot('fox-scorebar.png')
            for kind in ['batting_card','bowling_card','wicket_card','lineup','player_batting','player_bowling','coming_up','toss','sponsor','win','innings_break','run_chart','match_summary']:
                if kind in ('win','match_summary'):
                    score.graphics.config['result_override']='Pavilion XI wins by 4 wickets'
                if kind=='match_summary':
                    second=copy.deepcopy(first)
                    second.update(team='Creek XI',opposition='Pavilion XI',color='#00e76c',opposition_color='#35a7df',runs=96,wickets=6,balls=95)
                    score.graphics.innings=[first,second]
                score.broadcast_action(dict(action='show',kind=kind,team='Pavilion XI' if kind in ('lineup','player_batting','player_bowling') else '',player='Player 1'))
                wait(f"document.querySelector('.fox-{kind}:not([hidden])')!==null" if kind not in ('player_batting','player_bowling','wicket_card') else "!document.getElementById('wicketGraphic').hidden")
                time.sleep(.25);shot(kind+'.png')
                assert js('document.documentElement.scrollWidth<=innerWidth')
                if kind in ('batting_card','bowling_card'):
                    assert js("document.querySelector('.fox-table').getBoundingClientRect().bottom<=document.getElementById('statGraphic').getBoundingClientRect().bottom")
                if kind=='lineup':
                    assert js("document.querySelector('.fox-heading').getBoundingClientRect().bottom<=document.querySelector('.fox-lineup-body').getBoundingClientRect().top")
                    wait("document.querySelector('.fox-portrait')?.naturalWidth===400")
                if kind=='sponsor':wait("document.querySelector('.fox-sponsor-logo')?.naturalWidth===400")
                results.append(dict(graphic=kind,visible=True))
            for width,height in [(1920,1080),(1366,768),(1920,600),(390,844)]:
                size(width,height);time.sleep(.2)
                issues=js("(()=>{const out=[];for(const row of document.querySelectorAll('.fox-leader')){const r=row.getBoundingClientRect();for(const child of row.children){const c=child.getBoundingClientRect();if(c.top<r.top-.6||c.bottom>r.bottom+.6)out.push(row.textContent)}}return out})()")
                assert not issues,(width,height,issues)
                assert js('document.documentElement.scrollWidth<=innerWidth')
                shot(f'summary-{width}x{height}.png')
            size(1280,720);score.broadcast_action({'action':'hide'});wait("document.getElementById('statGraphic').hidden")
            js("window.drawDiagnosticEvent=FoxEvents.render.bind(FoxEvents);FoxEvents.render=(g,t,a)=>g.event?.id?.startsWith('diagnostic-')?drawDiagnosticEvent(g,t,a):undefined")
            for kind in ['four','six','wicket','wide']:
                js(f"FoxEvents.render({{config:{{pack:'fox_odi',event_animations:true}},event:{{id:'diagnostic-{kind}',kind:'{kind}',at:100}},innings:[{{color:'#35a7df',opposition_color:'#00e76c'}}]}},100,true)")
                time.sleep(2.3);shot('animation-'+kind+'.png')
                js('FoxEvents.hide()')
            js('FoxEvents.render=window.drawDiagnosticEvent')
            score.broadcast_settings({'pack':'bbl'});wait("document.body.dataset.pack==='bbl'");shot('bbl-preserved.png')
            # Generate actual encoded footage, then archive two wickets and a boundary.
            navigate('/api/health');time.sleep(.2)
            raw=base64.b64decode(js("""(async()=>{const c=document.createElement('canvas');c.width=640;c.height=360;const ctx=c.getContext('2d');let f=0;const draw=()=>{ctx.fillStyle='#2d5d45';ctx.fillRect(0,0,640,360);ctx.fillStyle='#ae9a69';ctx.fillRect(240,35,160,280);ctx.fillStyle='#fff';ctx.font='22px Arial';ctx.fillText('SYNTHETIC WICKET REPLAY',15,30);ctx.fillStyle='#ffe342';ctx.beginPath();ctx.arc(260+f++%110,240,9,0,7);ctx.fill();};draw();const stream=c.captureStream(20),rec=new MediaRecorder(stream,{mimeType:'video/webm;codecs=vp8'}),parts=[],done=new Promise(r=>rec.onstop=r);rec.ondataavailable=e=>parts.push(e.data);const timer=setInterval(draw,50);rec.start();await new Promise(r=>setTimeout(r,3100));rec.stop();await done;clearInterval(timer);stream.getTracks().forEach(t=>t.stop());const a=new Uint8Array(await new Blob(parts).arrayBuffer());let b='';for(const n of a)b+=String.fromCharCode(n);return btoa(b)})()"""))
            score.broadcast_settings({'pack':'fox_odi','auto_break_highlights':False});score.graphics.active=None;score.graphics.innings=[first];score.graphics.phase='innings_break'
            first['delivery_history']={f'0:{i}':dict(id=f'0:{i}',over=1,ball=f'0.{i+1}',legal_ball=i+1,token='W' if i<2 else '4',kind='wicket' if i<2 else 'four',runs=0 if i<2 else 4,legal=True,text='Wicket' if i<2 else '4 runs',batter=f'Dismissed player {i+1}',bowler='Fielding bowler',at=time.time()-30) for i in range(3)}
            archived=[];media=app.state.live_match.root/'media';media.mkdir(parents=True,exist_ok=True)
            for index,event in enumerate(app.state.live_match.state()['innings'][0]['deliveries']):
                cid=f'{index+1:032x}';(media/(cid+'.clip')).write_bytes(raw);start=100000+index*6000
                clip=dict(id=cid,device_id='camera1',start_ms=start,end_ms=start+3100,bytes=len(raw),mime='video/webm',audio=False,url='/api/live/media/'+cid)
                archived.append(dict(id='highlight'+str(index),event_id=event['id'],match_id=score.graphics.match_id,innings=0,kind=event['kind'],title=event['batter'],start_ms=start,end_ms=start+3000,clips=[clip],partial=False,coverage=[[start,start+3000]]))
            app.state.live_match.highlights=archived
            app.state.live_match.save_settings({'clips_enabled':True})
            app.state.broadcast_desk.program['camera_id']='camera1'
            navigate('/broadcast?follow=1&clean=1&client=obs&audio=0');wait('!!window.CricketProgram')
            js("fetch('/api/live/fielding-highlights',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(async r=>{if(!r.ok)throw Error(await r.text());return r.json()})")
            wait("document.querySelector('.fielding-reel video:not([hidden])')?.videoWidth===640")
            wait("document.querySelector('.fielding-caption')?.textContent.includes('Creek XI')")
            wait("document.querySelector('.fielding-caption')?.textContent.includes('Dismissed player 2')",seconds=12)
            shot('fielding-highlights.png')
            assert js("performance.getEntriesByType('resource').filter(r=>r.name.includes('/api/live/media/')).length")==2
            wait("document.querySelector('.fielding-reel')===null",seconds=12)
            assert app.state.broadcast_desk.program['mode']=='live'
            app.state.live_match.save_settings({'clips_enabled':False})
            rejected=js("fetch('/api/live/fielding-highlights',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(r=>r.status)")
            assert rejected==403
            results.append(dict(real_two_wicket_reel_played=True,boundary_excluded=True,complete_preload_before_play=True,return_live=True,disabled_highlights_blocked=True))
            (output/'results.json').write_text(json.dumps(results,indent=2),'utf-8');print(json.dumps(results,indent=2),flush=True)
        finally:
            if 'socket' in locals():socket.close()
            if 'process' in locals():process.terminate();process.wait(timeout=10)
            server.should_exit=True;thread.join(10)


if __name__=='__main__':
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    check(sys.argv[1])
