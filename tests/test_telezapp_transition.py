"""The TeleZapp rename must reach copies that are already installed.

An installed WinZapp 1.1.5.2 updates itself with the OLD updater: it only
understands four-number versions, relaunches the executable it was started
from (WinZapp.exe) after copying the ZIP over its folder, prefers WinZapp.zip,
and verifies a manifest whose first line starts with "# winzapp-version:". This
release therefore changes what people SEE (the name) and keeps those technical
names. These tests pin both halves so a later cleanup cannot quietly break the
update path of every installed copy.
"""

import json
import re
from pathlib import Path

from packaging.version import Version

from branding import APP_NAME, APP_NAMES, LEGACY_APP_NAME, is_app_window_title, is_default_account_name

ROOT = Path(__file__).resolve().parent.parent
LANGS = ("pt-BR", "pt-PT", "en-US", "es-ES", "pl")


def _read(*parts) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_branding_names():
    assert APP_NAME == "TeleZapp" and LEGACY_APP_NAME == "WinZapp"
    assert set(APP_NAMES) == {"TeleZapp", "WinZapp"}


def test_default_account_name_accepts_both_spellings():
    for name in (None, "", "TeleZapp", "WinZapp"):
        assert is_default_account_name(name)
    assert not is_default_account_name("Trabalho")


def test_window_title_match_accepts_both_spellings():
    assert is_app_window_title("TeleZapp")
    assert is_app_window_title("TeleZapp — Trabalho (2)")
    assert is_app_window_title("WinZapp")           # a copy that has not updated yet
    assert not is_app_window_title("Bloco de Notas")
    assert not is_app_window_title(None)


def test_every_language_uses_the_new_name():
    for lang in LANGS:
        data = json.loads(_read("client", "languages", f"{lang}.json"))
        assert data["app_name"] == "TeleZapp"
        leftovers = {k for k, v in data.items() if isinstance(v, str) and "WinZapp" in v}
        # Only the credit to the original project may keep the old name.
        assert leftovers == {"about_developed_by"}, (lang, leftovers)
        assert "TeleZapp" in data["about_developed_by"] and "WinZapp" in data["about_developed_by"]


def test_guides_use_the_new_name():
    for lang in LANGS:
        assert "WinZapp" not in _read("client", "data", "help_guide", f"{lang}.html")


def test_version_is_a_four_number_date_the_old_updater_accepts():
    version = re.search(r'__version__\s*=\s*"([^"]+)"', _read("client", "version.py")).group(1)
    # Same pattern the installed updater uses: exactly four numbers.
    old_updater_pattern = re.search(r'_VER_RE = re.compile\(r"(.+?)"', _read("client", "updater.py")).group(1)
    assert re.match(old_updater_pattern, version), version
    year, month, day, release = (int(p) for p in version.split("."))
    assert 2026 <= year and 1 <= month <= 12 and 1 <= day <= 31 and release >= 0
    # Windows VERSIONINFO takes 16-bit integers.
    assert all(p < 65536 for p in (year, month, day, release))
    # And it must sort above every release of the old numbering, or it is never offered.
    assert Version(version) > Version("1.1.5.2")


def test_changelogs_have_the_release_on_top_in_every_language():
    version = re.search(r'__version__\s*=\s*"([^"]+)"', _read("client", "version.py")).group(1)
    for lang in LANGS:
        first = _read("client", f"changelog_{lang}.txt").splitlines()[0].strip()
        assert first == f"V{version}", (lang, first)


def test_technical_names_old_installs_depend_on_are_unchanged():
    updater = _read("client", "updater.py")
    # After copying the ZIP over the install folder, the old updater reopens the
    # executable it was started from: that file must still exist in the new ZIP.
    assert 'os.path.join(extracted_dir, "WinZapp")' in updater
    assert '"WinZapp.exe"' in updater
    assert "WinZapp.zip" in updater
    # Manifest header that installed copies verify.
    assert '# winzapp-version:' in _read("scripts", "generate_release_manifest.py")
    build = _read("build.py")
    assert "StringStruct('OriginalFilename', 'WinZapp.exe')" in build
    # What the properties dialog shows is the new name.
    assert "StringStruct('ProductName', 'TeleZapp')" in build
    # Windows identities that would orphan settings or allow two instances if renamed.
    assert '_AUTORUN_NAME = "WinZapp"' in _read("client", "autostart.py")
    assert 'APP_ID    = "WinZapp"' in _read("client", "core", "notification_manager.py")
