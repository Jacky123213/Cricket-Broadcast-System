"""Shared, session-only program commands and bounded player self-reports.

Telemetry is from the browser playing the program, not the camera microphone
flag or OBS mixer. Never retain raw audio, receiver logs or remote IP addresses.
"""
import asyncio
import copy
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from .replay import now_ms
from .broadcast_review import BroadcastReview


class ProgramCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['camera', 'replay', 'live', 'play', 'pause', 'seek', 'speed', 'audio', 'retry']
    camera_id: str | None = Field(default=None, max_length=80)
    seconds: Literal[10, 30, 60] = 10
    position_ms: float | None = Field(default=None, ge=0, le=600000, allow_inf_nan=False)
    speed: Literal[.25, .5, 1] = 1
    muted: bool | None = None


class PlayerReport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    client_id: str = Field(min_length=8, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')
    role: Literal['obs', 'preview', 'browser']
    camera_id: str = Field(max_length=80)
    revision: StrictInt = Field(ge=0)
    mode: Literal['live', 'replay']
    state: Literal['playing', 'paused', 'buffering', 'offline', 'error']
    delay_seconds: float | None = Field(default=None, ge=0, le=3600, allow_inf_nan=False)
    available_seconds: float | None = Field(default=None, ge=0, le=3600, allow_inf_nan=False)
    headroom_seconds: float | None = Field(default=None, ge=0, le=3600, allow_inf_nan=False)
    last_frame_age_ms: float | None = Field(default=None, ge=0, le=3600000, allow_inf_nan=False)
    dropped_frames: StrictInt | None = Field(default=None, ge=0, le=1000000000)
    total_frames: StrictInt | None = Field(default=None, ge=0, le=1000000000)
    late_clips: StrictInt = Field(default=0, ge=0, le=1000000000)
    decode_errors: StrictInt = Field(default=0, ge=0, le=1000000000)
    poll_errors: StrictInt = Field(default=0, ge=0, le=1000000000)
    muted: bool = True
    audio_present: bool = False
    meter_dbfs: float | None = Field(default=None, ge=-120, le=0, allow_inf_nan=False)
    meter_state: Literal['active', 'suspended', 'unavailable', 'no_audio'] = 'unavailable'
    graphics_kind: Literal['scorebar','hidden','run_chart','batting_card','bowling_card','wicket_card','innings_break','match_summary','lineup','player_batting','player_bowling','coming_up','toss','sponsor','win'] | None = None
    graphics_surge: bool = False


class BroadcastDesk:
    def __init__(self, replay, devices, appearance=lambda:'#b8e34b'):
        self.replay = replay
        self.devices = devices
        self.lock = asyncio.Lock()
        self.program = dict(revision=0, camera_id=None, mode='live', review_id=None,
                            playing=True, position_ms=0, speed=1, anchor_ms=now_ms(), muted=False, retry_token=0)
        self.reports = {}
        self.review = BroadcastReview(self, lambda:now_ms(), appearance)
        self.fielding_return = None

    def end_fielding_reel(self):
        review = self.replay.reviews.get(self.program['review_id'])
        if review and review.get('kind')=='fielding_highlights':
            self.replay.reviews.pop(review['id'],None)
            self.program.update(mode='live',review_id=None,camera_id=review['return_camera_id'],playing=True,
                                position_ms=0,anchor_ms=now_ms(),revision=self.program['revision']+1)
            self.fielding_return = None

    def position(self, at):
        p = self.program
        review = self.replay.reviews.get(p['review_id'])
        if p['mode'] != 'replay' or not review: return 0
        elapsed = max(0, at-p['anchor_ms']) * p['speed'] if p['playing'] else 0
        return min(review['end_ms']-review['start_ms']-1, p['position_ms']+elapsed)

    def snapshot(self):
        at = now_ms()
        self.review.refresh(at)
        p = self.program
        roster = self.devices.connected_snapshot()
        if p['camera_id'] is None and roster:
            p['camera_id'] = next((d['device_id'] for d in roster if d['role']=='UMPIRE_POV'), roster[0]['device_id'])
            p['revision'] += 1
        review = self.replay.reviews.get(p['review_id'])
        if not review and self.fielding_return and self.fielding_return[0]==p['review_id']:
            p['camera_id']=self.fielding_return[1]
            self.fielding_return=None
        if review and review.get('kind')=='fielding_highlights' and not review.get('awaiting_ready') and self.position(at)>=review['end_ms']-1:
            self.end_fielding_reel()
            review = None
        if review:
            review['expires_ms'] = at+15*60*1000
        elif p['mode'] == 'replay':
            # Explicitly return to the delayed feed if the temporary review expired.
            p.update(mode='live', review_id=None, position_ms=0, playing=True, revision=p['revision']+1)
        result = copy.deepcopy(p)
        result['position_ms'] = self.position(at)
        if review and result['position_ms'] >= review['end_ms']-review['start_ms']-1:
            result['playing'] = False
        # Program playback needs clip metadata, not the umpire waveform arrays.
        result['review'] = copy.deepcopy({k:v for k,v in review.items() if k!='audio'}) if review else None
        return dict(program=result, devices=roster, server_ms=at, drs=self.review.snapshot())

    async def command(self, command):
        async with self.lock:
            self.snapshot()
            p = self.program
            at = now_ms()
            action = command.action
            if action == 'camera':
                if self.review.session and self.review.session['phase'] in ('on_air','decision'):
                    raise HTTPException(409, 'Use the DRS review angle controls or return to live')
                review = self.replay.reviews.get(p['review_id'])
                if review and review.get('kind')=='fielding_highlights':
                    raise HTTPException(409,'Return to live before changing the program camera')
                choices = {d['device_id'] for d in self.devices.connected_snapshot()}
                if p['mode']=='replay' and review: choices = set(review['coverage'])
                if command.camera_id not in choices: raise HTTPException(409,'This camera has no available program source')
                p['camera_id'] = command.camera_id
            elif action == 'replay':
                if self.review.session and self.review.session['phase'] in ('on_air','decision'):
                    raise HTTPException(409, 'End the DRS review before opening an ordinary replay')
                id = p['camera_id']
                clips = [c for c in self.replay.clips.values() if c['device_id']==id and c['end_ms']>at-90000]
                if not clips: raise HTTPException(409,'No recorded footage for the selected camera')
                end = min(max(c['end_ms'] for c in clips)-1, at-5000)
                start = end-command.seconds*1000
                if not any(c['end_ms']>start and c['start_ms']<end for c in clips):
                    raise HTTPException(409,'Selected camera has no footage in that replay window')
                review = await self.replay.create_review(command.seconds, start, end)
                old = p['review_id']
                p.update(mode='replay', review_id=review['id'], position_ms=0, playing=True, speed=1, anchor_ms=at)
                if old: self.replay.reviews.pop(old, None)
            elif action == 'live':
                self.end_fielding_reel()
                if self.review.session and self.review.session['phase'] in ('on_air','decision'):
                    p['camera_id'] = self.review.session.get('return_camera_id',p['camera_id'])
                self.review.clear()
                old = p['review_id']
                p.update(mode='live', review_id=None, position_ms=0, playing=True, speed=1, anchor_ms=at)
                if old: self.replay.reviews.pop(old, None)
            elif action == 'audio':
                if command.muted is None: raise HTTPException(422,'Choose whether program audio is muted')
                p['muted'] = command.muted
            elif action == 'retry':
                p['retry_token'] += 1
            else:
                if p['mode']!='replay': raise HTTPException(409,'Open a program replay first')
                active_review = self.replay.reviews.get(p['review_id'])
                if active_review and active_review.get('awaiting_ready'):
                    raise HTTPException(409,'Wait for the fielding highlights to finish loading on every output')
                if self.review.session and self.review.session.get('follow_controller'):
                    raise HTTPException(409,'This review follows the umpire console; use its playback controls')
                if self.review.session and self.review.session['phase']=='decision':
                    raise HTTPException(409,'The umpire decision is held; return to live to end the review')
                position = self.position(at)
                if action=='seek':
                    if command.position_ms is None: raise HTTPException(422,'Choose a replay position')
                    review = self.replay.reviews[p['review_id']]
                    position = min(command.position_ms, review['end_ms']-review['start_ms']-1)
                p.update(position_ms=position, anchor_ms=at)
                if action in ('play', 'pause'):
                    p['playing'] = action=='play'
                    review = self.replay.reviews[p['review_id']]
                    if action=='play' and position>=review['end_ms']-review['start_ms']-1:
                        p['position_ms'] = 0
                if action=='speed': p['speed'] = command.speed
            p['revision'] += 1
            return self.snapshot()

    def health(self):
        at = now_ms()
        self.reports = {id:r for id,r in self.reports.items() if at-r['received_ms']<120000}
        return dict(server_ms=at, clients=[{**r,'report_age_ms':max(0,at-r['received_ms'])} for r in self.reports.values()])

    def report(self, report):
        self.health()
        if report.client_id not in self.reports and len(self.reports)>=32:
            raise HTTPException(429,'Too many output monitors; close unused broadcast pages')
        self.reports[report.client_id] = {**report.model_dump(), 'received_ms':now_ms()}
        p = self.program
        review = self.replay.reviews.get(p['review_id'])
        if review and review.get('kind')=='fielding_highlights' and review.get('awaiting_ready'):
            fresh = [r for r in self.reports.values() if now_ms()-r['received_ms']<=4000]
            outputs = [r for r in fresh if r['role']=='obs'] or fresh
            if outputs and all(r['mode']=='replay' and r['revision']==p['revision'] and r['state']=='paused' for r in outputs):
                review['awaiting_ready'] = False
                p.update(playing=True,position_ms=0,anchor_ms=now_ms(),revision=p['revision']+1)

    def router(self):
        router = APIRouter(prefix='/api/broadcast')

        @router.get('/program')
        async def program(): return self.snapshot()

        @router.post('/program')
        async def command(command: ProgramCommand): return await self.command(command)

        @router.get('/health')
        async def health(): return self.health()

        @router.post('/health')
        async def report(report: PlayerReport):
            self.report(report)
            return {'ok':True}

        return router
