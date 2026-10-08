"""Keep the Puppeteer browser across WPPConnect Server updates.

A WPPConnect update used to wipe everything in ``api/`` that was not on the
keep-list, including ``api/.cache`` where the browser lives (``chrome`` on
Windows). The ``puppeteer browsers install`` step that follows then downloaded
the whole browser again, every time, although its version almost never changes.

With ``.cache`` kept, that step finds the version directory already there and
skips the download (and when the new dependencies need a different build, it
downloads only that one). Two things make keeping it safe:

* ``remove_incomplete()`` runs first. Puppeteer skips its download whenever the
  version directory EXISTS, even if it is damaged, so a half-written build left
  by an earlier failure would otherwise be kept forever. The check is the same
  one the startup path uses (``core.browser_payload.payload_problem``).
* ``prune_older()`` runs after a successful install, so the cache does not grow
  by a browser per update: only the newest complete build per platform stays.

Plain functions over paths, no wx and no Node, so it is tested on temporary
directories. Only directories whose names match the known
``<platform>-<a.b.c.d>`` layout are ever touched, and only when they really sit
inside the cache.
"""

import logging
import os
import re
import shutil

from core.browser_payload import payload_problem

_VERSION_DIR = re.compile(r"(win32|win64|linux)-(\d+(?:\.\d+){3})")


def _binary_for(version_dir: str, product: str, platform: str) -> str:
    folder = "%s-%s" % (product, "linux64" if platform == "linux" else platform)
    binary = product + (".exe" if platform.startswith("win") else "")
    return os.path.join(version_dir, folder, binary)


def _inside(cache_dir: str, path: str) -> bool:
    """Whether *path* really sits inside *cache_dir* (junctions/links included)."""
    try:
        root = os.path.realpath(cache_dir)
        return os.path.commonpath((root, os.path.realpath(path))) == root
    except (OSError, ValueError):
        return False


def _versions(cache_dir: str, product: str):
    """(platform, version_tuple, version_dir, binary) for every known layout."""
    product_dir = os.path.join(cache_dir, product)
    if not os.path.isdir(product_dir) or os.path.islink(product_dir):
        return
    if not _inside(cache_dir, product_dir):
        return
    try:
        names = os.listdir(product_dir)
    except OSError:
        return
    for name in names:
        match = _VERSION_DIR.fullmatch(name)
        version_dir = os.path.join(product_dir, name)
        if not match or not os.path.isdir(version_dir) or os.path.islink(version_dir):
            continue
        if not _inside(cache_dir, version_dir):
            continue
        version = tuple(int(part) for part in match.group(2).split("."))
        yield match.group(1), version, version_dir, _binary_for(version_dir, product, match.group(1))


def _complete(binary: str) -> bool:
    try:
        return (os.path.isfile(binary) and os.path.getsize(binary) > 0
                and payload_problem(binary) is None)
    except OSError:
        return False


def remove_incomplete(cache_dir: str, product: str) -> "list[str]":
    """Delete browser builds that cannot start, so puppeteer downloads them again.

    Returns the removed directories. Never raises.
    """
    removed = []
    try:
        for _platform, _version, version_dir, binary in list(_versions(cache_dir, product)):
            if _complete(binary):
                continue
            logging.info("[browser-cache] Removing incomplete browser build: %s", version_dir)
            shutil.rmtree(version_dir, ignore_errors=True)
            if not os.path.isdir(version_dir):
                removed.append(version_dir)
    except Exception:
        logging.exception("[browser-cache] Could not check the browser cache")
    return removed


def prune_older(cache_dir: str, product: str) -> "list[str]":
    """Keep only the newest COMPLETE build per platform; delete the older ones.

    Does nothing for a platform that has no complete build, so a failed
    download never leaves the install with less than it had. Returns the
    removed directories. Never raises.
    """
    removed = []
    try:
        by_platform = {}
        for platform, version, version_dir, binary in _versions(cache_dir, product):
            by_platform.setdefault(platform, []).append((version, version_dir, binary))
        for builds in by_platform.values():
            complete = sorted((b for b in builds if _complete(b[2])), key=lambda b: b[0])
            if not complete:
                continue
            newest = complete[-1][1]
            for _version, version_dir, _binary in builds:
                if version_dir == newest:
                    continue
                shutil.rmtree(version_dir, ignore_errors=True)
                if not os.path.isdir(version_dir):
                    logging.info("[browser-cache] Removed older browser build: %s", version_dir)
                    removed.append(version_dir)
    except Exception:
        logging.exception("[browser-cache] Could not prune older browser builds")
    return removed
