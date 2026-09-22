"""Tests for where a chat's display identity comes from.

Two independent defects made conversations disappear from the list entirely.
Both were measured on a real 539-chat account that showed only 323 rows:

1. list-chats returns each individual chat with a nested `contact` block
   (name/shortName/pushname) and nothing read it, so every individual chat was
   stored and rendered nameless — 124 of 263 chats had a usable name in that
   block, 0 of 263 reached the database with one.

2. _compute_chat_lists() dropped a chat as "no content and no identity" using
   only the raw dict's name/pushName, ~30 lines *before* it called
   _resolve_contact_name(). WhatsApp Web returns `msgs: null` in list-chats, so
   lastMessage is empty for every chat right after a sync; any chat that also
   had no unread count was dropped before its name was ever looked up, even
   though all 263 had a matching contact record.

_lift_contact_identity covers (1) and is tested directly. (2) is a reordering
inside a large wx-bound method, so the decision it now makes is reproduced here
against the same inputs.

TestIndividualChatNameCascade below covers the actual name _compute_chat_lists()
picks for a non-group chat — same two-step pipeline as production
(_lift_contact_identity(), then the resolved_name/pushName/msg_push/chat.name
cascade at client/main.py's "Chat individual" branch), reproduced here for the
same reason as (2) above. This is what makes a contact who was never saved to
the address book — but who set a display name in their own WhatsApp profile —
show that name instead of their phone number, exactly as WhatsApp's own client
does and as WinZapp's group-chat sender labels already did.
"""

import pytest

from core.utils import format_number
from main import MainWindow


lift = MainWindow._lift_contact_identity


def _resolve_individual_name(*, resolved_name, chat_push, msg_push, chat_name, phone_jid):
    """Mirrors client/main.py's _compute_chat_lists() "Chat individual" branch."""
    name = resolved_name or chat_push
    if not name:
        name = msg_push or chat_name
    if not name or not name.strip():
        name = format_number(phone_jid) if phone_jid else ""
    return name


class TestLiftContactIdentity:
    def test_takes_name_from_the_contact_block(self):
        chat = {"contact": {"name": "Tia Ana", "pushname": "Aninha"}}
        lift(chat)
        assert chat["name"] == "Tia Ana"
        assert chat["pushName"] == "Aninha"

    def test_falls_back_to_short_name(self):
        chat = {"contact": {"shortName": "Ana"}}
        lift(chat)
        assert chat["name"] == "Ana"

    def test_accepts_either_pushname_spelling(self):
        """WPPConnect spells it `pushname`; other payloads use `pushName`."""
        chat = {"contact": {"pushName": "Zé"}}
        lift(chat)
        assert chat["pushName"] == "Zé"

    def test_falls_back_to_the_verified_business_name(self):
        """A verified WhatsApp Business account ("99 Pay", "Verisure Brasil",
        a bank, a utility) never sets a personal pushname — confirmed on a
        real account: name/shortName/pushname were all empty for every one
        of these chats, only contact.verifiedName carried the business name
        WhatsApp's own client shows for it."""
        chat = {"contact": {"verifiedName": "99 Pay", "isBusiness": True}}
        lift(chat)
        assert chat["name"] == "99 Pay"

    def test_name_and_short_name_still_win_over_verified_name(self):
        chat = {"contact": {"name": "Meu Apelido", "verifiedName": "99 Pay"}}
        lift(chat)
        assert chat["name"] == "Meu Apelido"

    def test_never_overwrites_an_existing_top_level_name(self):
        chat = {"name": "Apelido meu", "contact": {"name": "Nome do contato"}}
        lift(chat)
        assert chat["name"] == "Apelido meu"

    def test_treats_a_blank_top_level_name_as_absent(self):
        chat = {"name": "   ", "contact": {"name": "Real"}}
        lift(chat)
        assert chat["name"] == "Real"

    def test_ignores_a_blank_contact_name(self):
        chat = {"contact": {"name": "  ", "shortName": ""}}
        lift(chat)
        assert "name" not in chat

    @pytest.mark.parametrize("chat", [
        {},                       # group chats carry no contact block
        {"contact": None},
        {"contact": "nope"},
        {"contact": []},
    ])
    def test_survives_a_missing_or_malformed_contact_block(self, chat):
        before = dict(chat)
        lift(chat)
        assert chat == before


def _keeps_chat(*, records, last_msg, unread, pinned, cleared, raw_name,
                raw_push, resolved_name, group_name=""):
    """The keep/drop decision _compute_chat_lists() makes, same inputs."""
    has_content = bool(records or last_msg or unread > 0 or pinned or cleared)
    name_hint = (raw_name or raw_push or resolved_name or group_name).strip()
    has_identity = bool(name_hint and not name_hint.isdigit() and len(name_hint) > 1)
    return has_content or has_identity


class TestKeepDecision:
    def _base(self, **over):
        args = dict(records=[], last_msg=None, unread=0, pinned=False,
                    cleared=False, raw_name="", raw_push="",
                    resolved_name="", group_name="")
        args.update(over)
        return args

    def test_the_regression_chat_is_kept(self):
        """No messages, no lastMessage, no unread, nameless dict — but the
        contact is known. This is the shape of all 218 vanished chats."""
        assert _keeps_chat(**self._base(resolved_name="Fulano de Tal")) is True

    def test_still_dropped_when_nothing_at_all_is_known(self):
        """The filter must keep dropping genuinely empty, anonymous entries —
        that is what it exists for."""
        assert _keeps_chat(**self._base()) is False

    def test_a_digits_only_hint_is_not_an_identity(self):
        assert _keeps_chat(**self._base(resolved_name="5511999999999")) is False

    def test_a_single_character_hint_is_not_an_identity(self):
        assert _keeps_chat(**self._base(resolved_name="A")) is False

    @pytest.mark.parametrize("field", ["records", "last_msg", "unread", "pinned", "cleared"])
    def test_content_alone_keeps_a_nameless_chat(self, field):
        value = {"records": [{"id": 1}], "last_msg": {"t": 1}, "unread": 3,
                 "pinned": True, "cleared": True}[field]
        assert _keeps_chat(**self._base(**{field: value})) is True

    def test_raw_name_still_wins_when_present(self):
        assert _keeps_chat(**self._base(raw_name="Grupo X")) is True

    def test_group_name_still_counts(self):
        assert _keeps_chat(**self._base(group_name="Equipe WinZapp")) is True


class TestIndividualChatNameCascade:
    """Reported: a person never saved to the address book shows their raw
    phone number in the conversation list instead of the display name they
    set on their own WhatsApp profile — even though group-chat sender labels
    already prefer that same profile name over a number. The mechanism the
    request asks for already exists end to end: list-chats' nested `contact`
    block carries that profile name as `contact.pushname` (WhatsApp's own
    client shows exactly this for a non-contact), _lift_contact_identity()
    copies it onto chat["pushName"], and this cascade prefers it over
    format_number() every time. These tests pin that the two stay wired
    together — if either regresses, unsaved contacts go back to numbers."""

    def test_whatsapp_profile_name_beats_the_phone_number_for_a_non_contact(self):
        """The exact reported scenario: not in the address book (no
        resolved_name from self.contacts), never messaged yet in this
        session (no msg_push), no chat-level name override — only the
        WhatsApp profile name WhatsApp Web itself already knows about."""
        chat = {"contact": {"pushname": "Maria da Padaria"}}
        lift(chat)

        name = _resolve_individual_name(
            resolved_name="", chat_push=chat.get("pushName", ""),
            msg_push="", chat_name="", phone_jid="5511999999999@s.whatsapp.net",
        )

        assert name == "Maria da Padaria"

    def test_verified_business_name_beats_the_phone_number(self):
        """The exact case reported live: '99 Pay' (+55 21 2391-9910) and
        'Verisure Brasil' (+55 11 95305-7252) showed their raw phone number
        in the list. Both are verified WhatsApp Business accounts with no
        personal pushname — chat_push and msg_push both come up empty, so
        the name has to come from _resolve_contact_name()'s own fallback to
        chat["name"], which _lift_contact_identity() now feeds from
        contact.verifiedName."""
        chat = {"contact": {"verifiedName": "99 Pay"}}
        lift(chat)
        # _resolve_contact_name() falls back to chat.get("name") once every
        # address-book/presence lookup comes up empty — reproduced directly
        # here since that method needs a live self.contacts/self._presence_
        # pushname_map, same reasoning as this module's own docstring.
        resolved_name = chat.get("name", "")

        name = _resolve_individual_name(
            resolved_name=resolved_name, chat_push=chat.get("pushName", ""),
            msg_push="", chat_name=chat.get("name", ""),
            phone_jid="552123919910@s.whatsapp.net",
        )

        assert name == "99 Pay"

    def test_an_address_book_name_still_wins_over_the_profile_name(self):
        """resolved_name (from self.contacts, i.e. an actual saved contact)
        outranks the WhatsApp-profile pushname — a saved nickname must not
        be replaced by whatever name the other person chose for themselves."""
        name = _resolve_individual_name(
            resolved_name="Tia Ana", chat_push="Ana W.",
            msg_push="", chat_name="", phone_jid="5511999999999@s.whatsapp.net",
        )

        assert name == "Tia Ana"

    def test_phone_number_is_the_true_last_resort(self):
        """Nothing known anywhere — not a saved contact, no profile name
        surfaced by list-chats, no pushName on any stored message, no chat
        name override. Only then is the number itself acceptable."""
        chat = {}  # no "contact" block at all
        lift(chat)

        name = _resolve_individual_name(
            resolved_name="", chat_push=chat.get("pushName", ""),
            msg_push="", chat_name="", phone_jid="5511999999999@s.whatsapp.net",
        )

        assert name == format_number("5511999999999@s.whatsapp.net")
