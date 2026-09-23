"""Generate dist/SHA256SUMS.txt for a locally built WinZapp release.

This is the one piece of the old CI release pipeline (.github/workflows/
build-windows.yml's "Generate SHA256SUMS.txt for release assets" step) that a
purely local `build.py` run has no equivalent for — everything else (compiling,
staging, zipping) already happens on your machine exactly the same way CI did
it. Releases are no longer built or published by GitHub Actions (see
CLAUDE.md's "Manual release process" section); this script is what replaces
that one step so the manual flow still produces a manifest the installed base
accepts.

Why this matters and isn't optional: client/core/release_keys.py already
trusts a stable signing key (see client/core/release_signature.py), so every
installed WinZapp refuses an update with no SHA256SUMS.txt/.sig — publishing a
release without running this script (and then release_signing.py sign-stable)
would silently strand every user's auto-updater.

Usage, after `venv\\Scripts\\python.exe build.py` has produced dist/:

    venv\\Scripts\\python.exe scripts\\generate_release_manifest.py

Then, from a GitHub release created as a DRAFT with WinZappInstaller.exe,
WinZapp.zip and this SHA256SUMS.txt already uploaded:

    python .github/scripts/release_signing.py sign-stable <tag> --key <offline-key-path>
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES_TO_HASH = ("WinZappInstaller.exe", "WinZapp.zip")


def read_version_py() -> str:
    """The version build.py just baked into the compiled app — see
    client/version.py and build-windows.yml's old "Set version.py" step,
    which this mirrors for the manual flow."""
    text = (ROOT / "client" / "version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("Could not read __version__ out of client/version.py")
    return match.group(1)


def sha256_of(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--dist-dir", default=str(ROOT / "dist"),
        help="Where build.py left WinZappInstaller.exe and WinZapp.zip. Default: dist/",
    )
    parser.add_argument(
        "--version", default=None,
        help="Defaults to client/version.py's __version__. Pass this only if you "
             "haven't bumped version.py yet and want the manifest to name the tag "
             "you're about to release as.",
    )
    args = parser.parse_args(argv)

    dist_dir = pathlib.Path(args.dist_dir)
    version = args.version or read_version_py()

    # Binds the manifest to one version (client/core/release_signature.py) so a
    # genuine old signature can't be replayed under a newer tag — sign-stable
    # refuses to sign a manifest whose declared version doesn't match the tag
    # being released.
    lines = [f"# winzapp-version: {version}"]
    for name in FILES_TO_HASH:
        path = dist_dir / name
        if not path.is_file():
            print(f"error: {path} does not exist — run build.py first", file=sys.stderr)
            return 1
        lines.append(f"{sha256_of(path)}  {name}")

    manifest_path = dist_dir / "SHA256SUMS.txt"
    manifest_path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")

    print(f"Wrote {manifest_path}:")
    for line in lines:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
