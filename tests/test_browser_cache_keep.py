"""The browser cache must survive a WPPConnect update, safely.

The update used to delete api/.cache, so every update downloaded the whole
browser again. It is kept now (_KEEP_RUNTIME), which is only safe because an
incomplete build is removed before puppeteer decides whether to download, and
older builds are pruned afterwards.
"""

import os
import re
from pathlib import Path

from core.browser_cache_keep import prune_older, remove_incomplete


def _build(cache: Path, version: str, *, platform="win64", product="chrome",
           icu=True, binary=True) -> Path:
    version_dir = cache / product / f"{platform}-{version}"
    payload = version_dir / f"{product}-{platform}"
    payload.mkdir(parents=True)
    if binary:
        (payload / f"{product}.exe").write_bytes(b"MZ-not-really")
    if icu:
        (payload / "icudtl.dat").write_bytes(b"icu")
    return version_dir


def test_complete_build_is_kept(tmp_path):
    good = _build(tmp_path, "142.0.7444.162")
    assert remove_incomplete(str(tmp_path), "chrome") == []
    assert good.is_dir()


def test_build_missing_its_icu_data_is_removed(tmp_path):
    broken = _build(tmp_path, "142.0.7444.162", icu=False)
    assert remove_incomplete(str(tmp_path), "chrome") == [str(broken)]
    assert not broken.exists()


def test_build_without_a_binary_is_removed(tmp_path):
    broken = _build(tmp_path, "142.0.7444.162", binary=False)
    remove_incomplete(str(tmp_path), "chrome")
    assert not broken.exists()


def test_unknown_entries_are_never_touched(tmp_path):
    stray = tmp_path / "chrome" / "something-else"
    stray.mkdir(parents=True)
    (stray / "file.txt").write_text("keep me")
    remove_incomplete(str(tmp_path), "chrome")
    prune_older(str(tmp_path), "chrome")
    assert (stray / "file.txt").exists()


def test_missing_cache_is_not_an_error(tmp_path):
    assert remove_incomplete(str(tmp_path / "nope"), "chrome") == []
    assert prune_older(str(tmp_path / "nope"), "chrome") == []


def test_prune_keeps_only_the_newest_complete_build(tmp_path):
    old = _build(tmp_path, "141.0.1.1")
    new = _build(tmp_path, "142.0.1.1")
    removed = prune_older(str(tmp_path), "chrome")
    assert removed == [str(old)]
    assert new.is_dir() and not old.exists()


def test_prune_orders_versions_numerically(tmp_path):
    nine = _build(tmp_path, "9.0.0.0")
    ten = _build(tmp_path, "10.0.0.0")
    prune_older(str(tmp_path), "chrome")
    assert ten.is_dir() and not nine.exists()


def test_prune_never_leaves_the_install_without_a_working_browser(tmp_path):
    old = _build(tmp_path, "141.0.1.1")
    new_broken = _build(tmp_path, "142.0.1.1", icu=False)
    prune_older(str(tmp_path), "chrome")
    assert old.is_dir()          # the only complete build stays
    assert not new_broken.exists()


def test_prune_with_no_complete_build_deletes_nothing(tmp_path):
    only = _build(tmp_path, "142.0.1.1", icu=False)
    assert prune_older(str(tmp_path), "chrome") == []
    assert only.is_dir()


def test_prune_is_per_platform(tmp_path):
    win = _build(tmp_path, "142.0.1.1", platform="win64")
    win32 = _build(tmp_path, "142.0.1.1", platform="win32")
    prune_older(str(tmp_path), "chrome")
    assert win.is_dir() and win32.is_dir()


def test_other_product_is_not_touched(tmp_path):
    shell = _build(tmp_path, "141.0.1.1", product="chrome-headless-shell")
    _build(tmp_path, "142.0.1.1", product="chrome")
    prune_older(str(tmp_path), "chrome")
    assert shell.is_dir()


def test_linked_version_directory_is_skipped(tmp_path):
    outside = tmp_path / "outside" / "win64-1.0.0.0"
    (outside / "chrome-win64").mkdir(parents=True)
    (outside / "chrome-win64" / "keep.txt").write_text("keep")
    cache = tmp_path / "cache"
    (cache / "chrome").mkdir(parents=True)
    link = cache / "chrome" / "win64-1.0.0.0"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        return  # symlinks unavailable here; the containment check is the same code path
    remove_incomplete(str(cache), "chrome")
    prune_older(str(cache), "chrome")
    assert (outside / "chrome-win64" / "keep.txt").exists()


def test_api_setup_keeps_the_cache_and_uses_the_helpers():
    source = (Path(__file__).resolve().parent.parent / "client" / "ui" / "dialogs" / "api_setup.py").read_text(encoding="utf-8")
    match = re.search(r"^_KEEP_RUNTIME = \{(.*?)\}$", source, re.MULTILINE)
    assert match and '".cache"' in match.group(1)
    assert "remove_incomplete(puppeteer_cache, browser_product)" in source
    assert "prune_older(puppeteer_cache, browser_product)" in source
    # Repair BEFORE puppeteer decides whether to download, prune only AFTER it.
    install = source.index('"browsers", "install", browser_product')
    assert source.index("remove_incomplete(puppeteer_cache") < install < source.index("prune_older(puppeteer_cache")
