"""resolve_model() is the one place that decides which Gemini model a call
actually uses — every caller in conversations.py goes through it instead of
repeating "or DEFAULT_MODEL" by hand. That single-source-of-truth property is
what this file is protecting: a caller that stops going through it would
silently pin itself to whatever DEFAULT_MODEL happened to be at the time,
instead of following it forward the next time a model gets retired (as
gemini-2.5-flash did — see DEFAULT_MODEL's own comment).
"""

import inspect

from core.gemini_client import DEFAULT_MODEL, RECOMMENDED_MODELS, resolve_model


class TestAutomaticFollowsTheDefault:
    def test_none_falls_back_to_the_default(self):
        assert resolve_model(None) == DEFAULT_MODEL

    def test_empty_string_falls_back_to_the_default(self):
        assert resolve_model("") == DEFAULT_MODEL

    def test_whitespace_only_falls_back_to_the_default(self):
        """A settings.json hand-edited to "   " should behave like "", not
        like a (broken) model id."""
        assert resolve_model("   ") == DEFAULT_MODEL


class TestAConfiguredModelIsPinned:
    def test_a_chosen_model_is_used_as_is(self):
        assert resolve_model("gemini-3.8-flash") == "gemini-3.8-flash"

    def test_surrounding_whitespace_is_stripped(self):
        assert resolve_model("  gemini-3.6-flash  ") == "gemini-3.6-flash"

    def test_a_model_outside_the_recommended_list_is_still_honored(self):
        """Settings.json may hold a model this version of WinZapp doesn't
        list anymore (or doesn't list yet) — resolve_model() itself has no
        opinion on that; it's not the validation layer, just the fallback."""
        assert resolve_model("gemini-9.9-flash") == "gemini-9.9-flash"


class TestTheDefaultIsAlwaysAnOfferedChoice:
    def test_default_model_is_one_of_the_recommended_models(self):
        """Otherwise Settings would offer choices that don't include what
        "Automatic" actually resolves to right now."""
        assert DEFAULT_MODEL in RECOMMENDED_MODELS


class TestEveryCallerGoesThroughResolveModel:
    """conversations.py must never read ai_accessibility['gemini_model'] and
    fall back to DEFAULT_MODEL by hand — that duplicates the rule this file
    tests above, and the two copies drifting apart is exactly how the model
    Settings shows as selected stops matching the model actually called."""

    def test_conversations_uses_resolve_model_not_a_hand_rolled_fallback(self):
        import ui.conversations as conversations_module

        src = inspect.getsource(conversations_module)
        assert "_gemini_resolve_model(" in src
        assert 'get("gemini_model")) or DEFAULT_MODEL' not in src
