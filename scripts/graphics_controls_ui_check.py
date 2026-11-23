"""Native responsive checks for graphics controls, image uploads and identity."""
import base64
import json
import time


def check_ui(app,output,js,wait,size,navigate,shot):
    import cv2
    import numpy as np
    score=app.state.scoreboard
    results=[]
    score.match_teams(dict(home_team='Pavilion XI',away_team='Creek XI'))
    for name,abbr,color in [('Pavilion XI','PAV','#35a7df'),('Creek XI','CRK','#00e76c')]:
        score.save_team(dict(name=name,abbreviation=abbr,color=color,logo=''))
    image=np.full((135,1920,3),(43,54,7),dtype=np.uint8)
    cv2.putText(image,'LOCAL SPONSOR BANNER',(60,85),cv2.FONT_HERSHEY_SIMPLEX,2,(110,241,204),3)
    ok,data=cv2.imencode('.png',image);assert ok
    encoded='data:image/png;base64,'+base64.b64encode(data.tobytes()).decode()
    url=score.packs.upload(encoded)
    score.packs.save({'details':dict(sponsor_image=url,coming_title='Tomorrow at the oval',coming_subtitle='Next match',sponsor_caption='Old description should be absent')})
    score.save_branding(dict(logo=encoded,visible=True))
    size(1440,900);navigate('/teams')
    wait("document.querySelector('#teamEditor [name=abbreviation]')?.value==='PAV'")
    js("document.querySelector('#teamEditor [name=abbreviation]').value='PVXI';document.getElementById('teamEditor').requestSubmit()")
    wait("document.getElementById('workspaceStatus').textContent.includes('saved')")
    assert score.snapshot()['score']['abbr1']=='PVXI'
    results.append(dict(abbreviation_saved_on_named_team=True))
    for route in ['teams','graphics']:
        navigate('/'+route)
        wait("document.querySelectorAll('.image-upload-hint').length>1")
        for theme in ['dark','light']:
            js('CricketPreferences.save({theme:'+json.dumps(theme)+'})')
            for width,height in [(1440,900),(1024,768),(390,844)]:
                size(width,height)
                time.sleep(.35)
                if route=='graphics':js("document.getElementById('tab-content').click()")
                state=js("({width:innerWidth,scroll:document.documentElement.scrollWidth,hints:[...document.querySelectorAll('input[type=file]')].filter(i=>i.accept.includes('image/')).every(i=>document.getElementById(i.getAttribute('aria-describedby'))?.textContent.includes('Max 1 MB'))})")
                assert state['scroll']<=width+1 and state['hints'],(route,theme,state)
                results.append(dict(route=route,theme=theme,width=width,all_image_guidance=True,no_overflow=True))
                if width in (1440,390):shot(route+'-uploads-'+theme+'-'+str(width)+'.png')
    size(1440,900);navigate('/match-setup')
    wait("document.querySelector('[name=home_team]')?.value==='Pavilion XI'")
    assert js("document.querySelector('[name=away_team]').value")=='Creek XI'
    assert js("document.querySelector('#matchTeams [name=team1]')===null")
    score.broadcast_action({'action':'end_innings'})
    score.broadcast_action({'action':'start_chase'})
    navigate('/match-setup')
    wait("document.querySelector('[name=home_team]')?.value==='Pavilion XI'")
    assert js("document.querySelector('[name=away_team]').value")=='Creek XI'
    assert score.snapshot()['score']['abbr1']=='CRK'
    results.append(dict(home_away_fixed_after_chase=True,abbreviation_follows_batting_swap=True))
    navigate('/graphics')
    wait("document.querySelector('[data-kind=blank]')")
    for kind in ['blank','coming_up','sponsor']:
        js("document.querySelector('[data-kind="+kind+"]').click()")
        assert js("document.querySelector('[name=previewTeam]').closest('label').hidden")
        assert js("document.querySelector('[name=previewPlayer]').closest('label').hidden")
        assert js("document.querySelector('[name=previewInnings]').closest('label').hidden")
        results.append(dict(kind=kind,irrelevant_choices_hidden=True))
    assert js("!document.querySelector('[name=sponsor_caption]')&&!document.querySelector('[name=sponsor_name]')")
    for pack in ['bbl','fox_odi']:
        score.broadcast_settings({'pack':pack})
        score.broadcast_action({'action':'show','kind':'coming_up','team':'Creek XI'})
        navigate('/overlay')
        wait("!document.getElementById('breakGraphic')?.hidden&&document.querySelector('.fox-mini small')?.textContent==='COMING UP'")
        assert js("document.getElementById('breakGraphic').style.getPropertyValue('--graphic-team')")=='#f0f3ff'
        assert js("!document.querySelector('.fox-mini-logo')")
        results.append(dict(pack=pack,neutral_coming_up=True))
        score.broadcast_action({'action':'show','kind':'sponsor'})
        wait("document.querySelector('.fox-sponsor-logo')?.complete")
        for width,height in [(1920,1080),(1024,768),(390,844)]:
            size(width,height)
            measure=js("(()=>{const e=document.getElementById('breakGraphic'),i=e.querySelector('img'),r=e.getBoundingClientRect(),s=i.getBoundingClientRect();return {width:r.width,left:r.left,image:s.width,height:r.height,imageHeight:s.height,text:e.textContent,inner:innerWidth,bottom:r.bottom,screen:innerHeight};})()")
            assert abs(measure['width']-width)<1 and abs(measure['left'])<1,measure
            assert abs(measure['image']-width)<1 and abs(measure['imageHeight']-measure['height'])<1,measure
            assert measure['text']=='' and abs(measure['bottom']-height)<1,measure
            results.append(dict(pack=pack,width=width,sponsor_fills_entire_row=True))
            if width==1920:shot(pack+'-sponsor.png')
        score.broadcast_action({'action':'show','kind':'blank'})
        wait("['scorebar','statGraphic','breakGraphic','wicketGraphic','powerSurge','connection','packEvent'].every(id=>document.getElementById(id).hidden)")
        assert js("getComputedStyle(document.body).backgroundColor")=='rgba(0, 0, 0, 0)'
        results.append(dict(pack=pack,blank_overlay_fully_empty=True))
        score.graphics.show('wicket_card',time.time(),reason='Automatic')
        assert score.graphics.active['kind']=='blank'
    navigate('/broadcast?delay=0')
    wait("document.getElementById('graphic')?.contentDocument?.getElementById('scorebar')?.hidden")
    wait("document.getElementById('broadcastLogo')?.hasAttribute('src')")
    assert js("document.getElementById('broadcastLogo').hidden")
    score.broadcast_action({'action':'hide'})
    wait("!document.getElementById('broadcastLogo').hidden")
    results.append(dict(blank_hides_watermark_then_clear_restores_it=True))
    return results
