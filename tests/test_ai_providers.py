"""core/ai_providers.py fans a single AI-accessibility call (transcribe,
describe, ask, PDF-to-text) out across whichever providers the user
configured — Gemini, then OpenAI, then Claude — trying each in turn until
one succeeds. This file protects that fallback behavior itself, independent
of any one provider's real API (each provider module has its own
test_<provider>_client.py for that), using fake provider modules so no
network call or API key is ever needed here.
"""

import pytest

import core.ai_providers as ai_providers


class _FakeModule:
    """Stands in for core.gemini_client/openai_client/claude_client: same
    four-function shape, but scripted to succeed or fail on command."""

    def __init__(self, name, fail=False):
        self.name = name
        self.fail = fail
        self.calls = []

    def resolve_model(self, configured):
        return (configured or "").strip() or f"{self.name}-default-model"

    def _maybe_fail_or(self, kind, result):
        self.calls.append(kind)
        if self.fail:
            raise Exception(f"{self.name} falhou em {kind}")
        return result

    def transcribe_audio(self, file_path, api_key, *, model=None):
        return self._maybe_fail_or("transcribe_audio", f"transcrito por {self.name}")

    def describe_visual_media(self, file_path, api_key, *, model=None, is_video=False):
        return self._maybe_fail_or("describe_visual_media", f"descrito por {self.name}")

    def ask_about_visual_media(self, file_path, api_key, question, *, model=None, is_video=False):
        return self._maybe_fail_or("ask_about_visual_media", f"resposta de {self.name}")

    def pdf_to_accessible_text(self, file_path, api_key, *, model=None):
        return self._maybe_fail_or("pdf_to_accessible_text", f"pdf por {self.name}")


@pytest.fixture
def fake_providers(monkeypatch):
    """Swaps the real Gemini/OpenAI/Claude specs for fakes with the same
    capability flags (video: Gemini only; audio: Gemini+OpenAI; image/PDF:
    all three) — every test in this file configures which ones fail."""
    gemini = _FakeModule("gemini")
    openai = _FakeModule("openai")
    claude = _FakeModule("claude")
    specs = [
        ai_providers._ProviderSpec(
            id="gemini", label="Gemini",
            key_setting="gemini_api_key", model_setting="gemini_model",
            module=gemini, supports_audio=True, supports_video=True,
        ),
        ai_providers._ProviderSpec(
            id="openai", label="OpenAI",
            key_setting="openai_api_key", model_setting="openai_model",
            module=openai, supports_audio=True, supports_video=False,
        ),
        ai_providers._ProviderSpec(
            id="claude", label="Claude",
            key_setting="claude_api_key", model_setting="claude_model",
            module=claude, supports_audio=False, supports_video=False,
        ),
    ]
    monkeypatch.setattr(ai_providers, "PROVIDERS", specs)
    return {"gemini": gemini, "openai": openai, "claude": claude}


ALL_KEYS = {"gemini_api_key": "g", "openai_api_key": "o", "claude_api_key": "c"}


class TestConfiguredProviderIds:
    def test_empty_settings_means_no_provider(self):
        assert ai_providers.configured_provider_ids({}) == []

    def test_only_providers_with_a_non_blank_key_count(self):
        settings = {"gemini_api_key": "", "openai_api_key": "  ", "claude_api_key": "c"}
        assert ai_providers.configured_provider_ids(settings) == ["claude"]

    def test_order_follows_the_fixed_fallback_order(self, fake_providers):
        assert ai_providers.configured_provider_ids(ALL_KEYS) == ["gemini", "openai", "claude"]


class TestFallbackOrder:
    def test_first_configured_provider_is_used_when_it_succeeds(self, fake_providers):
        text, used = ai_providers.describe_visual_media("/tmp/x.jpg", ALL_KEYS)
        assert used == "gemini"
        assert text == "descrito por gemini"
        # OpenAI/Claude should never even be tried.
        assert fake_providers["openai"].calls == []
        assert fake_providers["claude"].calls == []

    def test_falls_back_to_the_next_configured_provider_on_failure(self, fake_providers):
        fake_providers["gemini"].fail = True
        text, used = ai_providers.describe_visual_media("/tmp/x.jpg", ALL_KEYS)
        assert used == "openai"
        assert text == "descrito por openai"

    def test_falls_all_the_way_through_to_the_last_provider(self, fake_providers):
        fake_providers["gemini"].fail = True
        fake_providers["openai"].fail = True
        text, used = ai_providers.describe_visual_media("/tmp/x.jpg", ALL_KEYS)
        assert used == "claude"

    def test_raises_a_combined_error_when_every_configured_provider_fails(self, fake_providers):
        for mod in fake_providers.values():
            mod.fail = True
        with pytest.raises(ai_providers.AIProviderError) as excinfo:
            ai_providers.describe_visual_media("/tmp/x.jpg", ALL_KEYS)
        # Every provider's own failure message should be visible, not just
        # the last one tried — the user needs to know why each one failed.
        message = str(excinfo.value)
        assert "gemini" in message.lower()
        assert "openai" in message.lower()
        assert "claude" in message.lower()

    def test_a_provider_with_no_key_configured_is_skipped_entirely(self, fake_providers):
        settings = {"gemini_api_key": "", "openai_api_key": "o", "claude_api_key": "c"}
        text, used = ai_providers.describe_visual_media("/tmp/x.jpg", settings)
        assert used == "openai"
        assert fake_providers["gemini"].calls == []


class TestCapabilityLimits:
    """Video is Gemini-only; audio skips Claude — see each provider's own
    module docstring for why (no raw video or audio modality on the other
    APIs' side)."""

    def test_video_only_tries_gemini(self, fake_providers):
        text, used = ai_providers.describe_visual_media(
            "/tmp/x.mp4", ALL_KEYS, is_video=True
        )
        assert used == "gemini"
        assert fake_providers["openai"].calls == []
        assert fake_providers["claude"].calls == []

    def test_video_fails_outright_if_gemini_is_not_configured(self, fake_providers):
        settings = {"openai_api_key": "o", "claude_api_key": "c"}
        with pytest.raises(ai_providers.AIProviderError):
            ai_providers.describe_visual_media("/tmp/x.mp4", settings, is_video=True)

    def test_video_fails_outright_if_gemini_is_configured_but_errors(self, fake_providers):
        """No fallback net for video — OpenAI/Claude can't process it even
        though their keys are configured."""
        fake_providers["gemini"].fail = True
        with pytest.raises(ai_providers.AIProviderError):
            ai_providers.describe_visual_media("/tmp/x.mp4", ALL_KEYS, is_video=True)

    def test_audio_skips_claude_and_falls_back_to_openai(self, fake_providers):
        fake_providers["gemini"].fail = True
        text, used = ai_providers.transcribe_audio("/tmp/x.ogg", ALL_KEYS)
        assert used == "openai"
        assert fake_providers["claude"].calls == []

    def test_audio_fails_outright_if_only_claude_is_configured(self, fake_providers):
        settings = {"claude_api_key": "c"}
        with pytest.raises(ai_providers.AIProviderError):
            ai_providers.transcribe_audio("/tmp/x.ogg", settings)

    def test_pdf_and_image_are_supported_by_all_three(self, fake_providers):
        fake_providers["gemini"].fail = True
        fake_providers["openai"].fail = True
        text, used = ai_providers.pdf_to_accessible_text("/tmp/x.pdf", ALL_KEYS)
        assert used == "claude"


class TestAskPrefersTheProviderThatDescribed:
    def test_ask_tries_the_preferred_provider_first(self, fake_providers):
        text, used = ai_providers.ask_about_visual_media(
            "/tmp/x.jpg", ALL_KEYS, "qual a cor?", prefer="claude"
        )
        assert used == "claude"
        assert fake_providers["gemini"].calls == []
        assert fake_providers["openai"].calls == []

    def test_ask_still_falls_back_if_the_preferred_provider_now_fails(self, fake_providers):
        fake_providers["claude"].fail = True
        text, used = ai_providers.ask_about_visual_media(
            "/tmp/x.jpg", ALL_KEYS, "qual a cor?", prefer="claude"
        )
        # Falls back to the front of the normal order, skipping the failed
        # preferred provider — never gets stuck because a preference failed.
        assert used == "gemini"


class TestNoProviderConfiguredAtAll:
    def test_raises_a_clear_error_pointing_at_settings(self, fake_providers):
        with pytest.raises(ai_providers.AIProviderError) as excinfo:
            ai_providers.describe_visual_media("/tmp/x.jpg", {})
        assert "Configurações" in str(excinfo.value)
