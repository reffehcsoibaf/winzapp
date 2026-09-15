"""Guia de uso — an in-app usage guide, opened from Ajuda and from the
connection screen. Content lives in client/data/help_guide/<lang>.json, one
file per UI language; a language with no file yet (still being translated)
falls back to pt-BR rather than showing nothing.

Content is a list of {id, title, body} sections, written collaboratively
with the user a section at a time — some may still say "Em breve." until
their turn comes up.
"""

import json
import os

import wx

from app_paths import resource_path


def _load_guide_sections(lang: str) -> list:
    """Sections for *lang*, falling back to pt-BR if that language's guide
    file doesn't exist yet or fails to parse."""
    for candidate in (lang, "pt-BR"):
        path = resource_path("data", "help_guide", f"{candidate}.json")
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sections = data.get("sections")
                if isinstance(sections, list) and sections:
                    return sections
            except Exception:
                continue
    return []


class HelpGuideDialog(wx.Dialog):
    def __init__(self, parent, main_window):
        self.main_window = main_window
        i18n = main_window.i18n
        super().__init__(
            parent, title=i18n.t("help_guide_title"), size=(760, 520),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._sections = _load_guide_sections(i18n.language)

        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)

        body_sizer = wx.BoxSizer(wx.HORIZONTAL)

        left_sizer = wx.BoxSizer(wx.VERTICAL)
        left_sizer.Add(
            wx.StaticText(panel, label=i18n.t("help_guide_topics_label")), 0,
            wx.LEFT | wx.TOP, 8,
        )
        self._topics_list = wx.ListBox(
            panel, choices=[s.get("title", "") for s in self._sections],
        )
        self._topics_list.Bind(wx.EVT_LISTBOX, self._on_topic_selected)
        left_sizer.Add(self._topics_list, 1, wx.EXPAND | wx.ALL, 8)
        body_sizer.Add(left_sizer, 0, wx.EXPAND)

        right_sizer = wx.BoxSizer(wx.VERTICAL)
        self._content_text = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP,
        )
        right_sizer.Add(self._content_text, 1, wx.EXPAND | wx.ALL, 8)
        body_sizer.Add(right_sizer, 1, wx.EXPAND)

        outer.Add(body_sizer, 1, wx.EXPAND)

        close_btn = wx.Button(panel, wx.ID_CLOSE, i18n.t("close"))
        outer.Add(close_btn, 0, wx.ALL | wx.ALIGN_RIGHT, 8)
        close_btn.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_CLOSE))
        self.Bind(wx.EVT_CLOSE, lambda evt: self.EndModal(wx.ID_CLOSE))

        panel.SetSizer(outer)

        if self._sections:
            self._topics_list.SetSelection(0)
            self._show_section(0)
        self._topics_list.SetFocus()

    def _on_topic_selected(self, event):
        self._show_section(event.GetSelection())

    def _show_section(self, index: int):
        if 0 <= index < len(self._sections):
            self._content_text.SetValue(self._sections[index].get("body", ""))
