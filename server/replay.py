"""Bounded, temporary encoded clip store and pinned replay manifests."""
import asyncio
import math
import logging
from pydantic import BaseModel, Field
import time
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

# Stable epoch clock unaffected by system clock corrections during a session.
EPOCH = time.time() * 1000
ORIGIN = time.monotonic()
def now_ms():
    return EPOCH + (time.monotonic() - ORIGIN) * 1000

class RecorderStatus(BaseModel):
    message: str = Field(max_length=500)

class AudioPoint(BaseModel):
    t: float = Field(allow_inf_nan=False)
    rms: float = Field(ge=0,le=1,allow_inf_nan=False)
    peak: float = Field(ge=0,le=1,allow_inf_nan=False)
    impact: bool = False
class AudioBatch(BaseModel):
    points: list[AudioPoint] = Field(max_length=100)

def coverage(clips, start, end):
    merged=[]
    for c in sorted(clips,key=lambda x:x['start_ms']):
        a,b=max(start,c['start_ms']),min(end,c['end_ms'])
        if a>=b:continue
        if merged and a<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],b)
        else:merged.append([a,b])
    return merged

class ReplayStore:
    def __init__(self, root: Path):
        self.root = root
        self.clips = {}
        self.recorder_status = {}
        self.audio = {}
        self.reviews = {}
        self.lock = asyncio.Lock()
        self.limit = 512 * 1024 * 1024

    def initialise(self):
        self.root.mkdir(parents=True, exist_ok=True)
        # Only this component's temporary files; never match recordings or certs.
        for path in self.root.glob('*.clip'):
            path.unlink()

    def cleanup(self):
        now = now_ms()
        self.audio = {k:[p for p in pts if p['t']>now-90000] for k,pts in self.audio.items()}
        self.audio = {k:v for k,v in self.audio.items() if v}
        self.recorder_status = {k:v for k,v in self.recorder_status.items() if now-v['updated_ms'] < 180000}
        self.reviews = {k:v for k,v in self.reviews.items() if v['expires_ms'] > now}
        pinned = {c['id'] for r in self.reviews.values() for c in r['clips']}
        for key, clip in list(self.clips.items()):
            if clip['end_ms'] < now - 90000 and key not in pinned:
                (self.root / (key + '.clip')).unlink(missing_ok=True)
                del self.clips[key]

    async def create_review(self, seconds=60, start_ms=None, end_ms=None):
        if seconds not in (10,30,60): raise HTTPException(422,'Choose 10, 30 or 60 seconds')
        async with self.lock:
            self.cleanup()
            if len(self.reviews) >= 4: raise HTTPException(429,'Close an existing replay first')
            current=now_ms()
            latest={}
            for clip in self.clips.values():
                if clip['end_ms']>current-15000:
                    latest[clip['device_id']]=max(latest.get(clip['device_id'],0),clip['end_ms'])
            end = min(latest.values())-1 if latest else current
            start = end - seconds*1000
            if start_ms is not None or end_ms is not None:
                if start_ms is None or end_ms is None or not all(math.isfinite(v) for v in (start_ms,end_ms)) or not 0<end_ms-start_ms<=60000 or end_ms>current+1000:
                    raise HTTPException(422,'Invalid review window')
                start,end=start_ms,end_ms
            clips = sorted([dict(c) for c in self.clips.values() if c['end_ms']>start and c['start_ms']<end],key=lambda c:c['start_ms'])
            if not clips: raise HTTPException(409,'No footage yet. Connect a camera and wait for the first clip.')
            key = uuid.uuid4().hex
            result = dict(id=key,start_ms=start,end_ms=end,expires_ms=current+15*60*1000,clips=clips,live_delay_ms=current-end,
                coverage={id:coverage([c for c in clips if c["device_id"]==id],start,end) for id in {c["device_id"] for c in clips}},
                audio={id:[p for p in pts if start<=p["t"]<=end] for id,pts in self.audio.items()})
            self.reviews[key] = result
            return result

    def router(self):
        router = APIRouter(prefix='/api')

        @router.post('/audio/{device_id}')
        async def audio(device_id: str, batch: AudioBatch):
            if len(device_id)>80:raise HTTPException(422,'Invalid camera')
            now=now_ms()
            if any(p.t>now+5000 or p.t<now-90000 for p in batch.points):raise HTTPException(422,'Audio timestamps stale')
            async with self.lock:
                points=self.audio.setdefault(device_id,[])
                points.extend(p.model_dump() for p in batch.points)
                self.audio[device_id]=sorted(points,key=lambda p:p['t'])[-5000:]
            return {'ok':True}

        @router.post('/recorder-status/{device_id}')
        async def recorder_status(device_id: str, status: RecorderStatus):
            if len(device_id)>80: raise HTTPException(422,'Invalid device ID')
            self.recorder_status[device_id] = {'message': status.message, 'updated_ms': now_ms()}
            logging.getLogger('uvicorn.error').info('Replay recorder %s: %s', device_id, status.message)
            return {'ok':True}

        @router.get('/clock')
        async def clock():
            received = now_ms()
            return {'received_ms': received, 'sent_ms': now_ms()}

        @router.post('/clips/{device_id}')
        async def upload(device_id: str, request: Request, start_ms: float, end_ms: float,
                         uncertainty_ms: float, fps: float = 30, offset_ms: float = 0, audio: bool = False):
            if len(device_id) > 80 or not all(math.isfinite(v) for v in (start_ms,end_ms,uncertainty_ms,fps,offset_ms)):
                raise HTTPException(422, 'Invalid clip metadata')
            if not 0 < end_ms-start_ms <= 15000 or not 0 <= uncertainty_ms <= 5000 or not 1 <= fps <= 120:
                raise HTTPException(422, 'Clip duration, clock estimate or FPS outside bounds')
            if end_ms > now_ms()+5000 or end_ms < now_ms()-90000:
                raise HTTPException(422, 'Clip clock is stale or incorrect; resynchronise')
            mime = request.headers.get('content-type','').split(';')[0]
            if mime not in ('video/webm','video/mp4'):
                raise HTTPException(415, 'Use WebM or MP4')
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 12*1024*1024:
                    raise HTTPException(413, 'Clip exceeds 12 MB; lower camera quality')
            if not body:
                raise HTTPException(422, 'Empty clip')
            async with self.lock:
                self.cleanup()
                if sum(c['bytes'] for c in self.clips.values()) + len(body) > self.limit:
                    raise HTTPException(507, 'Temporary replay budget full; close reviews or lower quality')
                key = uuid.uuid4().hex
                path = self.root / (key + '.clip')
                await asyncio.to_thread(path.write_bytes, body)
                self.clips[key] = dict(id=key,device_id=device_id,start_ms=start_ms,end_ms=end_ms,
                    uncertainty_ms=uncertainty_ms,offset_ms=offset_ms,fps=fps,mime=mime,bytes=len(body),audio=audio,url=f'/api/clips/{key}')
            return {'id': key}

        @router.get('/clips/{key}')
        async def media(key: str):
            clip = self.clips.get(key)
            if not clip:
                raise HTTPException(404, 'Clip expired')
            return FileResponse(self.root / (key+'.clip'), media_type=clip['mime'],headers={'Cache-Control':'no-store'})

        @router.get('/buffer')
        async def status():
            async with self.lock:
                self.cleanup()
                cameras = {}
                for c in self.clips.values():
                    if c['end_ms'] < now_ms()-90000: continue
                    row = cameras.setdefault(c['device_id'],dict(start_ms=c['start_ms'],end_ms=0,seconds=0,uncertainty_ms=0))
                    row['start_ms'] = min(row['start_ms'],c['start_ms'])
                    row['end_ms'] = max(row['end_ms'],c['end_ms'])
                    row['seconds'] += (c['end_ms']-c['start_ms'])/1000
                    row['uncertainty_ms'] = c['uncertainty_ms']
                    row['offset_ms'] = c['offset_ms']
                for device_id,row in cameras.items():
                    intervals=coverage([c for c in self.clips.values() if c['device_id']==device_id],now_ms()-90000,now_ms())
                    row['seconds']=sum(b-a for a,b in intervals)/1000
                meters={k:v[-1] for k,v in self.audio.items() if v and now_ms()-v[-1]['t']<3000}
                return {'audio':meters,'server_ms':now_ms(),'cameras':cameras,'recorders':self.recorder_status,'bytes':sum(c['bytes'] for c in self.clips.values())}

        @router.get('/broadcast/camera/{device_id}')
        async def broadcast_camera(device_id: str):
            if len(device_id) > 80: raise HTTPException(422, 'Invalid camera')
            async with self.lock:
                current = now_ms()
                clips = sorted([dict(c) for c in self.clips.values()
                                if c['device_id'] == device_id and c['end_ms'] > current-30000],
                               key=lambda c:c['start_ms'])
                return {'server_ms':current, 'clips':clips,
                        'available_seconds':sum(b-a for a,b in coverage([c for c in self.clips.values() if c['device_id']==device_id],current-90000,current))/1000,
                        'recorder':self.recorder_status.get(device_id)}

        @router.post('/replays')
        async def review(seconds: int = 60, start_ms: float | None = None, end_ms: float | None = None):
            return await self.create_review(seconds, start_ms, end_ms)

        @router.delete('/replays/{key}')
        async def release(key: str):
            async with self.lock:
                self.reviews.pop(key,None)
                self.cleanup()
            return {'released':True}
        return router
