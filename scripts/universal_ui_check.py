"""Universal-player workflows with synthetic data in the native browser harness."""
import copy
import json
import time


def check_ui(app, output, js, wait, size, navigate, shot):
    from server.broadcast_graphics import new_innings
    career=app.state.career_stats;score=app.state.scoreboard
    name='Universal Tester';identity=career.register(name)['id'];results=[]
    size(1440,900);navigate('/statistics')
    wait("document.getElementById('universalPlayerPicker')?.options.length>1")
    js("document.getElementById('universalPlayerPicker').value="+json.dumps(identity)+";document.getElementById('universalPlayerPicker').dispatchEvent(new Event('change'));document.getElementById('isUniversalPlayer').click();document.getElementById('universalPlayerOptions').requestSubmit()")
    wait("document.getElementById('statsMessage').textContent.includes('is now universal')")
    assert len(career.directory()['players'])==1 and career.player(identity)['player']['universal']
    for theme in ['dark','light']:
        js("window.CricketPreferences.save({theme:'"+theme+"'})")
        for width,height in [(1440,900),(1024,768),(390,844)]:
            size(width,height);time.sleep(.15)
            assert js('document.documentElement.scrollWidth<=innerWidth')
            shot('universal-option-'+theme+'-'+str(width)+'.png')
            results.append(dict(page='statistics',theme=theme,width=width,passed=True))
    for team in ('Pavilion XI','Creek XI'):
        size(1440,900);navigate('/teams')
        wait("document.getElementById('universalRosterPlayer')?.options.length===2")
        js("document.getElementById('teamPicker').value="+json.dumps(team)+";document.getElementById('teamPicker').dispatchEvent(new Event('change'));document.getElementById('universalRosterPlayer').value="+json.dumps(identity)+";document.getElementById('addUniversalPlayer').click();document.getElementById('teamEditor').requestSubmit()")
        wait("document.getElementById('workspaceStatus').textContent.includes('roster and player details saved')")
        profile=next(t for t in score.packs.snapshot()['teams'] if t['team']==team)
        assert [p['player_id'] for p in profile['players'] if p['name']==name]==[identity]
        for theme in ['dark','light']:
            js("window.CricketPreferences.save({theme:'"+theme+"'})")
            for width,height in [(1440,900),(1024,768),(390,844)]:
                size(width,height);time.sleep(.15)
                assert js('document.documentElement.scrollWidth<=innerWidth')
                if team=='Creek XI':shot('universal-roster-'+theme+'-'+str(width)+'.png')
                results.append(dict(page=team,theme=theme,width=width,passed=True))
    assert len(career.directory()['players'])==1
    results.append(dict(existing_id_preserved=True,two_rosters_one_player=True))
    # The universal player appears for both sides in one fantasy game.
    with score.lock:
        innings=[]
        for team,opposition,runs in [('Pavilion XI','Creek XI',14),('Creek XI','Pavilion XI',9)]:
            row=new_innings({**score.data,'team1':team,'team2':opposition})
            row.update(runs=runs,wickets=0,balls=12,extras=0,
                       batters=[dict(name=name,runs=runs,balls=12,active=True,dismissal='not out',shots={},fours=0,sixes=0,dots=0)],
                       bowlers=[dict(name=name,figures='0–'+str(runs),overs='2.0',maidens=0)],
                       samples={'0':0,'12':runs})
            innings.append(row)
            score.packs.save({'lineup':dict(match_id=score.graphics.match_id,team=team,players=[name])})
        score.graphics.innings=innings;score.graphics.previous=copy.deepcopy(score.data)
        score.graphics.config['result_override']='No result';score.graphics.finish(time.time())
    career.stage_current()
    size(1440,900);navigate('/statistics')
    wait("document.querySelector('#resultsReview')?.open&&document.querySelectorAll('[data-result-player]').length===2")
    assert js("[...document.querySelectorAll('[data-identity]')].every(s=>s.value==="+json.dumps(identity)+")")
    shot('universal-result-mapping.png')
    js("const c=document.getElementById('acceptMissing');if(c)c.checked=true;document.getElementById('resultsForm').requestSubmit()")
    wait("!document.getElementById('resultsReview').open")
    p=career.player(identity)['player']
    assert p['matches']==1 and p['innings']==2 and p['runs']==23
    assert p['teams']==['Creek XI','Pavilion XI'] and len(career.directory()['players'])==1
    navigate('/stats');wait("document.querySelector('[data-player]')&&document.querySelector('.universal-badge')")
    js("document.querySelector('[data-player]').click()")
    wait("document.getElementById('detailTitle')?.textContent.includes('(Universal)')")
    assert js("document.getElementById('detailBody').textContent.includes('Pavilion XI / Creek XI')")
    size(390,844);time.sleep(.15);assert js('document.documentElement.scrollWidth<=innerWidth');shot('universal-profile-mobile.png')
    results.append(dict(both_teams_resolve_to_existing_id=True,combined_runs=23,match_count=1,public_universal_profile=True))
    return results
