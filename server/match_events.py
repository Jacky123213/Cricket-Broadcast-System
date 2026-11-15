"""Recorded delivery ledger: COV is a replaceable over snapshot, not an event.

We keep observed tokens, label unknown players honestly and never back-date a
new highlight to guessed footage when attaching to an innings already underway.
"""
import copy
import re


def token_info(token):
    value = token.strip().lower()
    if value == 'w': return {'kind':'wicket','runs':0,'legal':True,'text':'Wicket'}
    if value.isdigit():
        runs=int(value)
        return {'kind':'four' if runs==4 else 'six' if runs==6 else 'dot' if runs==0 else 'runs',
                'runs':runs,'legal':True,'text':'No run' if runs==0 else f'{runs} run'+('' if runs==1 else 's')}
    extra=re.fullmatch(r'(\d*)(wd|wds|nb|b|lb)',value)
    if extra:
        runs=int(extra[1] or 1); kind=extra[2]
        return {'kind':'extra','runs':runs,'legal':kind in ('b','lb'),
                'text':f'{runs} '+{'wd':'wide','wds':'wide','nb':'no-ball','b':'bye','lb':'leg bye'}[kind]+('s' if runs!=1 else '')}
    return {'kind':'unknown','runs':None,'legal':None,'text':token}


def record_deliveries(current, score, previous, now):
    from .broadcast_graphics import balls
    history=current.setdefault('delivery_history',{})
    valid=set()
    latest=[]
    for over_key,tokens in current.get('over_tokens',{}).items():
        over=int(over_key); legal=0
        for index,token in enumerate(tokens[:80]):
            info=token_info(token); key=f'{over}:{index}'
            ball=over*6+legal+1
            if info['legal']: legal+=1
            valid.add(key); latest.append((over,index,key))
            old=history.get(key)
            if old and old['token']==token: continue
            # Only the latest newly observed delivery can be timestamped now.
            # Full historical over snapshots can reconstruct outcomes, not video.
            prior=previous or {}; latest_score_ball=(current.get('balls') or 0)
            before=balls(prior.get('overs',''))
            recent=bool(previous and before is not None and 0<=latest_score_ball-before<=1)
            striker=prior.get('striker','none')
            batter=prior.get('batter'+striker+'_name','') if striker in ('1','2') else ''
            if not batter and previous:
                changed=[score.get(f'batter{s}_name','') for s in (1,2) if score.get(f'batter{s}_name')==prior.get(f'batter{s}_name') and score.get(f'batter{s}_balls')!=prior.get(f'batter{s}_balls')]
                if len(changed)==1: batter=changed[0]
            history[key]={'id':key,'over':over+1,'ball':f'{over}.{min(6,max(1,legal if info["legal"] else legal+1))}',
                          'legal_ball':ball,'token':token,**info,'batter':old.get('batter','') if old else batter if recent else '',
                          'bowler':old.get('bowler','') if old else (prior.get('bowler') or score.get('bowler','')) if recent else '',
                          'at':old.get('at') if old else None}
    # Remove corrected/undone tokens. Stable IDs prevent duplicate boundaries.
    current['delivery_history']={k:v for k,v in history.items() if k in valid}
    if latest and previous:
        last=current['delivery_history'][max(latest)[2]]
        if last['at'] is None and (previous.get('overs'),previous.get('runs'),previous.get('wickets'),previous.get('deliveries')) != (score['overs'],score['runs'],score['wickets'],score['deliveries']):
            # Do not timestamp old snapshots arriving after a multi-ball gap.
            before=balls(previous.get('overs',''))
            if before is not None and 0 <= (current['balls'] or 0)-before <= 1:
                last['at']=now


def deliveries(current):
    rows=sorted(copy.deepcopy(list(current.get('delivery_history',{}).values())),key=lambda r:(r['over'],int(r['id'].split(':')[1])))
    for row in rows:
        if row['kind']!='wicket': continue
        wicket=next((e for e in reversed(current.get('wicket_events',[])) if e['balls']==row['legal_ball']),None)
        if not wicket: continue
        player=next((b for b in current['batters'] if b.get('out_number')==wicket['number']),None)
        row['wicket_number']=wicket['number']
        if player:
            row.update(batter=player['name'],dismissal=player.get('dismissal') or 'Out',batter_runs=player.get('runs'),batter_balls=player.get('balls'))
        if wicket.get('delivery_runs')==6:
            row.update(kind='wicket',runs=6,text='6 and Out')
    return rows
