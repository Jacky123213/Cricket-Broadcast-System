import copy
import json
import os
import threading
import time
from collections import deque
from pathlib import Path
from .scoreboard_protocol import decode_packet
from .broadcast_graphics import BroadcastGraphics

DEFAULT = dict(team1='HOME', team2='AWAY', color1='#ec218c', color2='#ff922e',
               logo1='', logo2='', runs='', wickets='', overs='',
               batter1_name='', batter2_name='', batter1_runs='', batter2_runs='',
               batter1_balls='', batter2_balls='', striker='none', bowler='',
               bowler_figures='', bowler_overs='', deliveries='', banner='',
               visible=True, source='bluetooth', last_wicket_name='', last_wicket_code='',
               last_wicket_runs='', last_wicket_balls='', last_wicket_bowler='', last_wicket_fielder='')

WICKET_FIELDS = tuple(k for k in DEFAULT if k.startswith('last_wicket_'))


def team_key(name):
    return ' '.join(name.split()).casefold()


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('Expected a JSON object')
    for key, value in data.items():
        if key not in DEFAULT:
            raise ValueError('Unknown field: ' + key)
        if key == 'visible':
            if not isinstance(value, bool): raise ValueError('Visibility must be true/false')
            continue
        if not isinstance(value, str): raise ValueError(key + ' must be text')
        if key.startswith('logo'):
            import base64
            if not value: continue
            if len(value) > 1400000: raise ValueError('Logo exceeds 1 MB')
            head, sep, body = value.partition(',')
            if head not in ('data:image/png;base64','data:image/jpeg;base64') or not sep:
                raise ValueError('Use PNG or JPEG logos')
            try: raw = base64.b64decode(body, validate=True)
            except ValueError: raise ValueError('Invalid logo')
            if not (raw.startswith(b'\x89PNG\r\n\x1a\n') or raw.startswith(b'\xff\xd8\xff')):
                raise ValueError('Invalid logo image')
        elif len(value) > 160:
            raise ValueError(key + ' is too long')
        elif key.startswith('color'):
            import re
            if not re.fullmatch(r'#[0-9a-fA-F]{6}', value): raise ValueError('Invalid colour')
        elif key == 'source' and value not in ('manual','bluetooth'):
            raise ValueError('Invalid source')
        elif key == 'striker' and value not in ('none','1','2'):
            raise ValueError('Invalid striker')


class State:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.data = copy.deepcopy(DEFAULT)
        self.status = 'Bluetooth not started'
        self.last_packet = None
        self.last_score = None
        self.count = 0
        self.logs = deque(maxlen=100)
        self.program_history = deque(maxlen=400)
        self.error = ''
        self.teams = {}
        self.graphics = BroadcastGraphics()
        graphics_path = self.folder / 'broadcast.json'
        if graphics_path.exists():
            try:
                self.graphics = BroadcastGraphics(json.loads(graphics_path.read_text('utf-8')))
            except (ValueError, OSError, TypeError, KeyError) as exc:
                self.error = 'Could not restore broadcast history: ' + str(exc)
        path = self.folder / 'settings.json'
        if path.exists():
            try:
                saved = json.loads(path.read_text('utf-8')); validate(saved)
                self.data.update(saved)
            except (ValueError, OSError) as exc:
                self.error = 'Could not restore settings: ' + str(exc)
        profiles_path = self.folder / 'teams.json'
        if profiles_path.exists():
            try:
                profiles = json.loads(profiles_path.read_text('utf-8'))
                if not isinstance(profiles, list): raise ValueError('Invalid team profiles')
                for profile in profiles:
                    if not isinstance(profile, dict) or not isinstance(profile.get('name'), str):
                        raise ValueError('Invalid team profile')
                    validate({'team1': profile['name'], 'color1': profile['color'], 'logo1': profile['logo']})
                    if team_key(profile['name']): self.teams[team_key(profile['name'])] = profile
            except (ValueError, OSError, KeyError, TypeError) as exc:
                self.error = 'Could not restore team appearance: ' + str(exc)
        # Migrate existing history/settings without changing the user's colours.
        for innings in self.graphics.innings:
            for prefix in ('', 'opposition_'):
                name = innings.get('opposition' if prefix else 'team', '')
                self.teams.setdefault(team_key(name), {'name': name,
                    'color': innings.get(prefix + 'color', DEFAULT['color1']),
                    'logo': innings.get(prefix + 'logo', '')})
        for slot in (1, 2):
            name = self.data[f'team{slot}']
            self.teams.setdefault(team_key(name), {'name': name,
                'color': self.data[f'color{slot}'], 'logo': self.data[f'logo{slot}']})
        self.data = self._team_appearance(self.data, {})
        # Previous-match numbers are never silently restored as current live data.
        if self.data['source'] == 'bluetooth':
            for k in ('runs','wickets','overs','batter1_runs','batter2_runs','batter1_name',
                      'batter2_name','batter1_balls','batter2_balls','bowler','bowler_figures',
                      'bowler_overs','deliveries'): self.data[k] = ''
            self.data['striker'] = 'none'
            for key in WICKET_FIELDS: self.data[key] = ''

    def snapshot(self):
        with self.lock:
            now = time.time()
            self.graphics.flush(now)
            graphics = self.graphics.snapshot(self.data, now)
            self._save_graphics()
            result = dict(score=copy.deepcopy(self.data), status=self.status,
                        last_packet=self.last_packet, last_score=self.last_score,
                        packet_count=self.count, logs=list(self.logs), error=self.error,
                        server_time=now, graphics=graphics,
                        team_appearance=[{'name': p['name'], 'color': p['color']} for p in self.teams.values()])
            # Keep playout history in memory only; never include receiver logs.
            program = {k: result[k] for k in ('score','graphics','last_score','server_time')}
            if not self.program_history or now-self.program_history[-1]['server_time'] >= .1:
                self.program_history.append(copy.deepcopy(program))
            while self.program_history and now-self.program_history[0]['server_time'] > 35:
                self.program_history.popleft()
            return result

    def program_snapshot(self, at):
        with self.lock:
            current = self.snapshot()
            frame = next((item for item in reversed(self.program_history) if item['server_time'] <= at), None)
            if frame: return copy.deepcopy(frame)
            # Do not display present-time scores over footage older than our history.
            current = {k:current[k] for k in ('score','graphics','last_score','server_time')}
            current['score']['visible'] = False
            current['graphics']['active'] = None
            current['graphics']['power_surge'] = False
            return current

    def _team_appearance(self, updated, changes):
        """Resolve role slots from persistent team identities, including split BLE writes."""
        updated = dict(updated)
        for slot in (1, 2):
            name = updated[f'team{slot}']
            key = team_key(name)
            if not key: continue
            profile = copy.deepcopy(self.teams.get(key, {'name': name,
                'color': updated[f'color{slot}'], 'logo': updated[f'logo{slot}']}))
            changed_team = key != team_key(self.data[f'team{slot}'])
            for field in ('color', 'logo'):
                role_field = f'{field}{slot}'
                # Older control pages submit unchanged appearance fields along
                # with a team swap. Those values still belong to the old team.
                stale = changed_team and key in self.teams and changes.get(role_field) == self.data[role_field]
                if role_field in changes and not stale: profile[field] = changes[role_field]
            profile['name'] = name.strip()
            self.teams[key] = profile
            updated[f'color{slot}'], updated[f'logo{slot}'] = profile['color'], profile['logo']
        return updated

    def _persist_settings(self, updated):
        temp = self.folder / 'settings.tmp'
        temp.write_text(json.dumps(updated, ensure_ascii=False), encoding='utf-8')
        os.replace(temp, self.folder / 'settings.json')
        temp = self.folder / 'teams.tmp'
        temp.write_text(json.dumps(list(self.teams.values()), ensure_ascii=False), encoding='utf-8')
        os.replace(temp, self.folder / 'teams.json')

    def flush(self):
        with self.lock:
            self.graphics.flush(time.time(), force=True)
            self._save_graphics()

    def _save_graphics(self):
        if not self.graphics.dirty: return
        try:
            temp = self.folder / 'broadcast.tmp'
            temp.write_text(json.dumps(self.graphics.export(), ensure_ascii=False), encoding='utf-8')
            os.replace(temp, self.folder / 'broadcast.json')
            self.graphics.dirty = False
        except OSError as exc:
            self.error = 'Broadcast history could not be saved: ' + str(exc)

    def broadcast_settings(self, changes):
        with self.lock:
            self.graphics.configure(changes)
            self._save_graphics()

    def broadcast_action(self, command):
        if not isinstance(command, dict): raise ValueError('Expected an action object')
        with self.lock:
            now = time.time()
            if command.get('action') == 'start_chase':
                self.graphics.flush(now, force=True)
                if self.graphics.phase != 'innings_break' or len(self.graphics.innings) != 1:
                    raise ValueError('End the first innings before starting the chase')
                changes = {k: DEFAULT[k] for k in ('batter1_runs','batter2_runs','batter1_name',
                    'batter2_name','batter1_balls','batter2_balls','striker','bowler',
                    'bowler_figures','bowler_overs','deliveries')}
                for prefix in ('team', 'color', 'logo'):
                    changes[prefix+'1'], changes[prefix+'2'] = self.data[prefix+'2'], self.data[prefix+'1']
                changes.update(runs='0', wickets='0', overs='0.0')
                changes.update({key:'' for key in WICKET_FIELDS})
                self.graphics.action(command, {**self.data, **changes}, now)
                self.save(changes)
            else:
                self.graphics.action(command, self.data, now)
            self._save_graphics()

    def broadcast_stats(self, changes):
        if not isinstance(changes, dict): raise ValueError('Expected statistics object')
        with self.lock:
            self.graphics.flush(time.time(), force=True)
            self.graphics.edit_stats(changes)
            self._save_graphics()

    def save(self, changes):
        validate(changes)
        with self.lock:
            updated = self._team_appearance({**self.data, **changes}, changes)
            # Do not carry a previous innings' delta wicket fields into a chase.
            if updated['team1'] != self.data['team1']:
                for key in WICKET_FIELDS:
                    if key not in changes: updated[key] = ''
            self._persist_settings(updated)
            self.data = updated
            self.graphics.queue(self.data, changes, time.time())

    def reset(self):
        self.save({k: DEFAULT[k] for k in ('runs','wickets','overs','batter1_runs','batter2_runs',
                   'batter1_name','batter2_name','batter1_balls','batter2_balls','striker','bowler',
                   'bowler_figures','bowler_overs','deliveries','banner',*WICKET_FIELDS)})
        with self.lock:
            self.last_score = None
            config = copy.deepcopy(self.graphics.config)
            config.update(target=None, result_override='')
            self.graphics = BroadcastGraphics()
            self.graphics.configure(config)
            self._save_graphics()

    def set_status(self, text):
        with self.lock: self.status = text
        print(text, flush=True)

    def receive(self, raw):
        patch = decode_packet(raw)
        now = time.time()
        item = dict(at=now, text=raw.decode('utf-8', errors='replace'), hex=raw.hex(), fields=patch)
        with self.lock:
            self.count += 1; self.last_packet = now; self.logs.append(item)
            if patch and self.data['source'] == 'bluetooth':
                changes = dict(patch)
                off = changes.pop('_strike_off', None)
                if off == self.data['striker']: changes['striker'] = 'none'
                if 'team1' in changes and changes['team1'] != self.data['team1']:
                    changes.update({key:'' for key in WICKET_FIELDS})
                self.data = self._team_appearance({**self.data, **changes}, changes)
                if any(k in changes for k in ('team1', 'team2')):
                    try: self._persist_settings(self.data)
                    except OSError as exc: self.error = 'Team appearance could not be saved: ' + str(exc)
                self.graphics.queue(self.data, changes, now)
                # Only total/overs refresh score age, not a name-only packet.
                if any(k in patch for k in ('runs','wickets','overs')): self.last_score = now
            try:
                path = self.folder / 'packets.jsonl'
                if path.exists() and path.stat().st_size > 2_000_000:
                    os.replace(path, self.folder / 'packets.previous.jsonl')
                with path.open('a', encoding='utf-8') as f:
                    f.write(json.dumps(item, ensure_ascii=False) + '\n')
            except OSError as exc:
                self.error = 'Packet log could not be saved: ' + str(exc)
