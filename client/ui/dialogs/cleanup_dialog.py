"""Media cleanup dialog (Configurações > Armazenamento > Limpeza de mídia,
and Contas > Backup's neighbor in spirit — see core/cleanup.py for the
actual scan/delete engine). Two-step, matching what the user asked for:
build a filter, see a panorama of what it matches, THEN decide whether to
actually delete anything.
"""

import threading

import wx

from core.cleanup import MEDIA_CATEGORIES, execute_cleanup, scan_cleanup_candidates

_CATEGORY_LABEL_KEYS = {
    "photos": "backup_cat_photos",
    "videos": "backup_cat_videos",
    "audios": "backup_cat_audios",
    "voice_messages": "backup_cat_voice_messages",
    "documents": "backup_cat_documents",
}


class CleanupDialog(wx.Dialog):
    def __init__(self, parent, main_window):
        self.main_window = main_window
        i18n = main_window.i18n
        super().__init__(
            parent, title=i18n.t("cleanup_title"), size=(560, 680),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._i18n = i18n
        self._preview = None

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(wx.StaticText(panel, label=i18n.t("cleanup_chats_label")), 0, wx.ALL, 8)
        self._chat_list = wx.CheckListBox(panel)
        self._chat_jids = []
        for jid, chat in sorted(
            main_window.chats.items(),
            key=lambda kv: (kv[1].get("name") or kv[1].get("pushName") or kv[0]).lower(),
        ):
            name = chat.get("name") or chat.get("pushName") or jid
            self._chat_jids.append(jid)
            self._chat_list.Append(name)
        for i in range(self._chat_list.GetCount()):
            self._chat_list.Check(i, True)
        sizer.Add(self._chat_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        select_all_btn = wx.Button(panel, label=i18n.t("backup_select_all_button"))
        select_all_btn.Bind(wx.EVT_BUTTON, self._on_select_all)
        sizer.Add(select_all_btn, 0, wx.ALL, 8)

        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(wx.StaticText(panel, label=i18n.t("backup_media_types_label")), 0, wx.ALL, 8)
        self._category_checks = {}
        for cat in MEDIA_CATEGORIES:
            chk = wx.CheckBox(panel, label=i18n.t(_CATEGORY_LABEL_KEYS[cat]))
            chk.SetValue(True)
            sizer.Add(chk, 0, wx.LEFT | wx.RIGHT, 8)
            self._category_checks[cat] = chk

        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)
        size_row = wx.BoxSizer(wx.HORIZONTAL)
        size_row.Add(wx.StaticText(panel, label=i18n.t("cleanup_min_size_label")), 0,
                     wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self._min_size_field = wx.TextCtrl(panel, value="0", size=(80, -1))
        size_row.Add(self._min_size_field, 0)
        sizer.Add(size_row, 0, wx.ALL, 8)

        scan_btn = wx.Button(panel, label=i18n.t("cleanup_scan_button"))
        scan_btn.Bind(wx.EVT_BUTTON, self._on_scan)
        sizer.Add(scan_btn, 0, wx.ALL, 8)

        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(wx.StaticText(panel, label=i18n.t("cleanup_summary_label")), 0, wx.ALL, 8)
        self._summary_text = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 140)
        )
        sizer.Add(self._summary_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        self._status_label = wx.StaticText(panel, label="")
        sizer.Add(self._status_label, 0, wx.ALL, 8)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self._proceed_btn = wx.Button(panel, label=i18n.t("cleanup_proceed_button"))
        self._proceed_btn.Bind(wx.EVT_BUTTON, self._on_proceed)
        self._proceed_btn.Disable()
        btn_row.Add(self._proceed_btn, 0, wx.RIGHT, 8)
        close_btn = wx.Button(panel, wx.ID_CLOSE, i18n.t("close"))
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        btn_row.Add(close_btn, 0)
        sizer.Add(btn_row, 0, wx.ALL | wx.ALIGN_RIGHT, 8)

        panel.SetSizer(sizer)

    def _on_select_all(self, event):
        all_checked = all(self._chat_list.IsChecked(i) for i in range(self._chat_list.GetCount()))
        for i in range(self._chat_list.GetCount()):
            self._chat_list.Check(i, not all_checked)

    def _selected_jids(self):
        return [self._chat_jids[i] for i in range(self._chat_list.GetCount())
                if self._chat_list.IsChecked(i)]

    def _on_scan(self, event):
        i18n = self._i18n
        selected_jids = self._selected_jids()
        if not selected_jids:
            wx.MessageBox(i18n.t("backup_no_chats_selected"), i18n.t("error").format(
                app_name=self.main_window.app_name), wx.OK | wx.ICON_ERROR, self)
            return
        categories = [c for c, chk in self._category_checks.items() if chk.GetValue()]
        if not categories:
            wx.MessageBox(i18n.t("cleanup_no_categories_selected"), i18n.t("error").format(
                app_name=self.main_window.app_name), wx.OK | wx.ICON_ERROR, self)
            return
        try:
            min_size_mb = float(self._min_size_field.GetValue().replace(",", "."))
        except ValueError:
            min_size_mb = 0
        min_size_bytes = max(0, min_size_mb) * 1024 * 1024

        self._preview = None
        self._proceed_btn.Disable()
        self._summary_text.SetValue("")
        self._status_label.SetLabel(i18n.t("cleanup_scanning"))

        def _work():
            preview = scan_cleanup_candidates(
                self.main_window, selected_jids, categories, min_size_bytes
            )
            wx.CallAfter(self._on_scanned, preview)

        threading.Thread(target=_work, daemon=True).start()

    def _on_scanned(self, preview):
        i18n = self._i18n
        self._preview = preview
        self._status_label.SetLabel("")

        if preview.total_files == 0:
            self._summary_text.SetValue(i18n.t("cleanup_nothing_found"))
            self._proceed_btn.Disable()
            return

        lines = [i18n.t("cleanup_summary_header").format(
            chats=preview.chats_affected, files=preview.total_files,
            mb=preview.total_bytes / (1024 * 1024),
        ), ""]
        for cat, (count, total) in preview.by_category().items():
            label = i18n.t(_CATEGORY_LABEL_KEYS.get(cat, cat))
            lines.append(f"{label}: {count} ({total / (1024 * 1024):.1f} MB)")
        self._summary_text.SetValue("\n".join(lines))
        self._proceed_btn.Enable()

    def _on_proceed(self, event):
        i18n = self._i18n
        if not self._preview or self._preview.total_files == 0:
            return
        confirm = wx.MessageBox(
            i18n.t("cleanup_confirm_msg").format(
                files=self._preview.total_files,
                mb=self._preview.total_bytes / (1024 * 1024),
            ),
            i18n.t("cleanup_confirm_title"),
            wx.YES_NO | wx.ICON_WARNING, self,
        )
        if confirm != wx.YES:
            return

        preview = self._preview
        self._proceed_btn.Disable()
        self._status_label.SetLabel(i18n.t("cleanup_deleting"))

        def _progress(done, total):
            wx.CallAfter(
                self._status_label.SetLabel,
                i18n.t("cleanup_deleting_count").format(done=done, total=total),
            )

        def _work():
            stats = execute_cleanup(preview, progress_cb=_progress)
            wx.CallAfter(self._on_done, stats)

        threading.Thread(target=_work, daemon=True).start()

    def _on_done(self, stats):
        i18n = self._i18n
        self._status_label.SetLabel("")
        self._preview = None
        self._summary_text.SetValue("")
        wx.MessageBox(
            i18n.t("cleanup_done").format(
                files=stats.files_deleted, mb=stats.bytes_freed / (1024 * 1024),
            ),
            i18n.t("cleanup_title"), wx.OK | wx.ICON_INFORMATION, self,
        )
