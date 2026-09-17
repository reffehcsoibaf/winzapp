"""Profile editing (Contas > Perfil). Three independent fields — name,
About/"recado" text, and photo — each applied only if the person actually
filled it in (or chose a photo); leaving a field blank means "don't touch
this one", not "clear it". Backed by WPPConnect's own higher-level
setProfileName()/setProfileStatus()/setProfilePic() (see the three
set_profile_*() methods on MainWindow) rather than a direct wa-js
internal lookup, so this isn't exposed to the same class of bug that's
hit privacy and message-ack this session.
"""

import os

import wx


class ProfileDialog(wx.Dialog):
    def __init__(self, parent, main_window):
        self.main_window = main_window
        i18n = main_window.i18n
        super().__init__(
            parent, title=i18n.t("profile_dialog_title"), size=(480, 420),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._i18n = i18n
        self._photo_path = None

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(
            wx.StaticText(panel, label=i18n.t("profile_blank_note")), 0,
            wx.ALL, 8,
        )

        sizer.Add(wx.StaticText(panel, label=i18n.t("profile_name_label")), 0,
                  wx.LEFT | wx.TOP, 8)
        self._name_field = wx.TextCtrl(panel)
        sizer.Add(self._name_field, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

        sizer.Add(wx.StaticText(panel, label=i18n.t("profile_status_label")), 0,
                  wx.LEFT | wx.TOP, 8)
        self._status_field = wx.TextCtrl(panel)
        sizer.Add(self._status_field, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(wx.StaticText(panel, label=i18n.t("profile_photo_label")), 0, wx.ALL, 8)
        choose_photo_btn = wx.Button(panel, label=i18n.t("profile_choose_photo_button"))
        choose_photo_btn.Bind(wx.EVT_BUTTON, self._on_choose_photo)
        sizer.Add(choose_photo_btn, 0, wx.LEFT | wx.RIGHT, 8)
        self._photo_label = wx.StaticText(panel, label=i18n.t("profile_no_photo_chosen"))
        sizer.Add(self._photo_label, 0, wx.ALL, 8)

        self._status_label = wx.StaticText(panel, label="")
        sizer.Add(self._status_label, 0, wx.ALL, 8)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self._save_btn = wx.Button(panel, label=i18n.t("profile_save_button"))
        self._save_btn.Bind(wx.EVT_BUTTON, self._on_save)
        btn_row.Add(self._save_btn, 0, wx.RIGHT, 8)
        close_btn = wx.Button(panel, wx.ID_CLOSE, i18n.t("close"))
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        btn_row.Add(close_btn, 0)
        sizer.Add(btn_row, 0, wx.ALL | wx.ALIGN_RIGHT, 8)

        panel.SetSizer(sizer)

    def _on_choose_photo(self, event):
        i18n = self._i18n
        with wx.FileDialog(
            self, i18n.t("profile_choose_photo_button"),
            wildcard=i18n.t("profile_photo_wildcard"),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as file_dlg:
            if file_dlg.ShowModal() != wx.ID_OK:
                return
            self._photo_path = file_dlg.GetPath()
        self._photo_label.SetLabel(os.path.basename(self._photo_path))

    def _on_save(self, event):
        i18n = self._i18n
        name = self._name_field.GetValue().strip()
        status = self._status_field.GetValue().strip()
        photo = self._photo_path

        if not name and not status and not photo:
            wx.MessageBox(
                i18n.t("profile_nothing_to_save"),
                i18n.t("error").format(app_name=self.main_window.app_name),
                wx.OK | wx.ICON_ERROR, self,
            )
            return

        self._save_btn.Disable()
        self._status_label.SetLabel(i18n.t("profile_saving"))

        def _work():
            errors = []
            if name:
                err = self.main_window.set_profile_name(name)
                if err:
                    errors.append(f"{i18n.t('profile_name_label')}: {err}")
            if status:
                err = self.main_window.set_profile_status(status)
                if err:
                    errors.append(f"{i18n.t('profile_status_label')}: {err}")
            if photo:
                err = self.main_window.set_profile_pic(photo)
                if err:
                    errors.append(f"{i18n.t('profile_photo_label')}: {err}")
            wx.CallAfter(self._on_done, errors)

        import threading
        threading.Thread(target=_work, daemon=True).start()

    def _on_done(self, errors):
        i18n = self._i18n
        self._save_btn.Enable()
        self._status_label.SetLabel("")
        if errors:
            wx.MessageBox(
                i18n.t("profile_save_partial_error") + "\n\n" + "\n".join(errors),
                i18n.t("error").format(app_name=self.main_window.app_name),
                wx.OK | wx.ICON_ERROR, self,
            )
        else:
            wx.MessageBox(
                i18n.t("profile_save_success"),
                i18n.t("profile_dialog_title"), wx.OK | wx.ICON_INFORMATION, self,
            )
            self._name_field.SetValue("")
            self._status_field.SetValue("")
            self._photo_path = None
            self._photo_label.SetLabel(i18n.t("profile_no_photo_chosen"))
