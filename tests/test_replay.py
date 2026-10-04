from pathlib import Path
from fastapi.testclient import TestClient
from server.main import create_app
from server.config import Settings
from server.scoreboard_state import State
import server.replay as replay


def test_upload_pin_range_cleanup_and_limits(tmp_path, monkeypatch):
    current = [1000000.0]
    monkeypatch.setattr(replay,'now_ms',lambda:current[0])
    with TestClient(create_app(Settings(database_path=tmp_path/'test.db'),scoreboard=State(tmp_path/'scores'))) as c:
        assert c.post('/api/replays').status_code == 409
        params=dict(start_ms=current[0]-5000,end_ms=current[0]-1,uncertainty_ms=4,fps=30)
        response=c.post('/api/clips/phone',params=params,content=b'video bytes',headers={'Content-Type':'video/webm'})
        assert response.status_code == 200
        key=response.json()['id']
        review=c.post('/api/replays?seconds=60').json()
        assert review['end_ms']-review['start_ms']==60000
        assert review['clips'][0]['id']==key
        assert c.get('/api/clips/'+key,headers={'Range':'bytes=0-4'}).status_code == 206
        assert c.get('/api/buffer').json()['cameras']['phone']['seconds'] > 4
        current[0]+=100000
        assert c.get('/api/buffer').json()['cameras']=={}
        assert c.get('/api/clips/'+key).status_code == 200  # pin survives ring expiry
        c.delete('/api/replays/'+review['id'])
        assert c.get('/api/clips/'+key).status_code == 404
        assert c.post('/api/clips/phone',params=params,content=b'x',headers={'Content-Type':'video/webm'}).status_code==422
        params.update(start_ms=current[0]-1000,end_ms=current[0],uncertainty_ms=float('nan'))
        assert c.post('/api/clips/phone',params=params,content=b'x',headers={'Content-Type':'video/webm'}).status_code==422
        assert c.post('/api/replays?seconds=500').status_code==422


def test_clock_headers_and_multiple_angles(tmp_path):
    with TestClient(create_app(Settings(database_path=tmp_path/'test.db'),scoreboard=State(tmp_path/'scores'))) as c:
        t=c.get('/api/clock').json()
        assert t['sent_ms'] >= t['received_ms']
        for id in ('left','right'):
            assert c.post('/api/clips/'+id,params=dict(start_ms=t['sent_ms']-5000,end_ms=t['sent_ms'],uncertainty_ms=2),content=b'x',headers={'Content-Type':'video/mp4'}).status_code==200
        r=c.post('/api/replays?seconds=10').json()
        assert {v['device_id'] for v in r['clips']}=={'left','right'}
        assert all(v['start_ms']==t['sent_ms']-5000 for v in r['clips'])


def test_recorder_diagnostic_visible_before_any_upload(tmp_path):
    with TestClient(create_app(Settings(database_path=tmp_path/'test.db'),scoreboard=State(tmp_path/'scores'))) as c:
        r=c.post('/api/recorder-status/phone',json={'message':'Measuring clock 1/5'})
        assert r.status_code==200
        data=c.get('/api/buffer').json()
        assert data['cameras']=={}
        assert data['recorders']['phone']['message']=='Measuring clock 1/5'
        assert c.post('/api/recorder-status/phone',json={'message':'x'*501}).status_code==422


def test_broadcast_feed_is_camera_specific_and_carries_recorded_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(replay,'now_ms',lambda:1000000)
    with TestClient(create_app(Settings(database_path=tmp_path/'test.db'),scoreboard=State(tmp_path/'scores'))) as c:
        for id,end,audio in [('left',999000,True),('right',999000,False),('left',960000,False)]:
            params=dict(start_ms=end-5000,end_ms=end,uncertainty_ms=2,audio=audio)
            assert c.post('/api/clips/'+id,params=params,content=b'0123456789',headers={'Content-Type':'video/webm'}).status_code==200
        c.post('/api/recorder-status/left',json={'message':'Recording'})
        feed=c.get('/api/broadcast/camera/left').json()
        assert feed['server_ms']==1000000
        assert len(feed['clips'])==1 and feed['clips'][0]['audio'] is True
        assert feed['recorder']['message']=='Recording'
        media=c.get(feed['clips'][0]['url'],headers={'Range':'bytes=2-5'})
        assert media.status_code==206 and media.content==b'2345'
        assert c.get('/api/broadcast/camera/none').json()['clips']==[]
        assert c.get('/api/broadcast/camera/'+'x'*81).status_code==422
