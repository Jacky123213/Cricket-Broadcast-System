"""Preset card content. Uploaded artwork stays in saved data, never in the app."""
import base64
import copy
import hashlib
import json
import re
import threading

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .install_support import write_json_atomic


def key(name):
    return ' '.join(name.split()).casefold()


class Player(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    name: str = Field(min_length=1, max_length=80)
    player_id: str = Field(default='', pattern=r'^(?:[a-f0-9]{32})?$')
    role: str = Field(default='batter', pattern=r'^(batter|bowler|allrounder|keeper)$')
    captain: bool = False
    photo: str = Field(default='', max_length=120)
    age: str = Field(default='', max_length=12)
    matches: str = Field(default='', max_length=16)
    runs: str = Field(default='', max_length=16)
    wickets: str = Field(default='', max_length=16)
    average: str = Field(default='', max_length=16)
    strike_rate: str = Field(default='', max_length=16)
    economy: str = Field(default='', max_length=16)
    best: str = Field(default='', max_length=24)


class TeamProfile(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    team: str = Field(min_length=1, max_length=160)
    featured: str = Field(default='', max_length=80)
    players: list[Player] = Field(default_factory=list, max_length=24)


class Details(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    career_label: str = Field(default='ODI CAREER', max_length=60)
    coming_title: str = Field(default='', max_length=160)
    coming_subtitle: str = Field(default='', max_length=160)
    coming_image: str = Field(default='', max_length=120)
    toss_team: str = Field(default='', max_length=160)
    toss_choice: str = Field(default='bat', pattern=r'^(bat|field)$')
    sponsor_name: str = Field(default='', max_length=100)
    sponsor_image: str = Field(default='', max_length=120)
    sponsor_caption: str = Field(default='', max_length=160)


class MatchLineup(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    match_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    team: str = Field(min_length=1, max_length=160)
    players: list[str] = Field(max_length=24)


class GraphicsPacks:
    def __init__(self, folder):
        self.folder = folder
        self.path = folder/'graphics-packs.json'
        self.lock = threading.RLock()
        self.validate_players = None
        self.data = {'details': Details().model_dump(), 'teams': [], 'lineups': []}
        if self.path.exists():
            saved = json.loads(self.path.read_text('utf-8'))
            self.data = {'details': Details.model_validate(saved['details']).model_dump(),
                         'teams': [TeamProfile.model_validate(t).model_dump() for t in saved['teams']],
                         'lineups': [MatchLineup.model_validate(t).model_dump() for t in saved.get('lineups', [])]}

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.data)

    def asset_valid(self, path):
        return not path or bool(re.fullmatch(r'/api/graphics-packs/media/[a-f0-9]{64}\.(?:png|jpg)', path)
                                and (self.folder/'graphics-media'/path.rsplit('/', 1)[-1]).is_file())

    def save(self, changes):
        with self.lock:
            updated = self.snapshot()
            if set(changes)-{'details', 'team', 'lineup'}:
                raise ValueError('Unknown preset content setting')
            if 'details' in changes:
                if not isinstance(changes['details'], dict):
                    raise ValueError('Expected card detail fields')
                updated['details'] = Details.model_validate({**updated['details'], **changes['details']}).model_dump()
                if any(not self.asset_valid(updated['details'][f]) for f in ('coming_image','sponsor_image')):
                    raise ValueError('Upload artwork to this studio first')
            if 'team' in changes:
                team = TeamProfile.model_validate(changes['team']).model_dump()
                if len({key(p['name']) for p in team['players']})!=len(team['players']):
                    raise ValueError('Each lineup player needs a different name')
                identities = [p['player_id'] for p in team['players'] if p['player_id']]
                if len(identities) != len(set(identities)):
                    raise ValueError('A saved player can appear only once in a team roster')
                if self.validate_players:
                    self.validate_players(team)
                if team['featured'] and team['featured'] not in {p['name'] for p in team['players']}:
                    raise ValueError('Choose the featured player from this lineup')
                if any(not self.asset_valid(p['photo']) for p in team['players']):
                    raise ValueError('Upload player portraits to this studio first')
                updated['teams'] = [t for t in updated['teams'] if key(t['team'])!=key(team['team'])]+[team]
                if len(updated['teams'])>100:
                    raise ValueError('At most 100 team lineups can be saved')
                valid_names = {p['name'] for p in team['players']}
                for lineup in updated['lineups']:
                    if key(lineup['team']) == key(team['team']):
                        lineup['players'] = [name for name in lineup['players'] if name in valid_names]
            if 'lineup' in changes:
                lineup = MatchLineup.model_validate(changes['lineup']).model_dump()
                team = next((t for t in updated['teams'] if key(t['team']) == key(lineup['team'])), None)
                if not team or len(set(lineup['players'])) != len(lineup['players']) or not set(lineup['players']) <= {p['name'] for p in team['players']}:
                    raise ValueError('Select different players from the saved team roster')
                # Keep only this match's selections; old match history does not need roster drafts.
                updated['lineups'] = [t for t in updated['lineups'] if t['match_id'] == lineup['match_id'] and key(t['team']) != key(lineup['team'])]+[lineup]
            write_json_atomic(self.path, updated)
            self.data = updated
            return self.snapshot()

    def upload(self, content):
        if not isinstance(content, str) or len(content)>1_400_000:
            raise ValueError('Choose a PNG or JPEG smaller than 1 MB')
        header, sep, encoded = content.partition(',')
        if not sep or header not in ('data:image/png;base64','data:image/jpeg;base64'):
            raise ValueError('Choose a PNG or JPEG')
        raw = base64.b64decode(encoded, validate=True)
        if not 0<len(raw)<=1_000_000 or not (raw.startswith(b'\x89PNG\r\n\x1a\n') if 'png' in header else raw.startswith(b'\xff\xd8\xff')):
            raise ValueError('Invalid PNG/JPEG artwork')
        extension = '.png' if 'png' in header else '.jpg'
        name = hashlib.sha256(raw).hexdigest()+extension
        target = self.folder/'graphics-media'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        return '/api/graphics-packs/media/'+name

    def router(self):
        router = APIRouter(prefix='/api/graphics-packs')

        @router.get('')
        def get():
            return self.snapshot()

        @router.post('')
        def save(changes: dict):
            try:
                return self.save(changes)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc

        @router.post('/artwork')
        def artwork(body: dict):
            try:
                return {'url': self.upload(body.get('image'))}
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc

        @router.get('/media/{name}')
        def media(name: str):
            if not self.asset_valid('/api/graphics-packs/media/'+name):
                raise HTTPException(404, 'Artwork not found')
            return FileResponse(self.folder/'graphics-media'/name,
                                media_type='image/png' if name.endswith('.png') else 'image/jpeg')

        return router
