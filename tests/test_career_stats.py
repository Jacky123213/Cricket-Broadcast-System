import copy
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from server.career_stats import CareerStats, Conflict, Submission
from server.scoreboard_state import State, DEFAULT
from server.live_match import LiveMatch
from server.config import Settings
from server.main import create_app


def finished(match_id='a'*32):
    def batter(name,runs,out):
        return dict(name=name,runs=runs,balls=10,fours=0,sixes=0,dismissal='b Dee' if out else 'not out',active=not out)
    def bowler(name,wickets,runs):
        return dict(name=name,wickets=wickets,runs=runs,overs='1.4',maidens=0)
    return dict(match_id=match_id,title='Blue v Red',venue='Home',format='T20',competition='',date='2026-11-19',finished_at=100,total_overs=20,result='Red wins by 9 wickets',
                innings=[dict(team='Blue',opposition='Red',runs=10,wickets=1,overs='2.0',batters=[batter('Ali',10,True)],bowlers=[bowler('Dee',1,10)]),
                         dict(team='Red',opposition='Blue',runs=11,wickets=0,overs='1.4',batters=[batter('Dee',11,False)],bowlers=[bowler('Ali',0,11)])],
                lineups=[dict(team='Blue',players=['Ali','Did Not Bat']),dict(team='Red',players=['Dee'])])


@pytest.fixture
def store(tmp_path):
    state=State(tmp_path/'scoreboard');state.graphics.match_id='a'*32;state.graphics.phase='complete'
    service=CareerStats(tmp_path/'studio.sqlite',state,None)
    data=finished();service.capture=lambda:copy.deepcopy(data)
    return service,data


def submission(service,**changes):
    r=service.review()
    return Submission(match_id=r['match_id'],revision=r['revision'],outcome=r['outcome'] or 'no_result',winner=r['winner'],
                      players=[dict(key=p['key'],player_id=p['suggested_id'],name=p['name']) for p in r['players']],
                      accept_missing=True,**changes)


def test_confirmed_results_accumulate_roles_and_survive_restart(store):
    s,data=store
    assert s.status()['needs_review'] and not s.directory()['matches']
    request=submission(s);s.submit(request)
    assert not s.status()['needs_review']
    players={p['name']:p for p in s.directory()['players']}
    assert len(players)==3
    assert players['Ali']['matches']==1 and players['Ali']['runs']==10 and players['Ali']['conceded']==11
    assert players['Dee']['wickets']==1 and players['Dee']['highest']=='11*' and players['Dee']['average'] is None
    assert players['Did Not Bat']['matches']==1 and players['Did Not Bat']['innings']==0
    assert s.submit(request)['already_submitted']
    restored=CareerStats(s.path,s.scoreboard,None)
    assert restored.directory()==s.directory()
    data.update(match_id='b'*32);s.scoreboard.graphics.match_id='b'*32
    s.submit(submission(s))
    p=next(p for p in s.directory()['players'] if p['name']=='Ali')
    assert p['id']==players['Ali']['id'] and p['runs']==20 and p['matches']==2
    assert len(s.player(p['id'])['performances'])==2


def test_correction_replaces_one_contribution_stale_and_withdraw_guard(store):
    s,data=store;r=submission(s);s.submit(r)
    data['innings'][0]['batters'][0]['runs']=9
    assert s.status()['needs_review']
    with pytest.raises(Conflict):s.submit(r)
    corrected=submission(s,replace=True,previous_version=1)
    assert s.submit(corrected)['version']==2
    p=next(p for p in s.directory()['players'] if p['name']=='Ali')
    assert p['matches']==1 and p['runs']==9
    with pytest.raises(Conflict):s.withdraw(data['match_id'],1)
    s.withdraw(data['match_id'],2)
    assert s.directory()['matches']==[] and s.player(p['id'])['player']['matches']==0
    s.submit(submission(s,replace=True,previous_version=3))
    assert len(s.directory()['matches'])==1


def test_transaction_rolls_back_bad_identity_and_opposing_player_merge(store):
    s,_=store;r=submission(s)
    r.players[0].player_id='f'*32
    with pytest.raises(ValueError):s.submit(r)
    assert s.directory()==dict(players=[],teams=[],matches=[])
    existing=s.register('Same Name')['id'];r=submission(s)
    for p in r.players:p.player_id=existing
    with pytest.raises(ValueError,match='opposing|same player'):s.submit(r)
    assert len(s.directory()['players'])==1 and not s.directory()['matches']


def test_unknown_data_is_not_zero_and_missing_must_be_acknowledged(store):
    s,data=store;row=data['innings'][0]['batters'][0];row.update(runs=None,balls=None,dismissal='',active=False)
    r=submission(s);r.accept_missing=False
    with pytest.raises(ValueError,match='missing-data'):s.submit(r)
    r.accept_missing=True;s.submit(r)
    p=next(p for p in s.directory()['players'] if p['name']=='Ali')
    assert p['runs'] is None and p['average'] is None and p['strike_rate'] is None
    assert p['missing']['batting_runs']==1 and p['missing']['dismissals']==1
    assert next(p for p in s.directory()['players'] if p['name']=='Dee')['fours']==0


def test_concurrent_double_submit_only_counts_once_and_reopened_game_rejected(store):
    s,_=store;r=submission(s)
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies=list(pool.map(lambda _:s.submit(r),range(2)))
    assert sorted(r['already_submitted'] for r in replies)==[False,True]
    assert len(s.directory()['matches'])==1
    s.scoreboard.graphics.phase='second'
    with pytest.raises(Conflict,match='reopened'):s.submit(r)


def test_same_name_players_require_explicit_choice_and_lineups_are_canonical(store):
    s,data=store
    s.register('Ali');s.register('Ali')
    data['lineups'][0]['team']='blue'
    r=s.review();ali=next(p for p in r['players'] if p['name']=='Ali')
    assert ali['ambiguous'] and not ali['suggested_id'] and ali['team']=='Blue'


def test_capture_finished_game_and_reset_does_not_discard_pending(tmp_path):
    state=State(tmp_path/'scoreboard');settings=Settings(data_root=tmp_path)
    live=LiveMatch(settings,state,None,None);s=CareerStats(settings.database_path,state,live)
    score={**DEFAULT,'source':'manual','team1':'Blue','team2':'Red','runs':'0','wickets':'0','overs':'0.0','batter1_name':'Ali','batter1_runs':'0','batter1_balls':'0'}
    state.graphics.observe(score,100);state.graphics.config['result_override']='No result';state.graphics.finish(101)
    s.stage_current();match_id=state.graphics.match_id;state.reset()
    assert s.status()['pending']==1 and s.review(match_id)['snapshot']['innings'][0]['team']=='Blue'
    assert not s.status()['needs_review']


def test_read_only_routes_and_empty_player_lookup(tmp_path):
    from fastapi.testclient import TestClient
    app=create_app(Settings(data_root=tmp_path));client=TestClient(app)
    assert client.get('/stats').status_code==200
    assert client.get('/statistics').status_code==200
    assert client.get('/api/statistics').json()==dict(players=[],teams=[],matches=[])
    assert client.get('/api/statistics/players/'+'f'*32).status_code==404
    assert client.post('/stats',json={}).status_code==405
    assert client.get('/api/statistics/review').status_code==400
