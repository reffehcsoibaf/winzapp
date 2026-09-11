"""Local-only "locked chats" support (client/core/chat_lock.py).

WhatsApp's protocol has no concept of a "locked chat" — this is a WinZapp-only
UI feature: a chat can be flagged `locked` in the local database, which hides
it from the normal conversation list. Typing the configured unlock code into
the conversation-search field reveals locked chats in place of the normal
filtered view (mirrors official WhatsApp's own "type the code in Search" UX).

Hashing, not encryption
------------------------
We only ever need to VERIFY a typed code against the stored one — never
recover the plaintext — so this stores a salted SHA-256 digest, not a
reversible Fernet blob like token_vault.py uses for the WPPConnect session
token (which genuinely needs to be read back).

SHA-256 (not PBKDF2/bcrypt) is deliberate: the search field re-checks the
typed text on every keystroke (EVT_TEXT), so the comparison has to be fast
enough not to lag typing. The threat model here is a passerby glancing at
the screen or a family member browsing the phone/PC — not an offline
brute-force attacker with the database file, who could just as easily read
the app's own source to see how the check works, iterations or not. A slow
KDF buys no real protection for this threat model and costs real typing
latency, which is exactly the accessibility trade-off this codebase
consistently avoids elsewhere (see combo_search.py, focus_cloak.py).
"""

import hashlib
import secrets


def generate_salt() -> str:
    """A fresh random salt, hex-encoded so it's safe to store as plain JSON."""
    return secrets.token_hex(16)


def hash_code(code: str, salt: str) -> str:
    """Salted SHA-256 digest of *code*, hex-encoded."""
    if not code:
        return ""
    return hashlib.sha256((salt + code).encode("utf-8")).hexdigest()


def verify_code(code: str, salt: str, expected_hash: str) -> bool:
    """True if *code* hashes (with *salt*) to *expected_hash*.

    Empty *expected_hash* (no code configured yet) always returns False —
    an unconfigured lock code must never accidentally match an empty/blank
    search field.
    """
    if not code or not expected_hash:
        return False
    return secrets.compare_digest(hash_code(code, salt), expected_hash)
