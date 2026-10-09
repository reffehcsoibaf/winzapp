"""Setting the locked-chats code must not be rejected on the second apply.

Reported live: after a fresh pairing (no code yet) the user typed the code,
repeated it, pressed OK in the "Locked chats" window, then OK in Settings, and
was told the code was invalid. Ignoring the message and closing worked fine.

Cause: closing a sub-dialog with OK already applies the settings (see
SettingsDialog._add_subsection_button), which stores the code. The new/confirm
fields were not emptied, so the next OK/Apply validated them again, now with a
code configured: the "current code" was demanded (empty, or the old one, which
no longer matches) and reported incorrect, although the code had just been
saved. The fix empties the code fields once the new code is stored.

Needs a real wx dialog, like the other settings dialog tests (see conftest.py).
"""

import wx
import pytest

from core import chat_lock
from core.i18n import I18n
from core.sound_system import DEFAULT_PACK_ID
from ui.dialogs.settings_dialog import SettingsDialog
from tests.conftest import hidden_frame

pytestmark = pytest.mark.wxgui


class _FakeSoundSystem:
    def get_output_devices(self):
        return []

    def get_input_devices(self):
        return []

    def apply_output_device(self, name):
        return True

    def apply_effects_device(self, name):
        return True


def _make_frame(settings):
    frame = hidden_frame()
    frame.settings = settings
    frame.app_name = "TeleZapp"
    frame.i18n = I18n(frame)
    frame.i18n.get_language()
    frame.wpp_port = 6300
    frame.wpp_custom_api = False
    frame._sound_packs = {DEFAULT_PACK_ID: {"name": "Default", "path": ""}}
    frame._default_sound_pack = {"name": "Default", "path": ""}
    frame.set_global_hotkey = lambda vk, mod: None
    frame.save_settings = lambda: None
    frame.load_sounds = lambda: None
    frame.apply_language_changes = lambda: None
    frame.sound_system = _FakeSoundSystem()
    frame.refresh_sound_packs = lambda: None
    # Same behaviour as MainWindow's real methods, reading the same settings.
    frame.has_locked_chats_code_configured = lambda: bool(
        frame.settings.get("privacy", {}).get("locked_chats_code_hash", ""))
    frame.verify_locked_chats_code = lambda code: chat_lock.verify_code(
        code,
        frame.settings.get("privacy", {}).get("locked_chats_code_salt", ""),
        frame.settings.get("privacy", {}).get("locked_chats_code_hash", ""))
    return frame


@pytest.fixture
def make_dialog(wx_app, monkeypatch):
    created = []
    errors = []
    # Any validation failure shows a MessageBox and re-opens the sub-dialog;
    # record the first and stop the second from blocking the test.
    monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: errors.append(a))

    def _make(settings=None):
        dlg = SettingsDialog(_make_frame(settings if settings is not None else {}))
        monkeypatch.setattr(dlg._locked_chats_dialog, "ShowModal", lambda: wx.ID_CANCEL)
        created.append(dlg)
        return dlg, errors

    yield _make
    for dlg in created:
        dlg.Destroy()


def _type_new_code(dialog, code, current=None):
    if current is not None:
        dialog._privacy_current_code_field.SetValue(current)
    dialog._privacy_new_code_field.SetValue(code)
    dialog._privacy_confirm_code_field.SetValue(code)


class TestFirstTimeCode:
    def test_applying_twice_in_a_row_is_accepted(self, make_dialog):
        """The reported flow: sub-dialog OK applies, then Settings OK applies."""
        dialog, errors = make_dialog({})
        _type_new_code(dialog, "2468")

        assert dialog._apply_values() is True
        assert dialog._apply_values() is True
        assert errors == []

    def test_the_code_is_stored_and_works(self, make_dialog):
        dialog, _ = make_dialog({})
        _type_new_code(dialog, "2468")
        dialog._apply_values()

        assert dialog.main_window.verify_locked_chats_code("2468") is True
        assert dialog.main_window.verify_locked_chats_code("0000") is False

    def test_the_second_apply_keeps_the_same_code(self, make_dialog):
        dialog, _ = make_dialog({})
        _type_new_code(dialog, "2468")
        dialog._apply_values()
        salt_hash = dict(dialog.main_window.settings["privacy"])

        dialog._apply_values()
        assert dialog.main_window.settings["privacy"] == salt_hash

    def test_the_fields_are_emptied_and_the_current_code_field_appears(self, make_dialog):
        dialog, _ = make_dialog({})
        assert dialog._privacy_current_code_field.IsShown() is False
        _type_new_code(dialog, "2468")
        dialog._apply_values()

        assert dialog._privacy_new_code_field.GetValue() == ""
        assert dialog._privacy_confirm_code_field.GetValue() == ""
        assert dialog._privacy_current_code_field.GetValue() == ""
        assert dialog._privacy_current_code_field.IsShown() is True

    def test_emptying_the_fields_does_not_bring_the_apply_button_back(self, make_dialog):
        dialog, _ = make_dialog({})
        _type_new_code(dialog, "2468")
        dialog._loading_values = False
        dialog._dirty = False
        dialog._apply_values()

        assert dialog._dirty is False


class TestChangingAnExistingCode:
    def _configured(self, make_dialog, code="1111"):
        salt = chat_lock.generate_salt()
        return make_dialog({"privacy": {
            "locked_chats_code_salt": salt,
            "locked_chats_code_hash": chat_lock.hash_code(code, salt),
        }})

    def test_changing_the_code_then_applying_again_is_accepted(self, make_dialog):
        dialog, errors = self._configured(make_dialog, "1111")
        _type_new_code(dialog, "2222", current="1111")

        assert dialog._apply_values() is True
        assert dialog._apply_values() is True
        assert errors == []
        assert dialog.main_window.verify_locked_chats_code("2222") is True
        assert dialog.main_window.verify_locked_chats_code("1111") is False

    def test_a_wrong_current_code_is_still_rejected(self, make_dialog):
        """The fix must not weaken the takeover protection."""
        dialog, errors = self._configured(make_dialog, "1111")
        _type_new_code(dialog, "2222", current="9999")

        assert dialog._apply_values() is False
        assert len(errors) == 1
        assert dialog.main_window.verify_locked_chats_code("1111") is True
        assert dialog.main_window.verify_locked_chats_code("2222") is False

    def test_a_missing_current_code_is_still_rejected(self, make_dialog):
        dialog, errors = self._configured(make_dialog, "1111")
        _type_new_code(dialog, "2222")

        assert dialog._apply_values() is False
        assert len(errors) == 1
        assert dialog.main_window.verify_locked_chats_code("1111") is True

    def test_leaving_the_code_fields_blank_keeps_the_code(self, make_dialog):
        dialog, errors = self._configured(make_dialog, "1111")

        assert dialog._apply_values() is True
        assert errors == []
        assert dialog.main_window.verify_locked_chats_code("1111") is True


class TestMismatchStillCaught:
    def test_different_confirmation_is_rejected(self, make_dialog):
        dialog, errors = make_dialog({})
        dialog._privacy_new_code_field.SetValue("2468")
        dialog._privacy_confirm_code_field.SetValue("1357")

        assert dialog._apply_values() is False
        assert len(errors) == 1
        assert dialog.main_window.has_locked_chats_code_configured() is False
