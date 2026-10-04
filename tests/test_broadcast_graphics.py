import copy
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.broadcast_graphics import BroadcastGraphics, balls, validate_config
from server.config import Settings
from server.main import create_app
from server.scoreboard_state import DEFAULT, State


def scoreboard(**changes):
    return {**DEFAULT, 'team1': 'Pavilion', 'team2': 'Creek', 'source': 'manual',
            'runs': '0', 'wickets': '0', 'overs': '0.0', **changes}


def observe(engine, score, now=100):
    engine.queue(score, score, now)
    engine.flush(now, force=True)
    return engine.snapshot(score, now)


def test_legal_balls_and_one_combined_projection():
    assert balls('10.2') == 62
    assert balls('10.6') is None
    engine = BroadcastGraphics()
    engine.configure({'rotation_mode': 'automatic', 'interval_seconds': 5})
    score = scoreboard(runs='66', wickets='3', overs='10.2')
    observe(engine, score)
    first = engine.snapshot(score, 100)['strip']['text']
    assert first == 'PROJECTED: 6.39 RPO 128 | 7 RPO 134 | 8 RPO 143 | 9 RPO 153'
    assert len([c for c in engine.candidates(score) if c['kind'] == 'projection']) == 1
    engine.configure({'rotation_mode': 'mixed'})
    score['banner'] = 'Summer cricket'
    assert engine.snapshot(score, 106)['strip'] == {'kind': 'main', 'text': 'Summer cricket'}
    # A boundary interrupts immediately; projections have no forced follow-up steps.
    engine.priority = 'boundaries'
    engine.next_strip_at = 0
    engine.innings[0]['fours'] = 4
    assert engine.snapshot(score, 107)['strip']['kind'] == 'boundaries'


def test_duplicate_cov_undo_and_over_transition():
    engine = BroadcastGraphics()
    observe(engine, scoreboard())
    s = scoreboard(overs='0.2', runs='10', deliveries='4 6')
    observe(engine, s, 102)
    observe(engine, s, 104)
    stats = engine.snapshot(s, 104)['innings'][0]
    assert (stats['fours'], stats['sixes']) == (1, 1)
    s.update(overs='0.1', runs='4', deliveries='4')
    observe(engine, s, 106)
    assert engine.snapshot(s, 106)['innings'][0]['sixes'] == 0
    s.update(overs='1.0', runs='12', deliveries='4 0 0 0 4 4')
    observe(engine, s, 108)
    s.update(deliveries='')
    observe(engine, s, 110)
    s.update(overs='1.1', runs='18', deliveries='6')
    stats = observe(engine, s, 112)['innings'][0]
    assert (stats['fours'], stats['sixes']) == (3, 1)
    assert stats['chart'][0]['runs'] == 12
    assert stats['chart'][1]['runs'] == 6


def test_missing_overs_are_unknown_instead_of_invented():
    engine = BroadcastGraphics()
    s = scoreboard(overs='4.0', runs='31')
    data = observe(engine, s)
    assert [row['runs'] for row in data['innings'][0]['chart'][:4]] == [None]*4
    assert data['innings'][0]['extras'] is None


def test_wicket_identity_waits_for_player_change_and_undo_removes_it():
    engine = BroadcastGraphics()
    s = scoreboard(batter1_name='Ali', batter1_runs='12', batter1_balls='10',
                   batter2_name='Bo', batter2_runs='4', batter2_balls='6', runs='16', overs='2.4')
    observe(engine, s)
    s.update(wickets='1', overs='2.5')
    assert observe(engine, s, 102)['innings'][0]['last_wicket'] is None
    s.update(batter2_name='Cam', batter2_runs='0', batter2_balls='0')
    data = observe(engine, s, 104)
    assert data['innings'][0]['last_wicket']['name'] == 'Bo'
    assert data['strip']['text'] == 'LAST WICKET  Bo 4 (6)'
    s.update(wickets='0', overs='2.4', batter2_name='Bo', batter2_runs='4', batter2_balls='6')
    data = observe(engine, s, 106)
    assert data['innings'][0]['last_wicket'] is None
    assert not data['innings'][0]['wicket_events']


def test_drinks_once_at_halfway_and_early_wickets_end_first_innings():
    engine = BroadcastGraphics()
    engine.configure({'total_overs': 4, 'wickets_limit': 3})
    observe(engine, scoreboard(overs='1.5', runs='18'))
    s = scoreboard(overs='2.0', runs='20')
    assert observe(engine, s, 102)['active']['reason'] == 'Drinks break'
    engine.action({'action': 'hide'}, s, 103)
    assert observe(engine, s, 104)['active'] is None
    s.update(wickets='3', overs='2.1')
    data = observe(engine, s, 106)
    assert data['phase'] == 'innings_break'
    assert data['active']['kind'] == 'innings_break'


def test_chase_winner_and_summary_exactly_thirty_seconds_later():
    engine = BroadcastGraphics()
    engine.configure({'total_overs': 2, 'wickets_limit': 5})
    observe(engine, scoreboard(overs='2.0', runs='12', wickets='2'))
    s = scoreboard(team1='Creek', team2='Pavilion', runs='0', overs='0.0')
    observe(engine, s, 103)
    assert len(engine.innings) == 2
    s.update(runs='13', wickets='2', overs='1.1')
    data = observe(engine, s, 110)
    assert data['phase'] == 'complete'
    assert data['result'] == 'Creek wins by 3 wickets'
    assert data['active'] is None
    assert engine.snapshot(s, 139.99)['active'] is None
    assert engine.snapshot(s, 140)['active']['kind'] == 'match_summary'
    engine.action({'action': 'hide'}, s, 141)
    assert engine.snapshot(s, 142)['active'] is None
    engine.action({'action': 'reopen'}, s, 143)
    assert engine.snapshot(s, 144)['phase'] == 'live'


@pytest.mark.parametrize('runs,expected', [('11','Pavilion wins by 1 run'),('12','Match tied')])
def test_defending_result_and_tie(runs, expected):
    engine = BroadcastGraphics()
    engine.configure({'total_overs': 1})
    observe(engine, scoreboard(overs='1.0', runs='12'))
    observe(engine, scoreboard(team1='Creek', team2='Pavilion'), 102)
    s = scoreboard(team1='Creek', team2='Pavilion', overs='1.0', runs=runs)
    assert observe(engine, s, 104)['result'] == expected


def test_manual_messages_stats_and_colour_changes():
    engine = BroadcastGraphics()
    engine.configure({'rotation_mode':'manual', 'messages': [
        {'type':'attendance','attendance':'1234'},
        {'type':'head_to_head','team1':'Pavilion','team2':'Creek','wins1':'3','wins2':'2'}]})
    s = scoreboard(banner='Welcome to the ground', runs='24', overs='4.0')
    observe(engine, s)
    assert {c['text'] for c in engine.candidates(s)} == {
        'Welcome to the ground', 'ATTENDANCE  1,234', 'HEAD TO HEAD  Pavilion (3)  Creek (2)'}
    engine.edit_stats({'innings':0, 'fours':4, 'sixes':1, 'over_runs':[0,6,11,7],
                       'batters':[{'name':'Ali','runs':20,'balls':20,'dismissal':'b Bo'},
                                  {'name':'Cam','runs':4,'balls':4,'dismissal':'not out'}]})
    s['color1'] = '#123456'
    stats = engine.snapshot(s, 102)['innings'][0]
    assert stats['color'] == '#123456'
    assert stats['last_wicket']['name'] == 'Ali'
    assert stats['boundaries_complete'] is True
    assert stats['extras'] == 0
    assert [i['runs'] for i in stats['chart'][:4]] == [0,6,11,7]


def test_packet_batch_does_not_count_transient_chase_total():
    engine = BroadcastGraphics()
    engine.configure({'total_overs': 1})
    observe(engine, scoreboard(overs='1.0',runs='12'))
    # Team swap arrives before the total/overs reset. Wait for the complete batch.
    s = scoreboard(team1='Creek',team2='Pavilion',overs='1.0',runs='12')
    engine.queue(s, {'team1':'Creek'}, 102)
    s.update(overs='0.0',runs='0')
    engine.queue(s, {'overs':'0.0','runs':'0'}, 102.1)
    data=engine.snapshot(s, 103.5)
    assert data['phase']=='live'
    assert data['innings'][1]['runs']==0


def test_cov_before_ball_count_preserves_previous_over():
    engine = BroadcastGraphics()
    s = scoreboard()
    observe(engine, s)
    s.update(overs='1.0', runs='14', deliveries='4 4 4 0 1 1')
    observe(engine, s, 102)
    s.update(deliveries='6')
    engine.queue(s, {'deliveries':'6'}, 104)
    s.update(overs='1.1', runs='20')
    engine.queue(s, {'overs':'1.1','runs':'20'}, 104.1)
    data = engine.snapshot(s, 105.3)['innings'][0]
    assert (data['fours'],data['sixes'])==(3,1)
    assert [row['runs'] for row in data['chart'][:2]]==[14,6]


def test_automatic_chase_keeps_team_colours(tmp_path):
    state=State(tmp_path)
    with patch('server.scoreboard_state.time.time',return_value=100):
        state.save(scoreboard(runs='12',overs='1.0',color1='#123456',color2='#abcdef'))
        state.broadcast_settings({'total_overs':1})
        state.flush()
    with patch('server.scoreboard_state.time.time',return_value=102):
        state.save({'team1':'Creek','team2':'Pavilion','runs':'0','wickets':'0','overs':'0.0'})
    with patch('server.scoreboard_state.time.time',return_value=104):
        data=state.snapshot()
    assert data['score']['color1']=='#abcdef'
    assert data['score']['color2']=='#123456'
    assert data['graphics']['innings'][0]['color']=='#123456'
    assert data['graphics']['innings'][1]['color']=='#abcdef'


def test_late_player_and_boundary_packets_finish_the_scorecard():
    engine = BroadcastGraphics()
    engine.configure({'total_overs':1})
    s=scoreboard(overs='1.0',runs='12',bowler='Bo',bowler_figures='0–8',bowler_overs='0.5')
    assert observe(engine,s)['phase']=='innings_break'
    s.update(bowler_figures='0–12',bowler_overs='1.0',deliveries='0 0 4 4 0 4')
    data=observe(engine,s,102)
    assert data['innings'][0]['bowlers'][0]['figures']=='0–12'
    assert data['innings'][0]['fours']==3
    assert data['phase']=='innings_break'


def test_validation_atomic_stats_and_persistence(tmp_path):
    state = State(tmp_path)
    with patch('server.scoreboard_state.time.time', return_value=100):
        state.save(scoreboard(runs='10',overs='1.0'))
        state.graphics.flush(100, force=True)
        state.broadcast_settings({'total_overs':4})
        state.broadcast_stats({'innings':0,'fours':2,'sixes':0,'extras':2})
        original=copy.deepcopy(state.graphics.innings)
        with pytest.raises(ValueError): state.broadcast_stats({'innings':0,'fours':5,'batters':[{'name':'X','runs':-1}]})
        assert state.graphics.innings==original
        state.broadcast_action({'action':'show','kind':'run_chart'})
    restored=State(tmp_path)
    assert restored.graphics.config['total_overs']==4
    assert restored.graphics.innings[0]['fours']==2
    assert restored.graphics.active is None
    restored.reset()
    assert restored.graphics.innings==[]
    assert restored.graphics.config['total_overs']==4
    for changes in ({'total_overs':True}, {'target':-1}, {'auto_summary':'yes'}, {'messages':[{'type':'attendance','attendance':'lots'}]}):
        with pytest.raises(ValueError): validate_config(changes)


def test_broadcast_http_actions(tmp_path):
    state = State(tmp_path/'scores')
    app = create_app(Settings(database_path=tmp_path/'test.db'),scoreboard=state)
    with patch('server.main.start_receiver'), TestClient(app) as client:
        assert client.post('/api/scoreboard/broadcast/settings',json={'total_overs':2}).status_code==200
        assert client.post('/api/scoreboard/broadcast/settings',json={'total_overs':0}).status_code==400
        assert client.post('/api/scoreboard/settings',json=scoreboard(runs='12',overs='2.0')).status_code==200
        assert client.post('/api/scoreboard/broadcast/action',json={'action':'end_innings'}).status_code==200
        assert client.post('/api/scoreboard/broadcast/action',json={'action':'start_chase'}).status_code==200
        data=client.get('/api/scoreboard/state').json()
        assert data['score']['team1']=='Creek'
        assert data['score']['color1']==DEFAULT['color2']
        assert data['graphics']['innings'][0]['runs']==12
        assert client.post('/api/scoreboard/broadcast/action',json={'action':'show','kind':'run_chart','innings':'bad'}).status_code==400


def test_manual_graphics_hold_and_automatic_graphics_cannot_preempt():
    engine=BroadcastGraphics()
    s=scoreboard(runs='20',overs='1.5')
    observe(engine,s)
    engine.configure({'total_overs':4})
    engine.show('run_chart',101)
    s.update(overs='2.0',runs='21')
    assert observe(engine,s,102)['active']['kind']=='run_chart'
    assert engine.snapshot(s,10000)['active']['until'] is None
    engine.end_innings(10001)
    assert engine.active['kind']=='run_chart'
    engine.action({'action':'show','kind':'power_surge'},s,10002)
    assert engine.snapshot(s,10003)['power_surge']
    engine.action({'action':'hide'},s,10004)
    assert engine.active is None and not engine.power_surge
    assert engine.phase=='innings_break', 'Reopen scoreboard must not undo the match phase'


def test_wicket_panel_calculates_complete_shots_and_corrects_dismissal():
    engine=BroadcastGraphics()
    s=scoreboard(batter1_name='Ali',batter1_runs='0',batter1_balls='0',batter2_name='Bo')
    observe(engine,s)
    for i,(runs,tokens) in enumerate([(0,'0'),(4,'0 4'),(10,'0 4 6')],1):
        s.update(runs=str(runs),overs=f'0.{i}',batter1_runs=str(runs),batter1_balls=str(i),deliveries=tokens)
        observe(engine,s,100+i*2)
    s.update(wickets='1',overs='0.4',batter1_balls='4',deliveries='0 4 6 W')
    observe(engine,s,108)
    s.update(batter1_name='Cam',batter1_runs='0',batter1_balls='0')
    data=observe(engine,s,110)
    assert data['active']['kind']=='wicket_card'
    row=data['innings'][0]['last_wicket']
    assert (row['dots'],row['scoring_shots'],row['fours'],row['sixes'],row['strike_rate'])==(2,2,1,1,250)
    assert row['dismissal']=='Out'
    engine.action({'action':'wicket_details','innings':0,'name':'Ali','dismissal':'c Bo b Dee','show':True},s,111)
    assert engine.snapshot(s,1000)['innings'][0]['last_wicket']['dismissal']=='c Bo b Dee'
    assert engine.active['until'] is None
    with pytest.raises(ValueError):engine.wicket_details({'name':'Ali','dismissal':True})
    partial=engine.batter_stats({'name':'X','runs':14,'balls':12,'dismissal':'b Dee','shots':{}})
    assert partial['dots'] is None and partial['fours'] is None
    assert partial['strike_rate']==117


def test_partnership_includes_extras_resets_at_wicket_and_accepts_corrections():
    engine=BroadcastGraphics();s=scoreboard()
    observe(engine,s)
    s.update(runs='12',overs='1.0');stats=observe(engine,s,102)['innings'][0]
    assert (stats['partnership_runs'],stats['partnership_balls'])==(12,6)
    s.update(runs='13');stats=observe(engine,s,104)['innings'][0]
    assert (stats['partnership_runs'],stats['partnership_balls'])==(13,6)
    s.update(wickets='1',overs='1.1');observe(engine,s,106)
    s.update(runs='17',overs='1.2');stats=observe(engine,s,108)['innings'][0]
    assert (stats['partnership_runs'],stats['partnership_balls'])==(4,1)
    engine.edit_stats({'innings':0,'partnership_runs':7,'partnership_balls':3})
    s.update(runs='19',overs='1.3');stats=observe(engine,s,110)['innings'][0]
    assert (stats['partnership_runs'],stats['partnership_balls'])==(9,4)
    s.update(wickets='2',overs='1.4');stats=observe(engine,s,112)['innings'][0]
    assert (stats['partnership_runs'],stats['partnership_balls'])==(0,0)


def test_late_chase_favours_equation_and_rates_and_boundaries_have_cooldown():
    engine=BroadcastGraphics();engine.random.seed(123)
    engine.configure({'rotation_mode':'automatic','interval_seconds':5})
    observe(engine,scoreboard(runs='180',overs='20.0'))
    s=scoreboard(team1='Creek',team2='Pavilion')
    observe(engine,s,102)
    s.update(runs='140',overs='16.0',wickets='2',deliveries='4')
    observe(engine,s,104)
    kinds=[engine.snapshot(s,200+n*5)['strip']['kind'] for n in range(100)]
    assert sum(k in ('chase','rates') for k in kinds)>=85
    candidates={c['kind']:c['text'] for c in engine.candidates(s)}
    assert candidates['chase']=='Creek needs 41 runs from 24 balls'
    assert candidates['rates']=='RUN RATE 8.75   REQUIRED RUN RATE 10.25'
    engine.priority='boundaries';engine.next_strip_at=0;engine.last_boundary_strip=-100
    assert engine.snapshot(s,1000)['strip']['kind']=='boundaries'
    engine.priority='boundaries';engine.next_strip_at=0
    assert engine.snapshot(s,1005)['strip']['kind']!='boundaries'


def test_program_history_matches_delayed_picture_and_excludes_receiver_logs(tmp_path):
    state=State(tmp_path)
    with patch('server.scoreboard_state.time.time',return_value=100):
        state.save(scoreboard(runs='10',overs='1.0'));state.flush();state.snapshot()
    with patch('server.scoreboard_state.time.time',return_value=105):
        state.save({'runs':'14'});state.flush();state.snapshot()
        old=state.program_snapshot(100)
        assert old['score']['runs']=='10'
        assert 'logs' not in old and 'status' not in old
        assert state.program_snapshot(99)['score']['visible'] is False
        assert state.program_snapshot(105)['score']['runs']=='14'


def test_program_http_rejects_stale_and_invalid_timestamps(tmp_path):
    state=State(tmp_path/'scores')
    with patch('server.main.start_receiver'),patch('server.scoreboard_state.time.time',return_value=100),TestClient(create_app(Settings(database_path=tmp_path/'test.db'),scoreboard=state)) as c:
        state.save(scoreboard(runs='10',overs='1.0'));state.flush()
        c.get('/api/scoreboard/state')
        assert c.get('/api/scoreboard/program-state?at=100').json()['score']['runs']=='10'
        for at in ('nan','inf','64','102'):
            assert c.get('/api/scoreboard/program-state?at='+at).status_code==422


def test_first_overs_setting_validated_and_persisted(tmp_path):
    state=State(tmp_path)
    state.broadcast_settings({'powerplay_overs':4})
    assert State(tmp_path).graphics.config['powerplay_overs']==4
    for value in (-1,101,True,'4',4.5):
        with pytest.raises(ValueError):validate_config({'powerplay_overs':value})
    state.broadcast_settings({'powerplay_overs':0})
    assert state.graphics.config['powerplay_overs']==0


def test_bluetooth_caught_and_bowled_delta_packets_populate_cards(tmp_path):
    state=State(tmp_path)
    now=[100.0]
    def send(*packets):
        with patch('server.scoreboard_state.time.time',side_effect=lambda:now[0]):
            for packet in packets:
                state.receive(packet.encode());now[0]+=.06
            now[0]+=1.3
            return state.snapshot()
    send('BTNAlpha','FTNBeta','BTS0/0','OVB0','B1NAli','B1S0','B1B0','B2NBo','B2S0','B2B0')
    send('COV.','OVB0.1','B1B1')
    send('COV. 6','OVB0.2','BTS6/0','B1S6','B1B2')
    data=send('COV. 6 W','OVB0.3','BTS6/1','BTW1','B1NBo','B1S0','B1B0','B2N ',
              'F1S6/1 (0.3)','LWN Ali','LWS6 (3)','LWDc','LWBDee','LWFCam')
    row=data['graphics']['innings'][0]['last_wicket']
    assert (row['name'],row['runs'],row['balls'],row['dismissal'])==('Ali',6,3,'c Cam b Dee')
    assert row['dots']==2 and row['sixes']==1 and row['strike_rate']==200
    assert data['graphics']['active']['kind']=='wicket_card'
    send('B2NEve','B2S0','B2B0')
    # Unchanged LWB is deliberately absent from the next wicket's delta.
    data=send('COV. 6 W W','OVB0.4','BTS6/2','BTW2','B2N ',
              'F1S6/2 (0.4)','LWNEve','LWS0 (1)','LWDb','LWF ')
    rows=data['graphics']['innings'][0]['batters']
    assert next(r for r in rows if r['name']=='Ali')['dismissal']=='c Cam b Dee'
    row=data['graphics']['innings'][0]['last_wicket']
    assert (row['name'],row['runs'],row['balls'],row['dismissal'])==('Eve',0,1,'b Dee')
    assert row['dots']==1
    assert next(r for r in rows if r['name']=='Bo')['active'] is True
    with patch('server.scoreboard_state.time.time',return_value=now[0]):
        state.broadcast_action({'action':'wicket_details','name':'Eve','dismissal':'lbw b Dee'})
    data=send('BTS6/2')
    assert data['graphics']['innings'][0]['last_wicket']['dismissal']=='lbw b Dee','an explicit correction survives repeated feed state'
    # Duplicate snapshots neither add wickets nor extend the automatic timer.
    deadline=data['graphics']['active']['until']
    data=send('BTS6/2','LWNEve','LWS0 (1)')
    assert data['graphics']['active']['until']==deadline
    send('B2NFay','B2S0','B2B0')
    data=send('COV. 6 W W W','OVB0.5','BTS6/3','B2N ','LWNFay','LWDlbw')
    assert data['graphics']['innings'][0]['last_wicket']['dismissal']=='lbw b Dee'
    send('B2NGus','B2S0','B2B0')
    # Unchanged LWS is not resent; no bowler attribution on a run-out.
    data=send('COV. 6 W W W W','OVB1.0','BTS6/4','B2N ','F1S6/3 (1.0)',
              'LWNGus','LWDro','LWB ','LWFCam')
    assert data['score']['overs']=='1.0' and data['score']['bowler_overs']=='1.0'
    assert data['graphics']['innings'][0]['last_wicket']['dismissal']=='run out (Cam)'
    assert data['graphics']['innings'][0]['wicket_events'][-1]['balls']==6
    # Undo must not reapply the stale last-wicket delta to the restored batter.
    data=send('BTS6/3','OVB0.5','B2NGus','B2S0','B2B0')
    assert data['graphics']['innings'][0]['last_wicket'] is None
    assert next(r for r in data['graphics']['innings'][0]['batters'] if r['name']=='Gus')['active'] is True


def test_last_wicket_feed_works_without_incoming_batter_and_unknown_type_is_out():
    engine=BroadcastGraphics();s=scoreboard()
    observe(engine,s)
    s.update(wickets='1',overs='0.1',last_wicket_name='Ali',last_wicket_runs='0',last_wicket_balls='1',last_wicket_code='unconfirmed')
    data=observe(engine,s,102)
    assert data['innings'][0]['last_wicket']['dismissal']=='Out'
    assert data['active']['kind']=='wicket_card'
