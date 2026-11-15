"""Read-only match centre plus opt-in, bounded camera-highlight archiving."""
from __future__ import annotations

import asyncio
import copy
import json
import shutil
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .install_support import write_json_atomic
from .replay import now_ms, coverage
from .match_events import record_deliveries


class LiveSettings(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    stream_enabled: bool=False
    clips_enabled: bool=False
    duck_enabled: bool=True
    save_fours: bool=True
    save_sixes: bool=True
    save_wickets: bool=True
    save_other_runs: bool=False
    save_extras: bool=False
    save_dots: bool=False
    before_seconds: int=Field(default=8,ge=3,le=20)
    after_seconds: int=Field(default=5,ge=2,le=10)
    archive_limit_mb: int=Field(default=512,ge=64,le=8192)
    format: str=Field(default='Backyard cricket',max_length=100)
    competition: str=Field(default='',max_length=160)
    match_date: str=Field(default='',max_length=80)


class SaveHighlight(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    title: str=Field(default='Manual highlight',min_length=1,max_length=160)


class LiveMatch:
    def __init__(self, settings, scoreboard, replay, desk):
        self.scoreboard,self.replay,self.desk=scoreboard,replay,desk
        self.path=settings.scoreboard_path/'live-settings.json'
        self.root=settings.data_root/'highlights'
        self.index=self.root/'index.json'
        self.config=LiveSettings.model_validate(json.loads(self.path.read_text('utf-8'))) if self.path.exists() else LiveSettings()
        self.highlights=json.loads(self.index.read_text('utf-8')) if self.index.exists() else []
        if not isinstance(self.highlights,list): raise ValueError('Saved highlight index is damaged; nothing was reset')
        self.pending={}; self.seen=set(); self.status='Ready · waiting for a new scoring event' if self.config.clips_enabled else 'Clips off'; self.capture_lock=asyncio.Lock()
        self.break_started = None
        self.break_played = set()

    def settings(self):
        return {**self.config.model_dump(),'archive_count':len(self.highlights),
                'archive_bytes':sum(p.stat().st_size for p in (self.root/'media').glob('*.clip')) if (self.root/'media').exists() else 0,
                'status':self.status,'pending':len(self.pending)}

    def save_settings(self, changes):
        previous=self.config.clips_enabled
        proposed=LiveSettings.model_validate({**self.config.model_dump(),**changes})
        write_json_atomic(self.path,proposed.model_dump())
        self.config=proposed
        if not self.config.clips_enabled:
            self.pending.clear(); self.status='Clips off · saved highlights retained, playback disabled'
            self.desk.end_fielding_reel()
        elif not previous: self.status='Ready · waiting for a new scoring event'
        return self.settings()

    def state(self):
        with self.scoreboard.lock:
            now=time.time(); self.scoreboard.graphics.flush(now)
            g=self.scoreboard.graphics
            for innings_row in g.innings:
                if 'delivery_history' not in innings_row:
                    record_deliveries(innings_row,self.scoreboard.data,None,now)
                    g.dirty=True
            innings=[g.stats(i,include_history=True) for i in g.innings]
            self.scoreboard._save_graphics()
            for index,innings_row in enumerate(innings):
                for row in innings_row['deliveries']:
                    row['id']=f'{g.match_id}:{index}:{row["id"]}'
            events={row['id']:row for innings_row in innings for row in innings_row['deliveries']}
            valid_highlights=[h for h in self.highlights if h['match_id']==g.match_id and (h['kind']=='manual' or events.get(h['event_id'],{}).get('kind')==h['kind'])]
            manifest={h['event_id']:h['id'] for h in valid_highlights} if self.config.clips_enabled else {}
            for innings_row in innings:
                for row in innings_row['deliveries']: row['highlight_id']=manifest.get(row['id'])
            return {'match_id':g.match_id,'server_time':now,'score':copy.deepcopy(self.scoreboard.data),
                    'innings':innings,'phase':g.phase,'result':g.result(),'target':g.target() if len(innings)>1 else None,
                    'title':g.config['match_title'],'venue':g.config['venue'],'total_overs':g.config['total_overs'],
                    'config':self.config.model_dump(),'capture_status':self.status,
                    'highlights':[{k:v for k,v in h.items() if k!='clips'} for h in valid_highlights] if self.config.clips_enabled else []}

    async def tick(self):
        state=await asyncio.to_thread(self.state)
        reel=self.replay.reviews.get(self.desk.program['review_id'])
        if reel and reel.get('kind')=='fielding_highlights' and (not self.config.clips_enabled or state['phase']!='innings_break' or reel['match_id']!=state['match_id'] or self.scoreboard.graphics.config['pack']!='fox_odi'):
            self.desk.end_fielding_reel()
        if state['phase']!='innings_break': self.break_started=None
        elif self.break_started is None: self.break_started=state['server_time']
        active={row['id']:row for innings in state['innings'] for row in innings['deliveries']}
        # Undo/corrections invalidate automatically captured links rather than
        # showing a wicket/six that the scorer removed. Saved media is retained.
        for key in list(self.pending):
            if not key.startswith('manual:') and (key not in active or not self.event_enabled(active[key]['kind']) or active[key]['kind']!=self.pending[key]['kind']):
                self.pending.pop(key,None)
        if not self.config.clips_enabled:
            self.seen.update(active); return
        if len(self.seen)>10000: self.seen=set(active)
        saved={h['event_id'] for h in self.highlights}
        for index,innings in enumerate(state['innings']):
            for row in innings['deliveries']:
                key=row['id']
                if key in self.seen or key in saved or key in self.pending: continue
                self.seen.add(key)
                if self.event_enabled(row['kind']) and row.get('at') and 0<=state['server_time']-row['at']<30:
                    self.schedule(key,state['match_id'],index,row['at'],f'{row.get("bowler") or "Bowler"} to {row.get("batter") or "batter"}: {row.get("dismissal") or row["text"]}',row['kind'],row['ball'])
        for key,item in list(self.pending.items()):
            if now_ms()<item['end_ms']+2000: continue
            try:
                done=await self.capture(item)
                if done or now_ms()>item['end_ms']+18000: self.pending.pop(key,None)
            except (OSError,ValueError) as exc:
                self.status='Highlight not saved: '+str(exc); self.pending.pop(key,None)
        marker=(state['match_id'],len(state['innings'])-1)
        g=self.scoreboard.graphics
        if self.break_started is not None and state['server_time']-self.break_started>=5 and not self.pending and marker not in self.break_played and g.config['pack']=='fox_odi' and g.config['auto_break_highlights'] and self.desk.program['mode']=='live' and not self.desk.review.session and not (g.active and g.active.get('until') is None):
            try:
                await self.play_fielding_highlights()
                self.break_played.add(marker)
            except HTTPException:
                pass  # Nothing saved yet: remain on live, retry after the next capture.

    async def play_fielding_highlights(self):
        async with self.desk.lock:
            if not self.config.clips_enabled:
                raise HTTPException(403,'Enable highlight clips first')
            state=self.state()
            if state['phase']!='innings_break' or self.scoreboard.graphics.config['pack']!='fox_odi':
                raise HTTPException(409,'Choose FOX ODI and end the innings before playing break highlights')
            if self.desk.review.session or self.desk.program['mode']!='live':
                raise HTTPException(409,'Return the shared program to live and end any DRS review first')
            if len(self.replay.reviews)>=4:
                raise HTTPException(429,'Close another review before loading fielding highlights')
            index=len(state['innings'])-1
            innings=state['innings'][index]
            valid={h['id'] for h in state['highlights'] if h['innings']==index and h['kind']=='wicket'}
            highlights=sorted((h for h in self.highlights if h['id'] in valid and not h.get('partial')),key=lambda h:h['start_ms'])[:10]
            if not highlights:
                raise HTTPException(409,'No complete wicket highlights are saved for this fielding side')
            if sum(c['bytes'] for h in highlights for c in h['clips'])>256*1024*1024:
                raise HTTPException(409,'Fielding highlights exceed the 256 MB playback budget')
            clips=[]; items=[]; offset=0
            for h in highlights:
                duration=h['end_ms']-h['start_ms']
                if not 0<duration<=30000: continue
                event=next((r for r in innings['deliveries'] if r['id']==h['event_id']),{})
                items.append(dict(start_ms=offset,end_ms=offset+duration,title=h['title'],ball=h.get('ball',''),
                                  batter=event.get('batter',''),dismissal=event.get('dismissal','Out'),
                                  runs=event.get('batter_runs'),balls=event.get('batter_balls')))
                for c in h['clips']:
                    clips.append({**copy.deepcopy(c),'id':h['id']+':'+c['id'],'device_id':'fielding-highlights',
                                  'start_ms':offset+c['start_ms']-h['start_ms'],
                                  'end_ms':min(offset+duration,offset+c['end_ms']-h['start_ms']),
                                  'reel_item':len(items)-1})
                offset+=duration
            if not items: raise HTTPException(409,'No playable wicket highlights are available')
            at=now_ms(); id=uuid.uuid4().hex
            review=dict(id=id,kind='fielding_highlights',match_id=state['match_id'],start_ms=0,end_ms=offset,
                        expires_ms=at+15*60*1000,clips=clips,items=items,awaiting_ready=True,
                        return_camera_id=self.desk.program['camera_id'],batting_team=innings['team'],
                        batting_logo=innings['logo'],batting_color=innings['color'],total=f"{innings['wickets']}–{innings['runs']}",
                        fielding_team=innings['opposition'],fielding_logo=innings['opposition_logo'],fielding_color=innings['opposition_color'])
            self.replay.reviews[id]=review
            self.desk.fielding_return=(id,review['return_camera_id'])
            self.desk.program.update(mode='replay',review_id=id,camera_id='fielding-highlights',playing=False,
                                     position_ms=0,speed=1,anchor_ms=at,revision=self.desk.program['revision']+1)
            return self.desk.snapshot()

    def event_enabled(self,kind):
        field={'four':'save_fours','six':'save_sixes','wicket':'save_wickets',
               'runs':'save_other_runs','extra':'save_extras','dot':'save_dots'}.get(kind)
        return bool(field and getattr(self.config,field))

    def schedule(self,event_id,match_id,index,at,title,kind,ball=''):
        if len(self.pending)>=20:
            self.status='Highlight queue full; lower scoring/camera load'; return
        camera=self.desk.snapshot()['program']['camera_id']
        self.pending[event_id]={'event_id':event_id,'match_id':match_id,'innings':index,'title':title,'kind':kind,
                                'ball':ball,'camera_id':camera,'start_ms':at*1000-self.config.before_seconds*1000,
                                'end_ms':at*1000+self.config.after_seconds*1000}
        self.status='Waiting for camera footage to finish uploading…'

    async def capture(self,item):
        async with self.capture_lock, self.replay.lock:
            if not self.config.clips_enabled: return True
            clips=[copy.deepcopy(c) for c in self.replay.clips.values() if c['device_id']==item['camera_id'] and c['end_ms']>item['start_ms'] and c['start_ms']<item['end_ms']]
            intervals=coverage(clips,item['start_ms'],item['end_ms'])
            if not clips or not intervals:
                self.status='No footage for highlight · check selected program camera/recorder'; return False
            if intervals[-1][1]<item['end_ms']-100 and now_ms()<item['end_ms']+18000: return False
            media=self.root/'media'; existing=sum(p.stat().st_size for p in media.glob('*.clip')) if media.exists() else 0
            needed=sum(c['bytes'] for c in clips if not (media/(c['id']+'.clip')).exists())
            if existing+needed>self.config.archive_limit_mb*1024*1024 or len(self.highlights)>=500:
                self.status='Highlight storage full · increase the limit; existing saved clips were not deleted'; return True
            media.mkdir(parents=True,exist_ok=True)
            for clip in clips:
                dest=media/(clip['id']+'.clip')
                if not dest.exists(): await asyncio.to_thread(shutil.copyfile,self.replay.root/(clip['id']+'.clip'),dest)
                clip['url']='/api/live/media/'+clip['id']
            result={**item,'id':uuid.uuid4().hex,'clips':clips,'coverage':intervals,'created_at':time.time(),
                    'partial':sum(b-a for a,b in intervals)<item['end_ms']-item['start_ms']-200}
            self.highlights.append(result)
            await asyncio.to_thread(write_json_atomic,self.index,self.highlights)
            self.status='Highlight saved'+(' · partial footage available' if result['partial'] else '')
            return True

    def router(self):
        router=APIRouter(prefix='/api/live')

        @router.post('/fielding-highlights')
        async def fielding_highlights():
            return await self.play_fielding_highlights()

        @router.get('/state')
        async def state(): return await asyncio.to_thread(self.state)

        @router.get('/settings')
        async def settings(): return self.settings()

        @router.post('/settings')
        async def settings_update(changes:dict):
            try: return await asyncio.to_thread(self.save_settings,changes)
            except ValueError as exc: raise HTTPException(422,str(exc)) from exc

        @router.post('/highlights')
        async def manual(command:SaveHighlight):
            if not self.config.clips_enabled: raise HTTPException(409,'Enable highlight clips first')
            state=self.state()
            if not state['innings']: raise HTTPException(409,'Start an innings first')
            self.schedule('manual:'+uuid.uuid4().hex,state['match_id'],len(state['innings'])-1,time.time(),command.title,'manual')
            return {'pending':True}

        @router.get('/highlights/{identifier}')
        async def highlight(identifier:str):
            if not self.config.clips_enabled: raise HTTPException(403,'Highlight playback is disabled')
            row=next((h for h in self.highlights if h['id']==identifier),None)
            if not row: raise HTTPException(404,'Highlight not found')
            return row

        @router.get('/media/{identifier}')
        async def media(identifier:str):
            if not self.config.clips_enabled: raise HTTPException(403,'Highlight playback is disabled')
            clip=next((c for h in self.highlights for c in h['clips'] if c['id']==identifier),None)
            if not clip: raise HTTPException(404,'Highlight clip not found')
            path=self.root/'media'/(clip['id']+'.clip')
            if not path.is_file(): raise HTTPException(404,'Saved highlight media is missing')
            return FileResponse(path,media_type=clip['mime'],headers={'Cache-Control':'no-store'})

        return router
