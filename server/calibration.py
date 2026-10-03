"""Manual measured ground-plane calibration. No LBW prediction."""
import json
import sqlite3
from contextlib import closing
import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

class CalibrationInput(BaseModel):
    points: list[tuple[float, float]] = Field(min_length=4, max_length=4)
    width: int = Field(ge=100, le=4096)
    height: int = Field(ge=100, le=4096)
    length_m: float = Field(ge=1, le=40, allow_inf_nan=False)
    width_m: float = Field(ge=.3, le=10, allow_inf_nan=False)
    crease_m: float = Field(ge=0, allow_inf_nan=False)
    focal_px: float | None = Field(default=None, gt=0, allow_inf_nan=False)

def calculate(data):
    p=np.array(data.points,dtype=np.float32)
    if not np.isfinite(p).all() or np.any(p<0) or np.any(p[:,0]>=data.width) or np.any(p[:,1]>=data.height):
        raise ValueError('Points must be inside the image')
    if not cv2.isContourConvex(p.reshape(-1,1,2)) or abs(cv2.contourArea(p))<data.width*data.height*.005:
        raise ValueError('Select four well-separated corners around the pitch in order')
    if data.crease_m>=data.length_m:raise ValueError('Crease must be inside pitch length')
    world=np.array([[0,0],[data.width_m,0],[data.width_m,data.length_m],[0,data.length_m]],np.float32)
    h=cv2.getPerspectiveTransform(p,world)
    if not np.isfinite(h).all() or abs(np.linalg.det(h))<1e-12:raise ValueError('Degenerate calibration')
    result=data.model_dump();result.update(image_to_ground=h.tolist(),ground_to_image=np.linalg.inv(h).tolist(),pose=None)
    if data.focal_px is not None:
        k=np.array([[data.focal_px,0,data.width/2],[0,data.focal_px,data.height/2],[0,0,1]],float)
        obj=np.column_stack([world,np.zeros(4)]).astype(float)
        ok,r,t=cv2.solvePnP(obj,p.astype(float),k,np.zeros(5),flags=cv2.SOLVEPNP_IPPE)
        if not ok:raise ValueError('Pose could not be estimated')
        rotation=cv2.Rodrigues(r)[0]
        if np.any((rotation@obj.T+t)[2]<=0):raise ValueError('Pose puts pitch behind camera')
        predicted=cv2.projectPoints(obj,r,t,k,np.zeros(5))[0].reshape(-1,2)
        result['pose']={'position_m':(-rotation.T@t).ravel().tolist(),'world_to_camera_rotation':rotation.tolist(),'reprojection_rms_px':float(np.sqrt(np.mean(np.sum((predicted-p)**2,axis=1)))),'assumptions':'Supplied focal length, centred principal point, zero lens distortion. Approximate pose.'}
    return result

class Calibration:
    def __init__(self,path):self.path=path
    def initialise(self):
        with closing(sqlite3.connect(self.path)) as c:
            c.execute('CREATE TABLE IF NOT EXISTS camera_calibration(device_id TEXT PRIMARY KEY,data TEXT NOT NULL)');c.commit()
    def router(self):
        router=APIRouter(prefix='/api/calibration')
        @router.get('/{device_id}')
        def read(device_id:str):
            with closing(sqlite3.connect(self.path)) as c:row=c.execute('SELECT data FROM camera_calibration WHERE device_id=?',(device_id,)).fetchone()
            if not row:raise HTTPException(404,'No saved calibration for this angle')
            return json.loads(row[0])
        @router.put('/{device_id}')
        def save(device_id:str,data:CalibrationInput):
            if len(device_id)>80:raise HTTPException(422,'Invalid camera ID')
            try:result=calculate(data)
            except (ValueError,cv2.error,np.linalg.LinAlgError) as e:raise HTTPException(422,str(e))
            with closing(sqlite3.connect(self.path)) as c:
                c.execute('INSERT INTO camera_calibration VALUES(?,?) ON CONFLICT(device_id) DO UPDATE SET data=excluded.data',(device_id,json.dumps(result)));c.commit()
            return result
        return router
