"""Tests for the backup/cleanup chat-picker logic.

Two things are covered, both deliberately kept as plain functions with no
wx dependency so they run headless (see ChatCheckList's own docstring in
client/ui/dialogs/chat_picker.py for why):

- filter_options()/visible_all_checked() — the group/individual filter and
  the "select all" row's own checked state.
- MainWindow._conversation_chat_options() — building the picker's option
  list from the app's own main+archived conversation lists, exercised the
  same way other pure name-resolution methods are (test_sender_names.py):
  bound onto a plain stub instead of a real wx.Frame.
"""

from main import MainWindow
from ui.dialogs.chat_picker import filter_options, visible_all_checked


# ── filter_options / visible_all_checked (no wx.App needed) ────────────────

_OPTIONS = [
    ("g1@g.us", "Grupo da Família", True),
    ("5511999999999@s.whatsapp.net", "+55 11 99999-9999", False),
    ("g2@g.us", "Trabalho", True),
    ("5511988888888@s.whatsapp.net", "Ana", False),
]


def test_filter_options_all_keeps_everything():
    assert filter_options(_OPTIONS, "all") == _OPTIONS


def test_filter_options_groups_only():
    result = filter_options(_OPTIONS, "groups")
    assert [o[0] for o in result] == ["g1@g.us", "g2@g.us"]


def test_filter_options_individual_only():
    result = filter_options(_OPTIONS, "individual")
    assert [o[0] for o in result] == [
        "5511999999999@s.whatsapp.net", "5511988888888@s.whatsapp.net",
    ]


def test_visible_all_checked_true_when_every_visible_jid_is_checked():
    visible = ["a", "b", "c"]
    assert visible_all_checked(visible, {"a", "b", "c", "d"}) is True


def test_visible_all_checked_false_when_one_missing():
    visible = ["a", "b", "c"]
    assert visible_all_checked(visible, {"a", "b"}) is False


def test_visible_all_checked_false_when_empty():
    assert visible_all_checked([], {"a"}) is False


# ── MainWindow._conversation_chat_options (bound onto a plain stub) ────────

def _chat(remote_jid, **extra):
    d = {"remoteJid": remote_jid}
    d.update(extra)
    return d


def test_conversation_chat_options_merges_main_and_archived_sorted_by_name():
    main_chats = [_chat("b@s.whatsapp.net"), _chat("a@g.us")]
    main_names = ["Beatriz", "Alpha Group"]
    arch_chats = [_chat("c@s.whatsapp.net")]
    arch_names = ["Carlos"]
    chats_dict = {
        "b@s.whatsapp.net": main_chats[0],
        "a@g.us": main_chats[1],
        "c@s.whatsapp.net": arch_chats[0],
    }

    options = MainWindow._conversation_chat_options(
        main_chats, main_names, arch_chats, arch_names,
        chats_dict, is_locked=lambda jid: False,
    )

    assert options == [
        ("a@g.us", "Alpha Group", True),
        ("b@s.whatsapp.net", "Beatriz", False),
        ("c@s.whatsapp.net", "Carlos", False),
    ]


def test_conversation_chat_options_excludes_locked_chats():
    main_chats = [_chat("locked@s.whatsapp.net"), _chat("open@s.whatsapp.net")]
    main_names = ["Trancada", "Aberta"]
    chats_dict = {c["remoteJid"]: c for c in main_chats}

    options = MainWindow._conversation_chat_options(
        main_chats, main_names, [], [],
        chats_dict, is_locked=lambda jid: jid == "locked@s.whatsapp.net",
    )

    assert [o[0] for o in options] == ["open@s.whatsapp.net"]


def test_conversation_chat_options_recovers_real_chats_dict_key():
    # A merged/renamed chat can be stored in main_window.chats under a key
    # that no longer equals its own remoteJid (see _compute_chat_lists()'s
    # own note on this) — backup.py/cleanup.py still need the original key
    # to look the chat back up in main_window.chats.
    chat = _chat("5511999999999@s.whatsapp.net")
    chats_dict = {"old_lid_key@lid": chat}

    options = MainWindow._conversation_chat_options(
        [chat], ["Alguém"], [], [],
        chats_dict, is_locked=lambda jid: False,
    )

    assert options == [("old_lid_key@lid", "Alguém", False)]


def test_conversation_chat_options_dedupes_same_remote_jid():
    # Belt-and-braces: _compute_chat_lists() already renders each remoteJid
    # once, but the merge here must not reintroduce a duplicate if a chat
    # somehow appears in both the main and archived lists it's given.
    chat = _chat("dup@s.whatsapp.net")
    chats_dict = {"dup@s.whatsapp.net": chat}

    options = MainWindow._conversation_chat_options(
        [chat], ["Nome"], [chat], ["Nome"],
        chats_dict, is_locked=lambda jid: False,
    )

    assert len(options) == 1
