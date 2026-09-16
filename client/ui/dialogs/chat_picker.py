"""Shared chat-picker widget for the backup and media-cleanup dialogs.

Both dialogs need the same thing: a list of chats the user can check off,
filterable by group/individual, with a "select all" that behaves as an
ordinary item at the top of the list (row 1 of N) rather than a separate
button elsewhere in the tab order — so a screen-reader user arrowing
through the list hits it first, instead of having to find a button before
or after the list to select everything.

The filtering/select-all bookkeeping is kept in plain functions with no wx
dependency, so it can be tested without a running wx.App (see
tests/test_chat_picker.py) — ChatCheckList itself is a thin wx wrapper
around them.
"""

import wx


def filter_options(options, filter_key):
    """options: list of (jid, name, is_group). filter_key: 'all' | 'groups'
    | 'individual'. Returns the subset that filter_key selects, in the
    same order."""
    if filter_key == "groups":
        return [o for o in options if o[2]]
    if filter_key == "individual":
        return [o for o in options if not o[2]]
    return list(options)


def visible_all_checked(visible_jids, checked):
    """True if every currently-visible jid is checked (and there's at
    least one) — what the synthetic "select all" row should show."""
    return bool(visible_jids) and all(jid in checked for jid in visible_jids)


class ChatCheckList(wx.Panel):
    """A group/individual filter plus a checklist whose first row is a
    synthetic "select all" toggle scoped to whatever the filter currently
    shows, one row per chat below it.

    Populate with set_options() — loading the options (calling
    main_window.get_backup_chat_options(), which can touch the network) is
    the caller's job; this widget only renders whatever list it's given.
    """

    def __init__(self, parent, i18n, on_change=None):
        super().__init__(parent)
        self._i18n = i18n
        self._on_change = on_change
        self._options: list = []       # full set: (jid, name, is_group)
        self._checked: set = set()     # jids currently checked, survives filtering
        self._visible_jids: list = []  # jid behind each non-select-all row, in order
        self._filter = "all"

        sizer = wx.BoxSizer(wx.VERTICAL)

        self._filter_radio = wx.RadioBox(
            self,
            label=i18n.t("conv_filter_label"),
            choices=[
                i18n.t("conv_filter_all"),
                i18n.t("conv_filter_groups"),
                i18n.t("conv_filter_individual"),
            ],
            majorDimension=1,
            style=wx.RA_SPECIFY_ROWS,
        )
        self._filter_radio.Bind(wx.EVT_RADIOBOX, self._on_filter_changed)
        sizer.Add(self._filter_radio, 0, wx.EXPAND | wx.BOTTOM, 8)

        self._list = wx.CheckListBox(self)
        self._list.Bind(wx.EVT_CHECKLISTBOX, self._on_item_toggled)
        sizer.Add(self._list, 1, wx.EXPAND)

        self.SetSizer(sizer)
        self.set_loading()

    # ── Placeholder states ─────────────────────────────────────────────
    def set_placeholder(self, text):
        """Show a single disabled informational row instead of the chat
        list — used before there is anything to pick from yet (options
        still loading, or no backup file chosen)."""
        self._options = []
        self._checked = set()
        self._list.Clear()
        self._list.Append(text)
        self._list.Disable()
        self._filter_radio.Disable()

    def set_loading(self):
        """Show a placeholder row while options are being fetched (usually
        on a background thread) and disable the filter/list meanwhile."""
        self.set_placeholder(self._i18n.t("chat_picker_loading"))

    # ── Populating ──────────────────────────────────────────────────────
    def set_options(self, options, check_all=False):
        """options: list of (jid, name, is_group). Replaces the full set.
        Previously checked jids that still exist stay checked, unless
        check_all is True (used by Restore, which starts fully selected)."""
        self._options = list(options)
        if check_all:
            self._checked = {jid for jid, _, _ in self._options}
        else:
            valid = {jid for jid, _, _ in self._options}
            self._checked &= valid
        self._list.Enable()
        self._filter_radio.Enable()
        self._rebuild()

    def checked_jids(self):
        return [jid for jid, _, _ in self._options if jid in self._checked]

    def has_options(self):
        return bool(self._options)

    # ── Internals ───────────────────────────────────────────────────────
    def _rebuild(self):
        shown = filter_options(self._options, self._filter)
        self._visible_jids = [jid for jid, _, _ in shown]

        self._list.Freeze()
        self._list.Clear()
        if not shown:
            self._list.Append(self._i18n.t("chat_picker_empty"))
            self._list.Disable()
        else:
            self._list.Enable()
            self._list.Append(self._i18n.t("chat_picker_select_all"))
            self._list.Check(0, visible_all_checked(self._visible_jids, self._checked))
            for jid, name, _ in shown:
                idx = self._list.Append(name)
                self._list.Check(idx, jid in self._checked)
        self._list.Thaw()

    def _on_filter_changed(self, event):
        _map = ["all", "groups", "individual"]
        sel = self._filter_radio.GetSelection()
        self._filter = _map[sel] if 0 <= sel < len(_map) else "all"
        self._rebuild()

    def _on_item_toggled(self, event):
        idx = event.GetInt()
        if idx == 0:
            want = self._list.IsChecked(0)
            for jid in self._visible_jids:
                if want:
                    self._checked.add(jid)
                else:
                    self._checked.discard(jid)
            self._rebuild()
        else:
            row_jid = self._visible_jids[idx - 1]
            if self._list.IsChecked(idx):
                self._checked.add(row_jid)
            else:
                self._checked.discard(row_jid)
            # Keep the select-all row in sync without rebuilding the list
            # (which would move focus off the item the user just toggled).
            self._list.Check(0, visible_all_checked(self._visible_jids, self._checked))
        if self._on_change:
            self._on_change()
