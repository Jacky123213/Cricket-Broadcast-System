"""Native recorder -> HTTP ring -> full-file cache -> native decoder diagnostic.

Uses only a synthetic, static canvas (no camera/microphone/device permission).
An early clip download deliberately fails once to verify automatic recovery.
"""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlparse


PAGE = r'''<!doctype html><meta charset="utf-8"><body>
<style>#stage{position:relative;width:640px;height:360px}video,canvas.program-hold{position:absolute;width:100%;height:100%;inset:0}canvas.program-hold{z-index:10}</style><div id="stage"></div>
<script src="/assets/recording.js"></script><script src="/assets/replay-engine.js"></script>
<script src="/broadcast-assets/program-health.js"></script><script src="/broadcast-assets/program-transition.js"></script>
<script src="/broadcast-assets/live-clip-cache.js"></script><script src="/broadcast-assets/buffered-broadcast.js"></script>
<script>
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{let recorder,engine,source,paintTimer;const frames=[],statuses=[],capture=[];
 try{
  const canvas=document.createElement('canvas');canvas.width=1280;canvas.height=720;const ctx=canvas.getContext('2d');const paint=()=>{ctx.fillStyle='#19372a';ctx.fillRect(0,0,1280,720);};paint();paintTimer=setInterval(paint,33);document.body.append(canvas);
  source=canvas.captureStream(30);recorder=new DRSRecorder('synthetic',source,m=>capture.push(m));await recorder.start();
  engine=new DRSBufferedBroadcast('synthetic',document.getElementById('stage'),{onFrame:f=>frames.push({...f,local:performance.now()}),onStatus:m=>statuses.push(m),onBuffering:()=>statuses.push('BUFFERING'),onMute(){}});
  await sleep(26000);
  const health=engine.healthSnapshot(),gaps=frames.slice(1).map((f,i)=>f.local-frames[i].local);
  const result={userAgent:navigator.userAgent,health,frames:frames.length,first:frames[0]||null,last:frames.at(-1)||null,maximumGapMs:Math.max(0,...gaps),monotonic:frames.every((f,i)=>!i||f.at>=frames[i-1].at),statuses:[...new Set(statuses)],capture:[...new Set(capture)],timingTrack:!!recorder.timing};
  await fetch('/result',{method:'POST',body:JSON.stringify(result)});
 }catch(e){await fetch('/result',{method:'POST',body:JSON.stringify({error:e.stack||e.message,frames:frames.length,capture})});}
 finally{clearInterval(paintTimer);engine?.destroy();recorder?.stop();source?.getTracks().forEach(t=>t.stop());}
})();
</script>'''


def check(output, browser='firefox', corrupt=False):
    root = Path(__file__).resolve().parents[1]
    output = Path(output).resolve()
    if root not in output.parents:
        raise ValueError('Use a test folder inside the installer workspace')
    output.mkdir(parents=True, exist_ok=True)
    profile = output/'browser-profile'
    profile.mkdir()
    if browser == 'firefox':
        (profile/'user.js').write_text('user_pref("media.autoplay.default",0);\nuser_pref("media.autoplay.block-webaudio",false);\nuser_pref("browser.shell.checkDefaultBrowser",false);\nuser_pref("network.proxy.type",0);\nuser_pref("datareporting.policy.dataSubmissionEnabled",false);\n', encoding='utf-8')
    event = threading.Event()
    result, clips, files, failures = {}, [], {}, set()
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, content, mime, code=200):
            self.send_response(code)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == '/api/clock':
                at = time.time()*1000
                return self.send(json.dumps(dict(received_ms=at, sent_ms=at)).encode(), 'application/json')
            if path.startswith('/api/broadcast/camera/'):
                with lock:
                    data = dict(server_ms=time.time()*1000, clips=list(clips), available_seconds=len(clips)*2, recorder=None)
                return self.send(json.dumps(data).encode(), 'application/json')
            if path.startswith('/clip/'):
                with lock:
                    # A genuine HTTP error must never be fed to the video decoder.
                    if path.endswith('/2') and path not in failures:
                        failures.add(path)
                        return self.send(b'temporary download error', 'text/plain', 503)
                    content, mime = files[path]
                    if corrupt and path.endswith('/5'):
                        content = b'deliberately invalid recorded clip'
                return self.send(content, mime)
            for prefix, folder in [('/assets/', 'assets'), ('/broadcast-assets/', 'broadcast')]:
                if path.startswith(prefix):
                    name = path[len(prefix):]
                    if '/' in name or '..' in name:
                        return self.send(b'', 'text/plain', 404)
                    file = root/'frontend'/folder/name
                    return self.send(file.read_bytes(), 'application/javascript')
            return self.send(PAGE.encode(), 'text/html; charset=utf-8')

        def do_POST(self):
            body = self.rfile.read(int(self.headers['Content-Length']))
            if self.path.startswith('/api/clips/'):
                params = parse_qs(urlparse(self.path).query)
                with lock:
                    index = len(clips)+1
                    url = '/clip/'+str(index)
                    mime = self.headers['Content-Type']
                    files[url] = (body, mime)
                    clips.append(dict(id=str(index),url=url,mime=mime,start_ms=float(params['start_ms'][0]),end_ms=float(params['end_ms'][0]),audio=params['audio'][0]=='true'))
                return self.send(b'{}', 'application/json')
            result.update(json.loads(body))
            self.send(b'{}', 'application/json')
            event.set()

    class DiagnosticServer(ThreadingHTTPServer):
        def handle_error(self, request, address):
            if not isinstance(sys.exc_info()[1], (ConnectionResetError, BrokenPipeError)):
                super().handle_error(request,address)

    server = DiagnosticServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/'
    if browser == 'firefox':
        args = [r'C:\Program Files\Mozilla Firefox\firefox.exe', '--headless', '--no-remote', '--profile', str(profile), url]
    else:
        edge = Path(os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe'
        args = [str(edge), '--headless', '--no-first-run', '--no-default-browser-check', '--no-proxy-server', '--autoplay-policy=no-user-gesture-required', f'--user-data-dir={profile}', url]
    process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        if not event.wait(55):
            raise RuntimeError('Native playback test timed out')
        result['uploaded_clips'] = len(clips)
        result['forced_download_errors'] = len(failures)
        result['corrupt_clip_test'] = corrupt
        (output/'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result, indent=2), flush=True)
        assert not result.get('error'), result
        assert result['frames'] > 50 and result['monotonic'], result
        assert result['last']['local']-result['first']['local'] > 12000, result
        assert result['maximumGapMs'] < (2500 if corrupt else 1000), result
        assert result['health']['last_frame_age_ms'] < 1000, result
        assert 8 <= result['health']['target_delay_seconds'] <= 10, result
        assert result['health']['download_errors'] == 1, result
        if corrupt:
            assert 0 < result['health']['decode_errors'] <= 3, result
        else:
            assert result['health']['decode_errors'] == 0 and result['health']['recovery_attempts'] == 0, result
        assert result['forced_download_errors'] == 1
    finally:
        process.terminate()
        process.wait(timeout=10)
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    check(sys.argv[1], sys.argv[2] if len(sys.argv)>2 else 'firefox', corrupt='--corrupt' in sys.argv)
