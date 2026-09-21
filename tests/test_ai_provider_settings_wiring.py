"""Every provider in core/ai_providers.PROVIDERS has to be reachable from the
Settings dialog — a button that opens its own window, its key saved under the
key_setting the fallback chain reads, and all its strings in every locale.

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


def _button_ids_in_dialog_order():
    block = SOURCE[SOURCE.index("self._ai_provider_buttons = {}"):]
    block = block[:block.index("self._build_ai_provider_dialog(")]
    return re.findall(r'\("(\w+)", "\w+", \w+_RECOMMENDED_MODELS\)', block)


def test_dialog_lists_every_provider_in_fallback_order():
    assert _button_ids_in_dialog_order() == IDS


@pytest.mark.parametrize("spec", ai_providers.PROVIDERS, ids=IDS)
def test_key_and_model_are_saved_under_the_names_the_chain_reads(spec):
    assert f'"{spec.key_setting}": self._ai_{spec.id}_api_key_field' in SOURCE
    assert f'"{spec.model_setting}": self._selected_ai_model(' in SOURCE
    assert f"self._ai_{spec.id}_model_combo, self._ai_{spec.id}_model_values" in SOURCE


@pytest.mark.parametrize("locale", LOCALES)
def test_every_provider_has_its_strings_in_every_locale(locale):
    strings = json.loads((ROOT / "languages" / f"{locale}.json").read_text(encoding="utf-8"))
    needed = ["ai_provider_button"]
    for pid in IDS:
        needed += [f"{pid}_api_key_label", f"{pid}_api_key_help_label",
                   f"{pid}_model_label", f"{pid}_model_help_label"]
    assert [k for k in needed if k not in strings] == []
    assert "{provider}" in strings["ai_provider_button"]
