"""Arquivo > Contas — WhatsApp account-level settings, as opposed to
WinZapp's own app settings (which stay in the regular Settings dialog).

Currently holds the account privacy section (WPP.privacy bridge: visto
por último, online, recado, foto de perfil, confirmação de leitura,
quem pode me adicionar em grupos) that used to live inside Settings'
"Privacidade" tab, alongside the (WinZapp-only) chat-lock code fields.
Those two were split on purpose — this dialog is the "account" side;
Settings keeps the "app" side. Profile editing and backup are meant to
land here too later (see winzapp.md future-intentions list) — this
dialog exists so they have a home from day one instead of getting
bolted onto Settings again.
"""

import wx


class AccountsDialog(wx.Dialog):
    def __init__(self, parent, main_window):
        self.main_window = main_window
        i18n = main_window.i18n
        super().__init__(
            parent,
            title=i18n.t("accounts_dialog_title"),
            size=(480, 520),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._i18n = i18n

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # ── WhatsApp account privacy (WPP.privacy bridge) ───────────────────
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

        # TEMP — investigating the setPrivacyForOneCategory "is not a
        # function" bug (reported upstream: wppconnect-team/wa-js). Remove
        # once that's actually sorted (see debug_privacy_functions()'s
        # docstring on MainWindow).
        self._wa_privacy_debug_btn = wx.Button(panel, label="Depurar: ver funcoes WPP.privacy (temporario)")
        sizer.Add(self._wa_privacy_debug_btn, 0, wx.ALL, 8)
        self._wa_privacy_debug_btn.Bind(wx.EVT_BUTTON, self._on_debug_privacy_functions)

        sizer.AddStretchSpacer()
        close_btn = wx.Button(panel, wx.ID_CLOSE, i18n.t("close"))
        sizer.Add(close_btn, 0, wx.ALL | wx.ALIGN_RIGHT, 8)
        close_btn.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_CLOSE))
        self.Bind(wx.EVT_CLOSE, lambda evt: self.EndModal(wx.ID_CLOSE))

        panel.SetSizer(sizer)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(outer)

        self._load_values()

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

    def _on_debug_privacy_functions(self, event):
        """TEMP — see the button's own comment above."""
        report = self.main_window.debug_privacy_functions()
        wx.MessageBox(report, "Depurar WPP.privacy (temporario)", wx.OK, self)
