"""Media cleanup (client/core/cleanup.py)
==========================================
Frees disk space by deleting downloaded media FILES for messages matching
a filter (chat, media type, minimum size) — never the messages themselves.
A message whose file gets removed here just goes back to showing the
existing on-demand "Baixar" action (see conversations.py's media action
row) instead of Open/Save; nothing about the conversation history changes.

Two-step by design, matching the "reunir dados, ver um panorama, depois
decidir" the user asked for: scan_cleanup_candidates() only reads (walks
main_window.chats and stat()s files on disk, deletes nothing), returning
a CleanupPreview the UI shows before anything is touched.
execute_cleanup() takes that exact preview back and deletes only the
files it already found — never scanning again itself, so what gets
deleted is always exactly what the user was shown, even if new messages
arrive on the account in between (unlikely, given how fast this runs).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from app_paths import data_path
from core.utils import group_media_category

MEDIA_CATEGORIES = ("photos", "videos", "audios", "voice_messages", "documents")


@dataclass
class CleanupCandidate:
    chat_jid: str
    message_id: str
    category: str
    size_bytes: int
    path: str


@dataclass
class CleanupPreview:
    candidates: list = field(default_factory=list)

    @property
    def total_files(self) -> int:
        return len(self.candidates)

    @property
    def total_bytes(self) -> int:
        return sum(c.size_bytes for c in self.candidates)

    @property
    def chats_affected(self) -> int:
        return len({c.chat_jid for c in self.candidates})

    def by_category(self) -> dict:
        """{category: (count, total_bytes)}, only for categories that
        actually matched something — an empty category doesn't clutter
        the summary the user reviews before confirming."""
        out: dict = {}
        for c in self.candidates:
            count, total = out.get(c.category, (0, 0))
            out[c.category] = (count + 1, total + c.size_bytes)
        return out


@dataclass
class CleanupStats:
    files_deleted: int = 0
    bytes_freed: int = 0
    files_missing: int = 0   # already gone by execute time — not an error


def scan_cleanup_candidates(main_window, chat_jids: list, media_categories: list,
                             min_size_bytes: int = 0) -> CleanupPreview:
    """Read-only: finds every downloaded media file, among *chat_jids*,
    whose category is in *media_categories* and whose size is at least
    *min_size_bytes*. Deletes nothing."""
    category_set = set(media_categories)
    preview = CleanupPreview()

    for jid in chat_jids:
        chat = main_window.chats.get(jid)
        if not chat:
            continue
        records = (chat.get("messages") or {}).get("messages", {}).get("records", [])
        for msg in records:
            category = group_media_category(msg)
            if not category or category not in category_set:
                continue
            msg_id = msg.get("key", {}).get("id", "")
            if not msg_id:
                continue
            path = data_path("media", f"{msg_id}.wzmedia")
            if not os.path.isfile(path):
                continue
            size = os.path.getsize(path)
            if size < min_size_bytes:
                continue
            preview.candidates.append(
                CleanupCandidate(chat_jid=jid, message_id=msg_id,
                                  category=category, size_bytes=size, path=path)
            )

    return preview


def execute_cleanup(preview: CleanupPreview, progress_cb=None) -> CleanupStats:
    """Deletes exactly the files scan_cleanup_candidates() already found —
    see this module's own docstring for why it never re-scans. Missing a
    file that was already removed by something else in the meantime isn't
    an error, just counted separately."""
    stats = CleanupStats()
    total = len(preview.candidates)
    for i, cand in enumerate(preview.candidates):
        try:
            size = os.path.getsize(cand.path)
            os.remove(cand.path)
            stats.files_deleted += 1
            stats.bytes_freed += size
        except FileNotFoundError:
            stats.files_missing += 1
        if progress_cb:
            progress_cb(i + 1, total)
    return stats
