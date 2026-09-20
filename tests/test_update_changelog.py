"""What the update prompt's "Quais as novidades?" button shows.

The changelog installed with the app describes the version the user already
has, so the notes for the version on offer have to come from the release's own
tag. These tests pin where the text comes from and, just as important, that a
changelog with nothing new in it is never passed off as news.
"""

import updater
from updater import fetch_release_changelog, resolve_changelog

_CHANGELOG = (
    "V1.1.3.0\n\nNOVIDADES\n\n- Guia de uso dentro do app.\n\n"
    "V1.1.2.0\n\nMELHORIAS\n\n- Algo que o usuario ja tem.\n"
)
_OLD_INSTALLED = "V1.1.2.0\n\nMELHORIAS\n\n- Algo que o usuario ja tem.\n"


class TestFetchReleaseChangelog:
    def test_reads_the_file_at_the_releases_tag(self):
        urls = []

        def get_text(url):
            urls.append(url)
            return _CHANGELOG

        assert fetch_release_changelog("v1.1.3.0", "pt-BR", get_text) == _CHANGELOG
        assert urls == [
            f"https://raw.githubusercontent.com/{updater.GITHUB_REPO}/"
            "v1.1.3.0/client/changelog_pt-BR.txt"
        ]

    def test_falls_back_to_en_us_when_the_language_has_no_file(self):
        def get_text(url):
            if url.endswith("changelog_pl.txt"):
                raise RuntimeError("404")
            return "V1.1.3.0\n\n- english\n"

        assert "english" in fetch_release_changelog("v1.1.3.0", "pl", get_text)

    def test_a_failed_download_is_an_empty_string_not_an_exception(self):
        def get_text(url):
            raise ConnectionError("offline")

        assert fetch_release_changelog("v1.1.3.0", "pt-BR", get_text) == ""

    def test_an_empty_file_counts_as_no_file(self):
        assert fetch_release_changelog("v1.1.3.0", "en-US", lambda url: "  \n") == ""

    def test_the_tag_cannot_alter_the_path(self):
        urls = []
        fetch_release_changelog("v1/../../x", "en-US",
                                lambda url: urls.append(url) or "")
        assert "/../" not in urls[0]


class TestResolveChangelog:
    def test_the_release_tags_notes_win_over_the_installed_file(self, monkeypatch):
        monkeypatch.setattr(updater, "load_changelog_text", lambda lang: _OLD_INSTALLED)
        text = resolve_changelog("1.1.2.0", "1.1.3.0", "pt-BR", remote_text=_CHANGELOG)
        assert "Guia de uso dentro do app" in text
        assert "ja tem" not in text

    def test_notes_the_user_already_has_are_never_shown_as_news(self, monkeypatch):
        """The bug this replaces: nothing in (installed, offered] used to fall
        back to the whole installed file."""
        monkeypatch.setattr(updater, "load_changelog_text", lambda lang: _OLD_INSTALLED)
        assert resolve_changelog("1.1.2.0", "1.1.3.0", "pt-BR") == ""

    def test_the_installed_file_is_used_when_the_download_failed_but_it_covers_the_range(
        self, monkeypatch
    ):
        monkeypatch.setattr(updater, "load_changelog_text", lambda lang: _CHANGELOG)
        text = resolve_changelog("1.1.2.0", "1.1.3.0", "pt-BR", remote_text="")
        assert "Guia de uso dentro do app" in text

    def test_the_release_body_is_the_last_resort(self, monkeypatch):
        monkeypatch.setattr(updater, "load_changelog_text", lambda lang: "")
        assert resolve_changelog(
            "1.1.2.0", "1.1.3.0", "pt-BR", release_body="  corpo do release  "
        ) == "corpo do release"

    def test_a_jump_over_several_versions_includes_each_of_them(self, monkeypatch):
        monkeypatch.setattr(updater, "load_changelog_text", lambda lang: "")
        text = resolve_changelog("1.1.1.0", "1.1.3.0", "pt-BR", remote_text=_CHANGELOG)
        assert "V1.1.3.0" in text and "V1.1.2.0" in text


class _FakeI18n:
    def t(self, key):
        return key


class _FakeMainWindow:
    i18n = _FakeI18n()


class _Stub:
    _on_whats_new = updater.UpdateDialog._on_whats_new

    def __init__(self, changelog):
        self._changelog = changelog
        self._main_window = _FakeMainWindow()


class TestWhatsNewButton:
    def test_with_nothing_to_show_it_says_so_instead_of_opening_a_blank_window(
        self, monkeypatch
    ):
        boxes, dialogs = [], []
        monkeypatch.setattr(updater.wx, "MessageBox", lambda *a, **kw: boxes.append(a))
        monkeypatch.setattr(updater, "WhatsNewDialog",
                            lambda *a, **kw: dialogs.append(a))

        stub = _Stub("  \n")
        stub._on_whats_new(None)

        assert dialogs == []
        assert boxes[0][0] == "whats_new_none_message"
        assert boxes[0][1] == "whats_new_none_title"

    def test_with_notes_it_opens_the_whats_new_dialog(self, monkeypatch):
        shown = []

        class _FakeDialog:
            def __init__(self, parent, changelog):
                shown.append(changelog)

            def ShowModal(self):
                pass

            def Destroy(self):
                pass

        monkeypatch.setattr(updater, "WhatsNewDialog", _FakeDialog)
        monkeypatch.setattr(updater.wx, "MessageBox",
                            lambda *a, **kw: shown.append("MESSAGEBOX"))

        _Stub("V1.1.3.0\n- novo")._on_whats_new(None)

        assert shown == ["V1.1.3.0\n- novo"]
