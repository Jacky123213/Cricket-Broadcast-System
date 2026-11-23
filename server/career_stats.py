"""Confirmed match results and stable player identities in the existing saved SQLite DB."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from .broadcast_graphics import balls, overs


def key(value):
    return ' '.join(value.split()).casefold()


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def stamp():
    return datetime.now(timezone.utc).isoformat()


class Conflict(ValueError):
    pass


class Mapping(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    key: str = Field(min_length=1, max_length=64)
    player_id: str = Field(default='', pattern=r'^(?:[a-f0-9]{32})?$')
    name: str = Field(default='', max_length=160)
    same_as: str = Field(default='', max_length=64)


class Submission(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    match_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    revision: str = Field(pattern=r'^[a-f0-9]{64}$')
    players: list[Mapping] = Field(max_length=128)
    outcome: Literal['win', 'tie', 'no_result']
    winner: str = Field(default='', max_length=160)
    replace: bool = False
    previous_version: int | None = Field(default=None, ge=1)
    accept_missing: bool = False


class PlayerOption(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    universal: bool


SCHEMA = '''
CREATE TABLE IF NOT EXISTS career_players(id TEXT PRIMARY KEY,name TEXT NOT NULL,name_key TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS career_teams(id TEXT PRIMARY KEY,name TEXT NOT NULL,name_key TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS career_aliases(team_id TEXT NOT NULL,alias TEXT NOT NULL,player_id TEXT NOT NULL,
 PRIMARY KEY(team_id,alias,player_id));
CREATE TABLE IF NOT EXISTS career_drafts(id TEXT PRIMARY KEY,revision TEXT NOT NULL,snapshot TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS career_matches(id TEXT PRIMARY KEY,revision TEXT NOT NULL,version INTEGER NOT NULL,
 status TEXT NOT NULL,submission_key TEXT NOT NULL,outcome TEXT NOT NULL,winner TEXT NOT NULL,
 snapshot TEXT NOT NULL,submitted_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS career_entries(match_id TEXT NOT NULL,player_id TEXT NOT NULL,team_id TEXT NOT NULL,
 performance TEXT NOT NULL,PRIMARY KEY(match_id,player_id),
 FOREIGN KEY(match_id) REFERENCES career_matches(id),FOREIGN KEY(player_id) REFERENCES career_players(id));
CREATE INDEX IF NOT EXISTS career_entries_player ON career_entries(player_id);
CREATE INDEX IF NOT EXISTS career_aliases_name ON career_aliases(alias);
'''

PLAYER_OPTIONS_SCHEMA = '''
CREATE TABLE IF NOT EXISTS career_player_options(player_id TEXT PRIMARY KEY,
 universal INTEGER NOT NULL DEFAULT 0 CHECK(universal IN (0,1)),
 FOREIGN KEY(player_id) REFERENCES career_players(id));
'''


class CareerStats:
    def __init__(self, path, scoreboard, live):
        self.path, self.scoreboard, self.live = path, scoreboard, live
        self.lock = threading.RLock()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            # Separate metadata keeps the original player table compatible with
            # earlier app versions and leaves saved IDs and results untouched.
            db.executescript(SCHEMA + PLAYER_OPTIONS_SCHEMA)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def capture(self):
        with self.scoreboard.lock:
            g = self.scoreboard.graphics
            if g.phase != 'complete':
                return None
            g.flush(time.time(), force=True)
            config = self.live.config
            presentation = self.scoreboard.packs.snapshot()
            snapshot = {'match_id': g.match_id, 'title': g.config['match_title'], 'venue': g.config['venue'],
                    'format': config.format, 'competition': config.competition, 'date': config.match_date,
                    'finished_at': g.finished_at, 'total_overs': g.config['total_overs'], 'result': g.result(),
                    'innings': [g.stats(i, include_history=True) for i in g.innings],
                    'lineups': [r for r in presentation['lineups'] if r['match_id'] == g.match_id]}
            teams = {key(i[field]) for i in snapshot['innings'] for field in ('team','opposition')}
            links = [{'team':t['team'],'name':p['name'],'player_id':p['player_id']}
                     for t in presentation['teams'] if key(t['team']) in teams
                     for p in t['players'] if p.get('player_id')]
            if links: snapshot['player_links'] = links
            return snapshot

    def stage_current(self):
        snapshot = self.capture()
        if snapshot is None:
            return
        revision = digest(snapshot)
        with self.lock, self.connect() as db:
            db.execute('''INSERT INTO career_drafts VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                revision=excluded.revision,snapshot=excluded.snapshot,updated_at=excluded.updated_at
                WHERE career_drafts.revision<>excluded.revision''',
                       (snapshot['match_id'], revision, encoded(snapshot), stamp()))

    @staticmethod
    def participants(snapshot):
        teams = []
        for innings in snapshot['innings']:
            for name in (innings['team'], innings['opposition']):
                if key(name) and not any(key(t) == key(name) for t in teams):
                    teams.append(name)
        if len(teams) != 2:
            raise ValueError('The scorecards need two distinct, consistent team names before submission')
        people = {}
        def person(team, name):
            team = next(t for t in teams if key(t)==key(team))
            if not name.strip():
                raise ValueError('A recorded player has no name; correct the scorecard before submitting')
            identity = hashlib.sha256((key(team)+'\x1f'+key(name)).encode()).hexdigest()[:24]
            return people.setdefault(identity, {'key': identity, 'team': team, 'name': name,
                                                'batting': [], 'bowling': [], 'selected': False})
        for index, innings in enumerate(snapshot['innings']):
            for row in innings['batters']:
                dismissal = row.get('dismissal', '').strip()
                if key(dismissal) in ('dnb', 'did not bat', 'yet to bat'):
                    person(innings['team'], row['name'])['selected'] = True
                    continue
                not_out = key(dismissal) in ('not out', 'retired hurt', 'retired not out', 'absent hurt')
                out = False if not_out or row.get('active') else True if dismissal or row.get('out_number') else None
                person(innings['team'], row['name'])['batting'].append({
                    'innings': index, 'runs': row.get('runs'), 'balls': row.get('balls'),
                    'fours': row.get('fours'), 'sixes': row.get('sixes'), 'dismissal': dismissal, 'out': out})
            for row in innings['bowlers']:
                person(innings['opposition'], row['name'])['bowling'].append({
                    'innings': index, 'wickets': row.get('wickets'), 'runs': row.get('runs'),
                    'balls': balls(row.get('overs', '')), 'maidens': row.get('maidens')})
        for lineup in snapshot['lineups']:
            if any(key(t) == key(lineup['team']) for t in teams):
                for name in lineup['players']:
                    person(lineup['team'], name)['selected'] = True
        warnings = []
        for team in teams:
            if not any(key(r['team']) == key(team) for r in snapshot['lineups']):
                warnings.append(team+': no playing lineup saved; only observed players are counted.')
        for p in people.values():
            if any(any(r.get(f) is None for f in ('runs', 'balls', 'out')) for r in p['batting']):
                warnings.append(p['name']+': incomplete batting figures or dismissal status.')
            if any(any(r.get(f) is None for f in ('wickets', 'runs', 'balls')) for r in p['bowling']):
                warnings.append(p['name']+': incomplete bowling figures.')
        return teams, list(people.values()), warnings

    @staticmethod
    def _team(db, name):
        row = db.execute('SELECT id FROM career_teams WHERE name_key=?', (key(name),)).fetchone()
        if row:
            return row['id']
        identity = uuid.uuid4().hex
        db.execute('INSERT INTO career_teams VALUES(?,?,?)', (identity, name.strip(), key(name)))
        return identity

    def register(self, name, team='', universal=False):
        if not isinstance(name, str) or not name.strip() or len(name) > 160 or not isinstance(team, str) or len(team) > 160:
            raise ValueError('Enter a player name and optional team, up to 160 characters')
        if type(universal) is not bool:
            raise ValueError('Universal player must be true or false')
        with self.lock, self.connect() as db:
            identity = uuid.uuid4().hex
            db.execute('INSERT INTO career_players(id,name,name_key,created_at) VALUES(?,?,?,?)',
                       (identity, name.strip(), key(name), stamp()))
            db.execute('INSERT INTO career_player_options VALUES(?,?)', (identity,int(universal)))
            if team.strip():
                db.execute('INSERT INTO career_aliases VALUES(?,?,?)', (self._team(db, team), key(name), identity))
            return {'id': identity, 'name': name.strip(), 'universal': universal}

    def set_universal(self, identity, universal):
        if type(universal) is not bool: raise ValueError('Universal player must be true or false')
        # Match the roster-save lock order, so a concurrent second-team link
        # cannot race with disabling this option.
        with self.scoreboard.packs.lock:
            profiles = self.scoreboard.packs.snapshot()['teams']
            memberships = {key(t['team']) for t in profiles for p in t['players'] if p.get('player_id')==identity}
            with self.lock, self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT id,name FROM career_players WHERE id=?', (identity,)).fetchone()
                if not row: raise KeyError(identity)
                if not universal:
                    if len(memberships)>1:
                        raise Conflict('This player is linked to several rosters. Remove the other roster links before turning off Universal player.')
                    saved = db.execute("SELECT e.performance FROM career_entries e JOIN career_matches m ON m.id=e.match_id WHERE e.player_id=? AND m.status='accepted'", (identity,)).fetchall()
                    if any(len(json.loads(r['performance']).get('teams', []))>1 for r in saved):
                        raise Conflict('This player represents both teams in a submitted match. Keep Universal player enabled for that record.')
                db.execute('''INSERT INTO career_player_options VALUES(?,?) ON CONFLICT(player_id)
                    DO UPDATE SET universal=excluded.universal''', (identity,int(universal)))
        return {'id':identity, 'name':row['name'], 'universal':universal}

    def validate_roster(self, team):
        profiles = self.scoreboard.packs.snapshot()['teams']
        with self.connect() as db:
            for p in team['players']:
                identity = p.get('player_id')
                if not identity: continue
                saved = db.execute('''SELECT coalesce(o.universal,0) AS universal FROM career_players p
                    LEFT JOIN career_player_options o ON o.player_id=p.id WHERE p.id=?''', (identity,)).fetchone()
                if not saved: raise ValueError('Choose an existing saved player record for '+p['name'])
                other_team = any(key(t['team'])!=key(team['team']) and any(q.get('player_id')==identity for q in t['players']) for t in profiles)
                if other_team and not saved['universal']:
                    raise ValueError(p['name']+' is already linked to another team. Enable Universal player in Statistics first.')

    def status(self):
        self.stage_current()
        with self.scoreboard.lock:
            match_id, phase = self.scoreboard.graphics.match_id, self.scoreboard.graphics.phase
        with self.connect() as db:
            saved = db.execute('SELECT revision,version,status FROM career_matches WHERE id=?', (match_id,)).fetchone()
            draft = db.execute('SELECT revision FROM career_drafts WHERE id=?', (match_id,)).fetchone()
            pending = db.execute("SELECT count(*) FROM career_drafts d LEFT JOIN career_matches m ON d.id=m.id WHERE m.id IS NULL OR m.status<>'accepted' OR m.revision<>d.revision").fetchone()[0]
        return {'match_id': match_id, 'phase': phase, 'saved': dict(saved) if saved else None,
                'revision': draft['revision'] if draft else None, 'pending': pending,
                'needs_review': phase == 'complete' and draft is not None and (not saved or saved['status'] != 'accepted' or saved['revision'] != draft['revision'])}

    def review(self, match_id=None):
        self.stage_current()
        if match_id is None:
            with self.scoreboard.lock:
                match_id = self.scoreboard.graphics.match_id
        with self.connect() as db:
            draft = db.execute('SELECT * FROM career_drafts WHERE id=?', (match_id,)).fetchone()
            if not draft:
                raise ValueError('Finish a match before submitting its results')
            snapshot = json.loads(draft['snapshot'])
            teams, people, warnings = self.participants(snapshot)
            directory = [{**dict(r),'universal':bool(r['universal'])} for r in db.execute('''SELECT p.id,p.name,p.name_key,
                coalesce(o.universal,0) AS universal FROM career_players p LEFT JOIN career_player_options o ON o.player_id=p.id
                ORDER BY p.name COLLATE NOCASE''')]
            by_id = {p['id']:p for p in directory}
            links = snapshot.get('player_links', [])
            saved = db.execute('SELECT version,status,revision,outcome,winner FROM career_matches WHERE id=?', (match_id,)).fetchone()
            for p in people:
                team_ids = db.execute('SELECT id FROM career_teams WHERE name_key=?', (key(p['team']),)).fetchall()
                local = [r['player_id'] for r in db.execute('SELECT a.player_id FROM career_aliases a WHERE a.team_id=? AND a.alias=?', (team_ids[0]['id'], key(p['name'])))] if team_ids else []
                global_ids = [r['id'] for r in directory if r['name_key'] == key(p['name'])]
                roster = list({r['player_id'] for r in links if key(r['team'])==key(p['team']) and key(r['name'])==key(p['name'])})
                candidates = roster or local or global_ids
                p['suggested_id'] = candidates[0] if len(candidates) == 1 else ''
                p['linked'] = bool(roster or local)
                p['ambiguous'] = len(candidates) > 1 or bool(roster and roster[0] not in by_id)
                if p['ambiguous']: p['suggested_id'] = ''
                p['universal'] = bool(by_id.get(p['suggested_id'],{}).get('universal'))
            # Shared IDs on both sides need explicit roster links/previous mapping
            # and the universal option. A matching name alone is not proof.
            for p in people:
                opponents = [q for q in people if key(q['name'])==key(p['name']) and key(q['team'])!=key(p['team'])]
                if opponents and (not p['linked'] or any(p['suggested_id'] and q['suggested_id']==p['suggested_id'] and not p['universal'] for q in opponents)):
                    p['suggested_id'] = ''; p['ambiguous'] = True
        outcome, winner = ('tie', '') if snapshot['result'] == 'Match tied' else ('', '')
        if key(snapshot['result']) in ('no result','abandoned','match abandoned'):
            outcome = 'no_result'
        for team in teams:
            if snapshot['result'].startswith(team+' wins by '):
                outcome, winner = 'win', team
        if saved:
            outcome, winner = saved['outcome'], saved['winner']
        return {'match_id': match_id, 'revision': draft['revision'], 'snapshot': snapshot, 'teams': teams,
                'players': people, 'directory': directory, 'warnings': warnings, 'saved': dict(saved) if saved else None,
                'outcome': outcome, 'winner': winner}

    def submit(self, request: Submission):
        self.stage_current()
        with self.scoreboard.lock:
            current = self.scoreboard.graphics
            if request.match_id == current.match_id and current.phase != 'complete':
                raise Conflict('This match has been reopened. Finish it before submitting results.')
        request_key = digest(request.model_dump())
        with self.lock, self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            draft = db.execute('SELECT * FROM career_drafts WHERE id=?', (request.match_id,)).fetchone()
            if not draft or draft['revision'] != request.revision:
                raise Conflict('The result changed. Reload the review before submitting.')
            saved = db.execute('SELECT * FROM career_matches WHERE id=?', (request.match_id,)).fetchone()
            if saved and saved['status'] == 'accepted' and saved['submission_key'] == request_key:
                return {'ok': True, 'already_submitted': True, 'match_id': request.match_id, 'version': saved['version']}
            if saved and saved['status'] == 'accepted' and not request.replace:
                raise Conflict('This match is already submitted. Review it and choose Replace submitted result.')
            if saved and request.previous_version != saved['version']:
                raise Conflict('Another operator changed this saved result. Reload the review.')
            snapshot = json.loads(draft['snapshot'])
            teams, people, warnings = self.participants(snapshot)
            if warnings and not request.accept_missing:
                raise ValueError('Review the missing-data warnings and confirm that incomplete statistics may be saved')
            if request.outcome == 'win' and request.winner not in teams:
                raise ValueError('Choose the winning team')
            if request.outcome != 'win' and request.winner:
                raise ValueError('Clear the winner for a tie or no result')
            mapping = {m.key: m for m in request.players}
            if len(mapping) != len(request.players) or set(mapping) != {p['key'] for p in people}:
                raise ValueError('Map every recorded player once before submitting')
            team_ids = {name: self._team(db, name) for name in teams}
            resolved, merged = {}, {}
            def resolve(identity, chain=()):
                if identity in resolved:
                    return resolved[identity]
                if identity in chain or identity not in mapping:
                    raise ValueError('Player links contain a loop or an unknown player')
                m = mapping[identity]
                p = next(p for p in people if p['key'] == identity)
                if m.same_as:
                    if m.player_id:
                        raise ValueError('Choose a saved player or a same-player link')
                    value = resolve(m.same_as, chain+(identity,))
                elif m.player_id:
                    if not db.execute('SELECT id FROM career_players WHERE id=?', (m.player_id,)).fetchone():
                        raise ValueError('A chosen player no longer exists')
                    value = m.player_id
                else:
                    name = (m.name or p['name']).strip()
                    if not name:
                        raise ValueError('Enter the new player name')
                    value = uuid.uuid4().hex
                    db.execute('INSERT INTO career_players(id,name,name_key,created_at) VALUES(?,?,?,?)', (value, name, key(name), stamp()))
                resolved[identity] = value
                return value
            for p in people:
                identity = resolve(p['key'])
                target = merged.setdefault(identity, {'team': p['team'], 'teams': [], 'batting': [], 'bowling': []})
                if key(target['team']) != key(p['team']):
                    option = db.execute('SELECT universal FROM career_player_options WHERE player_id=?', (identity,)).fetchone()
                    universal = bool(option and option['universal'])
                    if not universal:
                        raise ValueError('Two opposing players cannot use the same player record unless Universal player is enabled')
                if p['team'] not in target['teams']: target['teams'].append(p['team'])
                for kind in ('batting', 'bowling'):
                    if {r['innings'] for r in target[kind]} & {r['innings'] for r in p[kind]}:
                        raise ValueError('Two '+kind+' rows use the same player in one innings. Correct their names or mapping.')
                    target[kind].extend({**r,'team':p['team']} for r in p[kind])
                db.execute('INSERT OR IGNORE INTO career_aliases VALUES(?,?,?)', (team_ids[p['team']], key(p['name']), identity))
            version = saved['version']+1 if saved else 1
            now = stamp()
            db.execute('''INSERT INTO career_matches VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                revision=excluded.revision,version=excluded.version,status=excluded.status,submission_key=excluded.submission_key,
                outcome=excluded.outcome,winner=excluded.winner,snapshot=excluded.snapshot,updated_at=excluded.updated_at''',
                (request.match_id, request.revision, version, 'accepted', request_key, request.outcome, request.winner,
                 encoded(snapshot), saved['submitted_at'] if saved else now, now))
            db.execute('DELETE FROM career_entries WHERE match_id=?', (request.match_id,))
            for identity, performance in merged.items():
                db.execute('INSERT INTO career_entries VALUES(?,?,?,?)', (request.match_id, identity, team_ids[performance['team']], encoded(performance)))
            return {'ok': True, 'already_submitted': False, 'match_id': request.match_id, 'version': version}

    def withdraw(self, match_id, version):
        with self.lock, self.connect() as db:
            row = db.execute('SELECT version,status FROM career_matches WHERE id=?', (match_id,)).fetchone()
            if not row or row['version'] != version:
                raise Conflict('The saved result changed. Refresh before withdrawing it.')
            db.execute("UPDATE career_matches SET status='withdrawn',version=version+1,updated_at=? WHERE id=?", (stamp(), match_id))
        return {'ok': True}

    @staticmethod
    def totals(performances):
        batting = [r for p in performances for r in p['batting']]
        bowling = [r for p in performances for r in p['bowling']]
        missing = {}
        def total(rows, field, label):
            known = [r[field] for r in rows if r.get(field) is not None]
            missing[label] = len(rows)-len(known)
            return sum(known) if known or not rows else None
        runs = total(batting, 'runs', 'batting_runs'); faced = total(batting, 'balls', 'batting_balls')
        fours = total(batting, 'fours', 'fours'); sixes = total(batting, 'sixes', 'sixes')
        wickets = total(bowling, 'wickets', 'bowling_wickets'); conceded = total(bowling, 'runs', 'bowling_runs')
        bowled = total(bowling, 'balls', 'bowling_balls'); maidens = total(bowling, 'maidens', 'maidens')
        outs = sum(r.get('out') is True for r in batting)
        missing['dismissals'] = sum(r.get('out') is None for r in batting)
        high = max((r for r in batting if r.get('runs') is not None), key=lambda r:(r['runs'],r.get('out') is False), default=None)
        best = max((r for r in bowling if r.get('wickets') is not None and r.get('runs') is not None), key=lambda r:(r['wickets'],-r['runs']), default=None)
        return {'matches': len(performances), 'innings': len(batting), 'runs': runs, 'balls': faced,
                'outs': outs, 'not_outs': sum(r.get('out') is False for r in batting), 'fours': fours, 'sixes': sixes,
                'highest': None if high is None else str(high['runs'])+('*' if high.get('out') is False else ''),
                'average': round(runs/outs,2) if outs and runs is not None and not missing['batting_runs'] and not missing['dismissals'] else None,
                'strike_rate': round(runs*100/faced,2) if faced and runs is not None and not missing['batting_runs'] and not missing['batting_balls'] else None,
                'fifties': sum(50 <= r['runs'] < 100 for r in batting if r.get('runs') is not None),
                'hundreds': sum(r['runs'] >= 100 for r in batting if r.get('runs') is not None),
                'wickets': wickets, 'conceded': conceded, 'bowling_balls': bowled, 'overs': overs(bowled), 'maidens': maidens,
                'economy': round(conceded*6/bowled,2) if bowled and conceded is not None and not missing['bowling_runs'] and not missing['bowling_balls'] else None,
                'bowling_average': round(conceded/wickets,2) if wickets and conceded is not None and not missing['bowling_runs'] and not missing['bowling_wickets'] else None,
                'best': None if best is None else str(best['wickets'])+'–'+str(best['runs']), 'missing': missing}

    def directory(self):
        profiles = self.scoreboard.packs.snapshot()['teams']
        with self.connect() as db:
            players = [{**dict(r),'universal':bool(r['universal'])} for r in db.execute('''SELECT p.id,p.name,
                coalesce(o.universal,0) AS universal FROM career_players p LEFT JOIN career_player_options o ON o.player_id=p.id
                ORDER BY p.name COLLATE NOCASE''')]
            entries = db.execute("SELECT e.*,t.name AS team FROM career_entries e JOIN career_matches m ON e.match_id=m.id JOIN career_teams t ON t.id=e.team_id WHERE m.status='accepted'").fetchall()
            teams = [dict(r) for r in db.execute('SELECT id,name FROM career_teams ORDER BY name COLLATE NOCASE')]
            matches = db.execute("SELECT * FROM career_matches WHERE status='accepted' ORDER BY submitted_at DESC").fetchall()
        for p in players:
            own = [r for r in entries if r['player_id'] == p['id']]
            performances = [json.loads(r['performance']) for r in own]
            p.update(self.totals(performances))
            played = {team for r in performances for team in r.get('teams', [r['team']])}
            p['roster_teams'] = sorted({t['team'] for t in profiles if any(q.get('player_id')==p['id'] for q in t['players'])})
            p['teams'] = sorted(played | set(p['roster_teams']))
        for team in teams:
            team.update(matches=0,wins=0,losses=0,ties=0,no_results=0,runs_for=0,runs_against=0,missing_innings=0)
            for row in matches:
                snapshot = json.loads(row['snapshot'])
                names = {key(i[field]) for i in snapshot['innings'] for field in ('team','opposition')}
                if key(team['name']) not in names: continue
                team['matches'] += 1
                team['ties' if row['outcome']=='tie' else 'no_results' if row['outcome']=='no_result' else 'wins' if key(row['winner'])==key(team['name']) else 'losses'] += 1
                for i in snapshot['innings']:
                    if i['runs'] is not None:
                        team['runs_for' if key(i['team'])==key(team['name']) else 'runs_against'] += i['runs']
                    else: team['missing_innings'] += 1
        history = [{'id':r['id'],'version':r['version'],'submitted_at':r['submitted_at'],'outcome':r['outcome'],'winner':r['winner'],
                    'title':json.loads(r['snapshot'])['title'],'date':json.loads(r['snapshot'])['date'],
                    'result': r['winner']+' won' if r['outcome']=='win' else 'Match tied' if r['outcome']=='tie' else 'No result'} for r in matches]
        return {'players':players,'teams':teams,'matches':history}

    def archive(self):
        with self.connect() as db:
            rows = db.execute('''SELECT d.id,d.snapshot,d.revision,m.status,m.version,m.revision AS submitted_revision
                FROM career_drafts d LEFT JOIN career_matches m ON m.id=d.id ORDER BY d.updated_at DESC''').fetchall()
        return [{'id':r['id'],'title':json.loads(r['snapshot'])['title'],'result':json.loads(r['snapshot'])['result'],
                 'date':json.loads(r['snapshot'])['date'],'status':r['status'] or 'pending','version':r['version'],
                 'changed':r['submitted_revision']!=r['revision']} for r in rows]

    def player(self, identity):
        profile = next((p for p in self.directory()['players'] if p['id']==identity), None)
        if profile is None: raise KeyError(identity)
        with self.connect() as db:
            rows = db.execute("""SELECT e.performance,m.id,m.snapshot,m.submitted_at FROM career_entries e
                JOIN career_matches m ON e.match_id=m.id WHERE e.player_id=? AND m.status='accepted'
                ORDER BY m.submitted_at DESC""", (identity,)).fetchall()
        return {'player':profile, 'performances':[{'match_id':r['id'], 'title':json.loads(r['snapshot'])['title'],
                'date':json.loads(r['snapshot'])['date'], **json.loads(r['performance'])} for r in rows]}

    def match(self, match_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM career_matches WHERE id=? AND status='accepted'", (match_id,)).fetchone()
            if not row: raise KeyError(match_id)
            entries = db.execute('SELECT e.*,p.name FROM career_entries e JOIN career_players p ON p.id=e.player_id WHERE match_id=?', (match_id,)).fetchall()
        return {'id':match_id,'version':row['version'],'outcome':row['outcome'],'winner':row['winner'],
                'snapshot':json.loads(row['snapshot']), 'players':[{'id':r['player_id'],'name':r['name'],**json.loads(r['performance'])} for r in entries]}

    def router(self):
        router = APIRouter(prefix='/api/statistics')
        def call(fn,*args):
            try: return fn(*args)
            except Conflict as exc: raise HTTPException(409,str(exc)) from exc
            except ValueError as exc: raise HTTPException(400,str(exc)) from exc
            except KeyError as exc: raise HTTPException(404,'Saved result not found') from exc
            except (OSError, sqlite3.Error) as exc:
                raise HTTPException(503,'Statistics could not be saved or read. Check the Studio data folder and retry.') from exc
        @router.get('/status')
        def status(): return call(self.status)
        @router.get('/review')
        def review(match_id: str | None=None): return call(self.review,match_id)
        @router.get('/archive')
        def archive(): return call(self.archive)
        @router.post('/submit')
        def submit(body:Submission): return call(self.submit,body)
        @router.post('/players')
        def register(body:dict): return call(self.register,body.get('name'),body.get('team',''),body.get('universal',False))
        @router.post('/players/{identity}/options')
        def player_options(identity:str, body:PlayerOption): return call(self.set_universal,identity,body.universal)
        @router.post('/withdraw')
        def withdraw(body:dict):
            if set(body)!={'match_id','version'} or type(body['version']) is not int: raise HTTPException(400,'Choose a saved result version')
            return call(self.withdraw,body['match_id'],body['version'])
        @router.get('')
        def directory(): return call(self.directory)
        @router.get('/players/{identity}')
        def player(identity:str): return call(self.player,identity)
        @router.get('/matches/{match_id}')
        def match(match_id:str): return call(self.match,match_id)
        return router
