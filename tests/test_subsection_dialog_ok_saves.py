"""Tests for the WinZapp settings sub-dialogs (Interface, Sons de eventos,
Transcrições e Descrições, Conversas trancadas, etc.) saving on close
instead of just closing.

Reported live: these dialogs — built by _wrap_pages_in_dialog(), opened via
_add_subsection_button() — only ever had a "Fechar" button that hid the
window. Any actual persistence only ever happened through the outer
SettingsDialog's own Apply/OK, so changes made purely inside one of these
sub-dialogs (without also clicking the outer dialog's Apply) looked saved
but weren't. The button is now OK (wx.ID_OK, the same id and label the
outer dialog's own OK button already uses), and closing it by any means
(button, Esc, title bar — see _wrap_pages_in_dialog()'s own EVT_CLOSE
binding) resolves ShowModal() to wx.ID_OK, which _add_subsection_button()
treats as "run the outer dialog's Apply now, since it's genuinely safe to —
ShowModal() only returns once that dialog's own modal loop has truly
ended".

_wrap_pages_in_dialog() constructs a real wx.Dialog here, but it is never
Show()n or ShowModal()'d — same reasoning as conftest.hidden_frame(): it
never becomes the foreground window, so this needs no wxgui marker.
_add_subsection_button()'s own behaviour (call owner._on_apply() exactly
when the dialog resolves to wx.ID_OK) is tested against a stub standing in
for the dialog, the same style test_settings_interface_button_focus.py
already uses.
"""

import wx
import pytest

from core.i18n import I18n
from ui.dialogs.settings_dialog import _add_subsection_button, _wrap_pages_in_dialog
from tests.conftest import hidden_frame


class _DialogStub:
    def __init__(self, result=wx.ID_OK):
        self._result = result
        self.shown = False

    def ShowModal(self):
        self.shown = True
        return self._result


class _OwnerStub:
    def __init__(self):
        self.apply_calls = 0

    def _on_apply(self, event):
        assert event is None
        self.apply_calls += 1


class _StubI18n:
    def t(self, key):
        return key


def _fire_click(button):
    evt = wx.CommandEvent(wx.EVT_BUTTON.typeId, button.GetId())
    evt.SetEventObject(button)
    button.GetEventHandler().ProcessEvent(evt)


@pytest.fixture
def page(wx_app):
    frame = hidden_frame()
    frame.Show()
    panel = wx.Panel(frame)
    yield panel
    frame.Destroy()


class TestSubsectionButtonSavesOnOk:
    def test_ok_result_triggers_apply(self, page):
        dialog = _DialogStub(result=wx.ID_OK)
        owner = _OwnerStub()
        sizer = wx.BoxSizer(wx.VERTICAL)
        btn = _add_subsection_button(page, sizer, _StubI18n(), "btn_x", dialog, owner)

        _fire_click(btn)

        assert dialog.shown is True
        assert owner.apply_calls == 1

    def test_non_ok_result_does_not_trigger_apply(self, page):
        """Belt and suspenders: every real path resolves to wx.ID_OK today
        (see _wrap_pages_in_dialog()'s own button/EVT_CLOSE bindings), but
        the guard itself must actually gate on the result rather than
        always applying regardless of it."""
        dialog = _DialogStub(result=wx.ID_CANCEL)
        owner = _OwnerStub()
        sizer = wx.BoxSizer(wx.VERTICAL)
        btn = _add_subsection_button(page, sizer, _StubI18n(), "btn_x", dialog, owner)

        _fire_click(btn)

        assert dialog.shown is True
        assert owner.apply_calls == 0


class TestWrapPagesInDialogButton:
    def test_the_button_is_ok_not_close(self, page):
        """Real _wrap_pages_in_dialog() construction — never Show()n or
        ShowModal()'d, so this never becomes the foreground window."""
        i18n = I18n(page)
        i18n.get_language()
        inner_panel = wx.Panel(page)
        dlg = _wrap_pages_in_dialog(page, i18n, "Test", [inner_panel])
        try:
            ok_button = dlg.FindWindow(wx.ID_OK)
            assert ok_button is not None
            assert ok_button.GetLabel() == i18n.t("ok")
        finally:
            dlg.Destroy()
