import base64
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.config import Settings
from server.main import create_app
from server.scoreboard_state import BRANDING_DEFAULT, State


PNG = 'data:image/png;base64,' + base64.b64encode(
    bytes.fromhex('89504e470d0a1a0a') + b'sample image').decode()


def test_logo_persists_independently_of_match_and_team_appearance(tmp_path):
    state = State(tmp_path)
    assert state.branding_snapshot() == BRANDING_DEFAULT
    state.save_branding(dict(logo=PNG, width_percent=10.5, margin_percent=1.5))
    state.save(dict(source='manual', runs='10', wickets='0', overs='1.0'))
    state.reset()
    assert state.branding_snapshot()['logo'] == PNG
    assert state.snapshot()['score']['logo1'] == ''
    restored = State(tmp_path)
    assert restored.branding_snapshot() == state.branding_snapshot()
    copy = restored.branding_snapshot()
    copy['logo'] = 'changed'
    assert restored.branding_snapshot()['logo'] == PNG
    restored.save_branding({'visible': False})
    assert restored.branding_snapshot()['logo'] == PNG
    restored.save_branding({'logo': ''})
    assert State(tmp_path).branding_snapshot()['logo'] == ''


@pytest.mark.parametrize('changes', [
    {'logo': 'https://remote/logo.png'}, {'logo': 'data:image/svg+xml;base64,AAAA'},
    {'logo': 'data:image/png;base64,AAAA'}, {'logo': None}, {'width_percent': 2},
    {'width_percent': 26}, {'margin_percent': -1}, {'margin_percent': 11},
    {'visible': 'yes'}, {'width_percent': True}, {'width_percent': float('nan')},
    {'width_percent': float('inf')}, {'margin_percent': '2'}, {'unknown': 'setting'},
    {'logo': 'data:image/png;base64,' + 'A' * 1400000}, [],
])
def test_rejects_invalid_branding_without_changing_previous_settings(tmp_path, changes):
    state = State(tmp_path)
    state.save_branding({'logo': PNG})
    with pytest.raises(ValueError): state.save_branding(changes)
    assert State(tmp_path).branding_snapshot()['logo'] == PNG


def test_branding_api_and_clean_broadcast_share_server_and_persist(tmp_path):
    state = State(tmp_path / 'scores')
    app = create_app(Settings(database_path=tmp_path / 'test.db'), scoreboard=state)
    with patch('server.main.start_receiver'), TestClient(app) as client:
        assert client.get('/api/broadcast/branding').json() == BRANDING_DEFAULT
        assert client.post('/api/broadcast/branding', json={'logo': PNG, 'visible': True}).status_code == 200
        response = client.get('/api/broadcast/branding')
        assert 'no-store' in response.headers['cache-control']
        assert response.json()['logo'] == PNG
        assert client.get('/api/scoreboard/state').json()['branding']['logo'] == PNG
        assert client.post('/api/broadcast/branding', json={'width_percent': 100}).status_code == 400
        for route in ['/broadcast', '/broadcast?clean=1&audio=1']:
            html = client.get(route).text
            assert 'id="broadcastLogo"' in html
            assert '/static/broadcast-logo.js?v=1.3.0' in html
        assert client.get('/static/app-theme.css').status_code == 200
        assert client.get('/static/sections.js').status_code == 200
        with patch.object(state, 'save_branding', side_effect=OSError('read only')):
            assert client.post('/api/broadcast/branding', json={'logo': ''}).status_code == 503
