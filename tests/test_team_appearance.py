import base64
from unittest.mock import patch

import pytest

from server.scoreboard_state import State


def logo(marker):
    return 'data:image/png;base64,' + base64.b64encode(b'\x89PNG\r\n\x1a\n' + marker).decode()


A_LOGO, B_LOGO = logo(b'A'), logo(b'B')


def teams(state, source='manual'):
    state.save({'team1': 'Pavilion', 'team2': 'Creek', 'color1': '#123456',
                'color2': '#abcdef', 'logo1': A_LOGO, 'logo2': B_LOGO,
                'source': source, 'runs': '24', 'wickets': '1', 'overs': '3.0'})
    state.flush()


def assert_swapped(score):
    assert (score['team1'], score['color1'], score['logo1']) == ('Creek', '#abcdef', B_LOGO)
    assert (score['team2'], score['color2'], score['logo2']) == ('Pavilion', '#123456', A_LOGO)


def test_manual_swap_restores_team_colours_and_logos_and_persists(tmp_path):
    state = State(tmp_path)
    teams(state)
    state.save({'team1': 'Creek', 'team2': 'Pavilion'})
    assert_swapped(state.data)
    assert_swapped(State(tmp_path).data)
    state.reset()
    assert_swapped(state.data)
    state.save({'team1': 'Pavilion', 'team2': 'Creek'})
    assert (state.data['color1'], state.data['logo1']) == ('#123456', A_LOGO)
    assert (state.data['color2'], state.data['logo2']) == ('#abcdef', B_LOGO)


def test_old_full_form_does_not_overwrite_known_team_appearance(tmp_path):
    state = State(tmp_path)
    teams(state)
    old_form = {**state.data, 'team1': 'Creek', 'team2': 'Pavilion'}
    state.save(old_form)
    assert_swapped(state.data)


@pytest.mark.parametrize('packets', [
    [b'BTNCreek', b'FTNPavilion'], [b'FTNPavilion', b'BTNCreek']])
def test_split_bluetooth_names_follow_team_not_role(tmp_path, packets):
    state = State(tmp_path)
    with patch('server.scoreboard_state.time.time', return_value=100):
        teams(state, source='bluetooth')
    first = state.graphics.innings[0].copy()
    for i, packet in enumerate(packets):
        # Force a snapshot between writes, beyond the coalescing interval.
        with patch('server.scoreboard_state.time.time', return_value=102 + i * 3):
            state.receive(packet)
        with patch('server.scoreboard_state.time.time', return_value=104 + i * 3):
            snap = state.snapshot()
        for n in (1, 2):
            is_a = snap['score'][f'team{n}'] == 'Pavilion'
            assert snap['score'][f'color{n}'] == ('#123456' if is_a else '#abcdef')
            assert snap['score'][f'logo{n}'] == (A_LOGO if is_a else B_LOGO)
        assert state.graphics.innings[0]['team'] == first['team']
        assert state.graphics.innings[0]['opposition'] == first['opposition']
        assert state.graphics.innings[0]['runs'] == 24
    assert_swapped(state.data)
    assert_swapped(State(tmp_path).data)


def test_profiles_match_case_and_whitespace_and_allow_edits(tmp_path):
    state = State(tmp_path)
    teams(state)
    state.save({'team1': ' creek ', 'team2': 'PAVILION'})
    assert state.data['color1'] == '#abcdef'
    state.save({'color1': '#112233', 'logo1': ''})
    state.save({'team1': 'Pavilion', 'team2': 'Creek'})
    assert state.data['color2'] == '#112233'
    assert state.data['logo2'] == ''


def test_shortened_innings_chase_preserves_first_history(tmp_path):
    state = State(tmp_path)
    with patch('server.scoreboard_state.time.time', return_value=100):
        teams(state)
        state.save({'deliveries': '4 4 4 4 4 4'})
        state.flush()
    with patch('server.scoreboard_state.time.time', return_value=102):
        state.save({'team1': 'Creek', 'team2': 'Pavilion', 'runs': '0',
                    'wickets': '0', 'overs': '0.0', 'deliveries': ''})
        state.flush()
        snap = state.snapshot()
    assert_swapped(snap['score'])
    first, second = snap['graphics']['innings']
    assert (first['team'], first['runs'], first['overs'], first['fours']) == ('Pavilion', 24, '3.0', 6)
    assert (second['team'], second['runs'], second['overs']) == ('Creek', 0, '0.0')
    assert (first['color'], first['logo']) == ('#123456', A_LOGO)
    assert (second['color'], second['logo']) == ('#abcdef', B_LOGO)


def test_manual_start_chase_preserves_both_identities(tmp_path):
    state = State(tmp_path)
    teams(state)
    state.broadcast_action({'action': 'end_innings'})
    state.broadcast_action({'action': 'start_chase'})
    assert_swapped(state.data)
    state.flush()
    assert [(i['team'], i['color'], i['logo']) for i in state.graphics.innings] == [
        ('Pavilion', '#123456', A_LOGO), ('Creek', '#abcdef', B_LOGO)]
