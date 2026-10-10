"""The privacy tab must still load when WPP.privacy.get() throws.

Reported live (wppconnect.log):
    (0 , n.getStatusPrivacySetting) is not a function

WPP.privacy.get() reads the six account fields and then also awaits
getStatusPrivacySetting(). On WhatsApp Web builds where the status module no
longer wraps its exports in `default` (>= 2.3000.1048775404) wa-js 4.6.1 and
earlier leave that binding unresolved (fixed by wa-js#3693, in no npm release
yet), so get() throws and the tab came up empty although the six fields it
shows are readable through WPP.whatsapp.functions.getUserPrivacySettings().

The route falls back to those six fields. The logic runs inside the browser, so
these tests pin its shape in the TypeScript source; the behaviour was also run
in Node against simulated WhatsApp states (get() working, get() failing with the
reported error, status readable/unreadable, nothing to fall back on).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = (ROOT / "client" / "api_patches" / "src" / "controller" / "deviceController.ts").read_text(encoding="utf-8")


def _get_privacy_settings() -> str:
    start = SOURCE.index("export async function getPrivacySettings")
    return SOURCE[start:SOURCE.index("// setter function name each setting maps", start)]


def test_get_is_tried_first_and_the_fallback_reads_the_six_fields():
    body = _get_privacy_settings()
    assert body.index("WPP.privacy.get()") < body.index("getUserPrivacySettings")
    assert "WPP.whatsapp && WPP.whatsapp.functions" in body


def test_the_original_error_is_rethrown_when_there_is_nothing_to_fall_back_on():
    body = _get_privacy_settings()
    assert "typeof fns.getUserPrivacySettings !== 'function'" in body
    assert "throw e;" in body


def test_the_status_field_is_best_effort():
    """A missing or failing status binding must not fail the six fields."""
    body = _get_privacy_settings()
    status_call = body.index("await fns.getStatusPrivacySetting()")
    try_start = body.rindex("try {", 0, status_call)
    catch_at = body.index("catch (_statusError)", status_call)
    assert try_start < status_call < catch_at
    assert "status === undefined ? fields" in body


def test_the_fallback_is_logged_so_it_can_be_noticed():
    assert "usedFallback" in _get_privacy_settings()
    assert "answered from getUserPrivacySettings()" in _get_privacy_settings()


def test_failures_still_answer_with_a_500_and_the_message():
    body = _get_privacy_settings()
    assert "message: 'Error on get privacy settings'" in body
    assert "res.status(500)" in body
