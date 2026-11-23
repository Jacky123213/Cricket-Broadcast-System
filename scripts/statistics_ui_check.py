"""Focused browser workflows; called with disposable data by operator_ui_check."""
import time


def check_ui(app, output, js, wait, size, navigate, shot):
    score=app.state.scoreboard
    score.graphics.config['result_override']='No result'
    score.graphics.finish(time.time())
    app.state.career_stats.stage_current()
    size(1440,900);navigate('/')
    wait("document.querySelector('#resultsReview')?.open")
    shot('results-review-dark.png')
    js("window.CricketPreferences.save({theme:'light'})")
    size(390,844);time.sleep(.3)
    assert js('document.documentElement.scrollWidth<=innerWidth')
    assert js("document.getElementById('resultsReview').getBoundingClientRect().width<=innerWidth")
    shot('results-review-mobile-light.png')
    js("document.getElementById('resultOutcome').value='no_result';document.getElementById('resultOutcome').dispatchEvent(new Event('change'));const c=document.getElementById('acceptMissing');if(c)c.checked=true;document.getElementById('resultsForm').requestSubmit()")
    wait("!document.getElementById('resultsReview').open")
    records=app.state.career_stats.directory()
    assert len(records['matches'])==1 and records['players']
    results=[dict(completed_match_prompt=True,explicit_submit=True,mobile_dialog=True)]
    size(1440,900)
    wait("document.getElementById('matchDayFrame').contentWindow.CricketProgram===undefined&&document.getElementById('matchDayFrame').contentDocument?.getElementById('programPreview')")
    js("document.querySelector('[data-view=statistics]').click()")
    wait("document.getElementById('statisticsFrame').contentDocument?.getElementById('recordCount')?.textContent.includes('1 confirmed')")
    wait("document.getElementById('matchDayFrame').contentDocument.getElementById('programPreview').contentWindow.CricketProgram?.health().preview_suspended===true")
    results.append(dict(hidden_match_day_decoder_suspended=True,sidebar_statistics=True))
    for route in ['/live#scorecard','/live#balls','/live#graphs','/live#summary','/stats']:
        navigate(route)
        wait("document.getElementById('teams')?.children.length||document.querySelector('[data-player]')")
        for theme in ['dark','light']:
            js("window.CricketPreferences.save({theme:'"+theme+"'})")
            for width,height in [(1440,900),(1024,768),(390,844)]:
                size(width,height);time.sleep(.12)
                assert js('document.documentElement.scrollWidth<=innerWidth'),(route,theme,width)
                assert js("document.documentElement.dataset.theme") == theme
                results.append(dict(route=route,theme=theme,width=width,passed=True))
                if width==1440 or width==390:shot(route.replace('/','').replace('#','-')+'-'+theme+'-'+str(width)+'.png')
        if route=='/live#scorecard':
            js("document.getElementById('shareLive').click()")
            wait("document.getElementById('shareLiveAddress').value.includes('/live#scorecard')")
        if route=='/stats':
            js("document.querySelector('[data-player]').click()")
            wait("document.getElementById('statsDetail').open&&document.querySelector('#detailBody .metric-grid')")
            assert js('document.documentElement.scrollWidth<=innerWidth')
            shot('player-profile-mobile.png')
    navigate('/statistics')
    wait("document.getElementById('recordCount')?.textContent.includes('1 confirmed')")
    js("document.querySelector('[data-review]').click()")
    wait("document.querySelector('#replaceResult')?.required")
    js("document.querySelector('#resultsReview [data-later]').click()")
    assert len(app.state.career_stats.directory()['matches'])==1
    results.append(dict(read_only_profiles_and_scorecards=True,lan_live_share=True,correction_confirmation=True,later_does_not_double_count=True))
    return results
