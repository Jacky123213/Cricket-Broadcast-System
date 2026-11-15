"""Export only reviewed application source, with hashes matching the installer."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile


def package(root: Path):
    sys.path.insert(0, str(root))
    from server.build_info import APP_VERSION
    output = root/'dist'
    setup = output/'CricketBroadcastSystem-Setup.exe'
    staging = root/'.installer-test'/('release-source-'+APP_VERSION)
    if staging.exists():
        raise RuntimeError('Choose a fresh release staging folder; an existing snapshot is never overwritten')
    if not setup.is_file():
        raise RuntimeError('Build and verify the installer first')
    staging.mkdir(parents=True)
    allowed = {'.py', '.js', '.css', '.html', '.cjs', '.svg', '.txt', '.md', '.ps1', '.iss', '.spec', '.bat'}
    files = []
    for folder in ('frontend', 'server', 'scripts', 'tests', 'packaging'):
        for path in sorted((root/folder).rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            rel = path.relative_to(root).as_posix()
            if path.suffix not in allowed:
                if rel != 'frontend/assets/duck-out.mp4' or hashlib.sha256(path.read_bytes()).hexdigest() != 'd84467011e2a5d2c2ec625558531979d14d6e6308eeaf9f6c1e767268702aa4d':
                    raise RuntimeError('Unreviewed source asset: '+rel)
            files.append(path)
    files += [p for p in sorted(root.iterdir()) if p.is_file() and (p.suffix in {'.md', '.bat'} or p.name in {'.gitattributes', '.gitignore', 'run.py', 'requirements.txt', 'requirements-dev.txt', 'requirements-build.txt'})]
    records=[]
    for path in sorted(set(files)):
        relative=path.relative_to(root)
        target=staging/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        raw=path.read_bytes()
        git_bytes=raw if path.suffix=='.mp4' else raw.replace(b'\r\n', b'\n')
        records.append(dict(path=relative.as_posix(), size=path.stat().st_size, sha256=hashlib.sha256(raw).hexdigest(), git_sha256=hashlib.sha256(git_bytes).hexdigest()))
    # Every shipped front-end byte must match its reviewed source byte.
    for row in records:
        if row['path'].startswith('frontend/'):
            bundled=output/'CricketBroadcastSystem'/'_internal'/row['path']
            if not bundled.is_file() or hashlib.sha256(bundled.read_bytes()).hexdigest()!=row['sha256']:
                raise RuntimeError('Source/bundle mismatch: '+row['path'])
    base, marker, candidate = APP_VERSION.partition('-rc.')
    windows_version = base+'.'+(candidate if marker and candidate.isdigit() else '0')
    manifest={'version':APP_VERSION,'windows_version':windows_version,'installer_sha256':hashlib.sha256(setup.read_bytes()).hexdigest(),'private_data_included':False,'hash_note':'sha256 matches raw source ZIP/bundle bytes; git_sha256 allows the repository’s LF text normalisation.','files':records}
    (staging/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,indent=2),'utf-8')
    archive=output/f'CricketBroadcastSystem-{APP_VERSION}-source.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(staging.rglob('*')):
            if path.is_file():z.write(path,path.relative_to(staging).as_posix())
    hashes=''.join(hashlib.sha256(p.read_bytes()).hexdigest().upper()+'  '+p.name+'\n' for p in (setup,archive))
    (output/'SHA256SUMS.txt').write_text(hashes,'utf-8')
    print(json.dumps({'version':APP_VERSION,'files':len(records),'archive':str(archive),'staging':str(staging),'installer_sha256':manifest['installer_sha256']},indent=2))


if __name__=='__main__':
    package(Path(__file__).resolve().parents[1])
