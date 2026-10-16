import hashlib
import ipaddress
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from scripts import generate_certificate as certificates
from server.app_paths import RESOURCE_ROOT, default_data_root
from server.config import Settings
from server.install_support import ensure_https, has_saved_data, import_legacy, load_preferences, write_json_atomic
from server.main import create_app


def hashes(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()}


def legacy_app(root, monkeypatch):
    root.mkdir()
    (root / 'data').mkdir()
    (root / 'data' / 'settings.json').write_text(json.dumps({'team1': 'Old home', 'source': 'manual', 'runs': '42'}))
    (root / 'data' / 'branding.json').write_text(json.dumps({'logo': '', 'visible': False}))
    (root / 'storage').mkdir()
    with sqlite3.connect(root / 'storage' / 'backyard_drs.db') as db:
        db.execute('CREATE TABLE original (name TEXT)')
        db.execute("INSERT INTO original VALUES ('Saved camera')")
    monkeypatch.setattr(certificates, 'local_addresses', lambda: [ipaddress.ip_address('127.0.0.1')])
    certificates.generate_certificates(root / 'certs')
    (root / 'storage' / 'buffer').mkdir()
    (root / 'storage' / 'buffer' / 'old.clip').write_bytes(b'private temporary footage')
    (root / 'data' / 'packets.jsonl').write_text('private receiver log')
    return root


def test_frozen_data_not_in_bundle_or_working_directory(monkeypatch, tmp_path):
    monkeypatch.delenv('CBS_DATA_DIR', raising=False)
    monkeypatch.delenv('DRS_DATA_ROOT', raising=False)
    monkeypatch.setattr('sys.frozen', True, raising=False)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.chdir(tmp_path)
    assert default_data_root() == tmp_path / 'CricketBroadcastSystem'
    settings = Settings()
    assert settings.data_root == tmp_path / 'CricketBroadcastSystem'
    assert settings.database_path == settings.data_root / 'storage' / 'backyard_drs.db'
    assert settings.scoreboard_path == settings.data_root / 'data'
    assert settings.ssl_certfile == settings.data_root / 'certs' / 'server.crt'
    assert settings.data_root != RESOURCE_ROOT


def test_source_paths_remain_compatible(monkeypatch):
    monkeypatch.delenv('CBS_DATA_DIR', raising=False)
    monkeypatch.delenv('DRS_DATA_ROOT', raising=False)
    assert default_data_root() == RESOURCE_ROOT


def test_override_paths_and_explicit_no_tls(tmp_path):
    settings = Settings(data_root=tmp_path, ssl_certfile=None, ssl_keyfile=None)
    assert settings.scoreboard_path == tmp_path / 'data'
    assert settings.ssl_certfile is None
    assert settings.ssl_keyfile is None


def test_relative_data_override_is_rejected(monkeypatch):
    monkeypatch.setenv('CBS_DATA_DIR', 'relative-folder')
    with pytest.raises(ValueError, match='absolute'):
        default_data_root()


def test_import_preserves_old_app_and_keys(tmp_path, monkeypatch):
    old = legacy_app(tmp_path / 'old', monkeypatch)
    original = hashes(old)
    target = tmp_path / 'new'
    report = import_legacy(old, target)
    assert hashes(old) == original
    assert not (target / 'storage' / 'buffer').exists()
    assert not (target / 'data' / 'packets.jsonl').exists()
    for name in ('rootCA.crt', 'rootCA.key.pem', 'server.key.pem'):
        assert (old / 'certs' / name).read_bytes() == (target / 'certs' / name).read_bytes()
        assert (Path(report['backup']) / 'certs' / name).read_bytes() == (old / 'certs' / name).read_bytes()
    with sqlite3.connect(target / 'storage' / 'backyard_drs.db') as db:
        assert db.execute('SELECT name FROM original').fetchone()[0] == 'Saved camera'
    before = hashes(target)
    with pytest.raises(ValueError, match='already has saved data'):
        import_legacy(old, target)
    assert hashes(target) == before


def test_import_rejects_overlapping_folders(tmp_path, monkeypatch):
    old = legacy_app(tmp_path / 'old', monkeypatch)
    with pytest.raises(ValueError, match='separate'):
        import_legacy(old, old / 'new')


def test_import_rejects_damaged_json_without_committing(tmp_path):
    old = tmp_path / 'old'
    (old / 'data').mkdir(parents=True)
    (old / 'data' / 'settings.json').write_text('{broken')
    with pytest.raises(ValueError):
        import_legacy(old, tmp_path / 'new')
    assert not (tmp_path / 'new' / 'data').exists()


def test_import_missing_ca_key_does_not_rotate_ca(tmp_path):
    old = tmp_path / 'old'
    (old / 'certs').mkdir(parents=True)
    (old / 'certs' / 'rootCA.crt').write_bytes(b'incomplete old CA')
    before = hashes(old)
    with pytest.raises(RuntimeError, match='missing'):
        import_legacy(old, tmp_path / 'new')
    assert hashes(old) == before
    assert not (tmp_path / 'new' / 'certs').exists()


def test_https_refresh_preserves_ca_and_server_key(tmp_path, monkeypatch):
    monkeypatch.setattr(certificates, 'local_addresses', lambda: [ipaddress.ip_address('127.0.0.1')])
    ensure_https(tmp_path)
    old = {name: (tmp_path / name).read_bytes() for name in ('rootCA.crt', 'rootCA.key.pem', 'server.key.pem')}
    old_server = (tmp_path / 'server.crt').read_bytes()
    ensure_https(tmp_path)
    assert (tmp_path / 'server.crt').read_bytes() == old_server
    monkeypatch.setattr(certificates, 'local_addresses', lambda: [ipaddress.ip_address('127.0.0.1'), ipaddress.ip_address('192.168.1.50')])
    ensure_https(tmp_path)
    assert all((tmp_path / name).read_bytes() == value for name, value in old.items())
    assert (tmp_path / 'server.crt.previous').read_bytes() == old_server


def test_explicit_certificate_repair_handles_broken_server_certificate(tmp_path, monkeypatch):
    monkeypatch.setattr(certificates, 'local_addresses', lambda: [ipaddress.ip_address('127.0.0.1')])
    ensure_https(tmp_path)
    ca = (tmp_path / 'rootCA.crt').read_bytes()
    (tmp_path / 'server.crt').write_text('damaged')
    ensure_https(tmp_path, refresh=True)
    assert (tmp_path / 'rootCA.crt').read_bytes() == ca
    certificates.load_certificate(tmp_path / 'server.crt')


def test_preferences_never_silently_reset_invalid_file(tmp_path):
    write_json_atomic(tmp_path / 'installation.json', {'setup_complete': True})
    assert load_preferences(tmp_path)['setup_complete']
    (tmp_path / 'installation.json').write_text('broken')
    with pytest.raises(RuntimeError, match='Nothing was reset'):
        load_preferences(tmp_path)


def test_missing_ca_does_not_replace_existing_server_keys(tmp_path):
    (tmp_path / 'server.key.pem').write_bytes(b'old private key must be kept')
    before = hashes(tmp_path)
    with pytest.raises(RuntimeError, match='without its CA'):
        ensure_https(tmp_path)
    assert hashes(tmp_path) == before


def test_default_server_writes_only_to_selected_data_root(tmp_path):
    settings = Settings(data_root=tmp_path)
    app = create_app(settings)
    with patch('server.main.start_receiver'), TestClient(app) as client:
        assert client.post('/api/scoreboard/settings', json={'team1': 'Installed home'}).status_code == 200
        assert (tmp_path / 'data' / 'settings.json').exists()
        assert (tmp_path / 'storage' / 'backyard_drs.db').exists()
        assert app.state.replay_store.root.is_relative_to(tmp_path)
        assert client.get('/local-ca.crt').status_code == 404
        (tmp_path / 'certs').mkdir()
        (tmp_path / 'certs' / 'rootCA.crt').write_bytes(b'only public CA')
        assert client.get('/local-ca.crt').content == b'only public CA'
        assert client.get('/certs/rootCA.key.pem').status_code == 404
        assert client.get('/storage/backyard_drs.db').status_code == 404


def test_second_instance_is_blocked_and_mutex_released():
    from run import DesktopInstance
    first, second = DesktopInstance(), DesktopInstance()
    first.acquire()
    try:
        with pytest.raises(RuntimeError, match='already running'):
            second.acquire()
    finally:
        first.close()
    second.acquire()
    second.close()


def test_download_adapter_uses_selected_folder_and_confirmed_save(tmp_path):
    from types import SimpleNamespace
    from server.desktop_downloads import configure_downloads
    from webview.platforms.edgechromium import EdgeChrome
    dialogs = []
    class Dialog:
        def __init__(self): dialogs.append(self)
        def ShowDialog(self, form): return 1
        def Dispose(self): self.disposed = True
    winforms = SimpleNamespace(SaveFileDialog=Dialog, DialogResult=SimpleNamespace(OK=1))
    args = SimpleNamespace(ResultFilePath='C:\\temp\\clip.mp4', Cancel=False)
    window = SimpleNamespace(pywebview_window=SimpleNamespace(localization={'windows.fileFilter.allFiles': 'All files'}), form=None)
    with patch('webview.platforms.edgechromium.WinForms', winforms), patch('webview.settings', {'ALLOW_DOWNLOADS': True}):
        configure_downloads(tmp_path)
        EdgeChrome.on_download_starting(window, None, args)
    assert dialogs[0].InitialDirectory == str(tmp_path)
    assert dialogs[0].OverwritePrompt is True
    assert dialogs[0].disposed is True


def test_trust_requires_explicit_action_and_is_current_user_only(tmp_path):
    from server.desktop_setup import trust_ca
    path = tmp_path / 'rootCA.crt'
    with patch('server.desktop_setup.subprocess.run') as command, patch('server.desktop_setup.is_ca_trusted', return_value=True):
        trust_ca(path)
        assert command.call_args.args[0] == ['certutil.exe', '-user', '-addstore', 'Root', str(path)]


def test_uninstaller_does_not_delete_user_files():
    script = (RESOURCE_ROOT / 'packaging' / 'CricketBroadcastSystem.iss').read_text()
    assert '[UninstallDelete]' not in script
    assert 'PrivilegesRequired=lowest' in script
    assert 'RuntimePage.Values[0] := False' in script
    assert 'AppMutex=Local\\CricketBroadcastSystem' in script
    assert 'CloseApplications=no' in script
