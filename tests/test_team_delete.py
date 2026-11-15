import copy
import json

from fastapi.testclient import TestClient

from server.config import Settings
from server.main import create_app
from server.broadcast_graphics import new_innings
from server.scoreboard_state import State


def prepared(tmp_path):
    app = create_app(Settings(data_root=tmp_path))
    s = app.state.scoreboard
    s.save({'source': 'manual', 'runs': '94', 'wickets': '4', 'overs': '14.1'})
    s.flush()
    for name in ('Practice / Reserve', 'Keep'):
        s.save_team({'name': name, 'color': '#235d41', 'logo': ''})
        s.packs.save({'team': {'team': name, 'players': [{'name': 'Captain', 'captain': True}]}})
        s.packs.save({'lineup': {'team': name, 'match_id': s.graphics.match_id, 'players': ['Captain']}})
    return TestClient(app), s


def remove(c, name):
    return c.request('DELETE', '/api/teams', json={'name': name})


def test_delete_team_removes_library_roster_and_selections_and_survives_restart(tmp_path):
    c, s = prepared(tmp_path)
    s.packs.save({'details': {'toss_team': 'Practice / Reserve', 'sponsor_name': 'Local Club'}})
    before = copy.deepcopy(s.data)
    innings = s.graphics.export()
    settings_bytes = (s.folder/'settings.json').read_bytes()
    result = remove(c, ' practice  / reserve ')
    assert result.status_code == 200
    assert all(t['name'] != 'Practice / Reserve' for t in result.json())
    content = s.packs.snapshot()
    assert [t['team'] for t in content['teams']] == ['Keep']
    assert [t['team'] for t in content['lineups']] == ['Keep']
    assert content['details']['toss_team'] == ''
    assert content['details']['sponsor_name'] == 'Local Club'
    assert s.data == before and s.graphics.export() == innings
    assert (s.folder/'settings.json').read_bytes() == settings_bytes
    restarted = State(s.folder)
    assert all(t['name'] != 'Practice / Reserve' for t in restarted.team_library())
    assert restarted.packs.snapshot() == content
    assert remove(c, 'Practice / Reserve').status_code == 404


def test_current_history_and_on_air_teams_are_protected_on_server(tmp_path):
    c, s = prepared(tmp_path)
    assert remove(c, 'home').status_code == 409
    assert remove(c, 'AWAY').status_code == 409
    s.graphics.innings.append(new_innings({**s.data, 'team1': 'Keep'}))
    assert remove(c, 'Keep').status_code == 409
    s.broadcast_settings({'pack': 'fox_odi'})
    s.broadcast_action({'action': 'show', 'kind': 'lineup', 'team': 'Practice / Reserve'})
    assert remove(c, 'Practice / Reserve').status_code == 409
    s.broadcast_action({'action': 'hide'})
    assert remove(c, 'Practice / Reserve').status_code == 200
    assert s.data['runs'] == '94' and s.data['wickets'] == '4'


def test_delete_rolls_back_roster_when_team_file_cannot_be_saved(tmp_path, monkeypatch):
    c, s = prepared(tmp_path)
    before = s.packs.snapshot()
    teams = s.team_library()
    from server import scoreboard_state
    real_write = scoreboard_state.write_json_atomic

    def fail_teams(path, data):
        if path.name == 'teams.json':
            raise PermissionError('Synthetic write failure')
        return real_write(path, data)

    monkeypatch.setattr(scoreboard_state, 'write_json_atomic', fail_teams)
    assert remove(c, 'Practice / Reserve').status_code == 503
    assert s.packs.snapshot() == before
    assert s.team_library() == teams
    assert json.loads(s.packs.path.read_text('utf-8')) == before
    assert State(s.folder).team_library() == teams


def test_delete_rejects_invalid_requests_without_removing_any_team(tmp_path):
    c, s = prepared(tmp_path)
    before = s.team_library()
    for command in ({}, {'name': ''}, {'name': ' '}, {'name': None}, {'name': 1}, {'name': 'x'*161}, {'name': 'Keep', 'all': True}):
        assert c.request('DELETE', '/api/teams', json=command).status_code == 400
    assert remove(c, 'Missing').status_code == 404
    assert s.team_library() == before
