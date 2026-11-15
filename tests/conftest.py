"""Never advertise a real Bluetooth service during build regression tests."""
import pytest
import uuid


@pytest.fixture(autouse=True)
def isolate_live_bluetooth(monkeypatch):
    monkeypatch.setattr("server.main.start_receiver", lambda *args, **kwargs: None)
    # Exercise the guard without colliding with the user's running studio.
    monkeypatch.setattr("run.DESKTOP_MUTEX", "Local\\CBSTest-" + uuid.uuid4().hex)
