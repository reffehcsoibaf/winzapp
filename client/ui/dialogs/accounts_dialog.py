"""Menu > Configurações > Configurações do WhatsApp — settings that live on
the WhatsApp account itself, as opposed to WinZapp's own app settings (which
stay in the regular Settings dialog, opened separately as "Configurações do
WinZapp").

Three tabs, reflecting how far each one actually is:
  - Privacidade: WPP.privacy bridge (visto por último, online, recado, foto
    de perfil, confirmação de leitura, quem pode me adicionar em grupos).
    Fully wired — reading always works; Apply can still fail on some fields
    while wppconnect-team/wa-js's setPrivacyForOneCategory is broken
    upstream, which _on_apply_whatsapp_privacy() already reports per field
    rather than pretending it succeeded.
  - Perfil: nome exibido, recado, foto — each applied independently via
    MainWindow.set_profile_name()/set_profile_status()/set_profile_pic(),
    which go through WPPConnect's own higher-level client methods rather
    than a direct wa-js internal lookup, so unlike Privacidade this isn't
    exposed to that same class of bug. A blank field (or no photo chosen)
    means "leave this one alone", not "clear it".
  - Contatos bloqueados: not built yet (a dedicated blocked-contacts screen
    is still on the winzapp.md future-intentions list). Gets a tab now,
    with a plain "ainda não implementado" placeholder, so the window this
    functionality lands in already exists instead of getting bolted onto
    Configurações again once it's ready.
"""

import wx


class AccountsDialog(wx.Dialog):
    def __init__(self, parent, main_window):
        self.main_window = main_window
        i18n = main_window.i18n
        super().__init__(
            parent,
            title=i18n.t("accounts_dialog_title"),
            size=(480, 560),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._i18n = i18n

        outer_panel = wx.Panel(self)
        outer_sizer = wx.BoxSizer(wx.VERTICAL)

        self._notebook = wx.Notebook(outer_panel)
        self._build_privacy_tab(i18n)
        self._build_profile_tab(i18n)
        self._build_blocked_contacts_tab(i18n)
        outer_sizer.Add(self._notebook, 1, wx.EXPAND | wx.ALL, 8)

        close_btn = wx.Button(outer_panel, wx.ID_CLOSE, i18n.t("close"))
        outer_sizer.Add(close_btn, 0, wx.ALL | wx.ALIGN_RIGHT, 8)
        close_btn.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_CLOSE))
        self.Bind(wx.EVT_CLOSE, lambda evt: self.EndModal(wx.ID_CLOSE))

        outer_panel.SetSizer(outer_sizer)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(outer_panel, 1, wx.EXPAND)
        self.SetSizer(outer)

        self._load_values()

    # ── Privacidade (WPP.privacy bridge) ────────────────────────────────────

    def _build_privacy_tab(self, i18n):
        panel = wx.Panel(self._notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Six simple-enum settings; "who sees my Status/Stories" needs a
        # contact-list picker instead of a dropdown, so it isn't here yet.
        self._wa_privacy_section_label = wx.StaticText(
            panel, label=i18n.t("wa_privacy_section_label")
        )
        sizer.Add(self._wa_privacy_section_label, 0, wx.ALL, 8)

        # (attribute prefix, i18n label key, [(raw_value, i18n option key), ...])
        self._WA_PRIVACY_FIELDS = [
            ("last_seen", "wa_privacy_last_seen_label",
             [("all", "wa_privacy_opt_all"), ("contacts", "wa_privacy_opt_contacts"), ("none", "wa_privacy_opt_none")]),
            ("online", "wa_privacy_online_label",
             [("all", "wa_privacy_opt_all"), ("match_last_seen", "wa_privacy_opt_match_last_seen")]),
            ("about", "wa_privacy_about_label",
             [("all", "wa_privacy_opt_all"), ("contacts", "wa_privacy_opt_contacts"), ("none", "wa_privacy_opt_none")]),
            ("profile_pic", "wa_privacy_profile_pic_label",
             [("all", "wa_privacy_opt_all"), ("contacts", "wa_privacy_opt_contacts"), ("none", "wa_privacy_opt_none")]),
            ("read_receipts", "wa_privacy_read_receipts_label",
             [("all", "wa_privacy_opt_on"), ("none", "wa_privacy_opt_off")]),
            ("group_add", "wa_privacy_group_add_label",
             [("all", "wa_privacy_opt_all"), ("contacts", "wa_privacy_opt_contacts")]),
        ]
        # server-field name each row maps to, for fetch/apply
        self._WA_PRIVACY_SERVER_FIELD = {
            "last_seen": "lastSeen",
            "online": "online",
            "about": "about",
            "profile_pic": "profilePicture",
            "read_receipts": "readReceipts",
            "group_add": "groupAdd",
        }
        self._wa_privacy_labels = {}
        for attr_prefix, label_key, options in self._WA_PRIVACY_FIELDS:
            label = wx.StaticText(panel, label=i18n.t(label_key))
            sizer.Add(label, 0, wx.LEFT | wx.TOP | wx.RIGHT, 8)
            self._wa_privacy_labels[attr_prefix] = (label, label_key)
            choice = wx.Choice(panel, choices=[i18n.t(opt_key) for _, opt_key in options])
            setattr(self, f"_wa_privacy_{attr_prefix}_choice", choice)
            sizer.Add(choice, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self._wa_privacy_status_label = wx.StaticText(panel, label="")
        sizer.Add(self._wa_privacy_status_label, 0, wx.ALL, 8)

        self._wa_privacy_apply_btn = wx.Button(panel, label=i18n.t("wa_privacy_apply_button"))
        sizer.Add(self._wa_privacy_apply_btn, 0, wx.ALL, 8)
        self._wa_privacy_apply_btn.Bind(wx.EVT_BUTTON, self._on_apply_whatsapp_privacy)

        panel.SetSizer(sizer)
        self._notebook.AddPage(panel, i18n.t("wa_settings_tab_privacy"))

    def _load_values(self):
        wa_privacy = self.main_window.fetch_privacy_settings()
        self._wa_privacy_apply_btn.Enable(bool(wa_privacy))
        if wa_privacy:
            self._wa_privacy_status_label.SetLabel("")
            for attr_prefix, _label_key, options in self._WA_PRIVACY_FIELDS:
                server_field = self._WA_PRIVACY_SERVER_FIELD[attr_prefix]
                current_value = wa_privacy.get(server_field, "")
                choice = getattr(self, f"_wa_privacy_{attr_prefix}_choice")
                raw_values = [raw for raw, _opt_key in options]
                if current_value in raw_values:
                    choice.SetSelection(raw_values.index(current_value))
                else:
                    choice.SetSelection(wx.NOT_FOUND)
        else:
            self._wa_privacy_status_label.SetLabel(self._i18n.t("wa_privacy_load_failed"))

    def _apply_whatsapp_privacy_settings(self) -> list:
        """Sends every dropdown's current selection to WhatsApp via
        set_privacy_setting(). Always sends all six (not just changed ones)
        — re-sending an unchanged value is a harmless no-op on WhatsApp's
        side, and skipping that complexity means one clear action instead
        of tracking a dirty/clean state per dropdown."""
        errors = []
        for attr_prefix, _label_key, options in self._WA_PRIVACY_FIELDS:
            choice = getattr(self, f"_wa_privacy_{attr_prefix}_choice")
            sel = choice.GetSelection()
            if sel == wx.NOT_FOUND:
                continue
            raw_value = options[sel][0]
            server_field = self._WA_PRIVACY_SERVER_FIELD[attr_prefix]
            error = self.main_window.set_privacy_setting(server_field, raw_value)
            if error:
                errors.append(error)
        return errors

    def _on_apply_whatsapp_privacy(self, event):
        i18n = self._i18n
        errors = self._apply_whatsapp_privacy_settings()
        if errors:
            self._wa_privacy_status_label.SetLabel(i18n.t("wa_privacy_apply_partial_error"))
            wx.MessageBox(
                "\n".join(errors),
                i18n.t("error").format(app_name=self.main_window.app_name),
                wx.OK | wx.ICON_ERROR,
                self,
            )
        else:
            self._wa_privacy_status_label.SetLabel(i18n.t("wa_privacy_apply_success"))

    # ── Perfil ────────────────────────────────────────────────────────────

    def _build_profile_tab(self, i18n):
        panel = wx.Panel(self._notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(wx.StaticText(panel, label=i18n.t("profile_blank_note")), 0, wx.ALL, 8)

        sizer.Add(wx.StaticText(panel, label=i18n.t("profile_name_label")), 0,
                  wx.LEFT | wx.TOP, 8)
        self._profile_name_field = wx.TextCtrl(panel)
        sizer.Add(self._profile_name_field, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

        sizer.Add(wx.StaticText(panel, label=i18n.t("profile_status_label")), 0,
                  wx.LEFT | wx.TOP, 8)
        self._profile_status_field = wx.TextCtrl(panel)
        sizer.Add(self._profile_status_field, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(wx.StaticText(panel, label=i18n.t("profile_photo_label")), 0, wx.ALL, 8)
        choose_photo_btn = wx.Button(panel, label=i18n.t("profile_choose_photo_button"))
        choose_photo_btn.Bind(wx.EVT_BUTTON, self._on_choose_profile_photo)
        sizer.Add(choose_photo_btn, 0, wx.LEFT | wx.RIGHT, 8)
        self._profile_photo_path = None
        self._profile_photo_label = wx.StaticText(panel, label=i18n.t("profile_no_photo_chosen"))
        sizer.Add(self._profile_photo_label, 0, wx.ALL, 8)

        self._profile_status_msg = wx.StaticText(panel, label="")
        sizer.Add(self._profile_status_msg, 0, wx.ALL, 8)

        self._profile_save_btn = wx.Button(panel, label=i18n.t("profile_save_button"))
        self._profile_save_btn.Bind(wx.EVT_BUTTON, self._on_save_profile)
        sizer.Add(self._profile_save_btn, 0, wx.ALL, 8)

        panel.SetSizer(sizer)
        self._notebook.AddPage(panel, i18n.t("wa_settings_tab_profile"))

    def _on_choose_profile_photo(self, event):
        i18n = self._i18n
        with wx.FileDialog(
            self, i18n.t("profile_choose_photo_button"),
            wildcard=i18n.t("profile_photo_wildcard"),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as file_dlg:
            if file_dlg.ShowModal() != wx.ID_OK:
                return
            self._profile_photo_path = file_dlg.GetPath()
        import os
        self._profile_photo_label.SetLabel(os.path.basename(self._profile_photo_path))

    def _on_save_profile(self, event):
        i18n = self._i18n
        name = self._profile_name_field.GetValue().strip()
        status = self._profile_status_field.GetValue().strip()
        photo = self._profile_photo_path

        if not name and not status and not photo:
            wx.MessageBox(
                i18n.t("profile_nothing_to_save"),
                i18n.t("error").format(app_name=self.main_window.app_name),
                wx.OK | wx.ICON_ERROR, self,
            )
            return

        self._profile_save_btn.Disable()
        self._profile_status_msg.SetLabel(i18n.t("profile_saving"))

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
            wx.CallAfter(self._on_profile_save_done, errors)

        import threading
        threading.Thread(target=_work, daemon=True).start()

    def _on_profile_save_done(self, errors):
        i18n = self._i18n
        self._profile_save_btn.Enable()
        self._profile_status_msg.SetLabel("")
        if errors:
            wx.MessageBox(
                i18n.t("profile_save_partial_error") + "\n\n" + "\n".join(errors),
                i18n.t("error").format(app_name=self.main_window.app_name),
                wx.OK | wx.ICON_ERROR, self,
            )
        else:
            wx.MessageBox(
                i18n.t("profile_save_success"),
                i18n.t("wa_settings_tab_profile"), wx.OK | wx.ICON_INFORMATION, self,
            )
            self._profile_name_field.SetValue("")
            self._profile_status_field.SetValue("")
            self._profile_photo_path = None
            self._profile_photo_label.SetLabel(i18n.t("profile_no_photo_chosen"))

    # ── Contatos bloqueados (placeholder — not implemented yet) ─────────────

    def _build_blocked_contacts_tab(self, i18n):
        panel = wx.Panel(self._notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        label = wx.StaticText(panel, label=i18n.t("wa_blocked_contacts_coming_soon"))
        label.Wrap(400)
        sizer.Add(label, 0, wx.ALL, 12)
        panel.SetSizer(sizer)
        self._notebook.AddPage(panel, i18n.t("wa_settings_tab_blocked"))
