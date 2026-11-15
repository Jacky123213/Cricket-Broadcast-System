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


def prepare_review(c, **changes):
    return c.post('/api/broadcast/review', json={'action':'prepare','camera_ids':['umpire'],'kind':'run_out',**changes})


def review_action(c, id, action, **changes):
    return c.post('/api/broadcast/review',json={'action':action,'review_id':id,**changes})


def review_ready(c, id, role='review_preview', state='ready', client='review-preview-test'):
    return c.post('/api/broadcast/review/ready',json={'review_id':id,'role':role,'state':state,'client_id':client})


def test_review_preparation_and_private_transport_do_not_take_air_or_change_score(desk):
    c,app,clock,roster=desk
    upload(c);upload(c,'left',980000,994000)
    before=c.get('/api/broadcast/program').json()['program'];score=app.state.scoreboard.snapshot()['score']
    r=prepare_review(c,kind='caught_behind',camera_ids=['umpire','left'],original='not_out')
    assert r.status_code==200,r.text
    s=r.json()['review'];id=s['id']
    assert s['phase']=='private' and s['layout']=='split' and not s['playing']
    assert c.get('/api/broadcast/program').json()['program']==before
    assert 'manifest' not in c.get('/api/broadcast/program').json()['drs']
    manifest=c.get('/api/broadcast/review').json()['review']['manifest']
    assert set(manifest['coverage'])=={'left','umpire'} and 'audio' in manifest
    assert manifest['end_ms']<=clock[0]-5000
    assert review_action(c,id,'play').json()['review']['playing']
    clock[0]+=1000
    assert c.get('/api/broadcast/review').json()['review']['position_ms']==500
    assert review_action(c,id,'pause').status_code==200
    assert review_action(c,id,'seek',position_ms=2000).json()['review']['position_ms']==2000
    assert review_action(c,id,'decision',verdict='out').status_code==409
    assert c.get('/api/broadcast/program').json()['program']==before
    assert app.state.scoreboard.snapshot()['score']==score
    assert c.get('/review-preview').status_code==200


def test_take_requires_fresh_readiness_and_does_not_accept_only_preview_when_obs_loading(desk):
    c,app,clock,roster=desk;upload(c)
    id=prepare_review(c).json()['review']['id']
    assert review_action(c,id,'take').status_code==409
    assert review_ready(c,id).status_code==200
    assert review_ready(c,id,'obs','loading','obs-test-output').status_code==200
    assert review_action(c,id,'take').status_code==409
    assert review_ready(c,id,'obs','ready','obs-test-output').status_code==200
    clock[0]+=4500
    assert review_action(c,id,'take').status_code==409
    review_ready(c,id,'obs','ready','obs-test-output')
    s=review_action(c,id,'take').json()['review']
    p=c.get('/api/broadcast/program').json()['program']
    assert s['phase']=='on_air' and not s['playing'] and p['mode']=='replay'
    assert p['review_id']==id and not p['playing']


def test_obs_without_a_review_readiness_report_blocks_take(desk):
    c,app,clock,roster=desk;upload(c)
    id=prepare_review(c).json()['review']['id'];review_ready(c,id)
    c.post('/api/broadcast/health',json={'client_id':'obs-visible-123','role':'obs','camera_id':'umpire','revision':1,'mode':'live','state':'playing'})
    assert any(r['client_id']=='obs-visible-123' and r['state']=='loading' for r in c.get('/api/broadcast/program').json()['drs']['outputs'])
    assert review_action(c,id,'take').status_code==409
    review_ready(c,id,'obs','ready','obs-visible-123')
    assert review_action(c,id,'take').status_code==200


def test_manual_runout_guides_decision_and_return_live_are_scoring_independent(desk):
    c,app,clock,roster=desk;upload(c);upload(c,'left',980000,994000)
    score=app.state.scoreboard.snapshot()['score']
    id=prepare_review(c,camera_ids=['umpire','left']).json()['review']['id']
    assert review_action(c,id,'announce').json()['review']['phase']=='announced'
    assert c.get('/api/broadcast/program').json()['program']['mode']=='live'
    review_action(c,id,'seek',position_ms=2500)
    review_action(c,id,'play')
    assert review_action(c,id,'mark_wicket').status_code==409
    review_action(c,id,'pause')
    assert review_action(c,id,'mark_wicket').json()['review']['wicket_ms']==2500
    assert review_action(c,id,'crease',points=[[.1,.8],[.9,.7]]).json()['review']['crease']['camera_id']=='umpire'
    assert review_action(c,id,'crease',points=[[0,0],[1.1,1]]).status_code==422
    assert review_action(c,id,'zoom',camera_id='left',zoom=2,x=.2,y=.3).json()['review']['zoom']['left']['zoom']==2
    assert review_action(c,id,'layout',layout='split').status_code==200
    assert review_action(c,id,'primary',camera_id='left').status_code==200
    assert review_action(c,id,'audio_source',camera_id='left').status_code==200
    review_ready(c,id);assert review_action(c,id,'take').status_code==200
    assert c.get('/api/broadcast/program').json()['program']['camera_id']=='left'
    assert review_action(c,id,'play').status_code==200
    clock[0]+=500
    assert c.post('/api/broadcast/program',json={'action':'camera','camera_id':'umpire'}).status_code==409
    assert c.post('/api/broadcast/program',json={'action':'replay'}).status_code==409
    result=review_action(c,id,'decision',verdict='not_out').json()['review']
    assert result['phase']=='decision' and result['verdict']=='not_out' and not result['playing']
    clock[0]+=10000
    assert c.get('/api/broadcast/review').json()['review']['position_ms']==result['position_ms']
    assert review_action(c,id,'play').status_code==409
    assert c.post('/api/broadcast/program',json={'action':'play'}).status_code==409
    assert app.state.scoreboard.snapshot()['score']==score
    assert review_action(c,id,'live').json()['review'] is None
    p=c.get('/api/broadcast/program').json()['program']
    assert p['mode']=='live' and p['review'] is None and id not in app.state.replay_store.reviews
    assert p['camera_id']=='umpire','Return to the live program camera, not an offline/alternate review angle'
    assert review_ready(c,id).status_code==409


def test_lbw_is_explicit_manual_fields_without_trajectory_or_automatic_verdict(desk):
    c,app,clock,roster=desk;upload(c)
    id=prepare_review(c,kind='lbw').json()['review']['id']
    s=review_action(c,id,'lbw',pitching='outside_off',impact='in_line',wickets='missing').json()['review']
    assert s['lbw']==dict(pitching='outside_off',impact='in_line',wickets='missing')
    assert s['verdict'] is None and 'trajectory' not in s
    assert review_action(c,id,'mark_wicket').status_code==409
    assert review_action(c,id,'lbw',wickets='umpires_call').status_code==422
    assert review_action(c,id,'cancel').status_code==200
    assert c.get('/api/broadcast/program').json()['program']['mode']=='live'


@pytest.mark.parametrize('changes',[
    {'camera_ids':['umpire','umpire']},{'camera_ids':['missing']},
    {'camera_ids':['umpire','left','extra']},{'seconds':20},{'kind':'hawk_eye'}])
def test_bad_review_preparation_never_changes_program(desk,changes):
    c,app,clock,roster=desk;upload(c)
    before=c.get('/api/broadcast/program').json()['program']
    assert prepare_review(c,**changes).status_code in (409,422)
    assert c.get('/api/broadcast/program').json()['program']==before
    assert app.state.broadcast_desk.review.session is None


def test_review_cleanup_stale_controls_and_normal_live_button(desk):
    c,app,clock,roster=desk;upload(c)
    id=prepare_review(c).json()['review']['id']
    assert prepare_review(c).status_code==409
    assert review_action(c,'stale-review','announce').status_code==409
    assert review_action(c,'stale-review','cancel').status_code==409
    review_ready(c,id);review_action(c,id,'take')
    assert c.post('/api/broadcast/program',json={'action':'live'}).status_code==200
    assert c.get('/api/broadcast/review').json()['review'] is None
    assert id not in app.state.replay_store.reviews
    id=prepare_review(c).json()['review']['id'];review_ready(c,id);review_action(c,id,'take')
    app.state.replay_store.reviews.pop(id)
    p=c.get('/api/broadcast/program').json()
    assert p['drs'] is None and p['program']['mode']=='live'


def attached_review(c, **extra):
    source=c.post('/api/replays?seconds=10').json()['id']
    result=c.post('/api/broadcast/review',json={'action':'attach','source_review_id':source,
        'controller_id':'umpire-owner-123','kind':'lbw',**extra})
    assert result.status_code==200,result.text
    return source,result.json()['review']['id']


def follow_view(c,source,id,sequence=1,**extra):
    return c.post('/api/broadcast/review/follow',json={
        'review_id':id,'source_review_id':source,'controller_id':'umpire-owner-123',
        'sequence':sequence,'position_ms':1500,'playing':False,'speed':.5,
        'primary':'umpire','secondary':'left','audio_source':'umpire','available':True,
        'zoom':{'umpire':{'zoom':2,'x':.3,'y':.6,'aspect':16/9}},**extra})


def test_attach_owns_a_manifest_without_changing_private_source_or_air(desk):
    c,app,clock,roster=desk;upload(c);upload(c,'left',980000,994000)
    upload(c,'third',980000,994000)
    before=c.get('/api/broadcast/program').json()['program'];score=app.state.scoreboard.snapshot()['score']
    source,id=attached_review(c)
    s=c.get('/api/broadcast/review').json()['review']
    assert id!=source and s['phase']=='private' and s['source_review_id']==source
    assert len(s['cameras'])==3 and s['follow_status']=='selecting_angle'
    assert c.get('/api/broadcast/program').json()['program']==before
    assert follow_view(c,source,id).status_code==200
    s=c.get('/api/broadcast/program').json()['drs']
    assert s['primary']=='umpire' and s['secondary']=='left' and s['layout']=='split'
    assert s['position_ms']==1500 and s['zoom']['umpire']['zoom']==2
    assert s['follow_status']=='ready' and not s['show_assessment']
    c.delete('/api/replays/'+source)
    assert id in app.state.replay_store.reviews,'The public copy pins footage independently'
    assert app.state.scoreboard.snapshot()['score']==score
    assert review_action(c,id,'cancel').status_code==200
    assert id not in app.state.replay_store.reviews


def test_follow_on_air_mirrors_live_controls_and_stops_at_last_received_frame_on_loss(desk):
    c,app,clock,roster=desk;upload(c);upload(c,'left',980000,994000)
    source,id=attached_review(c)
    follow_view(c,source,id,playing=True,waveform=True,assessment=True)
    review_ready(c,id)
    assert review_action(c,id,'take').status_code==200
    p=c.get('/api/broadcast/program').json()['program']
    assert p['playing'] and p['speed']==.5 and p['position_ms']==1500
    clock[0]+=500
    assert c.get('/api/broadcast/program').json()['program']['position_ms']==1750
    assert follow_view(c,source,id,sequence=2,position_ms=4000,primary='left',secondary=None,
        zoom={'left':{'zoom':5,'x':.2,'y':.4,'aspect':4/3}}).status_code==200
    s=c.get('/api/broadcast/program').json()['drs']
    assert s['layout']=='single' and s['primary']=='left' and s['position_ms']==4000
    assert c.post('/api/broadcast/program',json={'action':'play'}).status_code==409
    assert review_action(c,id,'seek',position_ms=100).status_code==409
    clock[0]+=2600
    result=c.get('/api/broadcast/program').json()
    assert result['drs']['follow_status']=='controller_lost'
    assert result['program']['position_ms']==4000 and not result['program']['playing']
    assert follow_view(c,source,id,sequence=3,position_ms=4500,playing=True).status_code==200
    assert c.get('/api/broadcast/program').json()['drs']['follow_status']=='ready'


@pytest.mark.parametrize('extra,status',[
    ({'controller_id':'different-console'},409),({'source_review_id':'wrong'},409),
    ({'review_id':'old-review'},409),({'sequence':True},422),
    ({'primary':'missing'},422),({'secondary':'umpire'},422),
    ({'zoom':{'umpire':{'zoom':7,'x':.5,'y':.5}}},422),
    ({'zoom':{'umpire':{'zoom':2,'x':.5,'y':.5,'aspect':0}}},422),
    ({'private_control_html':'not allowed'},422)])
def test_follow_rejects_other_controllers_invalid_camera_geometry_and_private_payloads(desk,extra,status):
    c,app,clock,roster=desk;upload(c);upload(c,'left',980000,994000)
    source,id=attached_review(c)
    assert follow_view(c,source,id,**extra).status_code==status
    assert c.get('/api/broadcast/program').json()['program']['mode']=='live'


def test_follow_stale_sequence_empty_selection_and_manual_decision_hold(desk):
    c,app,clock,roster=desk;upload(c);upload(c,'left',980000,994000)
    source,id=attached_review(c);follow_view(c,source,id,sequence=4)
    assert follow_view(c,source,id,sequence=3,position_ms=9000).status_code==409
    assert c.get('/api/broadcast/program').json()['drs']['position_ms']==1500
    follow_view(c,source,id,sequence=5,available=False,primary=None,secondary=None,audio_source=None)
    review_ready(c,id)
    assert review_action(c,id,'take').status_code==409
    follow_view(c,source,id,sequence=6);review_ready(c,id);review_action(c,id,'take')
    review_action(c,id,'decision',verdict='not_out')
    before=c.get('/api/broadcast/program').json()['program']['position_ms']
    assert follow_view(c,source,id,sequence=7,position_ms=8000,playing=True).json()['held']
    clock[0]+=3000
    result=c.get('/api/broadcast/program').json()
    assert result['drs']['phase']=='decision' and result['program']['position_ms']==before
    assert not result['program']['playing']


def test_abandoned_private_follow_releases_only_its_own_pin(desk):
    c,app,clock,roster=desk;upload(c);upload(c,'left',980000,994000)
    source,id=attached_review(c);follow_view(c,source,id)
    clock[0]+=61000
    assert c.get('/api/broadcast/program').json()['drs'] is None
    assert id not in app.state.replay_store.reviews and source in app.state.replay_store.reviews
