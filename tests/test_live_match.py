import asyncio
import copy
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from server.config import Settings
from server.main import create_app
from server.broadcast_graphics import BroadcastGraphics
from server.live_match import LiveMatch
from server.match_events import token_info
from server.scoreboard_state import State, DEFAULT
from server.replay import now_ms


def observe(g,now=100,**changes):
    score={**DEFAULT,'source':'manual','team1':'Blue XI','team2':'Red XI','runs':'0','wickets':'0','overs':'0.0',**changes}
    g.observe(score,now);return score


def test_confirmed_zero_boundaries_not_dash_and_unknown_not_invented():
    g=BroadcastGraphics()
    for runs in (0,1,2,3):
        row=g.batter_stats({'name':'Batter','runs':runs,'balls':5,'shots':{}})
        assert row['fours']==0 and row['sixes']==0
    row=g.batter_stats({'name':'Batter','runs':None,'balls':None,'shots':{}})
    assert row['fours'] is None and row['sixes'] is None
    row=g.batter_stats({'name':'Batter','runs':5,'balls':5,'shots':{}})
    assert row['fours'] is None and row['sixes']==0


def test_delivery_snapshots_deduplicate_corrections_extras_and_wicket_details():
    g=BroadcastGraphics();s=observe(g,batter1_name='Ali',batter1_runs='0',batter1_balls='0',striker='1',bowler='Dee')
    for n,token in enumerate(['0','4','W'],1):
        s={**s,'overs':'0.'+str(n),'runs':'4','deliveries':' '.join(['0','4','W'][:n]),'wickets':'1' if n==3 else '0'}
        if n==3:s.update(last_wicket_name='Ali',last_wicket_runs='4',last_wicket_balls='3',last_wicket_code='b',last_wicket_bowler='Dee')
        g.observe(s,100+n)
    rows=g.stats(g.innings[0],include_history=True)['deliveries']
    assert len(rows)==3 and rows[1]['kind']=='four' and rows[-1]['dismissal']=='b Dee'
    g.observe(s,110);assert len(g.stats(g.innings[0],include_history=True)['deliveries'])==3
    s.update(overs='0.2',wickets='0',deliveries='0 4');g.observe(s,111)
    assert len(g.stats(g.innings[0],include_history=True)['deliveries'])==2
    assert token_info('2wd')=={'kind':'extra','runs':2,'legal':False,'text':'2 wides'}
    assert token_info('Nb')['legal'] is False and token_info('2lb')['legal'] is True
    assert token_info('unrecognised')['runs'] is None
    # The normal broadcast/program-history payload must not retain the full ledger.
    assert 'deliveries' not in g.stats(g.innings[0]) and 'worm' not in g.stats(g.innings[0])


def test_joining_mid_over_has_no_fabricated_video_time():
    g=BroadcastGraphics();observe(g,overs='5.3',runs='38',deliveries='0 4 1')
    rows=g.stats(g.innings[0],include_history=True)['deliveries']
    assert len(rows)==3 and all(row['at'] is None and row['batter']=='' for row in rows)


def test_legacy_match_migrates_identity_and_recorded_tokens_without_guessing_times(tmp_path):
    import json
    folder=tmp_path/'data'/'scoreboard'
    state=State(folder);observe(state.graphics,overs='0.2',runs='4',deliveries='0 4')
    saved=state.graphics.export();saved.pop('match_id');saved['innings'][0].pop('delivery_history')
    (folder/'broadcast.json').write_text(json.dumps(saved),'utf-8')
    restored=State(folder)
    from types import SimpleNamespace
    settings=SimpleNamespace(scoreboard_path=folder,data_root=tmp_path)
    live=LiveMatch(settings,restored,None,None);data=live.state()
    assert [r['token'] for r in data['innings'][0]['deliveries']]==['0','4']
    assert all(r['at'] is None for r in data['innings'][0]['deliveries'])
    assert json.loads((folder/'broadcast.json').read_text())['match_id']==data['match_id']
    assert State(folder).graphics.match_id==data['match_id']


def test_duck_requires_confirmed_zero_dismissal_and_unique_match_identity():
    g=BroadcastGraphics();s=observe(g,batter1_name='Ali',batter1_runs='0',batter1_balls='0')
    s.update(overs='0.1',wickets='1',deliveries='W',last_wicket_name='Ali',last_wicket_runs='0',last_wicket_balls='1',last_wicket_code='b')
    g.observe(s,101);duck=g.snapshot(s,102)['duck'];assert duck['name']=='Ali' and duck['at']==101
    restored=BroadcastGraphics(g.export());assert restored.match_id==g.match_id
    assert BroadcastGraphics().match_id!=g.match_id
    s.update(wickets='0',overs='0.0',deliveries='');g.observe(s,103);assert g.snapshot(s,103)['duck'] is None


def test_live_routes_are_read_only_safe_and_broadcast_defaults_to_shared_program(tmp_path):
    app=create_app(Settings(data_root=tmp_path,host='127.0.0.1'))
    with TestClient(app) as c:
        assert c.get('/live').status_code==200 and c.get('/ball-by-ball').status_code==200
        assert c.get('/cameras').text.count('src="/camera?slot=')==3
        assert 'Duck' not in c.get('/live').text
        data=c.get('/api/live/state').json();assert not data['config']['clips_enabled'] and not data['config']['stream_enabled']
        assert 'logs' not in data and 'packet_count' not in data
        assert c.get('/broadcast',follow_redirects=False).headers['location']=='/broadcast?follow=1'
        assert c.get('/broadcast?camera=fixed',follow_redirects=False).status_code==200
        assert c.post('/api/live/settings',json={'clips_enabled':'yes'}).status_code==422
        assert c.post('/api/live/settings',json={'unknown':True}).status_code==422
        assert c.post('/api/live/highlights',json={}).status_code==409
        assert c.get('/api/live/media/secret').status_code==403
        assert c.get('/static/duck-out.mp4').status_code==200


def test_highlights_are_opt_in_persisted_outside_temp_buffer_and_blocked_when_disabled(tmp_path):
    app=create_app(Settings(data_root=tmp_path,host='127.0.0.1'))
    live=app.state.live_match;replay=app.state.replay_store
    replay.initialise();at=now_ms();key='a'*32;body=b'test encoded media'
    (replay.root/(key+'.clip')).write_bytes(body)
    replay.clips[key]={'id':key,'device_id':'cam','start_ms':at-20000,'end_ms':at+10000,'mime':'video/mp4','bytes':len(body),'url':'/api/clips/'+key}
    item={'event_id':'manual:1','match_id':'m','innings':0,'title':'Saved','kind':'manual','ball':'','camera_id':'cam','start_ms':at-8000,'end_ms':at+5000}
    assert asyncio.run(live.capture(item)) is True and not live.highlights
    live.save_settings({'clips_enabled':True})
    assert asyncio.run(live.capture(item)) is True
    assert len(live.highlights)==1 and (live.root/'media'/(key+'.clip')).read_bytes()==body
    restored=LiveMatch(app.state.settings,app.state.scoreboard,replay,app.state.broadcast_desk)
    assert restored.highlights[0]['title']=='Saved'
    # Replay startup can remove temporary clips without losing the archive.
    replay.initialise();assert (live.root/'media'/(key+'.clip')).exists()
    with TestClient(app) as c:
        assert c.get('/api/live/highlights/'+live.highlights[0]['id']).status_code==200
        assert c.get('/api/live/media/'+key).content==body
        c.post('/api/live/settings',json={'clips_enabled':False})
        assert c.get('/api/live/media/'+key).status_code==403
        assert (live.root/'media'/(key+'.clip')).read_bytes()==body


def test_auto_highlight_is_queued_once_from_selected_program_camera(tmp_path):
    app=create_app(Settings(data_root=tmp_path,host='127.0.0.1'))
    live=app.state.live_match;state=app.state.scoreboard;g=state.graphics
    s=observe(g,time.time(),batter1_name='Ali',striker='1',bowler='Dee')
    live.save_settings({'clips_enabled':True})
    app.state.broadcast_desk.program['camera_id']='selected-camera'
    s.update(overs='0.1',runs='4',deliveries='4');g.observe(s,time.time())
    asyncio.run(live.tick());assert len(live.pending)==1
    first=next(iter(live.pending.values()));assert first['camera_id']=='selected-camera' and first['kind']=='four'
    asyncio.run(live.tick());assert len(live.pending)==1
    s.update(overs='0.0',runs='0',deliveries='');g.observe(s,time.time());asyncio.run(live.tick());assert not live.pending


def test_three_camera_connections_on_one_pc_remain_separate_and_program_switches(tmp_path):
    from contextlib import ExitStack
    app=create_app(Settings(data_root=tmp_path,host='127.0.0.1'))
    with TestClient(app) as c, ExitStack() as stack:
        cameras=[]
        for n in range(1,4):
            camera=stack.enter_context(c.websocket_connect('/ws/camera'))
            camera.send_json({'type':'register','device_id':f'pc-camera-{n}','name':f'PC camera {n}','role':'UMPIRE_POV'})
            assert camera.receive_json()['type']=='registered'
            cameras.append(camera)
        assert len([d for d in c.get('/api/devices').json()['devices'] if d['status']=='connected'])==3
        for n in (2,3,1):
            r=c.post('/api/broadcast/program',json={'action':'camera','camera_id':f'pc-camera-{n}'})
            assert r.status_code==200 and r.json()['program']['camera_id']==f'pc-camera-{n}'
            assert c.get('/api/broadcast/program').json()['program']['camera_id']==f'pc-camera-{n}'


@pytest.mark.parametrize('selected,expected',[
    ('save_fours','four'),('save_sixes','six'),('save_wickets','wicket'),
    ('save_other_runs','runs'),('save_extras','extra'),('save_dots','dot'),(None,None)])
def test_only_selected_new_delivery_types_queue_clips(tmp_path,selected,expected):
    app=create_app(Settings(data_root=tmp_path,host='127.0.0.1'));live=app.state.live_match;g=app.state.scoreboard.graphics
    options={key:False for key in ('save_fours','save_sixes','save_wickets','save_other_runs','save_extras','save_dots')}
    if selected:options[selected]=True
    live.save_settings({'clips_enabled':True,**options});app.state.broadcast_desk.program['camera_id']='selected'
    s=observe(g,time.time(),batter1_name='Ali',striker='1',bowler='Dee');tokens=[];legal=0;runs=0
    for token in ('0','1','4','6','2wd','W'):
        tokens.append(token);legal+=token!='2wd';runs+=0 if token in ('W','0') else 2 if token=='2wd' else int(token)
        s.update(deliveries=' '.join(tokens),overs='0.'+str(legal),runs=str(runs),wickets='1' if token=='W' else '0')
        g.observe(s,time.time());asyncio.run(live.tick())
    assert [p['kind'] for p in live.pending.values()]==([expected] if expected else [])
    # Re-enabling types does not retroactively capture already-seen balls.
    live.save_settings({key:True for key in options});asyncio.run(live.tick())
    assert len(live.pending)==(1 if expected else 0)
