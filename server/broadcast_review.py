"""Session-only, manually operated DRS presentation. Never edits scoring data."""
import copy
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt


class ReviewCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['prepare', 'attach', 'announce', 'take', 'decision', 'cancel', 'live',
                    'play', 'pause', 'seek', 'speed', 'layout', 'primary',
                    'audio_source', 'zoom', 'mark_wicket', 'crease', 'lbw', 'original']
    review_id: str | None = Field(default=None, max_length=40)
    source_review_id: str | None = Field(default=None, max_length=40)
    controller_id: str | None = Field(default=None, min_length=8, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')
    kind: Literal['caught_behind', 'run_out', 'stumping', 'lbw', 'general'] = 'run_out'
    original: Literal['out', 'not_out', 'not_given'] = 'not_given'
    seconds: Literal[10, 30, 60] = 10
    camera_ids: list[str] = Field(default_factory=list, max_length=2)
    camera_id: str | None = Field(default=None, max_length=80)
    position_ms: float | None = Field(default=None, ge=0, le=60000, allow_inf_nan=False)
    speed: Literal[.25, .5, 1] = 1
    layout: Literal['single', 'split'] = 'single'
    verdict: Literal['out', 'not_out', 'inconclusive'] | None = None
    zoom: float = Field(default=1, ge=1, le=4, allow_inf_nan=False)
    x: float = Field(default=.5, ge=0, le=1, allow_inf_nan=False)
    y: float = Field(default=.5, ge=0, le=1, allow_inf_nan=False)
    # Normalised original-image coordinates, never screen/letterbox coordinates.
    points: list[tuple[float, float]] = Field(default_factory=list, max_length=2)
    pitching: Literal['not_assessed', 'outside_off', 'in_line', 'outside_leg'] = 'not_assessed'
    impact: Literal['not_assessed', 'outside_off', 'in_line', 'outside_leg'] = 'not_assessed'
    wickets: Literal['not_assessed', 'hitting', 'missing', 'uncertain'] = 'not_assessed'


class FollowZoom(BaseModel):
    model_config = ConfigDict(extra='forbid')
    zoom: float = Field(ge=1, le=6, allow_inf_nan=False)
    x: float = Field(ge=0, le=1, allow_inf_nan=False)
    y: float = Field(ge=0, le=1, allow_inf_nan=False)
    aspect: float = Field(default=16/9, ge=.1, le=10, allow_inf_nan=False)


class FollowView(BaseModel):
    """Only evidence/display state, never a screen capture or a scoring command."""
    model_config = ConfigDict(extra='forbid')
    review_id: str = Field(min_length=1, max_length=40)
    source_review_id: str = Field(min_length=1, max_length=40)
    controller_id: str = Field(min_length=8, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')
    sequence: StrictInt = Field(ge=0, le=1000000000)
    position_ms: float = Field(ge=0, le=60000, allow_inf_nan=False)
    playing: bool
    speed: Literal[.25, .5, 1] = 1
    primary: str | None = Field(default=None, max_length=80)
    secondary: str | None = Field(default=None, max_length=80)
    audio_source: str | None = Field(default=None, max_length=80)
    available: bool = True
    waveform: bool = False
    assessment: bool = False
    zoom: dict[str, FollowZoom] = Field(default_factory=dict, max_length=8)


class ReviewReady(BaseModel):
    model_config = ConfigDict(extra='forbid')
    review_id: str = Field(min_length=1, max_length=40)
    client_id: str = Field(min_length=8, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')
    role: Literal['obs', 'preview', 'browser', 'review_preview']
    state: Literal['loading', 'ready', 'error']
    error: str = Field(default='', max_length=200)


class BroadcastReview:
    LABELS = dict(caught_behind='Caught behind', run_out='Run out', stumping='Stumping', lbw='LBW', general='General')

    def __init__(self, desk, clock, appearance):
        self.desk, self.clock, self.appearance = desk, clock, appearance
        self.session = None
        self.ready = {}

    def clear(self):
        if self.session:
            self.desk.replay.reviews.pop(self.session['id'], None)
        self.session = None
        self.ready.clear()

    def refresh(self, at):
        s = self.session
        if not s:
            return
        manifest = self.desk.replay.reviews.get(s['id'])
        if manifest:
            manifest['expires_ms'] = at + 15 * 60 * 1000
            source = self.desk.replay.reviews.get(s.get('source_review_id'))
            if source:
                source['expires_ms'] = at + 15 * 60 * 1000
            if s.get('follow_controller') and s['phase']=='private' and at-s['follow_updated_ms']>60000:
                self.clear()
                return
            if s.get('follow_controller') and s['phase']!='decision' and at-s['follow_updated_ms']>2500 and s['follow_status']!='controller_lost':
                # Stop at the last frame reported by the umpire, not an extrapolated
                # future frame. A quiet/disconnected controller must not keep air moving.
                s.update(position_ms=s['follow_position_ms'], anchor_ms=at, playing=False,
                         follow_status='controller_lost', revision=s['revision']+1)
                self._sync_program()
        else:
            if self.desk.program['review_id'] == s['id']:
                self.desk.program.update(mode='live', review_id=None, position_ms=0,
                                         playing=True, camera_id=s.get('return_camera_id',self.desk.program['camera_id']),
                                         revision=self.desk.program['revision']+1)
            self.clear()

    def position(self, at):
        s = self.session
        if s['phase'] in ('on_air', 'decision'):
            return self.desk.position(at)
        return min(s['duration_ms']-1, s['position_ms'] +
                   (max(0, at-s['anchor_ms'])*s['speed'] if s['playing'] else 0))

    def snapshot(self, manifest=False):
        at = self.clock()
        self.refresh(at)
        s = self.session
        if not s:
            return None
        result = copy.deepcopy(s)
        result['position_ms'] = self.position(at)
        if s['phase'] in ('on_air', 'decision'):
            result['playing'] = self.desk.program['playing']
            result['speed'] = self.desk.program['speed']
        if result['position_ms'] >= s['duration_ms']-1:
            result['playing'] = False
        self.ready = {k:v for k,v in self.ready.items() if at-v['received_ms'] < 15000}
        result['outputs'] = [{**r, 'age_ms':max(0, at-r['received_ms'])} for r in self.ready.values()]
        known = {r['client_id'] for r in result['outputs']}
        for r in self.desk.reports.values():
            if r['role']=='obs' and at-r['received_ms']<=4000 and r['client_id'] not in known:
                result['outputs'].append(dict(client_id=r['client_id'], role='obs', state='loading',
                    error='', age_ms=max(0,at-r['received_ms']), review_id=s['id']))
        if manifest:
            result['manifest'] = copy.deepcopy(self.desk.replay.reviews[s['id']])
        return result

    def report(self, report):
        self.refresh(self.clock())
        if not self.session or report.review_id != self.session['id']:
            raise HTTPException(409, 'This review has ended or been replaced')
        self.snapshot()
        if report.client_id not in self.ready and len(self.ready) >= 32:
            raise HTTPException(429, 'Close unused review outputs')
        self.ready[report.client_id] = {**report.model_dump(), 'received_ms':self.clock()}

    def _require_ready(self):
        fresh = [r for r in self.ready.values() if self.clock()-r['received_ms'] <= 4000]
        # An OBS-labelled output must be ready, not just the operator's preview.
        obs_ids = {r['client_id'] for r in self.desk.reports.values()
                   if r['role']=='obs' and self.clock()-r['received_ms'] <= 4000}
        obs_ids.update(r['client_id'] for r in fresh if r['role']=='obs')
        if obs_ids:
            if any(not any(r['client_id']==id and r['state']=='ready' for r in fresh) for id in obs_ids):
                raise HTTPException(409, 'Wait for every connected OBS output to finish loading the review')
        elif not any(r['state']=='ready' for r in fresh):
            raise HTTPException(409, 'Open the private review preview and wait until it is ready')

    def _sync_program(self):
        s, p = self.session, self.desk.program
        if s['phase'] in ('on_air', 'decision'):
            p.update(position_ms=s['position_ms'], anchor_ms=s['anchor_ms'],
                     playing=s['playing'], speed=s['speed'], camera_id=s['primary'])
            p['revision'] += 1

    async def command(self, cmd):
        async with self.desk.lock:
            self.refresh(self.clock())
            program_review=self.desk.replay.reviews.get(self.desk.program['review_id'])
            if cmd.action in ('prepare','attach') and program_review and program_review.get('kind')=='fielding_highlights':
                raise HTTPException(409,'Return fielding highlights to live before preparing a DRS review')
            if cmd.action in ('live', 'cancel'):
                if self.session and cmd.review_id != self.session['id']:
                    raise HTTPException(409, 'This review has been replaced; refresh before ending it')
                if self.session and self.session['phase'] in ('on_air', 'decision'):
                    self.desk.program.update(mode='live', review_id=None, position_ms=0,
                                             playing=True, speed=1, anchor_ms=self.clock(),
                                             camera_id=self.session.get('return_camera_id',self.desk.program['camera_id']))
                if self.session and self.session['phase'] != 'private':
                    self.desk.program['revision'] += 1
                self.clear()
                return self.snapshot()
            if cmd.action == 'attach':
                if self.session:
                    raise HTTPException(409, 'End the existing broadcast review before linking this umpire')
                source = self.desk.replay.reviews.get(cmd.source_review_id)
                if not source or not cmd.controller_id:
                    raise HTTPException(409, 'Open a recorded umpire review before linking it')
                ids = list(source['coverage'])
                if not ids or len(ids)>8 or sum(c['bytes'] for c in source['clips'])>256*1024*1024:
                    raise HTTPException(409, 'Choose a shorter review with at most eight recorded cameras (256 MB maximum)')
                if len(self.desk.replay.reviews)>=4:
                    raise HTTPException(429, 'Close another replay before linking this one')
                review = copy.deepcopy(source)
                review.update(id=uuid.uuid4().hex, expires_ms=self.clock()+15*60*1000)
                self.desk.replay.reviews[review['id']] = review
                labels = {d['device_id']:d['name'] for d in self.desk.devices.connected_snapshot()}
                ids = sorted(ids)
                self.session = dict(id=review['id'], kind=cmd.kind, label=self.LABELS[cmd.kind],
                    phase='private', original=cmd.original, verdict=None, revision=1,
                    cameras=[dict(id=id,name=labels.get(id,id)) for id in ids], primary=ids[0], secondary=None,
                    audio_source=ids[0], layout='single', color=self.appearance(),
                    duration_ms=review['end_ms']-review['start_ms'], position_ms=0,
                    playing=False, speed=.5, anchor_ms=self.clock(), wicket_ms=None, crease=[],
                    zoom={id:dict(zoom=1,x=.5,y=.5,aspect=16/9) for id in ids},
                    lbw=dict(pitching='not_assessed',impact='not_assessed',wickets='not_assessed'),
                    show_waveform=False, show_assessment=False, follow_controller=cmd.controller_id,
                    source_review_id=cmd.source_review_id, follow_sequence=-1, follow_updated_ms=self.clock(),
                    follow_position_ms=0, follow_status='selecting_angle')
                return self.snapshot()
            if cmd.action == 'prepare':
                if self.session:
                    raise HTTPException(409, 'End the existing broadcast review before preparing another')
                ids = cmd.camera_ids or [self.desk.snapshot()['program']['camera_id']]
                if len(set(ids)) != len(ids) or any(not id or len(id)>80 for id in ids):
                    raise HTTPException(422, 'Choose one or two different cameras')
                at = self.clock()
                clips = [c for c in self.desk.replay.clips.values() if c['device_id'] in ids and c['end_ms']>at-15000]
                if any(not any(c['device_id']==id for c in clips) for id in ids):
                    raise HTTPException(409, 'Each selected angle needs recent recorded footage')
                end = min(at-5000, *(max(c['end_ms'] for c in clips if c['device_id']==id)-1 for id in ids))
                start = end-cmd.seconds*1000
                clips = [c for c in self.desk.replay.clips.values()
                         if c['device_id'] in ids and c['end_ms']>start and c['start_ms']<end]
                candidates = sorted({start, *(max(start,c['start_ms']) for c in clips)})
                first = next((t for t in candidates if t<end and all(
                    any(c['device_id']==id and c['start_ms']<=t<c['end_ms'] for c in clips) for id in ids)), None)
                if first is None:
                    raise HTTPException(409, 'Selected angles have no common recorded frame in this window')
                if sum(c['bytes'] for c in clips) > 256*1024*1024:
                    raise HTTPException(409, 'Choose a shorter review; selected footage exceeds 256 MB')
                review = await self.desk.replay.create_review(cmd.seconds, start, end)
                review['clips'] = [c for c in review['clips'] if c['device_id'] in ids]
                review['coverage'] = {id:review['coverage'][id] for id in ids}
                review['audio'] = {id:review['audio'].get(id, []) for id in ids}
                labels = {d['device_id']:d['name'] for d in self.desk.devices.connected_snapshot()}
                self.session = dict(id=review['id'], kind=cmd.kind, label=self.LABELS[cmd.kind],
                    phase='private', original=cmd.original, verdict=None, revision=1,
                    cameras=[dict(id=id, name=labels.get(id,id)) for id in ids], primary=ids[0],
                    secondary=ids[1] if len(ids)>1 else None,
                    audio_source=ids[0], layout='split' if len(ids)==2 and cmd.kind=='caught_behind' else 'single',
                    color=self.appearance(), duration_ms=end-start, position_ms=first-start,
                    playing=False, speed=.5, anchor_ms=at, wicket_ms=None, crease=[],
                    zoom={id:dict(zoom=1,x=.5,y=.5) for id in ids},
                    lbw=dict(pitching='not_assessed',impact='not_assessed',wickets='not_assessed'))
                return self.snapshot()
            s = self.session
            if not s or cmd.review_id != s['id']:
                raise HTTPException(409, 'This review has ended or been replaced; refresh the controls')
            if s.get('follow_controller') and cmd.action in ('play','pause','seek','speed','layout','primary','audio_source','zoom','mark_wicket','crease'):
                raise HTTPException(409, 'This review follows the umpire console; use that console to change the evidence view')
            at = self.clock()
            position = self.position(at)
            if s['phase'] in ('on_air', 'decision'):
                s.update(playing=self.desk.program['playing'], speed=self.desk.program['speed'])
            s.update(position_ms=position, anchor_ms=at)
            if cmd.action == 'announce':
                if s['phase'] not in ('private', 'announced'):
                    raise HTTPException(409, 'Review is already on air')
                s['phase'] = 'announced'
                self.desk.program['revision'] += 1
            elif cmd.action == 'take':
                if s['phase'] not in ('private', 'announced'):
                    raise HTTPException(409, 'Review is already on air')
                self._require_ready()
                if s.get('follow_controller') and s['follow_status']!='ready':
                    raise HTTPException(409, 'Wait for a visible, decoded frame from the linked umpire')
                old = self.desk.program['review_id']
                s.update(phase='on_air', playing=s['playing'] if s.get('follow_controller') else False,
                         return_camera_id=self.desk.program['camera_id'])
                self.desk.program.update(mode='replay', review_id=s['id'])
                if old and old != s['id']:
                    self.desk.replay.reviews.pop(old, None)
            elif cmd.action == 'decision':
                if s['phase'] not in ('on_air', 'decision') or cmd.verdict is None:
                    raise HTTPException(409, 'Take the review on air, then choose a manual decision')
                s.update(phase='decision', verdict=cmd.verdict, playing=False)
            elif cmd.action in ('play', 'pause', 'seek', 'speed'):
                if s['phase']=='decision':
                    raise HTTPException(409, 'The decision is held; return to live to end the review')
                if cmd.action=='seek':
                    if cmd.position_ms is None:
                        raise HTTPException(422, 'Choose a position')
                    s['position_ms'] = min(cmd.position_ms, s['duration_ms']-1)
                if cmd.action in ('play','pause'):
                    s['playing'] = cmd.action=='play'
                    if s['playing'] and position>=s['duration_ms']-1:
                        s['position_ms'] = 0
                if cmd.action=='speed':
                    s['speed'] = cmd.speed
            elif cmd.action in ('primary','audio_source','zoom'):
                if cmd.camera_id not in {c['id'] for c in s['cameras']}:
                    raise HTTPException(422, 'Choose an angle included in this review')
                if cmd.action=='zoom':
                    s['zoom'][cmd.camera_id] = dict(zoom=cmd.zoom,x=cmd.x,y=cmd.y)
                else:
                    if cmd.action=='primary' and s.get('secondary')==cmd.camera_id:
                        s['secondary']=s['primary']
                    s[cmd.action] = cmd.camera_id
            elif cmd.action=='layout':
                if cmd.layout=='split' and len(s['cameras'])<2:
                    raise HTTPException(422, 'Split view needs two recorded angles')
                s['layout'] = cmd.layout
            elif cmd.action in ('mark_wicket','crease'):
                if s['kind'] not in ('run_out','stumping'):
                    raise HTTPException(409, 'Wicket/crease markers are for run-out and stumping reviews')
                if cmd.action=='mark_wicket':
                    if s['playing'] and position < s['duration_ms']-1:
                        raise HTTPException(409, 'Pause on the wicket-breaking frame before marking it')
                    marked = min(cmd.position_ms if cmd.position_ms is not None else position, s['duration_ms']-1)
                    s.update(wicket_ms=marked, position_ms=marked, playing=False)
                else:
                    if len(cmd.points) not in (0,2) or any(not 0<=v<=1 for pt in cmd.points for v in pt):
                        raise HTTPException(422, 'Choose two points inside the original image, or clear the guide')
                    s['crease'] = dict(camera_id=s['primary'],points=cmd.points) if cmd.points else []
            elif cmd.action=='lbw':
                if s['kind']!='lbw':
                    raise HTTPException(409, 'LBW assessments are only available in an LBW review')
                s['lbw'] = dict(pitching=cmd.pitching,impact=cmd.impact,wickets=cmd.wickets)
            elif cmd.action=='original':
                s['original'] = cmd.original
            s['revision'] += 1
            self._sync_program()
            return self.snapshot()

    async def follow(self, view):
        async with self.desk.lock:
            self.refresh(self.clock())
            s = self.session
            if not s or view.review_id!=s['id'] or view.controller_id!=s.get('follow_controller') or view.source_review_id!=s.get('source_review_id'):
                raise HTTPException(409, 'This console is not linked to the current broadcast review')
            if view.sequence<=s['follow_sequence']:
                raise HTTPException(409, 'Stale umpire view update ignored')
            ids = {c['id'] for c in s['cameras']}
            if set(view.zoom)-ids or any(id is not None and id not in ids for id in (view.primary,view.secondary,view.audio_source)):
                raise HTTPException(422, 'The selected camera is not in this recorded umpire review')
            if view.secondary and view.secondary==view.primary:
                raise HTTPException(422, 'Choose two different evidence angles')
            if view.available and (not view.primary or not view.audio_source):
                raise HTTPException(422, 'A visible evidence angle and audio source are required')
            at = self.clock()
            s.update(follow_sequence=view.sequence, follow_updated_ms=at)
            if s['phase']=='decision':
                return {'ok':True, 'held':True}
            if not view.available:
                s.update(position_ms=s['follow_position_ms'], anchor_ms=at, playing=False, follow_status='selecting_angle')
            else:
                position=min(view.position_ms,s['duration_ms']-1)
                s.update(primary=view.primary, secondary=view.secondary,
                         audio_source=view.audio_source, layout='split' if view.secondary else 'single',
                         position_ms=position, follow_position_ms=position, anchor_ms=at,
                         playing=view.playing, speed=view.speed, show_waveform=view.waveform,
                         show_assessment=view.assessment, follow_status='ready')
                for id,z in view.zoom.items():
                    s['zoom'][id]=z.model_dump()
            s['revision']+=1
            self._sync_program()
            return {'ok':True}

    def router(self):
        router = APIRouter(prefix='/api/broadcast/review')

        @router.get('')
        async def get_review():
            return dict(server_ms=self.clock(), review=self.snapshot(manifest=True))

        @router.post('')
        async def command(cmd: ReviewCommand):
            return dict(server_ms=self.clock(), review=await self.command(cmd))

        @router.post('/ready')
        async def ready(report: ReviewReady):
            self.report(report)
            return {'ok':True}

        @router.post('/follow')
        async def follow(view: FollowView):
            return await self.follow(view)

        return router
