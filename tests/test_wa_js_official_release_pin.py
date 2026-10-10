"""wa-js and wppconnect are pinned to official npm releases, not to a commit.

The Privacidade and Nome tabs needed two wa-js fixes (#3632 and #3682) that were
in no release for a while, so wa-js was pinned to a GitHub commit. A git
dependency makes `npm install` build wa-js on every user's machine (webpack plus
its dev dependencies, roughly three minutes). wa-js 4.6.1 contains both fixes,
so the pin is a plain version again. These tests keep it that way, and keep it
from moving below the release that carries the fixes.
"""

import json
import re
from pathlib import Path

from packaging.version import Version

ROOT = Path(__file__).resolve().parent.parent
_EXACT = re.compile(r"\d+\.\d+\.\d+")


def _dependencies() -> dict:
    return json.loads(
        (ROOT / "client" / "api_patches" / "package.json").read_text(encoding="utf-8")
    )["dependencies"]


def test_wa_js_is_an_exact_npm_version_not_a_git_dependency():
    pin = _dependencies()["@wppconnect/wa-js"]
    assert _EXACT.fullmatch(pin), (
        f"@wppconnect/wa-js is {pin!r}. A git URL makes npm install build wa-js "
        f"on the user's machine; use an exact npm version."
    )


def test_wa_js_is_not_older_than_the_release_with_the_privacy_and_name_fixes():
    # 4.6.0 lacks wa-js#3632 (privacy setters) and #3682 (profile name).
    assert Version(_dependencies()["@wppconnect/wa-js"]) >= Version("4.6.1")


def test_wppconnect_is_an_exact_npm_version():
    pin = _dependencies()["@wppconnect-team/wppconnect"]
    assert _EXACT.fullmatch(pin), pin


def test_wppconnect_is_new_enough_for_the_pinned_wa_js():
    """wppconnect 2.3.4 is the first to declare wa-js ^4.6.1; with an older one
    the installed pair would no longer be the one that was audited together."""
    assert Version(_dependencies()["@wppconnect-team/wppconnect"]) >= Version("2.3.4")


def test_no_git_dependency_is_left_in_the_patched_package_json():
    for name, spec in _dependencies().items():
        assert "github:" not in spec and not spec.startswith("git"), (name, spec)
