import copy

from fastapi.testclient import TestClient

from server.config import Settings
from server.main import create_app
from server.scoreboard_state import State


def test_team_library_does_not_replace_live_score_and_follows_innings(tmp_path):
    s = State(tmp_path)
    s.save(dict(source='manual', team1='Batters', team2='Fielders', runs='94', wickets='4', overs='14.1'))
    s.flush()
    before = copy.deepcopy(s.data)
    s.save_team(dict(name='Future team', color='#235d41', logo=''))
    assert s.data == before
    s.save_team(dict(name='Fielders', color='#123456', logo=''))
    assert s.data['color2'] == '#123456'
    assert s.data['runs'] == '94' and s.data['wickets'] == '4'
    assert s.graphics.innings[0]['opposition_color'] == '#123456'
    assert any(t['name'] == 'Future team' for t in State(tmp_path).team_library())


def test_roster_and_match_lineup_are_separate_and_migrate_old_profiles(tmp_path):
    s = State(tmp_path)
    roster = dict(team='HOME', players=[dict(name='One'), dict(name='Two'), dict(name='Reserve')])
    s.packs.save({'team': roster})
    match_id = s.graphics.match_id
    s.packs.save({'lineup': dict(match_id=match_id, team='HOME', players=['One', 'Two'])})
    restored = State(tmp_path).packs.snapshot()
    assert len(restored['teams'][0]['players']) == 3
    assert restored['lineups'][0]['players'] == ['One', 'Two']
    roster['players'] = [dict(name='One'), dict(name='Reserve')]
    s.packs.save({'team': roster})
    assert s.packs.snapshot()['lineups'][0]['players'] == ['One']
    s.packs.save({'details': {'sponsor_name': 'Local Club'}})
    s.packs.save({'details': {'toss_team': 'HOME'}})
    assert s.packs.snapshot()['details']['sponsor_name'] == 'Local Club'
    assert s.data['runs'] == ''


def test_sections_and_team_validation_use_existing_origin(tmp_path):
    app = create_app(Settings(data_root=tmp_path))
    c = TestClient(app)
    for route in ('/scoreboard', '/match-setup', '/teams', '/graphics', '/highlights', '/connections', '/settings', '/help'):
        response = c.get(route)
        assert response.status_code == 200
        assert f'data-operator="{route[1:]}"' in response.text
        assert '__STUDIO_CONNECTION__' not in response.text
        assert 'no-store' in response.headers['cache-control']
    assert c.get('/api/teams').status_code == 200
    assert c.post('/api/teams', json={'name': 'Other', 'color': '#123456', 'logo': ''}).status_code == 200
    assert c.post('/api/teams', json={'name': '', 'color': '#123456', 'logo': ''}).status_code == 400
    assert c.post('/api/teams', json={'name': 'Other', 'color': 'red', 'logo': ''}).status_code == 400
    assert c.post('/api/graphics-packs', json={'lineup': {'match_id': app.state.scoreboard.graphics.match_id, 'team': 'Other', 'players': ['Unknown']}}).status_code == 422
    for invalid in (None, [], 'not an object'):
        assert c.post('/api/graphics-packs', json={'details': invalid}).status_code == 422
    assert 'id="statsEditor"' in c.get('/scoreboard?legacy=1').text
    assert 'operator-nav.js' not in c.get('/live').text
    assert 'preferences.js' not in c.get('/overlay').text
