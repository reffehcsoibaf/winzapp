"""Tests for client/updater.py's release-picking logic — find_zip_asset(),
select_release(), version comparison, and the dual-endpoint _fetch_releases().

This used to be tests/test_alpha_updates.py, covering the two-channel
(stable/alpha) release selection. The alpha channel was retired on
2026-09-22 (see CLAUDE.md's "Manual release process" section) — nothing
publishes an "alpha"-tagged release any more, and select_release() no longer
distinguishes one from a normal release. What survives here is what still
matters with a single channel: picking the newest eligible release out of a
list that mixes real releases with drafts, unparseable tags, and releases
missing their ZIP asset — plus version comparison, which still has to parse
an "alpha"/"dev" suffix correctly forever, since already-published releases
carrying one are immutable on GitHub and will keep showing up in the listing.
"""

import pytest

import updater


def _assets(*names):
    return [
        {"name": n, "browser_download_url": f"https://example.invalid/{n}"}
        for n in names
    ]


def _release(tag, name=None, draft=False, assets=None):
    return {
        "tag_name": tag,
        "name": name if name is not None else tag,
        "draft": draft,
        "assets": _assets("WinZappInstaller.exe", "WinZapp.zip", "SHA256SUMS.txt")
        if assets is None else assets,
    }


# ── find_zip_asset ────────────────────────────────────────────────────────────

def test_zip_asset_prefers_exact_winzapp_zip():
    url = updater.find_zip_asset(_assets("extras.zip", "WinZapp.zip", "SHA256SUMS.txt"))
    assert url.endswith("/WinZapp.zip")


def test_zip_asset_falls_back_to_any_zip():
    url = updater.find_zip_asset(_assets("SHA256SUMS.txt", "portable-build.zip"))
    assert url.endswith("/portable-build.zip")


def test_zip_asset_absent():
    assert updater.find_zip_asset(_assets("SHA256SUMS.txt")) == ""
    assert updater.find_zip_asset([]) == ""
    assert updater.find_zip_asset(None) == ""


# ── select_release ────────────────────────────────────────────────────────────

def test_newest_version_wins():
    releases = [_release("v0.25.0.0"), _release("v0.26.0.0"), _release("v0.24.2.0")]
    picked = updater.select_release(releases)
    assert picked["tag_name"] == "v0.26.0.0"


def test_drafts_are_never_selected():
    releases = [_release("v0.25.0.2", draft=True), _release("v0.25.0.1")]
    picked = updater.select_release(releases)
    assert picked["tag_name"] == "v0.25.0.1"


def test_release_without_zip_asset_is_skipped_not_blocking():
    """A release whose ZIP upload was cut short must not block updates for
    everyone until the next one is cut — the previous good one still wins."""
    releases = [
        _release("v0.25.0.2", assets=_assets("SHA256SUMS.txt")),
        _release("v0.25.0.1"),
    ]
    picked = updater.select_release(releases)
    assert picked["tag_name"] == "v0.25.0.1"


def test_unparseable_tags_are_ignored():
    """The joaopr4 pre-release workflow publishes "-pre" tags that aren't
    WinZapp versions at all; they can't be compared, so they can't be chosen."""
    releases = [_release("v2026.08.21.1200-pre"), _release("v0.25.0.0")]
    picked = updater.select_release(releases)
    assert picked["tag_name"] == "v0.25.0.0"


def test_returns_none_when_nothing_eligible():
    assert updater.select_release([]) is None
    assert updater.select_release([_release("not-a-version")]) is None


def test_a_historical_alpha_tagged_release_still_parses_and_can_be_picked():
    """Old alpha-channel releases are immutable on GitHub and stay in the
    listing forever — select_release() must not choke on one, even though
    nothing publishes new ones any more. Whether it beats a stable release
    is governed purely by version comparison (see below), same as any two
    ordinary releases."""
    releases = [_release("v0.25.0.1500alpha"), _release("v0.24.2.0")]
    picked = updater.select_release(releases)
    assert picked["tag_name"] == "v0.25.0.1500alpha"


# ── Version comparison ─────────────────────────────────────────────────────────

def test_alpha_suffixed_version_still_parses():
    """Historical support: an already-published alpha release's tag must keep
    parsing correctly forever (see module docstring)."""
    assert updater.parse_version("0.25.0.1500alpha") == ((0, 25, 0, 1500), "alpha")


def test_beta_orders_below_no_suffix():
    assert updater.is_newer("0.25.0.0", "0.25.0.0beta") is True
    assert updater.is_newer("0.25.0.0beta", "0.25.0.0") is False


def test_newer_patch_wins():
    assert updater.is_newer("0.25.1.0", "0.25.0.0") is True
    assert updater.is_newer("0.25.0.0", "0.25.1.0") is False


def test_identical_versions_are_not_newer():
    assert updater.is_newer("0.25.0.0", "0.25.0.0") is False


# ── _fetch_releases: listing + /releases/latest ────────────────────────────────

def _fetching_checker(responses):
    """Build a checker whose _get_json() answers from *responses* (url
    substring -> payload, or an Exception instance to raise)."""
    checker = updater.UpdateChecker(_StubMainWindow({}))
    calls = []

    def _get_json(url, params=None):
        calls.append((url, params))
        for fragment, payload in responses.items():
            if url.endswith(fragment):
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise AssertionError(f"unexpected url {url}")

    checker._get_json = _get_json
    checker._calls = calls
    return checker


class _StubMainWindow:
    def __init__(self, settings):
        self.settings = settings


def test_fetch_merges_listing_and_latest_stable():
    listing = [_release(f"v0.25.0.{n}") for n in range(0, 40)]
    stable  = _release("v0.25.0.100")
    checker = _fetching_checker({"/releases/latest": stable, "/releases": listing})

    fetched = checker._fetch_releases()
    tags = {r["tag_name"] for r in fetched}
    assert "v0.25.0.100" in tags
    assert "v0.25.0.39" in tags


def test_fetch_asks_for_a_full_page():
    checker = _fetching_checker({
        "/releases/latest": _release("v0.25.0.0"),
        "/releases": [],
    })
    checker._fetch_releases()
    listing_call = [c for c in checker._calls if c[0].endswith("/releases")][0]
    assert listing_call[1] == {"per_page": 100}


def test_fetch_dedupes_a_release_returned_by_both_endpoints():
    stable = dict(_release("v0.25.0.0"), id=42)
    checker = _fetching_checker({"/releases/latest": stable, "/releases": [stable]})
    assert len(checker._fetch_releases()) == 1


def test_fetch_survives_a_failing_listing():
    """A rate-limited listing still leaves the stable release reachable."""
    checker = _fetching_checker({
        "/releases/latest": _release("v0.25.0.0"),
        "/releases": RuntimeError("HTTP 403 rate limited"),
    })
    fetched = checker._fetch_releases()
    assert [r["tag_name"] for r in fetched] == ["v0.25.0.0"]


def test_fetch_survives_a_missing_latest_stable():
    """/releases/latest 404s on a repo that only ever published prereleases."""
    checker = _fetching_checker({
        "/releases/latest": RuntimeError("HTTP 404"),
        "/releases": [_release("v0.25.0.0")],
    })
    fetched = checker._fetch_releases()
    assert [r["tag_name"] for r in fetched] == ["v0.25.0.0"]


def test_fetch_raises_only_when_both_endpoints_fail():
    checker = _fetching_checker({
        "/releases/latest": RuntimeError("HTTP 404"),
        "/releases": RuntimeError("HTTP 403 rate limited"),
    })
    with pytest.raises(Exception):
        checker._fetch_releases()


def test_fetch_accepts_a_single_release_object_from_a_fork():
    """A fork could point the configured URL at one release rather than a list."""
    checker = _fetching_checker({
        "/releases/latest": RuntimeError("HTTP 404"),
        "/releases": _release("v0.25.0.0"),
    })
    assert [r["tag_name"] for r in checker._fetch_releases()] == ["v0.25.0.0"]


def test_configured_stable_url_is_the_listing_url_plus_latest():
    import config
    assert config.GITHUB_API_LATEST_STABLE_RELEASE == (
        config.GITHUB_API_LATEST_RELEASE + "/latest"
    )


# ── End-to-end: _check_once picks the right release and offers it ─────────────

class _I18n:
    def get_language(self):
        return "pt-BR"

    def t(self, key):
        return key


def _end_to_end_checker(monkeypatch, releases, local_version):
    """Drive the real _check_once() with the network and wx stubbed out, and
    report what it decided to offer the user."""
    mw = _StubMainWindow({"general": {}})
    mw.i18n = _I18n()
    checker = updater.UpdateChecker(mw)

    monkeypatch.setattr(updater, "__version__", local_version)
    monkeypatch.setattr(checker, "_fetch_releases", lambda: releases)
    # Don't leave a real 3-hour threading.Timer behind.
    outcome = {"offered": None, "retried": False}
    monkeypatch.setattr(checker, "_schedule_retry", lambda: outcome.update(retried=True))
    monkeypatch.setattr(
        updater.wx, "CallAfter",
        lambda fn, *a, **kw: outcome.update(offered=(getattr(fn, "__name__", ""), a)),
    )

    checker._check_once()
    return outcome


def test_end_to_end_user_is_offered_the_newest_release(monkeypatch):
    releases = [_release("v0.25.0.1"), _release("v0.25.0.0")]
    out = _end_to_end_checker(monkeypatch, releases, "0.24.2.0")
    assert out["offered"][0] == "_show_update_dialog"
    version, _changelog, zip_url, sums_url = out["offered"][1]
    assert version == "0.25.0.1"
    assert zip_url.endswith("/WinZapp.zip")
    assert sums_url.endswith("/SHA256SUMS.txt")


def test_end_to_end_user_running_latest_is_not_offered_anything(monkeypatch):
    releases = [_release("v0.25.0.0")]
    out = _end_to_end_checker(monkeypatch, releases, "0.25.0.0")
    assert out["offered"] is None
    assert out["retried"] is True


def test_end_to_end_network_failure_just_retries(monkeypatch):
    mw = _StubMainWindow({"general": {}})
    mw.i18n = _I18n()
    checker = updater.UpdateChecker(mw)
    retried = []
    monkeypatch.setattr(checker, "_fetch_releases", lambda: (_ for _ in ()).throw(RuntimeError("no net")))
    monkeypatch.setattr(checker, "_schedule_retry", lambda: retried.append(True))
    checker._check_once()
    assert retried == [True]
