import ipaddress
import json
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from scripts import generate_certificate as certificates
from server.config import Settings
from server.main import create_app
from server.install_support import load_preferences, write_json_atomic
from server.studio_client import StudioClient, ApprovalRequired, ConnectionError, public_ca, remember_connection, studio_url
from server.studio_network import COOKIE, StudioNetwork, discover_studios


@pytest.fixture
def secure_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(certificates, 'local_addresses', lambda: [ipaddress.ip_address('127.0.0.1')])
    settings = Settings(data_root=tmp_path / 'host', host='127.0.0.1', port=8765)
    certificates.generate_certificates(settings.certificate_dir)
    return settings


def test_host_code_approval_single_use_remember_revoke_and_no_key_transfer(secure_settings):
    app = create_app(secure_settings)
    with TestClient(app, base_url='https://127.0.0.1:8765') as client:
        assert client.post('/api/studio-network/pair', json={'code': '1234', 'name': 'Other PC'}).status_code == 403
        assert client.post('/api/studio-network/settings', json={'name': 'Jack’s PC', 'allow_join': True}).status_code == 200
        code = client.get('/api/studio-network/settings').json()['code']
        paired = client.post('/api/studio-network/pair', json={'code': code, 'name': 'OBS PC'}).json()
        assert paired['studio']['name'] == 'Jack’s PC'
        assert len(paired['token']) > 30
        assert client.post('/api/studio-network/pair', json={'code': code, 'name': 'Unapproved'}).status_code == 403
        assert client.post('/api/studio-network/ticket', headers={'Authorization': 'Bearer wrong'}).status_code == 401
        joined = client.post('/api/studio-network/join', json={'ticket': paired['ticket']}, follow_redirects=False)
        assert joined.status_code == 303
        cookie = joined.headers['set-cookie']
        assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=strict' in cookie
        assert client.post('/api/studio-network/join', json={'ticket': paired['ticket']}).status_code == 401
        assert client.get('/api/app-status').status_code == 200
        assert client.get('/api/studio-network/settings').status_code == 403  # joined clients cannot approve more PCs
        client.cookies.clear()
        saved = json.loads((secure_settings.data_root/'studio-network.json').read_text())
        assert paired['token'] not in json.dumps(saved)  # host stores only hashes
        identifier = next(iter(saved['clients']))
        client.delete('/api/studio-network/clients/'+identifier)
        assert client.post('/api/studio-network/ticket', headers={'Authorization': 'Bearer '+paired['token']}).status_code == 401
        client.cookies.set(COOKIE, paired['token'])
        assert client.get('/api/scoreboard/state').status_code == 401
        with pytest.raises(Exception):
            with client.websocket_connect('/ws/umpire?console_id=revoked'):
                pass
        client.cookies.clear()
        # Browser camera/umpire/OBS access remains as before, not role-restricted.
        assert client.get('/umpire').status_code == 200
        assert client.get('/broadcast').status_code == 200
        assert client.get('/certs/rootCA.key.pem').status_code == 404


def test_codes_expire_attempts_bounded_and_tls_required(secure_settings):
    studio = StudioNetwork(secure_settings)
    studio.configure('Host', True)
    code = studio.code
    studio.code_until = 0
    with pytest.raises(Exception) as error:
        studio.pair(code, 'Client', '192.168.1.5')
    assert error.value.status_code == 403
    studio.rotate_code()
    for _ in range(4):
        with pytest.raises(Exception):
            studio.pair('WRONG', 'Client', '192.168.1.5')
    with pytest.raises(Exception) as error:
        studio.pair(studio.code, 'Client', '192.168.1.5')
    assert error.value.status_code == 429
    app = create_app(secure_settings)
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        assert client.post('/api/studio-network/pair', json={'code': 'WRONG', 'name': 'Client'}).status_code == 403


def test_host_management_local_only_and_cross_site_denied(secure_settings):
    app = create_app(secure_settings)
    with TestClient(app, base_url='https://127.0.0.1:8765') as client:
        assert client.post('/api/studio-network/settings', json={'name': 'Host', 'allow_join': True}, headers={'Origin': 'https://evil.example'}).status_code == 403
        assert client.post('/api/studio-network/settings', json={'name': 'Host', 'allow_join': True}, headers={'Origin': 'https://127.0.0.1:8765'}).status_code == 200
    with TestClient(app, base_url='https://192.168.1.68:8765', client=('192.168.1.80',12345)) as client:
        assert client.get('/api/studio-network/settings').status_code == 403
        assert client.get('/api/studio-network/info').status_code == 200
        assert 'code' not in client.get('/api/studio-network/info').json()


def test_approved_connections_survive_host_restart_and_new_joins_can_be_off(secure_settings):
    first = StudioNetwork(secure_settings)
    first.configure('Remembered host', True)
    pair = first.pair(first.code, 'Client', '192.168.1.5')
    first.configure('Remembered host', False)
    second = StudioNetwork(secure_settings)
    ticket = second.issue_ticket(pair['token'])['ticket']
    assert second.consume_ticket(ticket) == pair['token']
    assert second.public()['name'] == 'Remembered host'
    assert second.public()['allow_join'] is False
    second.revoke(next(iter(second.state['clients'])))
    with pytest.raises(Exception):
        second.issue_ticket(pair['token'])


@pytest.mark.parametrize('value', ['http://192.168.1.5:8765', 'https://example.com', 'https://8.8.8.8',
                                'https://user:password@192.168.1.5', 'https://192.168.1.5/?token=secret',
                                'https://192.168.1.5:99999', 'https://192.168.1.5/api/reset', 'https://0.0.0.0'])
def test_client_rejects_public_insecure_or_credential_urls(value):
    with pytest.raises(ValueError):
        studio_url(value)


def test_client_normalizes_manual_address():
    assert studio_url('192.168.1.68') == 'https://192.168.1.68:8765'
    assert studio_url('https://192.168.1.68:8765/umpire') == 'https://192.168.1.68:8765'


def test_public_certificate_only_and_client_saved_without_keys(secure_settings, tmp_path):
    ca = secure_settings.certificate_dir/'rootCA.crt'
    der, fingerprint, pem = public_ca(ca)
    assert len(fingerprint) == 64 and pem.startswith('-----BEGIN CERTIFICATE')
    with pytest.raises(ValueError):
        public_ca(secure_settings.certificate_dir/'rootCA.key.pem')
    client = StudioClient('https://127.0.0.1:8765', ca)
    network = StudioNetwork(secure_settings)
    network.configure('Host', True)
    result = network.pair(network.code, 'Client', '127.0.0.1')
    client_root = tmp_path/'client'
    remember_connection(client_root, client, result)
    pref = load_preferences(client_root)
    assert pref['studio_mode'] == 'connect'
    assert Path(pref['connection']['ca']).read_bytes() == der
    assert not (client_root/'certs').exists()
    assert not (client_root/'data').exists()
    assert not (client_root/'storage').exists()
    assert not list(client_root.rglob('*.pem'))


def test_discovery_reply_is_local_and_nonce_matched(secure_settings, monkeypatch):
    from server.studio_network import DISCOVERY_PORT
    monkeypatch.setattr('server.network.discover_local_ips', lambda: ['127.0.0.1'])
    network = StudioNetwork(secure_settings)
    network.configure('Nearby studio', True)
    # Loopback-only diagnostic responder, never LAN discovery during tests.
    thread = threading.Thread(target=network._serve_discovery, daemon=True)
    thread.start()
    import time
    try:
        for _ in range(20):
            if network.discovery_status != 'Off':
                break
            time.sleep(.025)
        assert network.discovery_status.startswith('Ready')
        result = discover_studios(.3, targets=[('127.0.0.1', DISCOVERY_PORT)])
        assert result == [{'id': network.state['id'], 'name': 'Nearby studio', 'url': 'https://127.0.0.1:8765'}]
        network.configure('Nearby studio', False)
        assert discover_studios(.3, targets=[('127.0.0.1', DISCOVERY_PORT)]) == []
    finally:
        network.stop_event.set()
        thread.join(2)


def test_launcher_client_mode_never_imports_or_starts_server(tmp_path, monkeypatch):
    import run
    monkeypatch.setenv('CBS_DATA_DIR', str(tmp_path))
    monkeypatch.setattr('server.studio_launcher.show_launcher', lambda settings: {'mode': 'connect', 'url':'https://192.168.1.5:8765/studio/join#ticket', 'origin':'https://192.168.1.5:8765', 'name':'Host'})
    opened = []
    monkeypatch.setattr(run, 'configure_logging', lambda root: None)
    monkeypatch.setattr(run, 'open_desktop', lambda *args, **kwargs: opened.append((args,kwargs)))
    with patch('uvicorn.Server') as server, patch('server.desktop_setup.show_setup') as setup, patch('server.main.create_app') as create:
        assert run.main([]) == 0
        server.assert_not_called()
        setup.assert_not_called()
        create.assert_not_called()
    assert opened[0][1]['client_origin'] == 'https://192.168.1.5:8765'
    assert not (tmp_path/'certs').exists() and not (tmp_path/'storage').exists()


def test_verified_tls_pair_ticket_reconnect_and_wrong_ca(secure_settings, tmp_path):
    import uvicorn
    from run import wait_for_server
    app = create_app(secure_settings)
    app.state.studio_network.configure('TLS host', True)
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=0, log_config=None,
        ssl_certfile=str(secure_settings.ssl_certfile), ssl_keyfile=str(secure_settings.ssl_keyfile)))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        wait_for_server(server, thread)
        port = server.servers[0].sockets[0].getsockname()[1]
        client = StudioClient(f'https://127.0.0.1:{port}', secure_settings.certificate_dir/'rootCA.crt')
        result = client.connect(code=app.state.studio_network.code)
        assert result['studio']['name'] == 'TLS host'
        again = client.connect(token=result['token'], expected_id=result['studio']['id'])
        assert again['ticket'] != result['ticket']
        with pytest.raises(ConnectionError, match='different studio'):
            client.connect(token=result['token'], expected_id='other-studio')
        with pytest.raises(ApprovalRequired):
            client.connect(token='unknown-token')
        certificates.generate_certificates(tmp_path/'different-ca')
        wrong = StudioClient(client.url, tmp_path/'different-ca'/'rootCA.crt')
        with pytest.raises(ConnectionError, match='verify'):
            wrong.info()
    finally:
        server.should_exit = True
        thread.join(8)
