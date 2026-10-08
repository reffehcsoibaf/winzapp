"""Keep a newer WPPConnect Server when WinZapp itself updates.

The WinZapp release ZIP carries ``api/package.json`` and ``api/dist/`` built
from the WPPConnect Server tag in ``wpp_minimum_version.txt``. The installer
script copies the ZIP over the install folder with ``xcopy /E /Y``, so those two
land on top of whatever the user already has.

When the user had updated the server past the bundled one (in-app WPPConnect
update, Force Reinstall), that copy put the *older* ``package.json`` back. The
server's version is read from that file, so the very next check saw the old
number and offered the same WPPConnect update again.

``keep_newer_installed_server()`` runs on the extracted payload BEFORE the
installer script starts. When the installed ``package.json`` is strictly newer
than the one in the payload, the payload's copy is replaced by a merge, so the
xcopy writes back the newer server version instead of the older one:

* everything comes from the INSTALLED file (it matches the ``node_modules`` that
  is already on disk), except
* the dependencies WinZapp pins itself (``patched_keys``, i.e. the wppconnect
  library the patches target) take the payload's value, so the existing
  "library drift" check still fires if node_modules disagrees, and
* any dependency the payload has and the installed file lacks is added, because
  the payload's ``dist/`` (which still comes from the release — it is how
  WinZapp's own patched controllers reach an install) may require it.

Deliberately stdlib-only and plain functions over paths: no wx, no Node, no
network, so it is tested on temporary directories. It never raises into the
updater: the worst outcome of any failure here is the old behaviour.
"""

import json
import logging
import os
import tempfile


def _read_package(path: str) -> dict:
    try:
        with open(path, encoding="utf-8-sig") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def is_newer_server(installed: str, shipped: str) -> bool:
    """True only when *installed* is strictly newer than *shipped*.

    Anything unparseable answers False: "I cannot tell" must never become
    "keep the installed file", which would freeze an install on a version the
    release's dist/ may no longer match.
    """
    if not isinstance(installed, str) or not isinstance(shipped, str):
        return False
    if not installed.strip() or not shipped.strip():
        return False
    try:
        from packaging.version import Version
        return Version(installed.strip().lstrip("vV")) > Version(shipped.strip().lstrip("vV"))
    except Exception:
        return False


def merged_package(installed: dict, shipped: dict, patched_keys) -> dict:
    """The package.json that is written back: installed, plus the release's pins."""
    merged = json.loads(json.dumps(installed))  # deep copy; installed stays untouched
    shipped_deps = shipped.get("dependencies")
    shipped_deps = shipped_deps if isinstance(shipped_deps, dict) else {}
    deps = merged.get("dependencies")
    if not isinstance(deps, dict):
        deps = {}
        merged["dependencies"] = deps
    for key in patched_keys or ():
        if key in shipped_deps:
            deps[key] = shipped_deps[key]
    for name, version in shipped_deps.items():
        if name not in deps:
            deps[name] = version
    return merged


def keep_newer_installed_server(payload_api_dir: str, installed_api_dir: str,
                                patched_keys) -> bool:
    """Replace the payload's package.json when the installed server is newer.

    Returns True when the payload file was replaced. Never raises.
    """
    try:
        payload_path = os.path.join(payload_api_dir, "package.json")
        installed_path = os.path.join(installed_api_dir, "package.json")
        if not (os.path.isfile(payload_path) and os.path.isfile(installed_path)):
            return False
        shipped = _read_package(payload_path)
        installed = _read_package(installed_path)
        if not is_newer_server(installed.get("version"), shipped.get("version")):
            return False

        merged = merged_package(installed, shipped, patched_keys)
        # Build the text first: a package.json that cannot be serialised must
        # not leave an empty temp file in the payload.
        text = json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
        fd, tmp_path = tempfile.mkstemp(prefix="package.", suffix=".tmp", dir=payload_api_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
            os.replace(tmp_path, payload_path)
        except Exception:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise
        logging.info(
            "[update-keeps-server] Installed WPPConnect Server %s is newer than the "
            "bundled %s — keeping it across this update.",
            installed.get("version"), shipped.get("version"),
        )
        return True
    except Exception:
        logging.exception("[update-keeps-server] Could not check the installed WPPConnect Server")
        return False
