from fastapi.testclient import TestClient
from server.main import create_app
from server.config import Settings
from server.replay import coverage


def test_match_controls_removed_without_deleting_database(tmp_path):
    import sqlite3
    path=tmp_path/'match.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE matches(id INTEGER PRIMARY KEY,name TEXT)')
        db.execute("INSERT INTO matches VALUES(1,'Existing game')")
    with TestClient(create_app(Settings(database_path=path))) as c:
        assert c.get('/api/match').status_code==404
        assert c.post('/api/match/balls',json={}).status_code==404
        html=c.get('/umpire').text
        assert 'id="markBall"' not in html and 'id="ballHistory"' not in html
        assert 'id="cameraQR"' in html
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT name FROM matches').fetchone()[0]=='Existing game'


def test_overlap_audio_and_common_end(tmp_path):
    with TestClient(create_app(Settings(database_path=tmp_path/'test.db'))) as c:
        t=c.get('/api/clock').json()['sent_ms']
        for device,a,b in [('a',-10000,-5000),('a',-6000,-1000),('b',-9000,-2000)]:
            assert c.post('/api/clips/'+device,params={'start_ms':t+a,'end_ms':t+b,'uncertainty_ms':3},content=b'encoded',headers={'Content-Type':'video/mp4'}).status_code==200
        assert c.post('/api/audio/a',json={'points':[{'t':t-3000,'rms':.2,'peak':.8,'impact':True}]}).status_code==200
        assert c.post('/api/audio/a',json={'points':[{'t':t,'rms':2,'peak':.8}]}).status_code==422
        r=c.post('/api/replays?seconds=10').json()
        assert r['end_ms']==t-2001
        assert len(r['coverage']['a'])==1 and r['audio']['a'][0]['impact']
        assert 8.9<c.get('/api/buffer').json()['cameras']['a']['seconds']<9.1
        explicit=c.post('/api/replays',params={'start_ms':t-8000,'end_ms':t-3000}).json()
        assert explicit['start_ms']==t-8000 and explicit['end_ms']==t-3000
        assert c.post('/api/replays',params={'start_ms':t-8000}).status_code==422
    assert coverage([{'start_ms':0,'end_ms':5},{'start_ms':7,'end_ms':10}],0,10)==[[0,5],[7,10]]
