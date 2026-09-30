"""Tests for the delayed first automatic update check.

At launch WinZapp is connecting and syncing; an update prompt (or the
WPPConnect restart) landing on top of that can corrupt the session. So the
checks start ~10 minutes after launch, only when the "Verificar atualizações
automaticamente" box is ticked, and postpone themselves while pairing/syncing
is still going on.

MainWindow is a wx.Frame, so the methods are exercised on a small stub.
"""

import main
from main import MainWindow


class _Timers(list):
    pass


class _MainWindowStub:
    _update_check_should_wait = MainWindow._update_check_should_wait
    _startup_update_check = MainWindow._startup_update_check
    wpp_update_may_run_now = MainWindow.wpp_update_may_run_now
    _is_pairing_dialog_active = MainWindow._is_pairing_dialog_active

    def __init__(self, enabled=True, connected=False, synced=False,
                 pairing=False, offline=False, background=False):
        self.settings = {"general": {"updates_enabled": enabled}}
        self.background_mode = background
        self._wa_connected = connected
        self._sync_completed = synced
        self._pairing_in_progress = pairing
        self.offline_mode = offline
        self.connect = type("C", (), {"connection_dial": None})()
        self._startup_update_timers = _Timers()
        self.started = []

    def _start_update_checker(self, force=False):
        self.started.append("winzapp")

    def _start_wpp_update_checker(self, force=False, manual=False):
        self.started.append("wpp")


class _FakeCallLater:
    calls = []

    def __init__(self, ms, fn, *args):
        _FakeCallLater.calls.append((ms, fn.__name__, args))


def _patch(monkeypatch):
    _FakeCallLater.calls = []
    monkeypatch.setattr(main.wx, "CallLater", _FakeCallLater)


def test_startup_delays_are_minutes_not_seconds():
    assert main._UPDATE_CHECK_STARTUP_DELAY_MS >= 5 * 60 * 1000
    assert main._WPP_UPDATE_CHECK_STARTUP_DELAY_MS >= 5 * 60 * 1000


def test_runs_when_idle(monkeypatch):
    _patch(monkeypatch)
    mw = _MainWindowStub(connected=True, synced=True)
    mw._startup_update_check()
    mw._startup_update_check(True)
    assert mw.started == ["winzapp", "wpp"]


def test_does_nothing_when_the_box_is_unticked(monkeypatch):
    _patch(monkeypatch)
    mw = _MainWindowStub(enabled=False, connected=True, synced=True)
    mw._startup_update_check()
    mw._startup_update_check(True)
    assert mw.started == []
    assert _FakeCallLater.calls == []


def test_postpones_while_syncing(monkeypatch):
    _patch(monkeypatch)
    mw = _MainWindowStub(connected=True, synced=False)
    mw._startup_update_check()
    assert mw.started == []
    assert _FakeCallLater.calls == [
        (main._UPDATE_CHECK_DEFER_MS, "_startup_update_check", (False, 1))
    ]


def test_postpones_while_pairing(monkeypatch):
    _patch(monkeypatch)
    mw = _MainWindowStub(pairing=True)
    mw._startup_update_check(True)
    assert mw.started == []
    assert _FakeCallLater.calls[0][2] == (True, 1)


def test_gives_up_waiting_after_the_cap(monkeypatch):
    """A stuck sync must not block the check forever."""
    _patch(monkeypatch)
    mw = _MainWindowStub(connected=True, synced=False)
    mw._startup_update_check(False, main._UPDATE_CHECK_MAX_DEFERS)
    assert mw.started == ["winzapp"]


def test_offline_does_not_wait_for_a_sync_that_cannot_happen(monkeypatch):
    _patch(monkeypatch)
    mw = _MainWindowStub(connected=True, synced=False, offline=True)
    mw._startup_update_check()
    assert mw.started == ["winzapp"]


def test_background_mode_never_checks(monkeypatch):
    _patch(monkeypatch)
    mw = _MainWindowStub(background=True, connected=True, synced=True)
    mw._startup_update_check()
    assert mw.started == []
