import base64
import json

import pytest
from fastapi.testclient import TestClient

from server.broadcast_graphics import BroadcastGraphics
from server.config import Settings
from server.main import create_app
from server.scoreboard_state import State, DEFAULT


@pytest.mark.parametrize('pack',['bbl','fox_odi'])
def test_blank_is_available_before_scoring_held_over_events_and_survives_pack_change(pack):
    g=BroadcastGraphics();g.configure({'pack':pack})
    g.action({'action':'show','kind':'blank'},DEFAULT,100)
    assert g.active['kind']=='blank' and g.active['until'] is None and not g.power_surge
    g.show('coming_up',101,reason='Automatic')
    assert g.active['kind']=='blank'
    g.configure({'pack':'bbl' if pack=='fox_odi' else 'fox_odi'})
    assert g.active['kind']=='blank'
    restored=BroadcastGraphics(g.export());assert restored.active['kind']=='blank'
    restored.action({'action':'hide'},DEFAULT,1000);assert restored.active is None


@pytest.mark.parametrize('pack',['bbl','fox_odi'])
def test_coming_up_is_common_and_has_no_team_or_player_style(pack):
    g=BroadcastGraphics();g.configure({'pack':pack})
    g.action({'action':'show','kind':'coming_up','team':'Selected team','player':'Selected player'},DEFAULT,100)
    assert g.active['team']=='' and g.active['player']==''
    g.configure({'pack':'bbl' if pack=='fox_odi' else 'fox_odi'})
    assert g.active['kind']=='coming_up'


def test_abbreviations_follow_named_teams_through_ble_swap_and_restart(tmp_path):
    state=State(tmp_path)
    state.save_team(dict(name='Pavilion',abbreviation=' pav ',color='#123456',logo=''))
    state.save_team(dict(name='Creek',abbreviation='crk',color='#abcdef',logo=''))
    state.save(dict(team1='Pavilion',team2='Creek',source='bluetooth'))
    assert (state.snapshot()['score']['abbr1'],state.snapshot()['score']['abbr2'])==('PAV','CRK')
    state.receive(b'BTNCreek');state.receive(b'FTNPavilion')
    assert (state.snapshot()['score']['abbr1'],state.snapshot()['score']['abbr2'])==('CRK','PAV')
    restored=State(tmp_path)
    assert (restored.snapshot()['score']['abbr1'],restored.snapshot()['score']['abbr2'])==('CRK','PAV')
    assert 'abbr1' not in restored.data and 'abbr1' not in json.loads((tmp_path/'settings.json').read_text('utf-8'))
    restored.save_team(dict(name='Pavilion',color='#222222',logo=''))
    assert next(t for t in restored.team_library() if t['name']=='Pavilion')['abbreviation']=='PAV'
    with pytest.raises(ValueError):restored.save_team(dict(name='Creek',abbreviation='TOO-LONG-CODE',color='#abcdef',logo=''))


def test_home_away_remain_fixed_when_batting_changes_and_through_restart(tmp_path):
    state=State(tmp_path)
    state.match_teams(dict(home_team='Pavilion',away_team='Creek'))
    state.save(dict(source='manual',runs='10',wickets='0',overs='1.0'))
    state.flush();before=state.data.copy()
    state.match_teams(dict(home_team='Creek',away_team='Pavilion'))
    assert state.data==before,'changing the home label must not swap the live batting side'
    state.match_teams(dict(home_team='Pavilion',away_team='Creek'))
    state.broadcast_action({'action':'end_innings'});state.broadcast_action({'action':'start_chase'})
    assert state.data['team1']=='Creek'
    assert state.match_setup_snapshot()['home_team']=='Pavilion'
    restored=State(tmp_path)
    assert restored.match_setup_snapshot()['home_team']=='Pavilion'
    assert restored.match_setup_snapshot()['away_team']=='Creek'
    with pytest.raises(ValueError,match='recorded innings'):state.match_teams(dict(home_team='Another team'))
    state.reset();assert state.match_setup_snapshot()['home_team']=='Pavilion'
    assert state.match_setup_snapshot()['match_id']==state.graphics.match_id
    state.match_teams(dict(home_team='New Home',away_team='New Away'))
    assert (state.data['team1'],state.data['team2'])==('New Home','New Away')


def test_match_setup_api_validates_distinct_sides_and_sponsor_requires_image(tmp_path):
    app=create_app(Settings(data_root=tmp_path));c=TestClient(app)
    assert c.post('/api/scoreboard/match-teams',json={'home_team':'A','away_team':'A'}).status_code==400
    assert c.post('/api/scoreboard/match-teams',json={'home_team':'A','away_team':'B'}).status_code==200
    assert c.get('/api/scoreboard/state').json()['match_setup']['home_team']=='A'
    assert c.post('/api/scoreboard/broadcast/action',json={'action':'show','kind':'sponsor'}).status_code==400
    image='data:image/png;base64,'+base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode()
    url=c.post('/api/graphics-packs/artwork',json={'image':image}).json()['url']
    assert c.post('/api/graphics-packs',json={'details':{'sponsor_image':url}}).status_code==200
    for pack in ['bbl','fox_odi']:
        c.post('/api/scoreboard/broadcast/settings',json={'pack':pack})
        assert c.post('/api/scoreboard/broadcast/action',json={'action':'show','kind':'sponsor'}).status_code==200
    assert 'foxSponsorCaption' not in c.get('/scoreboard?legacy=1').text
