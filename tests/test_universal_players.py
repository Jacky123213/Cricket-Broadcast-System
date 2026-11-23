import copy
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from server.career_stats import CareerStats, Conflict, SCHEMA, Submission
from server.config import Settings
from server.main import create_app
from server.scoreboard_state import State, DEFAULT
from server.live_match import LiveMatch
from test_career_stats import finished, store, submission


def roster(service, team, identity, name='Ali'):
    service.scoreboard.packs.validate_players=service.validate_roster
    service.scoreboard.packs.save({'team':dict(team=team,players=[dict(name=name,player_id=identity)])})


def links(data, pairs):
    data['player_links']=[dict(team=team,name=name,player_id=identity) for team,name,identity in pairs]


def test_one_universal_player_across_two_of_four_fantasy_teams(store):
    s,data=store;identity=s.register('Ali',universal=True)['id']
    roster(s,'Blue',identity);roster(s,'Green',identity)
    s.scoreboard.packs.save({'team':dict(team='Red',players=[dict(name='Dee')])})
    s.scoreboard.packs.save({'team':dict(team='Gold',players=[dict(name='Dee')])})
    links(data,[('Blue','Ali',identity)])
    assert next(p for p in s.review()['players'] if p['name']=='Ali')['suggested_id']==identity
    s.submit(submission(s))
    data['match_id']='b'*32;s.scoreboard.graphics.match_id='b'*32
    for i in data['innings']:
        i['team']={'Blue':'Green','Red':'Gold'}[i['team']]
        i['opposition']={'Blue':'Green','Red':'Gold'}[i['opposition']]
    for lineup in data['lineups']:lineup['team']={'Blue':'Green','Red':'Gold'}[lineup['team']]
    data['result']='Gold wins by 9 wickets';links(data,[('Green','Ali',identity)])
    s.submit(submission(s))
    profiles=[p for p in s.directory()['players'] if p['name']=='Ali']
    assert len(profiles)==1
    p=profiles[0]
    assert p['id']==identity and p['universal'] is True and p['matches']==2 and p['runs']==20
    assert p['teams']==['Blue','Green'] and p['roster_teams']==['Blue','Green']
    assert len(s.directory()['teams'])==4
    assert len(s.player(identity)['performances'])==2


def test_head_to_head_keeps_both_innings_and_counts_one_match(store):
    s,data=store;identity=s.register('Ali',universal=True)['id']
    data['innings'][1]['batters'][0]['name']='Ali';data['innings'][0]['bowlers'][0]['name']='Ali'
    data['lineups'][1]['players']=['Ali']
    roster(s,'Blue',identity);roster(s,'Red',identity)
    links(data,[('Blue','Ali',identity),('Red','Ali',identity)])
    people=[p for p in s.review()['players'] if p['name']=='Ali']
    assert len(people)==2 and all(p['suggested_id']==identity and not p['ambiguous'] for p in people)
    request=submission(s);s.submit(request);assert s.submit(request)['already_submitted']
    p=s.player(identity)['player']
    assert p['matches']==1 and p['innings']==2 and p['runs']==21 and p['balls']==20
    assert p['wickets']==1 and p['conceded']==21 and p['outs']==1 and p['not_outs']==1
    assert p['teams']==['Blue','Red']
    rows=s.player(identity)['performances'];assert len(rows)==1
    assert rows[0]['teams']==['Blue','Red']
    assert {b['team'] for b in rows[0]['batting']}=={'Blue','Red'}
    assert all(t['matches']==1 for t in s.directory()['teams'])
    data['innings'][0]['batters'][0]['runs']=9
    s.submit(submission(s,replace=True,previous_version=1))
    assert s.player(identity)['player']['runs']==20 and s.player(identity)['player']['matches']==1
    for team in ('Blue','Red'):s.scoreboard.packs.save({'team':dict(team=team,players=[])})
    with pytest.raises(Conflict,match='both teams'):s.set_universal(identity,False)
    s.withdraw(data['match_id'],2)
    assert s.player(identity)['player']['runs']==0 and s.player(identity)['player']['matches']==0
    s.submit(submission(s,replace=True,previous_version=3))
    assert s.player(identity)['player']['runs']==20


def test_normal_record_needs_universal_before_second_roster_and_turning_it_off_is_guarded(store):
    s,_=store;identity=s.register('Ali')['id'];roster(s,'Blue',identity)
    before=s.scoreboard.packs.snapshot()
    with pytest.raises(ValueError,match='Universal'):roster(s,'Red',identity)
    assert s.scoreboard.packs.snapshot()==before
    s.set_universal(identity,True);roster(s,'Red',identity)
    with pytest.raises(Conflict,match='several rosters'):s.set_universal(identity,False)
    assert s.player(identity)['player']['universal'] is True
    s.scoreboard.packs.save({'team':dict(team='Red',players=[])})
    s.set_universal(identity,False)
    assert s.player(identity)['player']['universal'] is False


def test_linked_names_do_not_merge_different_people_with_identical_names(store):
    s,data=store;first=s.register('Ali')['id'];second=s.register('Ali')['id']
    data['innings'][1]['batters'][0]['name']='Ali';data['innings'][0]['bowlers'][0]['name']='Ali'
    data['lineups'][1]['players']=['Ali'];links(data,[('Blue','Ali',first),('Red','Ali',second)])
    r=s.review();people=[p for p in r['players'] if p['name']=='Ali']
    assert {p['suggested_id'] for p in people}=={first,second} and not any(p['ambiguous'] for p in people)
    s.submit(submission(s))
    assert s.player(first)['player']['runs']==10 and s.player(second)['player']['runs']==11


def test_roster_rejects_unknown_and_repeated_ids_and_survives_reload(store):
    s,_=store;identity=s.register('Ali',universal=True)['id'];roster(s,'Blue',identity)
    before=s.scoreboard.packs.snapshot()
    with pytest.raises(ValueError,match='existing saved'):roster(s,'Blue','f'*32)
    with pytest.raises(ValueError,match='only once'):
        s.scoreboard.packs.save({'team':dict(team='Blue',players=[dict(name='Ali',player_id=identity),dict(name='Alias',player_id=identity)])})
    assert s.scoreboard.packs.snapshot()==before
    restored=State(s.scoreboard.folder)
    assert restored.packs.snapshot()['teams'][0]['players'][0]['player_id']==identity


def test_additive_migration_preserves_legacy_ids_and_saved_totals(store,tmp_path):
    s,_=store;s.submit(submission(s));expected=s.directory();legacy=tmp_path/'legacy.sqlite'
    # Construct the previous four-column player schema with a real saved match.
    with sqlite3.connect(s.path) as source,sqlite3.connect(legacy) as target:
        target.executescript(SCHEMA)
        for table in ('career_players','career_teams','career_aliases','career_drafts','career_matches','career_entries'):
            columns=[r[1] for r in target.execute('PRAGMA table_info('+table+')')]
            rows=source.execute('SELECT '+','.join(columns)+' FROM '+table).fetchall()
            target.executemany('INSERT INTO '+table+' VALUES('+','.join('?' for _ in columns)+')',rows)
        for match_id,player_id,raw in target.execute('SELECT match_id,player_id,performance FROM career_entries').fetchall():
            performance=json.loads(raw);performance.pop('teams',None)
            for kind in ('batting','bowling'):
                for row in performance[kind]:row.pop('team',None)
            target.execute('UPDATE career_entries SET performance=? WHERE match_id=? AND player_id=?',(json.dumps(performance),match_id,player_id))
    migrated=CareerStats(legacy,s.scoreboard,None)
    assert migrated.directory()==expected
    with sqlite3.connect(legacy) as db:
        assert [r[1] for r in db.execute('PRAGMA table_info(career_players)')]==['id','name','name_key','created_at']
        # An older app can still create a player using its original four columns.
        db.execute('INSERT INTO career_players VALUES(?,?,?,?)',('f'*32,'Legacy writer','legacy writer','now'))
        db.execute('DELETE FROM career_players WHERE id=?',('f'*32,))
    assert CareerStats(legacy,s.scoreboard,None).directory()==expected
    identity=expected['players'][0]['id'];before=migrated.player(identity)['player']
    migrated.set_universal(identity,True)
    after=migrated.player(identity)['player'];assert after['id']==before['id'] and after['runs']==before['runs'] and after['matches']==before['matches']


def test_finished_snapshot_keeps_player_links_after_starting_new_match(tmp_path):
    state=State(tmp_path/'scoreboard');settings=Settings(data_root=tmp_path)
    s=CareerStats(settings.database_path,state,LiveMatch(settings,state,None,None))
    identity=s.register('Ali',universal=True)['id'];roster(s,'Blue',identity)
    score={**DEFAULT,'source':'manual','team1':'Blue','team2':'Red','runs':'0','wickets':'0','overs':'0.0','batter1_name':'Ali','batter1_runs':'0','batter1_balls':'0'}
    state.graphics.observe(score,100);state.graphics.config['result_override']='No result';state.graphics.finish(101)
    s.stage_current();match_id=state.graphics.match_id;state.reset()
    other=s.register('Someone else',universal=True)['id'];roster(s,'Blue',other,name='Ali')
    ali=next(p for p in s.review(match_id)['players'] if p['name']=='Ali')
    assert ali['suggested_id']==identity


def test_player_options_api_and_roster_links_use_existing_record(tmp_path):
    app=create_app(Settings(data_root=tmp_path));c=TestClient(app)
    player=c.post('/api/statistics/players',json={'name':'Ali','universal':True}).json();identity=player['id']
    assert player['universal'] is True
    for team in ('Blue','Red'):
        assert c.post('/api/graphics-packs',json={'team':dict(team=team,players=[dict(name='Ali',player_id=identity)])}).status_code==200
    assert len(c.get('/api/statistics').json()['players'])==1
    assert c.post('/api/statistics/players/'+identity+'/options',json={'universal':False}).status_code==409
    assert c.post('/api/statistics/players/'+identity+'/options',json={'universal':'yes'}).status_code==422
    assert c.post('/api/statistics/players/'+'f'*32+'/options',json={'universal':True}).status_code==404
    assert c.post('/api/statistics/players',json={'name':'Bad','universal':'true'}).status_code==400
