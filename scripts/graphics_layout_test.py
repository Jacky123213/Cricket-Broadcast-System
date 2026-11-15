"""Real WebView2 layout regression checks with synthetic, isolated match data."""
from __future__ import annotations

import json
import time
from pathlib import Path


FRAME_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Graphics layout diagnostics</title>
<style>html,body{margin:0;padding:0}iframe{display:block;border:0}</style></head><body>
<iframe id="stage" width="1280" height="720" srcdoc="&lt;!doctype html&gt;&lt;html&gt;&lt;head&gt;&lt;link rel='stylesheet' href='/style.css'&gt;&lt;link rel='stylesheet' href='/scoreboard-assets/graphics.css'&gt;&lt;style&gt;*,*:before,*:after{animation:none!important;transition:none!important}body{background:#172034}&lt;/style&gt;&lt;/head&gt;&lt;body class='overlay-body'&gt;&lt;section id='statGraphic' hidden&gt;&lt;/section&gt;&lt;aside id='breakGraphic' hidden&gt;&lt;/aside&gt;&lt;aside id='wicketGraphic' hidden&gt;&lt;/aside&gt;&lt;aside id='powerSurge' hidden&gt;&lt;/aside&gt;&lt;script src='/scoreboard-assets/graphic-renderer.js'&gt;&lt;/script&gt;&lt;/body&gt;&lt;/html&gt;"></iframe></body></html>"""

FIXTURE = """(()=>{
const f=document.getElementById('stage'),w=f.contentWindow;
const batter=(name,runs,balls)=>({name,runs,balls,active:runs===20,dismissal:runs===20?'not out':'b Bowler'});
const bowlers=Array.from({length:4},(_,i)=>({name:'Bowler '+(i+1),figures:(3-i)+'–'+(10+i),overs:'2.0',wickets:3-i,runs:10+i,economy:(10+i)/2}));
const first={team:'Blue XI',opposition:'Red XI',color:'#0055ff',opposition_color:'#ed3479',logo:'',opposition_logo:'',runs:42,wickets:0,overs:'5.0',balls:30,extras:5,run_rate:8.4,batters:[batter('P 2',20,17),batter('P 1',17,15)],bowlers,chart:[]};
const second={...first,team:'Red XI',opposition:'Blue XI',color:'#ed3479',opposition_color:'#0055ff',runs:45,wickets:3,overs:'3.1',balls:19,run_rate:14.21,batters:[batter('P 13',20,9),batter('P 12',18,5),batter('P 15',7,4),batter('P 14',0,1)],bowlers:bowlers.slice(0,2)};
window.layoutFixture={first,second,batter,bowlers};return true;
})()"""

MEASURE = """(()=>{
const d=document.getElementById('stage').contentDocument,box=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height}};
const failures=[];const inside=(inner,outer)=>inner.x>=outer.x-.6&&inner.y>=outer.y-.6&&inner.right<=outer.right+.6&&inner.bottom<=outer.bottom+.6;
for(const section of d.querySelectorAll('.summary-innings')){
 const sectionBox=box(section),players=section.querySelector('.summary-players'),playerBox=box(players);
 if(!inside(playerBox,sectionBox))failures.push('Player area outside innings');
 for(const list of players.children){const listBox=box(list);for(const row of list.querySelectorAll('.summary-player')){
  if(!inside(box(row),listBox)||!inside(box(row),sectionBox))failures.push('Row outside box: '+row.textContent);
  for(const text of row.children)if(!inside(box(text),box(row)))failures.push('Text outside row: '+text.textContent);
 }}
}
const body=d.querySelector('.summary-body'),result=d.querySelector('.result-band');if(body&&box(body).bottom>box(result).y)failures.push('Summary overlaps result');
return {width:d.defaultView.innerWidth,height:d.defaultView.innerHeight,failures,lastBatter:d.querySelector('.summary-innings:last-child .summary-list:first-child .summary-player:last-child')?.textContent,rows:d.querySelectorAll('.summary-player').length};
})()"""


def draw_script(width, height, long_names=False):
    setup = """(()=>{const f=document.getElementById('stage'),s=window.layoutFixture;f.width=WIDTH;f.height=HEIGHT;
    const first=structuredClone(s.first),second=structuredClone(s.second);
    if(LONG){first.batters=second.batters=Array.from({length:4},(_,i)=>s.batter('Very long batter name '+i+' abcdefghijklmnopqrstuvwxyz'.repeat(3),20-i,i+1));first.bowlers=second.bowlers=s.bowlers;}
    f.contentWindow.BackyardGraphics.render({active:{kind:'match_summary',innings:1,reason:'Manual'},innings:[first,second],result:'Red XI wins by 7 wickets',config:{match_title:'BACKYARD CRICKET',venue:''}},{visible:true});return true;})()"""
    return setup.replace("WIDTH", str(width)).replace("HEIGHT", str(height)).replace("LONG", "true" if long_names else "false")


def check_graphics_layout(window, origin: str, output: Path):
    window.load_url(origin + "/diagnostic-graphics")
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if window.evaluate_js("!!document.getElementById('stage')?.contentWindow?.BackyardGraphics"):
            break
        time.sleep(.1)
    else:
        raise RuntimeError("Graphics regression renderer did not load")
    window.evaluate_js(FIXTURE)
    cases = []
    for width, height in [(2560,1326),(1920,1080),(1366,768),(1280,720),(1024,768),(1920,600),(844,390),(390,844)]:
        for rows in ("photo", "four-long-names"):
            window.evaluate_js(draw_script(width, height, rows != "photo"))
            # Wait for frame viewport and container-query font metrics to settle.
            time.sleep(.06)
            measured = window.evaluate_js(MEASURE)
            if measured["failures"] or measured["width"] != width or measured["height"] != height:
                raise AssertionError(f"Summary layout {width}×{height} ({rows}): {measured}")
            if rows == "photo" and not measured["lastBatter"].startswith("P 14"):
                raise AssertionError("The fourth batter must stay present, not be hidden to avoid overflow")
            cases.append({"width":width,"height":height,"scenario":rows,"rows":measured["rows"],"passed":True})
    return cases


def capture_headless(output: Path):
    """Source-only visual QA in an isolated Edge profile, not the user's browser."""
    import os
    import subprocess
    import tempfile
    import threading
    import uvicorn
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, FileResponse
    from server.app_paths import RESOURCE_ROOT
    from run import wait_for_server
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    edge = Path(os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)'))/'Microsoft'/'Edge'/'Application'/'msedge.exe'
    if not edge.is_file():
        raise RuntimeError('Edge executable unavailable for source-only visual captures')
    app = FastAPI()

    @app.get('/')
    def fixture(width: int = 2560, height: int = 1326):
        if (width,height) not in ((2560,1326),(1920,600)):
            return HTMLResponse('Unknown test size',status_code=400)
        script = "<script>const ready=setInterval(()=>{if(!document.getElementById('stage').contentWindow.BackyardGraphics)return;clearInterval(ready);"+FIXTURE+";"+draw_script(width,height)+";document.title='Graphics capture ready';},20);</script>"
        return HTMLResponse(FRAME_PAGE.replace('</body>',script+'</body>'))

    @app.get('/style.css')
    def base_css():
        return FileResponse(RESOURCE_ROOT/'frontend'/'scoreboard'/'style.css')

    @app.get('/scoreboard-assets/graphics.css')
    def graphics_css():
        return FileResponse(RESOURCE_ROOT/'frontend'/'scoreboard'/'graphics.css')

    @app.get('/scoreboard-assets/graphic-renderer.js')
    def renderer():
        return FileResponse(RESOURCE_ROOT/'frontend'/'scoreboard'/'graphic-renderer.js')

    server = uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=0,log_config=None))
    thread = threading.Thread(target=server.run,daemon=True)
    thread.start()
    try:
        wait_for_server(server,thread)
        port = server.servers[0].sockets[0].getsockname()[1]
        # This profile is created solely for these captures and contains no
        # saved match/user browser data. It stays in the disposable test folder.
        profile = Path(tempfile.mkdtemp(prefix='edge-qa-',dir=output))
        for width,height in ((2560,1326),(1920,600)):
            path = output/f'summary-{width}x{height}.png'
            result = subprocess.run([str(edge),'--headless','--disable-gpu','--no-first-run','--no-default-browser-check',
                '--disable-background-networking','--no-proxy-server','--disable-extensions','--hide-scrollbars',
                '--virtual-time-budget=2000',f'--user-data-dir={profile}',f'--window-size={width},{height}',f'--screenshot={path}',
                f'http://127.0.0.1:{port}/?width={width}&height={height}'],capture_output=True,timeout=45)
            if result.returncode or not path.is_file():
                raise RuntimeError('Headless graphics capture failed: '+result.stderr.decode(errors='replace')[-600:])
            print(path)
    finally:
        server.should_exit=True
        thread.join(5)


if __name__ == '__main__':
    import argparse
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    parser=argparse.ArgumentParser()
    parser.add_argument('--screenshots',type=Path,required=True)
    args=parser.parse_args()
    capture_headless(args.screenshots)
