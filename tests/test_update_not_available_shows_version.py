"""The "no update available" dialog (Ajuda > Verificar atualizações, forced
check, when already on the latest release) must name the version that's
actually running.

Reported live: it previously just said "you're already on the latest
version" with no number, which is unhelpful when someone deliberately
checks to confirm what they have installed. update_not_available now takes
a {current} placeholder, the same pattern wpp_update_up_to_date_msg already
used for the WPPConnect Server update check.
"""

import wx

from updater import UpdateChecker


class _StubI18n:
    def t(self, key):
        return {
            "update_not_available": "Already on the latest version ({current}).",
            "update_not_available_title": "No updates",
        }[key]


class _StubMainWindow:
    def __init__(self):
        self.i18n = _StubI18n()


def test_show_no_update_includes_the_running_version(monkeypatch):
    captured = {}

    def fake_message_box(message, caption, style, parent):
        captured["message"] = message
        captured["caption"] = caption

    monkeypatch.setattr(wx, "MessageBox", fake_message_box)

    checker = UpdateChecker(_StubMainWindow())
    checker._show_no_update("1.1.4.1")

    assert captured["message"] == "Already on the latest version (1.1.4.1)."
    assert captured["caption"] == "No updates"
