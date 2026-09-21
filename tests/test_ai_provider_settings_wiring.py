"""Every provider in core/ai_providers.PROVIDERS has to be reachable from the
Settings dialog — a button that opens the shared key/model window, its values
saved under the names the fallback chain reads, and all its strings in every
locale.

The dialog itself can't be built here (a plain pytest never opens a window —
see CLAUDE.md), so this reads the source and the language files instead: it
catches the drift that actually happens, a provider added to PROVIDERS and
forgotten in the UI, or the reverse.
"""

import json
import re
from pathlib import Path

import pytest

from core import ai_providers

ROOT = Path(__file__).resolve().parent.parent / "client"
SOURCE = (ROOT / "ui" / "dialogs" / "settings_dialog.py").read_text(encoding="utf-8")
LOCALES = sorted(p.stem for p in (ROOT / "languages").glob("*.json") if p.stem != "language_map")
IDS = [p.id for p in ai_providers.PROVIDERS]


def _ids_in_dialog_table():
    block = SOURCE[SOURCE.index("_AI_PROVIDER_UI = ("):]
    block = block[:block.index("\n)\n")]
    return re.findall(r'\("(\w+)", "\w+", \w+_RECOMMENDED_MODELS\)', block)


def test_dialog_lists_every_provider_in_fallback_order():
    assert _ids_in_dialog_table() == IDS


@pytest.mark.parametrize("spec", ai_providers.PROVIDERS, ids=IDS)
def test_settings_names_follow_the_pattern_the_dialog_saves_under(spec):
    """The dialog stores each provider's values under f"{id}_api_key" and
    f"{id}_model" (one shared window, driven by a table) — the chain reads
    key_setting/model_setting, so the two have to agree."""
    assert spec.key_setting == f"{spec.id}_api_key"
    assert spec.model_setting == f"{spec.id}_model"


def test_the_dialog_saves_and_loads_by_that_same_pattern():
    assert '(f"{pid}_api_key", st["key"])' in SOURCE
    assert '(f"{pid}_model", st["model"])' in SOURCE
    assert 'ai_settings.get(f"{_pid}_api_key")' in SOURCE
    assert 'ai_settings.get(f"{_pid}_model")' in SOURCE


def test_the_provider_window_is_built_lazily_and_only_once():
    """Five ready-made windows per SettingsDialog exhausted the Windows handle
    quota in CI (tests/test_settings_files_saving_tab.py) — the window must not
    be created in _build_ui()."""
    build_ui = SOURCE[SOURCE.index("    def _build_ui(self"):SOURCE.index("    def _open_ai_provider_dialog")]
    assert '_wrap_pages_in_dialog(self, i18n, ""' not in build_ui
    assert "self._ai_provider_dialog = None" in build_ui


@pytest.mark.parametrize("locale", LOCALES)
def test_every_provider_has_its_strings_in_every_locale(locale):
    strings = json.loads((ROOT / "languages" / f"{locale}.json").read_text(encoding="utf-8"))
    needed = ["ai_provider_button"]
    for pid in IDS:
        needed += [f"{pid}_api_key_label", f"{pid}_api_key_help_label",
                   f"{pid}_model_label", f"{pid}_model_help_label"]
    assert [k for k in needed if k not in strings] == []
    assert "{provider}" in strings["ai_provider_button"]
