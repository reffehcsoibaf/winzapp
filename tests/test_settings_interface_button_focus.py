"""Tests for the "Interface" button (Configurações > Geral) putting focus on
the "Interface" sub-dialog's first field instead of wherever focus was left.

Reported live: the dialog built by _wrap_pages_in_dialog() is created once
and reused across openings (ShowModal()/EndModal() just show/hide it), so wx
only auto-focuses its first control the very first time it's shown. Every
later opening lands wherever focus was left when the dialog was last
closed — for this dialog, usually somewhere in the middle, on the "Como devo
me referir a você" radio group, since that's a common thing to tab to and
change. _add_subsection_button()'s new focus_ctrl parameter moves focus onto
a given control right before ShowModal(), the same pattern already used by
every validation-error call site in settings_dialog.py (e.g.
self._sound_event_path_field.SetFocus() before
self._sound_events_dialog.ShowModal()).

No real wx.Dialog is constructed here — a plain stub stands in for it — so
this doesn't need the wxgui marker; see conftest.py's hidden_frame() and
wx_app fixture docstrings for why that distinction matters on this project.
"""

import wx
import pytest

from ui.dialogs.settings_dialog import _add_subsection_button
from tests.conftest import hidden_frame


class _DialogStub:
    """Stands in for the real, reused wx.Dialog: records whether the target
    control already had focus by the time ShowModal() would have been
    called, without ever actually opening a modal window."""

    def __init__(self):
        self.shown = False
        self.focused_control_on_show = None

    def ShowModal(self):
        self.shown = True
        self.focused_control_on_show = wx.Window.FindFocus()


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


class TestFocusCtrlMovesFocusBeforeShowModal:
    def test_no_focus_ctrl_leaves_focus_untouched(self, page):
        """Existing subsection buttons pass no focus_ctrl — behaviour for
        them must be unchanged."""
        other_field = wx.TextCtrl(page)
        other_field.SetFocus()
        dialog = _DialogStub()
        sizer = wx.BoxSizer(wx.VERTICAL)

        btn = _add_subsection_button(page, sizer, _StubI18n(), "btn_x", dialog)
        _fire_click(btn)

        assert dialog.shown is True
        assert dialog.focused_control_on_show is other_field

    def test_focus_ctrl_gets_focus_before_show_modal(self, page):
        """The "Interface" button's own case: the target field must hold
        focus by the time ShowModal() runs, regardless of what had focus
        before the click."""
        messages_page_size_field = wx.TextCtrl(page)
        elsewhere = wx.TextCtrl(page)
        elsewhere.SetFocus()
        dialog = _DialogStub()
        sizer = wx.BoxSizer(wx.VERTICAL)

        btn = _add_subsection_button(
            page, sizer, _StubI18n(), "btn_interface", dialog,
            focus_ctrl=messages_page_size_field,
        )
        _fire_click(btn)

        assert dialog.shown is True
        assert dialog.focused_control_on_show is messages_page_size_field


class _StubI18n:
    def t(self, key):
        return key
