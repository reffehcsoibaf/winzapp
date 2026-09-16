"""Backup and restore (client/core/backup.py)
=================================================
Builds a portable, selective backup of one account's chats/media/settings,
and restores one back in — merge-only, never overwriting anything already
present locally. Written mainly for the portable build (carrying a paired
session between machines without redownloading everything), but works the
same way for an installed copy.

Container format
-----------------
A single file, always readable the same way regardless of whether a
password was set:

    - No password: the file IS a plain .zip (openable by anything, even
      without WinZapp — manifest.json, messages.db, media/, and
      settings.json if that category was included).
    - With a password: the same zip bytes, encrypted whole with Fernet
      under a key derived from the password via PBKDF2-HMAC-SHA256 (600k
      iterations — current OWASP-recommended minimum; slow on purpose,
      this is exactly the "attacker has the file, brute-forces offline"
      threat model PBKDF2 exists for. Distinct from chat_lock.py's plain
      SHA-256, which is a different threat model — see that module's own
      docstring). The file starts with the 5-byte magic b"WZBK1" followed
      by a 16-byte salt, which a plain zip never starts with (zip's own
      magic is b"PK\\x03\\x04") — so restore can tell which case it's
      looking at from the first bytes alone, no separate "encrypted"
      flag needed anywhere else.

Backup content is always PLAINTEXT inside the zip (messages.db here is a
fresh, unencrypted SQLite file — NOT a copy of the live, Fernet-at-rest
messages.db) — the live DB's payload encryption uses this install's own
secret.key, which won't exist on whatever machine restores the backup.
The backup's own optional password is the only protection a backup file
gets; that's why it's worth setting one for anything containing real
conversations.

Restore is merge-only by design (the user's own choice): a chat or
message already present locally is left completely untouched — only
what's genuinely missing gets added. See restore_backup()'s own docstring
for exactly what "missing" means per data type.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import time
import zipfile
from dataclasses import dataclass, field

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from core.utils import group_media_category, backfill_missing_defaults, format_number

log = logging.getLogger(__name__)

_MAGIC = b"WZBK1"
_SALT_LEN = 16
_KDF_ITERATIONS = 600_000
_MANIFEST_VERSION = 1

# Categories offered in the picker UI, in display order. "messages" is not
# itself a media category — it stands for the chat's text/metadata, which
# is always included for any chat the user picks; it exists here only so
# it can be greyed out and shown as always-on rather than hidden entirely.
MEDIA_CATEGORIES = ("photos", "videos", "audios", "voice_messages", "documents")


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                      iterations=_KDF_ITERATIONS)
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


@dataclass
class BackupStats:
    chats_included: int = 0
    messages_included: int = 0
    media_files_included: int = 0
    media_bytes_included: int = 0


@dataclass
class RestoreStats:
    chats_added: int = 0
    chats_skipped_existing: int = 0
    messages_added: int = 0
    messages_skipped_existing: int = 0
    media_files_added: int = 0
    media_files_skipped_existing: int = 0
    settings_keys_added: int = 0


@dataclass
class BackupInfo:
    """What read_backup_info() hands the UI to build the restore picker from."""
    requires_password: bool
    created_at: str = ""
    account_name: str = ""
    chats: list = field(default_factory=list)   # [{"jid","name","message_count"}]
    media_categories: list = field(default_factory=list)
    has_settings: bool = False


def _open_container_bytes(path: str, password: "str | None") -> bytes:
    """Return the plain zip bytes for *path*, decrypting first if it's the
    password-protected container shape. Raises ValueError on a wrong
    password or a corrupt/unrecognized file — callers turn that into a
    user-facing message rather than a traceback."""
    with open(path, "rb") as f:
        head = f.read(len(_MAGIC))
        if head != _MAGIC:
            f.seek(0)
            return f.read()
        salt = f.read(_SALT_LEN)
        token = f.read()
    if not password:
        raise ValueError("password_required")
    key = _derive_key(password, salt)
    try:
        return Fernet(key).decrypt(token)
    except InvalidToken:
        raise ValueError("wrong_password")


def read_backup_info(path: str, password: "str | None" = None) -> BackupInfo:
    """Peek at a backup file's manifest without restoring anything. If the
    file is password-protected and *password* is None or wrong, raises
    ValueError("password_required") / ValueError("wrong_password") — the
    caller prompts and retries rather than this function looping on input
    itself, since it has no UI of its own."""
    with open(path, "rb") as f:
        is_encrypted = f.read(len(_MAGIC)) == _MAGIC
    if is_encrypted and not password:
        return BackupInfo(requires_password=True)
    data = _open_container_bytes(path, password)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    return BackupInfo(
        requires_password=False,
        created_at=manifest.get("created_at", ""),
        account_name=manifest.get("account_name", ""),
        chats=manifest.get("chats", []),
        media_categories=manifest.get("media_categories", []),
        has_settings=manifest.get("has_settings", False),
    )


def create_backup(main_window, dest_path: str, chat_jids: list,
                   media_categories: list, include_settings: bool,
                   password: "str | None" = None,
                   progress_cb=None) -> BackupStats:
    """Build a backup at *dest_path* covering exactly *chat_jids* (every
    message in each, regardless of media_categories — text is never
    filtered out) plus whichever of *media_categories* asks for actual
    media FILES to be bundled alongside. *progress_cb*, if given, is
    called with (done, total) periodically — this can run long for a
    large account, and the caller is expected to show that in a modal
    wait dialog rather than freezing with no feedback.
    """
    stats = BackupStats()
    media_set = set(media_categories)

    with tempfile.TemporaryDirectory(prefix="winzapp_backup_") as tmp:
        db_path = os.path.join(tmp, "messages.db")
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE chats (
                jid TEXT PRIMARY KEY, remote_jid TEXT, name TEXT,
                push_name TEXT, chat_type TEXT
            );
            CREATE TABLE messages (
                message_id TEXT, remote_jid TEXT, message_json TEXT,
                timestamp INTEGER, PRIMARY KEY (message_id, remote_jid)
            );
        """)

        manifest_chats = []
        media_dir = os.path.join(tmp, "media")
        media_included_ids = set()

        total = len(chat_jids)
        for i, jid in enumerate(chat_jids):
            chat = main_window.chats.get(jid)
            if not chat:
                continue
            remote_jid = chat.get("remoteJid", jid)
            # Never fall back to the raw JID here — it's exactly the "weird
            # identifier" NVDA would otherwise read out digit by digit, both
            # in the create-backup picker and later in Restore's own list
            # (manifest_chats below feeds that list straight from "name").
            name = chat.get("name") or chat.get("pushName") or ""
            if not name:
                name = (main_window.i18n.t("unknown_group") if remote_jid.endswith("@g.us")
                        else format_number(remote_jid))
            conn.execute(
                "INSERT INTO chats (jid, remote_jid, name, push_name, chat_type) "
                "VALUES (?, ?, ?, ?, ?)",
                (jid, remote_jid, name,
                 chat.get("pushName", ""), chat.get("chatType", "chat")),
            )
            records = (chat.get("messages") or {}).get("messages", {}).get("records", [])
            msg_count = 0
            for msg in records:
                msg_id = msg.get("key", {}).get("id", "")
                if not msg_id:
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO messages (message_id, remote_jid, message_json, timestamp) "
                    "VALUES (?, ?, ?, ?)",
                    (msg_id, jid, json.dumps(msg, ensure_ascii=False),
                     int(msg.get("messageTimestamp", 0) or 0)),
                )
                msg_count += 1
                stats.messages_included += 1

                category = group_media_category(msg)
                if category and category in media_set:
                    from app_paths import data_path
                    src = data_path("media", f"{msg_id}.wzmedia")
                    if os.path.isfile(src) and msg_id not in media_included_ids:
                        os.makedirs(media_dir, exist_ok=True)
                        shutil.copy2(src, os.path.join(media_dir, f"{msg_id}.wzmedia"))
                        media_included_ids.add(msg_id)
                        stats.media_files_included += 1
                        stats.media_bytes_included += os.path.getsize(src)

            manifest_chats.append({"jid": jid, "name": name, "message_count": msg_count})
            stats.chats_included += 1
            if progress_cb:
                progress_cb(i + 1, total)

        conn.commit()
        conn.close()

        manifest = {
            "version": _MANIFEST_VERSION,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "account_name": getattr(main_window, "account_name", "") or "",
            "chats": manifest_chats,
            "media_categories": sorted(media_set),
            "has_settings": include_settings,
        }
        manifest_path = os.path.join(tmp, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        if include_settings:
            settings_path = os.path.join(tmp, "settings.json")
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(main_window.settings, f, ensure_ascii=False, indent=2)

        zip_path = os.path.join(tmp, "backup.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(manifest_path, "manifest.json")
            zf.write(db_path, "messages.db")
            if include_settings:
                zf.write(os.path.join(tmp, "settings.json"), "settings.json")
            if os.path.isdir(media_dir):
                for fname in os.listdir(media_dir):
                    zf.write(os.path.join(media_dir, fname), f"media/{fname}")

        if password:
            salt = os.urandom(_SALT_LEN)
            key = _derive_key(password, salt)
            with open(zip_path, "rb") as f:
                token = Fernet(key).encrypt(f.read())
            with open(dest_path, "wb") as f:
                f.write(_MAGIC)
                f.write(salt)
                f.write(token)
        else:
            shutil.copy2(zip_path, dest_path)

    return stats


def restore_backup(main_window, path: str, password: "str | None",
                    chat_jids: list, media_categories: list,
                    include_settings: bool, progress_cb=None) -> RestoreStats:
    """Merge *chat_jids* (and, within them, *media_categories*' files) from
    the backup at *path* into the current account. Never overwrites:

    - A chat already present locally (has_message()/get_chat_jids() would
      find it): left exactly as it is — no fields updated, even if the
      backup's copy differs.
    - A message already present (same message_id + remote_jid): skipped.
      Only messages the local DB has never seen are inserted.
    - A media file already on disk under the same message id: skipped —
      same content by construction (the filename IS the message id).
    - A settings key/section already present locally: left alone.
      backfill_missing_defaults() already has exactly this semantics
      (only ever fills genuinely ABSENT keys), reused here as-is instead
      of a second copy of the same rule.
    """
    stats = RestoreStats()
    data = _open_container_bytes(path, password)

    with tempfile.TemporaryDirectory(prefix="winzapp_restore_") as tmp:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(tmp)

        db_path = os.path.join(tmp, "messages.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        existing_jids = set(main_window.db.get_chat_jids())
        total = len(chat_jids)

        for i, jid in enumerate(chat_jids):
            row = conn.execute("SELECT * FROM chats WHERE jid = ?", (jid,)).fetchone()
            if jid in existing_jids:
                stats.chats_skipped_existing += 1
            elif row is not None:
                main_window.db.upsert_chat(jid, {
                    "remoteJid": row["remote_jid"], "name": row["name"],
                    "pushName": row["push_name"], "chatType": row["chat_type"],
                })
                stats.chats_added += 1

            for mrow in conn.execute(
                "SELECT message_id, message_json FROM messages WHERE remote_jid = ?", (jid,)
            ):
                msg_id = mrow["message_id"]
                if main_window.db.has_message(jid, msg_id):
                    stats.messages_skipped_existing += 1
                    continue
                msg = json.loads(mrow["message_json"])
                main_window.db.insert_message(jid, msg)
                stats.messages_added += 1

                category = group_media_category(msg)
                if category in media_categories:
                    src = os.path.join(tmp, "media", f"{msg_id}.wzmedia")
                    if os.path.isfile(src):
                        from app_paths import data_path
                        dest = data_path("media", f"{msg_id}.wzmedia")
                        if os.path.isfile(dest):
                            stats.media_files_skipped_existing += 1
                        else:
                            os.makedirs(os.path.dirname(dest), exist_ok=True)
                            shutil.copy2(src, dest)
                            stats.media_files_added += 1
            if progress_cb:
                progress_cb(i + 1, total)

        conn.close()

        if include_settings:
            settings_path = os.path.join(tmp, "settings.json")
            if os.path.isfile(settings_path):
                with open(settings_path, "r", encoding="utf-8") as f:
                    backed_up_settings = json.load(f)
                if backfill_missing_defaults(main_window.settings, backed_up_settings):
                    main_window.save_settings()
                    stats.settings_keys_added = 1  # exact count not tracked by that helper

    return stats
