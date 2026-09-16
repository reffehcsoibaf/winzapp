"""Backup/restore dialogs (Contas > Backup). See core/backup.py for the
actual engine — this file is UI only: chat/media-type pickers, the
password prompt, a progress readout while the (potentially slow)
create/restore work runs on a background thread, and a summary at the
end. Restore is merge-only; see core/backup.py's own docstring for
exactly what that means per data type.
"""

import logging
import os
import threading

import wx

from core.backup import (
    MEDIA_CATEGORIES, create_backup, read_backup_info, restore_backup,
)
from core.utils import format_number
from ui.dialogs.chat_picker import ChatCheckList


_CATEGORY_LABEL_KEYS = {
    "photos": "backup_cat_photos",
    "videos": "backup_cat_videos",
    "audios": "backup_cat_audios",
    "voice_messages": "backup_cat_voice_messages",
    "documents": "backup_cat_documents",
}


def _manifest_display_name(i18n, chat_entry):
    """Display name for one manifest chat entry ({"jid","name",
    "message_count"}), with the message count appended. A backup created
    before create_backup() learned the phone-number fallback (see
    core/backup.py) can still carry a raw JID as "name" — recognizable
    because it contains "@", which no resolved contact/group name ever
    does — so that case is caught here too, defensively.
    """
    jid = chat_entry.get("jid", "")
    name = (chat_entry.get("name") or "").strip()
    if not name or "@" in name:
        if jid.endswith("@g.us"):
            name = i18n.t("unknown_group")
        else:
            name = format_number(jid) if jid else i18n.t("unknown_contact")
    return f"{name} ({chat_entry.get('message_count', 0)})"


class BackupHubDialog(wx.Dialog):
    """Contas > Backup — just the two entry points; each opens its own
    dialog rather than cramming both flows into one window."""

    def __init__(self, parent, main_window):
        self.main_window = main_window
        i18n = main_window.i18n
        super().__init__(parent, title=i18n.t("backup_hub_title"), size=(420, 220))
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        create_btn = wx.Button(panel, label=i18n.t("backup_create_button"))
        create_btn.Bind(wx.EVT_BUTTON, self._on_create)
        sizer.Add(create_btn, 0, wx.EXPAND | wx.ALL, 12)

        restore_btn = wx.Button(panel, label=i18n.t("backup_restore_button"))
        restore_btn.Bind(wx.EVT_BUTTON, self._on_restore)
        sizer.Add(restore_btn, 0, wx.EXPAND | wx.ALL, 12)

        close_btn = wx.Button(panel, wx.ID_CLOSE, i18n.t("close"))
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        sizer.Add(close_btn, 0, wx.ALL | wx.ALIGN_RIGHT, 12)

        panel.SetSizer(sizer)

    def _on_create(self, event):
        dlg = CreateBackupDialog(self, self.main_window)
        dlg.ShowModal()
        dlg.Destroy()

    def _on_restore(self, event):
        dlg = RestoreBackupDialog(self, self.main_window)
        dlg.ShowModal()
        dlg.Destroy()


class CreateBackupDialog(wx.Dialog):
    def __init__(self, parent, main_window):
        self.main_window = main_window
        i18n = main_window.i18n
        super().__init__(
            parent, title=i18n.t("backup_create_title"), size=(520, 620),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._i18n = i18n
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(wx.StaticText(panel, label=i18n.t("backup_chats_label")), 0, wx.ALL, 8)
        self._chat_picker = ChatCheckList(panel, i18n)
        sizer.Add(self._chat_picker, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        self._load_chat_options()

        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(wx.StaticText(panel, label=i18n.t("backup_media_types_label")), 0, wx.ALL, 8)
        self._category_checks = {}
        for cat in MEDIA_CATEGORIES:
            chk = wx.CheckBox(panel, label=i18n.t(_CATEGORY_LABEL_KEYS[cat]))
            chk.SetValue(True)
            sizer.Add(chk, 0, wx.LEFT | wx.RIGHT, 8)
            self._category_checks[cat] = chk

        self._settings_check = wx.CheckBox(panel, label=i18n.t("backup_include_settings_label"))
        sizer.Add(self._settings_check, 0, wx.ALL, 8)

        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(wx.StaticText(panel, label=i18n.t("backup_password_label")), 0, wx.LEFT | wx.TOP, 8)
        self._password_field = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        sizer.Add(self._password_field, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(wx.StaticText(panel, label=i18n.t("backup_password_confirm_label")), 0, wx.LEFT | wx.TOP, 8)
        self._password_confirm_field = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        sizer.Add(self._password_confirm_field, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, 8)

        self._status_label = wx.StaticText(panel, label="")
        sizer.Add(self._status_label, 0, wx.ALL, 8)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self._create_btn = wx.Button(panel, label=i18n.t("backup_create_go_button"))
        self._create_btn.Bind(wx.EVT_BUTTON, self._on_go)
        btn_row.Add(self._create_btn, 0, wx.RIGHT, 8)
        close_btn = wx.Button(panel, wx.ID_CLOSE, i18n.t("close"))
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        btn_row.Add(close_btn, 0)
        sizer.Add(btn_row, 0, wx.ALL | wx.ALIGN_RIGHT, 8)

        panel.SetSizer(sizer)

    def _load_chat_options(self):
        """Populate the picker from the app's own conversation lists (main +
        archived), never from a contacts search. get_backup_chat_options()
        can do blocking network requests (uncached group names), so it runs
        on a background thread — the picker shows its own loading row
        meanwhile (ChatCheckList.set_loading(), already called by its
        constructor)."""
        main_window = self.main_window

        def _work():
            try:
                options = main_window.get_backup_chat_options()
            except Exception:
                logging.exception("[CreateBackupDialog] failed to load chat options")
                options = []
            wx.CallAfter(self._chat_picker.set_options, options)

        threading.Thread(target=_work, daemon=True).start()

    def _on_go(self, event):
        i18n = self._i18n
        selected_jids = self._chat_picker.checked_jids()
        if not selected_jids:
            wx.MessageBox(i18n.t("backup_no_chats_selected"), i18n.t("error").format(
                app_name=self.main_window.app_name), wx.OK | wx.ICON_ERROR, self)
            return

        password = self._password_field.GetValue()
        if password != self._password_confirm_field.GetValue():
            wx.MessageBox(i18n.t("backup_password_mismatch"), i18n.t("error").format(
                app_name=self.main_window.app_name), wx.OK | wx.ICON_ERROR, self)
            return

        with wx.FileDialog(
            self, i18n.t("backup_save_dialog_title"),
            wildcard=i18n.t("backup_file_wildcard"),
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as file_dlg:
            if file_dlg.ShowModal() != wx.ID_OK:
                return
            dest_path = file_dlg.GetPath()
        if not dest_path.lower().endswith(".wzbackup"):
            dest_path += ".wzbackup"

        categories = [c for c, chk in self._category_checks.items() if chk.GetValue()]
        include_settings = self._settings_check.GetValue()
        self._create_btn.Disable()
        self._status_label.SetLabel(i18n.t("backup_in_progress"))

        def _progress(done, total):
            wx.CallAfter(
                self._status_label.SetLabel,
                i18n.t("backup_in_progress_count").format(done=done, total=total),
            )

        def _work():
            try:
                stats = create_backup(
                    self.main_window, dest_path, selected_jids, categories,
                    include_settings, password or None, progress_cb=_progress,
                )
                wx.CallAfter(self._on_done, stats, None)
            except Exception as exc:
                logging_exc = exc
                wx.CallAfter(self._on_done, None, logging_exc)

        threading.Thread(target=_work, daemon=True).start()

    def _on_done(self, stats, error):
        i18n = self._i18n
        self._create_btn.Enable()
        if error is not None:
            self._status_label.SetLabel("")
            wx.MessageBox(
                i18n.t("backup_create_failed").format(error=str(error)),
                i18n.t("error").format(app_name=self.main_window.app_name),
                wx.OK | wx.ICON_ERROR, self,
            )
            return
        self._status_label.SetLabel("")
        wx.MessageBox(
            i18n.t("backup_create_done").format(
                chats=stats.chats_included, messages=stats.messages_included,
                media=stats.media_files_included,
                mb=stats.media_bytes_included / (1024 * 1024),
            ),
            i18n.t("backup_create_title"), wx.OK | wx.ICON_INFORMATION, self,
        )
        self.EndModal(wx.ID_OK)


class RestoreBackupDialog(wx.Dialog):
    def __init__(self, parent, main_window):
        self.main_window = main_window
        i18n = main_window.i18n
        super().__init__(
            parent, title=i18n.t("backup_restore_title"), size=(520, 620),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._i18n = i18n
        self._backup_path = None
        self._info = None

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        choose_btn = wx.Button(panel, label=i18n.t("backup_choose_file_button"))
        choose_btn.Bind(wx.EVT_BUTTON, self._on_choose_file)
        sizer.Add(choose_btn, 0, wx.ALL, 8)
        self._file_label = wx.StaticText(panel, label=i18n.t("backup_no_file_chosen"))
        sizer.Add(self._file_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        sizer.Add(wx.StaticText(panel, label=i18n.t("backup_chats_label")), 0, wx.ALL, 8)
        self._chat_picker = ChatCheckList(panel, i18n)
        self._chat_picker.set_placeholder(i18n.t("backup_no_file_chosen"))
        sizer.Add(self._chat_picker, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(wx.StaticText(panel, label=i18n.t("backup_media_types_label")), 0, wx.ALL, 8)
        self._category_checks = {}
        for cat in MEDIA_CATEGORIES:
            chk = wx.CheckBox(panel, label=i18n.t(_CATEGORY_LABEL_KEYS[cat]))
            chk.SetValue(True)
            chk.Hide()
            sizer.Add(chk, 0, wx.LEFT | wx.RIGHT, 8)
            self._category_checks[cat] = chk

        self._settings_check = wx.CheckBox(panel, label=i18n.t("backup_include_settings_label"))
        self._settings_check.Hide()
        sizer.Add(self._settings_check, 0, wx.ALL, 8)

        self._merge_note = wx.StaticText(panel, label=i18n.t("backup_merge_note"))
        sizer.Add(self._merge_note, 0, wx.ALL, 8)

        self._status_label = wx.StaticText(panel, label="")
        sizer.Add(self._status_label, 0, wx.ALL, 8)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self._restore_btn = wx.Button(panel, label=i18n.t("backup_restore_go_button"))
        self._restore_btn.Bind(wx.EVT_BUTTON, self._on_go)
        self._restore_btn.Disable()
        btn_row.Add(self._restore_btn, 0, wx.RIGHT, 8)
        close_btn = wx.Button(panel, wx.ID_CLOSE, i18n.t("close"))
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        btn_row.Add(close_btn, 0)
        sizer.Add(btn_row, 0, wx.ALL | wx.ALIGN_RIGHT, 8)

        panel.SetSizer(sizer)

    def _on_choose_file(self, event):
        i18n = self._i18n
        with wx.FileDialog(
            self, i18n.t("backup_open_dialog_title"),
            wildcard=i18n.t("backup_file_wildcard"),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as file_dlg:
            if file_dlg.ShowModal() != wx.ID_OK:
                return
            path = file_dlg.GetPath()

        password = None
        info = None
        for attempt in range(3):
            try:
                info = read_backup_info(path, password)
            except ValueError as exc:
                if str(exc) == "wrong_password":
                    wx.MessageBox(i18n.t("backup_wrong_password"), i18n.t("error").format(
                        app_name=self.main_window.app_name), wx.OK | wx.ICON_ERROR, self)
                    password = None
                    continue
                wx.MessageBox(i18n.t("backup_read_failed"), i18n.t("error").format(
                    app_name=self.main_window.app_name), wx.OK | wx.ICON_ERROR, self)
                return
            if info.requires_password:
                dlg = wx.PasswordEntryDialog(
                    self, i18n.t("backup_password_prompt"), i18n.t("backup_restore_title")
                )
                if dlg.ShowModal() != wx.ID_OK:
                    dlg.Destroy()
                    return
                password = dlg.GetValue()
                dlg.Destroy()
                continue
            break
        else:
            wx.MessageBox(i18n.t("backup_wrong_password"), i18n.t("error").format(
                app_name=self.main_window.app_name), wx.OK | wx.ICON_ERROR, self)
            return

        if info is None or info.requires_password:
            return

        self._backup_path = path
        self._password = password
        self._info = info
        self._file_label.SetLabel(os.path.basename(path))

        options = []
        for c in info.chats:
            jid = c.get("jid", "")
            options.append((jid, _manifest_display_name(i18n, c), jid.endswith("@g.us")))
        self._chat_picker.set_options(options, check_all=True)

        for cat, chk in self._category_checks.items():
            available = cat in info.media_categories
            chk.Show(available)
            chk.SetValue(available)
        self._settings_check.Show(info.has_settings)
        self._settings_check.SetValue(info.has_settings)
        self.Layout()
        self._restore_btn.Enable(bool(info.chats))

    def _on_go(self, event):
        i18n = self._i18n
        selected_jids = self._chat_picker.checked_jids()
        if not selected_jids:
            wx.MessageBox(i18n.t("backup_no_chats_selected"), i18n.t("error").format(
                app_name=self.main_window.app_name), wx.OK | wx.ICON_ERROR, self)
            return

        categories = [c for c, chk in self._category_checks.items()
                      if chk.IsShown() and chk.GetValue()]
        include_settings = self._settings_check.IsShown() and self._settings_check.GetValue()
        self._restore_btn.Disable()
        self._status_label.SetLabel(i18n.t("backup_in_progress"))

        def _progress(done, total):
            wx.CallAfter(
                self._status_label.SetLabel,
                i18n.t("backup_in_progress_count").format(done=done, total=total),
            )

        def _work():
            try:
                stats = restore_backup(
                    self.main_window, self._backup_path, self._password,
                    selected_jids, categories, include_settings, progress_cb=_progress,
                )
                wx.CallAfter(self._on_done, stats, None)
            except Exception as exc:
                wx.CallAfter(self._on_done, None, exc)

        threading.Thread(target=_work, daemon=True).start()

    def _on_done(self, stats, error):
        i18n = self._i18n
        self._restore_btn.Enable()
        if error is not None:
            self._status_label.SetLabel("")
            wx.MessageBox(
                i18n.t("backup_restore_failed").format(error=str(error)),
                i18n.t("error").format(app_name=self.main_window.app_name),
                wx.OK | wx.ICON_ERROR, self,
            )
            return
        self._status_label.SetLabel("")
        wx.MessageBox(
            i18n.t("backup_restore_done").format(
                chats_added=stats.chats_added, chats_skipped=stats.chats_skipped_existing,
                messages_added=stats.messages_added, messages_skipped=stats.messages_skipped_existing,
                media_added=stats.media_files_added, media_skipped=stats.media_files_skipped_existing,
            ),
            i18n.t("backup_restore_title"), wx.OK | wx.ICON_INFORMATION, self,
        )
        self.EndModal(wx.ID_OK)
