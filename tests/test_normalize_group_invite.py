"""Tests for WebSocketClient._normalize_wpp_message()'s "groups_v4_invite" branch.

Reported live: a shared "join this group" invite (WhatsApp's own group-invite
message, sent to share a group via a clickable link — distinct from actually
being added to a group, which arrives as a "gp2"/groupNotification instead)
was silently dropped. WPPConnect's raw message model tags this type
"groups_v4_invite" (MessageType.GROUPS_V4_INVITE) and flattens the invite
onto inviteGrp/inviteGrpName/inviteCode/inviteCodeExp rather than nesting it
— with no branch for this type at all, message_content stayed {}, so the
invite never reached main.py: no row in the chat, no unread bump, no
notification, indistinguishable from the message never having arrived.

WebSocketClient needs a live Socket.IO client normally, but
_normalize_wpp_message()/_clean_jid() touch no I/O — exercised as plain
functions against a small stub, same approach as
tests/test_normalize_document_forward.py.
"""

from core.websocket_client import WebSocketClient
from main import MainWindow, is_countable_message


class _Stub:
    _normalize_wpp_message = WebSocketClient._normalize_wpp_message
    _clean_jid = WebSocketClient._clean_jid


def _base_msg(**overrides):
    msg = {
        "id": "true_5511999999999@c.us_ABC123",
        "from": "5511999999999@c.us",
        "to": "5511999999999@c.us",
        "fromMe": False,
        "timestamp": 1700000000,
        "type": "groups_v4_invite",
        "inviteGrp": "120363012345678901@g.us",
        "inviteGrpName": "Família Silva",
        "inviteCode": "AbCdEfGhIjK",
        "inviteCodeExp": 1700086400,
    }
    msg.update(overrides)
    return msg


class TestGroupInviteNormalization:
    def test_invite_fields_are_carried_through(self):
        stub = _Stub()

        result = stub._normalize_wpp_message(_base_msg())

        invite = result["message"]["groupInviteMessage"]
        assert invite["groupJid"] == "120363012345678901@g.us"
        assert invite["groupName"] == "Família Silva"
        assert invite["inviteCode"] == "AbCdEfGhIjK"
        assert invite["inviteExpiration"] == 1700086400

    def test_caption_falls_back_to_body(self):
        stub = _Stub()

        result = stub._normalize_wpp_message(_base_msg(body="Vem pro grupo!"))

        assert result["message"]["groupInviteMessage"]["caption"] == "Vem pro grupo!"

    def test_message_type_maps_to_group_invite_message(self):
        stub = _Stub()

        result = stub._normalize_wpp_message(_base_msg())

        assert result["messageType"] == "groupInviteMessage"

    def test_wid_object_group_jid_is_flattened_to_a_plain_string(self):
        stub = _Stub()
        msg = _base_msg(inviteGrp={
            "server": "g.us", "user": "120363012345678901",
            "_serialized": "120363012345678901@g.us",
        })

        result = stub._normalize_wpp_message(msg)

        assert result["message"]["groupInviteMessage"]["groupJid"] == "120363012345678901@g.us"

    def test_missing_group_name_does_not_crash(self):
        stub = _Stub()
        msg = _base_msg(inviteGrpName=None)

        result = stub._normalize_wpp_message(msg)

        assert result["message"]["groupInviteMessage"]["groupName"] == ""

    def test_group_invite_counts_as_real_conversation_activity(self):
        """The actual reported symptom: the invite must not be treated like
        a silent system event (groupNotification/protocolMessage) — it is a
        real message from a real sender and must bump unread/sort/notify."""
        stub = _Stub()
        normalized = stub._normalize_wpp_message(_base_msg())

        assert is_countable_message(normalized) is True

    def test_group_invite_is_a_displayable_last_message(self):
        stub = _Stub()
        normalized = stub._normalize_wpp_message(_base_msg())

        assert MainWindow._counts_as_last_message(normalized) is True
