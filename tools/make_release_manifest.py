"""Build dist/SHA256SUMS.txt for a WinZapp release.

Run this after build.py has produced the release files in dist/. It hashes
every file you pass (default: WinZapp.zip and WinZappInstaller.exe, skipping
whichever one isn't there) and writes dist/SHA256SUMS.txt with the version
line client/core/release_signature.py's manifest_version() requires on top.

No secrets are involved here - this step never touches your private key.
Next step is sign_manifest.py.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
sys.path.insert(0, str(ROOT / "client"))

from version import __version__  # noqa: E402


def sha256_of(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "files", nargs="*", default=["WinZapp.zip", "WinZappInstaller.exe"],
        help="Filenames inside dist/ to hash (default: WinZapp.zip, WinZappInstaller.exe)",
    )
    parser.add_argument(
        "--version", default=__version__,
        help="Version to declare in the manifest (default: whatever client/version.py says)",
    )
    args = parser.parse_args()

    lines = [f"# winzapp-version: {args.version}\n"]
    found = 0
    for name in args.files:
        path = DIST / name
        if not path.is_file():
            print(f"[skip] {name} not found in {DIST}")
            continue
        digest = sha256_of(path)
        lines.append(f"{digest}  {name}\n")
        print(f"[ok] {name}: {digest}")
        found += 1

    if found == 0:
        print("No files hashed - nothing to write.", file=sys.stderr)
        return 1

    out_path = DIST / "SHA256SUMS.txt"
    out_path.write_text("".join(lines), encoding="utf-8", newline="\n")
    print(f"\nWritten: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
