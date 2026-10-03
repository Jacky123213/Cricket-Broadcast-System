import numpy as np
from fastapi.testclient import TestClient
from server.main import create_app
from server.config import Settings
from server.calibration import calculate,CalibrationInput

def test_ground_plane_roundtrip_and_persistence(tmp_path):
    data=dict(points=[[80,320],[560,320],[440,60],[200,60]],width=640,height=360,length_m=10,width_m=2,crease_m=1.22)
    settings=Settings(database_path=tmp_path/'db')
    with TestClient(create_app(settings)) as c:
        r=c.put('/api/calibration/phone',json=data)
        assert r.status_code==200
        cal=r.json();h=np.array(cal['image_to_ground'])
        for p,w in zip(data['points'],[[0,0],[2,0],[2,10],[0,10]]):
            q=h@np.array([*p,1]);assert np.allclose(q[:2]/q[2],w)
        assert cal['pose'] is None
        assert c.put('/api/calibration/phone',json={**data,'points':[[1,1]]*4}).status_code==422
        assert c.put('/api/calibration/phone',json={**data,'crease_m':20}).status_code==422
        assert c.put('/api/calibration/phone',json={**data,'points':[[-1,1],*data['points'][1:]]}).status_code==422
    with TestClient(create_app(settings)) as c:assert c.get('/api/calibration/phone').json()['length_m']==10

def test_pose_with_known_intrinsics():
    import cv2
    world=np.array([[0,0,0],[2,0,0],[2,10,0],[0,10,0]],float)
    k=np.array([[700,0,640],[0,700,480],[0,0,1]],float)
    r=np.array([.5,.1,0.],float);t=np.array([-1,-3,15.],float)
    points=cv2.projectPoints(world,r,t,k,np.zeros(5))[0].reshape(-1,2)
    cal=calculate(CalibrationInput(points=points.tolist(),width=1280,height=960,length_m=10,width_m=2,crease_m=1,focal_px=700))
    expected=(-cv2.Rodrigues(r)[0].T@t)
    assert np.allclose(cal['pose']['position_m'],expected,atol=.01)

def test_qr_uses_selected_server_address(tmp_path,monkeypatch):
    import qrcode
    seen=[];original=qrcode.QRCode.add_data
    def track(self,data,*args,**kwargs):seen.append(data);return original(self,data,*args,**kwargs)
    monkeypatch.setattr(qrcode.QRCode,'add_data',track)
    with TestClient(create_app(Settings(database_path=tmp_path/'db'))) as c:
        urls=c.get('/api/server-info').json()['camera_urls']
        response=c.get('/api/camera-qr?index=0')
        assert response.status_code==200 and '<svg' in response.text
        assert response.headers['content-type'].startswith('image/svg+xml')
        assert urls[0] in seen
        assert c.get('/api/camera-qr?index=9999').status_code==404
