import base64
import copy
import time

import pytest
from fastapi.testclient import TestClient

from server.config import Settings
from server.main import create_app
from server.scoreboard_state import State


@pytest.fixture
def studio(tmp_path):
    app=create_app(Settings(data_root=tmp_path))
    return TestClient(app), app


def test_preset_upgrade_and_settings_survive_restart_and_reset(studio):
    c, app=studio
    s=app.state.scoreboard
    assert s.snapshot()['graphics']['config']['pack']=='bbl'
    assert c.post('/api/scoreboard/broadcast/settings',json={'pack':'bad'}).status_code==400
    c.post('/api/scoreboard/broadcast/settings',json={'pack':'fox_odi','event_animations':False})
    assert State(s.folder).snapshot()['graphics']['config']['pack']=='fox_odi'
    s.reset()
    assert s.snapshot()['graphics']['config']['event_animations'] is False


def test_prematch_cards_hold_and_return_to_bbl_without_changing_scores(studio):
    c, app=studio
    before=app.state.scoreboard.snapshot()['score']
    assert c.post('/api/scoreboard/broadcast/action',json={'action':'show','kind':'lineup','team':'HOME'}).status_code==400
    c.post('/api/scoreboard/broadcast/settings',json={'pack':'fox_odi'})
    assert c.post('/api/scoreboard/broadcast/action',json={'action':'show','kind':'lineup','team':'HOME'}).status_code==200
    state=app.state.scoreboard.snapshot()
    assert state['graphics']['active']['until'] is None
    assert state['score']==before
    c.post('/api/scoreboard/broadcast/settings',json={'pack':'bbl'})
    assert app.state.scoreboard.snapshot()['graphics']['active'] is None


def test_profiles_are_named_teams_and_artwork_is_local_and_validated(studio):
    c, app=studio
    png=base64.b64encode(b'\x89PNG\r\n\x1a\n'+b'fixture').decode()
    url=c.post('/api/graphics-packs/artwork',json={'image':'data:image/png;base64,'+png}).json()['url']
    assert c.get(url).content.startswith(b'\x89PNG')
    profile={'team':'Jackson','featured':'Captain','players':[{'name':'Captain','captain':True,'photo':url,'matches':'12','runs':'0'}]}
    assert c.post('/api/graphics-packs',json={'team':profile}).status_code==200
    assert State(app.state.scoreboard.folder).packs.snapshot()['teams'][0]['team']=='Jackson'
    app.state.scoreboard.save({'team1':'Finlay','team2':'Jackson'})
    assert app.state.scoreboard.snapshot()['graphics']['presentation']['teams'][0]['players'][0]['runs']=='0'
    profile['players'][0]['photo']='https://example.com/external.jpg'
    assert c.post('/api/graphics-packs',json={'team':profile}).status_code==422
    assert c.post('/api/graphics-packs/artwork',json={'image':'data:image/svg+xml;base64,AA=='}).status_code==422
    assert c.get('/api/graphics-packs/media/not-an-image.png').status_code==404
    assert c.post('/api/graphics-packs',json={'code':'arbitrary markup'}).status_code==422


def score_wicket(app):
    s=app.state.scoreboard
    s.save({'source':'manual','team1':'Batters','team2':'Fielders','runs':'0','wickets':'0','overs':'0.0','deliveries':'','striker':'1','batter1_name':'Duck','batter1_runs':'0','batter1_balls':'0'})
    s.flush()
    s.save({'runs':'0','wickets':'1','overs':'0.1','deliveries':'W','batter1_balls':'1'})
    s.flush()
    s.broadcast_settings({'pack':'fox_odi'})
    return app.state.live_match.state()


def highlights(app):
    state=score_wicket(app)
    event=state['innings'][0]['deliveries'][0]
    clip={'id':'a'*32,'url':'/api/live/media/'+'a'*32,'device_id':'camera1','start_ms':1000,'end_ms':5000,'bytes':10,'mime':'video/webm','audio':False}
    valid={'id':'h1','event_id':event['id'],'match_id':state['match_id'],'innings':0,'kind':'wicket','start_ms':1000,'end_ms':5000,'title':'Fielding wicket','clips':[clip],'partial':False,'coverage':[[1000,5000]]}
    rows=[valid,{**copy.deepcopy(valid),'id':'boundary','kind':'four'},
          {**copy.deepcopy(valid),'id':'old-match','match_id':'another-match'},
          {**copy.deepcopy(valid),'id':'other-innings','innings':1},
          {**copy.deepcopy(valid),'id':'removed-wicket','event_id':'removed-event'},
          {**copy.deepcopy(valid),'id':'missing-footage','partial':True}]
    app.state.live_match.highlights=rows
    app.state.scoreboard.broadcast_action({'action':'end_innings'})
    app.state.broadcast_desk.program['camera_id']='camera1'
    return valid


def test_break_highlights_cannot_run_when_disabled_or_live(studio):
    c,app=studio
    assert c.post('/api/live/fielding-highlights',json={}).status_code==403
    c.post('/api/live/settings',json={'clips_enabled':True})
    assert c.post('/api/live/fielding-highlights',json={}).status_code==409
    assert app.state.broadcast_desk.program['mode']=='live'


def test_break_reel_only_current_fielding_wickets_and_waits_for_obs(studio):
    c,app=studio
    highlights(app)
    c.post('/api/live/settings',json={'clips_enabled':True})
    before=app.state.scoreboard.snapshot()['score']
    response=c.post('/api/live/fielding-highlights',json={})
    assert response.status_code==200, response.text
    p=response.json()['program'];r=p['review']
    assert r['fielding_team']=='Fielders' and r['batting_team']=='Batters'
    assert len(r['items'])==1 and len(r['clips'])==1
    assert r['items'][0]['title']=='Fielding wicket'
    assert p['playing'] is False and r['awaiting_ready'] is True
    report={'client_id':'obs-test-123','role':'obs','camera_id':'fielding-highlights','revision':p['revision'],'mode':'replay','state':'buffering'}
    c.post('/api/broadcast/health',json=report)
    assert app.state.broadcast_desk.program['playing'] is False
    second={**report,'client_id':'obs-second-123'}
    c.post('/api/broadcast/health',json=second)
    report['state']='paused';c.post('/api/broadcast/health',json=report)
    assert app.state.broadcast_desk.program['playing'] is False
    second['state']='paused';c.post('/api/broadcast/health',json=second)
    assert app.state.broadcast_desk.program['playing'] is True
    assert app.state.scoreboard.snapshot()['score']==before
    assert c.post('/api/broadcast/program',json={'action':'camera','camera_id':'another'}).status_code==409
    c.post('/api/live/settings',json={'clips_enabled':False})
    assert app.state.broadcast_desk.program['mode']=='live'
    assert app.state.broadcast_desk.program['camera_id']=='camera1'


def test_reel_returns_live_at_end_and_does_not_repeat(studio,monkeypatch):
    c,app=studio
    highlights(app);c.post('/api/live/settings',json={'clips_enabled':True})
    p=c.post('/api/live/fielding-highlights',json={}).json()['program']
    c.post('/api/broadcast/health',json={'client_id':'obs-test-123','role':'obs','camera_id':'fielding-highlights','revision':p['revision'],'mode':'replay','state':'paused'})
    anchor=app.state.broadcast_desk.program['anchor_ms']
    monkeypatch.setattr('server.broadcast_desk.now_ms',lambda:anchor+4100)
    assert app.state.broadcast_desk.snapshot()['program']['mode']=='live'
    assert p['review_id'] not in app.state.replay_store.reviews


def test_events_have_stable_ids_and_wide_is_not_a_no_ball(studio):
    _,app=studio
    score_wicket(app)
    s=app.state.scoreboard
    e=s.snapshot()['graphics']['event']
    assert e['kind']=='wicket' and s.snapshot()['graphics']['event']['id']==e['id']
    s.save({'runs':'1','deliveries':'W 1wd'});s.flush()
    assert s.snapshot()['graphics']['event']['kind']=='wide'
    s.save({'runs':'2','deliveries':'W 1nb'});s.flush()
    assert s.snapshot()['graphics']['event'] is None
    s.save({'runs':'4','overs':'0.2','deliveries':'W 4'});s.flush()
    assert s.snapshot()['graphics']['event']['kind']=='four'


def test_reel_blocks_overlapping_drs_and_expiry_restores_real_camera(studio):
    c,app=studio
    highlights(app);c.post('/api/live/settings',json={'clips_enabled':True})
    p=c.post('/api/live/fielding-highlights',json={}).json()['program']
    assert c.post('/api/broadcast/review',json={'action':'prepare','camera_ids':['camera1']}).status_code==409
    app.state.replay_store.reviews.pop(p['review_id'])
    result=app.state.broadcast_desk.snapshot()['program']
    assert result['mode']=='live' and result['camera_id']=='camera1'


def test_optional_auto_break_reel_waits_for_delay_and_runs_once(studio,monkeypatch):
    import asyncio
    c,app=studio
    highlights(app);c.post('/api/live/settings',json={'clips_enabled':True})
    app.state.scoreboard.broadcast_settings({'auto_break_highlights':True})
    clock=[time.time()]
    monkeypatch.setattr('server.live_match.time.time',lambda:clock[0])
    live=app.state.live_match
    asyncio.run(live.tick())
    assert app.state.broadcast_desk.program['mode']=='live'
    clock[0]+=6
    asyncio.run(live.tick())
    assert app.state.broadcast_desk.program['mode']=='replay'
    app.state.broadcast_desk.end_fielding_reel()
    asyncio.run(live.tick())
    assert app.state.broadcast_desk.program['mode']=='live'
