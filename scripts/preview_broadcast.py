"""Opt-in visual test server. All sample data stays in an isolated temp folder."""
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import uvicorn
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from server.config import Settings
from server.main import create_app
from server.scoreboard_state import DEFAULT, State


def serve(state, root):
    app = create_app(Settings(database_path=root/'drs.db', port=8871, ssl_certfile=None,
                              ssl_keyfile=None), scoreboard=state)
    if '--camera-test' in sys.argv:
        # Opt-in synthetic camera; never mounted by the production application.
        app.mount('/test-assets', StaticFiles(directory=ROOT/'tests'/'fixtures'))

        @app.get('/test-camera', include_in_schema=False)
        async def test_camera():
            page = (ROOT/'frontend'/'camera'/'index.html').read_text('utf-8')
            return HTMLResponse(page.replace('</head>',
                '<script src="/test-assets/broadcast-camera.js"></script></head>'))
    with patch('server.main.start_receiver'):
        uvicorn.run(app, host='127.0.0.1', port=8871, log_level='warning')


def main():
    (ROOT / '.preview').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='graphics-', dir=ROOT / '.preview') as directory:
        root = Path(directory)
        state = State(root / 'scores')
        if '--live' in sys.argv or '--camera-test' in sys.argv:
            state.save({**DEFAULT, 'source': 'manual', 'team1': 'Pavilion XI', 'team2': 'Creek XI',
                        'runs': '66', 'wickets': '3', 'overs': '10.2', 'color1': '#14b8a6',
                        'color2': '#f6b342', 'batter1_name': 'A. Rivers', 'batter2_name': 'M. Reid',
                        'batter1_runs': '35', 'batter2_runs': '16', 'batter1_balls': '29',
                        'batter2_balls': '12', 'striker': '1', 'bowler': 'J. Hart',
                        'bowler_figures': '2–24', 'bowler_overs': '4.0'})
            state.flush()
            state.broadcast_settings({'rotation_mode': 'automatic', 'auto_drinks': False})
            serve(state, root)
            return
        state.save({**DEFAULT, 'source': 'manual', 'team1': 'Pavilion XI', 'team2': 'Creek XI',
                    'runs': '132', 'wickets': '5', 'overs': '20.0', 'batter1_name': 'A. Rivers',
                    'batter1_runs': '35', 'batter1_balls': '29', 'batter2_name': 'M. Reid',
                    'batter2_runs': '16', 'batter2_balls': '12', 'striker': '1',
                    'bowler': 'J. Hart', 'bowler_figures': '2–24', 'bowler_overs': '4.0',
                    'banner': 'Backyard Cricket · Summer series', 'color1': '#14b8a6', 'color2': '#f6b342'})
        state.graphics.flush(time.time(), force=True)
        state.broadcast_stats({'innings': 0, 'extras': 7, 'fours': 12, 'sixes': 3,
            'over_runs': [1, 6, 11, 13, 7, 6, 4, 8, 5, 6, 8, 5, 9, 10, 3, 4, 5, 6, 7, 8],
            'batters': [{'name': 'L. Hayes', 'dismissal': 'c Hart b Lane', 'runs': 24, 'balls': 21},
                        {'name': 'J. Finch', 'dismissal': 'b Stone', 'runs': 7, 'balls': 10},
                        {'name': 'S. Blake', 'dismissal': 'lbw b Lane', 'runs': 28, 'balls': 23},
                        {'name': 'A. Rivers', 'dismissal': 'not out', 'runs': 35, 'balls': 29},
                        {'name': 'T. Moss', 'dismissal': 'run out (Hart)', 'runs': 4, 'balls': 8},
                        {'name': 'P. Woods', 'dismissal': 'c Reid b Hart', 'runs': 11, 'balls': 17},
                        {'name': 'M. Reid', 'dismissal': 'not out', 'runs': 16, 'balls': 12},
                        *[{'name': name, 'dismissal': '', 'runs': None, 'balls': None} for name in ['D. West','R. Page','C. Shaw','K. Lee']]],
            'bowlers': [{'name': 'J. Hart', 'figures': '2–24', 'overs': '4.0'},
                        {'name': 'C. Lane', 'figures': '2–30', 'overs': '4.0'},
                        {'name': 'F. Stone', 'figures': '1–18', 'overs': '4.0'}]})
        state.broadcast_action({'action': 'start_chase'})
        state.save({'runs': '136', 'wickets': '4', 'overs': '19.2'})
        state.graphics.flush(time.time(), force=True)
        state.broadcast_stats({'innings': 1, 'extras': 5,
            'batters': [{'name': 'C. Lane', 'dismissal': 'b Lee', 'runs': 44, 'balls': 40},
                        {'name': 'J. Hart', 'dismissal': 'c Reid b West', 'runs': 27, 'balls': 25},
                        {'name': 'B. Holt', 'dismissal': 'not out', 'runs': 42, 'balls': 30},
                        {'name': 'F. Stone', 'dismissal': 'not out', 'runs': 18, 'balls': 19}],
            'bowlers': [{'name': 'K. Lee', 'figures': '2–28', 'overs': '4.0'},
                        {'name': 'D. West', 'figures': '1–32', 'overs': '4.0'},
                        {'name': 'C. Shaw', 'figures': '1–21', 'overs': '3.0'}]})
        state.broadcast_settings({'auto_summary': False})
        state.broadcast_action({'action': 'show', 'kind': 'match_summary'})
        serve(state, root)


if __name__ == '__main__': main()
