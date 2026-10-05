from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import server.broadcast_desk as desk_module
import server.replay as replay_module
from server.main import create_app
from server.config import Settings
from server.scoreboard_state import State


@pytest.fixture
def desk(tmp_path, monkeypatch):
    clock = [1000000.0]
    monkeypatch.setattr(desk_module, 'now_ms', lambda:clock[0])
    monkeypatch.setattr(replay_module, 'now_ms', lambda:clock[0])
    app = create_app(Settings(database_path=tmp_path/'test.db'), scoreboard=State(tmp_path/'scores'))
    roster = [{'device_id':'left','name':'Left crease','role':'CREASE_LEFT'}, {'device_id':'umpire','name':'Umpire','role':'UMPIRE_POV'}]
    app.state.devices.connected_snapshot = lambda:list(roster)
    with patch('server.main.start_receiver'), TestClient(app) as client:
        yield client, app, clock, roster


def upload(client, id='umpire', start=980000, end=994000):
    response=client.post('/api/clips/'+id,params={'start_ms':start,'end_ms':end,'uncertainty_ms':2,'audio':True},content=b'synthetic-test',headers={'Content-Type':'video/webm'})
    assert response.status_code==200
    return response.json()['id']


def test_match_day_default_source_shared_commands_and_fixed_output_compatibility(desk):
    c,app,clock,roster=desk
    assert c.get('/api/broadcast/program').json()['program']['camera_id']=='umpire'
    p=c.post('/api/broadcast/program',json={'action':'camera','camera_id':'left'}).json()['program']
    assert p['camera_id']=='left' and p['revision']==2
    assert c.get('/api/broadcast/program').json()['program']['camera_id']=='left'
    roster.pop(0)
    assert c.get('/api/broadcast/program').json()['program']['camera_id']=='left','Never silently cut away from an offline selected camera'
    assert c.post('/api/broadcast/program',json={'action':'camera','camera_id':'missing'}).status_code==409
    assert c.post('/api/broadcast/program',json={'action':'retry'}).json()['program']['retry_token']==1
    assert c.post('/api/broadcast/program',json={'action':'audio','muted':True}).json()['program']['muted'] is True
    assert c.post('/api/broadcast/program',json={'action':'audio'}).status_code==422
    assert c.get('/match-day').status_code==200
    assert 'programPreview' in c.get('/match-day').text
    assert c.get('/reliability-checklist').status_code==200
    assert 'second innings' in c.get('/reliability-checklist').text
    saved=c.get('/reliability-checklist?download=true')
    assert saved.status_code==200 and 'RELIABILITY_TEST_CHECKLIST.md' in saved.headers['content-disposition']
    assert 'follow=1' in c.get('/broadcast').text or 'program-output.js' in c.get('/broadcast').text
    assert c.get('/broadcast?camera=left&clean=1').status_code==200


def test_program_replay_controls_pin_only_their_manifest_and_return_to_delayed_live(desk):
    c,app,clock,roster=desk
    upload(c)
    upload(c,'left',980000,992000)
    manual=c.post('/api/replays?seconds=10').json()['id']
    p=c.post('/api/broadcast/program',json={'action':'replay','seconds':10}).json()['program']
    assert p['mode']=='replay' and p['playing'] is True
    assert 'audio' not in p['review'],'Polling program control must not transfer unneeded waveform arrays'
    assert p['review']['end_ms']<=clock[0]-5000
    review=p['review_id']
    clock[0]+=1000
    assert c.get('/api/broadcast/program').json()['program']['position_ms']==1000
    paused=c.post('/api/broadcast/program',json={'action':'pause'}).json()['program']
    clock[0]+=2000
    assert c.get('/api/broadcast/program').json()['program']['position_ms']==paused['position_ms']
    assert c.post('/api/broadcast/program',json={'action':'seek','position_ms':5000}).json()['program']['position_ms']==5000
    assert c.post('/api/broadcast/program',json={'action':'speed','speed':.5}).status_code==200
    assert c.post('/api/broadcast/program',json={'action':'play'}).status_code==200
    clock[0]+=1000
    assert c.get('/api/broadcast/program').json()['program']['position_ms']==5500
    assert c.post('/api/broadcast/program',json={'action':'camera','camera_id':'left'}).json()['program']['mode']=='replay'
    live=c.post('/api/broadcast/program',json={'action':'live'}).json()['program']
    assert live['mode']=='live' and live['playing'] is True and live['review'] is None
    assert review not in app.state.replay_store.reviews and manual in app.state.replay_store.reviews
    assert c.post('/api/broadcast/program',json={'action':'pause'}).status_code==409


def test_replay_failure_is_atomic_and_end_holds_until_return_live(desk):
    c,app,clock,roster=desk
    before=c.get('/api/broadcast/program').json()['program']
    assert c.post('/api/broadcast/program',json={'action':'replay','seconds':10}).status_code==409
    assert c.get('/api/broadcast/program').json()['program']==before
    upload(c)
    c.post('/api/broadcast/program',json={'action':'replay','seconds':10})
    clock[0]+=20000
    p=c.get('/api/broadcast/program').json()['program']
    assert p['mode']=='replay' and not p['playing'] and p['position_ms']==9999
    assert c.post('/api/broadcast/program',json={'action':'play'}).json()['program']['position_ms']==0
    assert c.post('/api/broadcast/program',json={'action':'speed','speed':2}).status_code==422
    assert c.post('/api/broadcast/program',json={'action':'seek','position_ms':'NaN'}).status_code==422
    assert c.post('/api/broadcast/program',json={'action':'live','unknown':1}).status_code==422
    clock[0]+=90000
    held=c.get('/api/broadcast/program').json()['program']['review_id']
    assert c.post('/api/broadcast/program',json={'action':'replay','seconds':10}).status_code==409
    assert c.get('/api/broadcast/program').json()['program']['review_id']==held,'Old pinned clips must not masquerade as a fresh last-ten-seconds replay'


def test_health_is_player_specific_stale_bounded_and_not_persisted(desk):
    c,app,clock,roster=desk
    report={'client_id':'obs-test-123','role':'obs','camera_id':'umpire','revision':1,'mode':'live','state':'playing','delay_seconds':5.2,'muted':False,'audio_present':True,'meter_dbfs':-18,'meter_state':'active','dropped_frames':3,'total_frames':1000}
    assert c.post('/api/broadcast/health',json=report).status_code==200
    clock[0]+=5000
    row=c.get('/api/broadcast/health').json()['clients'][0]
    assert row['report_age_ms']==5000 and row['meter_dbfs']==-18
    for patch in ({'meter_dbfs':'NaN'},{'dropped_frames':True},{'late_clips':-1},{'role':'made-up'},{'client_id':'bad/id'},{'raw_audio':'private'}):
        assert c.post('/api/broadcast/health',json={**report,**patch}).status_code==422
    for n in range(31):
        assert c.post('/api/broadcast/health',json={**report,'client_id':f'preview-test-{n}'}).status_code==200
    assert c.post('/api/broadcast/health',json={**report,'client_id':'extra-client-123'}).status_code==429
    clock[0]+=120000
    assert c.get('/api/broadcast/health').json()['clients']==[]
    assert not app.state.scoreboard.branding.get('clients')


def test_available_footage_counts_overlap_once_and_program_does_not_persist(desk):
    c,app,clock,roster=desk
    upload(c,start=980000,end=988000)
    upload(c,start=986000,end=994000)
    assert c.get('/api/broadcast/camera/umpire').json()['available_seconds']==14
    assert 'clients' not in app.state.scoreboard.graphics.export()
