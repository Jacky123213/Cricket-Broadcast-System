from types import SimpleNamespace
from server import power


def test_windows_sleep_guard_releases_request(monkeypatch):
    calls = []
    def request(flags):
        calls.append(flags)
        return 0x80000000
    monkeypatch.setattr(power.sys, 'platform', 'win32')
    monkeypatch.setattr(power.ctypes, 'WinDLL', lambda *a, **kw: SimpleNamespace(SetThreadExecutionState=request), raising=False)
    guard = power.SleepGuard()
    guard.start()
    assert 'prevented' in guard.status
    guard.stop()
    assert calls == [0x80000001, 0x80000000]


def test_windows_failure_is_visible(monkeypatch):
    def request(flags):
        return 0
    monkeypatch.setattr(power.sys, 'platform', 'win32')
    monkeypatch.setattr(power.ctypes, 'WinDLL', lambda *a, **kw: SimpleNamespace(SetThreadExecutionState=request), raising=False)
    guard = power.SleepGuard()
    guard.start()
    assert 'unavailable' in guard.status
    guard.stop()
