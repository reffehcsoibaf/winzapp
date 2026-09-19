"""Sign a stable release's SHA256SUMS.txt by hand, with no GitHub CLI involved.

TEMPORARY — the normal path is `.github/scripts/release_signing.py sign-stable`,
which does this AND uploads/publishes automatically via `gh`. This script only
covers the signing step, for when `gh` isn't installed/working: you download
SHA256SUMS.txt from the draft release yourself, run this to produce
SHA256SUMS.txt.sig, then upload that file and click "Publish release" by hand
on the GitHub Releases page. Delete this file once `gh` is sorted out, or keep
it around — it doesn't touch anything else.

Usage:
    python sign_release_manual.py <path-to-SHA256SUMS.txt> <tag> --key <path-to-private-key.pem>

Example:
    python sign_release_manual.py C:\\Users\\fabio\\Downloads\\SHA256SUMS.txt v1.1.2.0 --key C:\\WinZappKeys\\stable-primary.pem

It will:
  1. Ask for the private key's passphrase (hidden input).
  2. Sign the manifest and double-check the signature against the public keys
     already committed in client/core/release_keys.py (the same check the
     installed app itself does) — so a wrong key or a manifest that doesn't
     match the tag is caught here, not after it's already public.
  3. Write SHA256SUMS.txt.sig next to the manifest you gave it.
"""

from __future__ import annotations

import argparse
import ast
import getpass
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "client"))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from core import release_signature as rs  # noqa: E402

KEYS_FILE = ROOT / "client" / "core" / "release_keys.py"


def read_configured_keys(path: pathlib.Path = KEYS_FILE) -> "tuple[tuple[str, ...], tuple[str, ...]]":
    values = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            values[node.target.id] = tuple(ast.literal_eval(node.value))
    return values.get("STABLE_PUBLIC_KEYS", ()), values.get("ALPHA_PUBLIC_KEYS", ())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("manifest", help="Path to the SHA256SUMS.txt you downloaded from the draft release")
    parser.add_argument("tag", help="The release tag, e.g. v1.1.2.0")
    parser.add_argument("--key", required=True, help="Path to the stable private key .pem")
    args = parser.parse_args()

    manifest_path = pathlib.Path(args.manifest).expanduser()
    if not manifest_path.is_file():
        print(f"Not a file: {manifest_path}", file=sys.stderr)
        return 1
    manifest = manifest_path.read_bytes()

    declared = rs.manifest_version(manifest)
    expected = rs.normalize_version(args.tag)
    if declared != expected:
        print(
            f"SHA256SUMS.txt declares version {declared!r}, but you gave tag {args.tag!r} "
            f"(normalized {expected!r}). Make sure you downloaded the right draft's file.",
            file=sys.stderr,
        )
        return 1

    key_path = pathlib.Path(args.key).expanduser()
    if not key_path.is_file():
        print(f"Not a file: {key_path}", file=sys.stderr)
        return 1
    passphrase = getpass.getpass("Stable key passphrase: ").encode("utf-8")
    try:
        private_key = serialization.load_pem_private_key(key_path.read_bytes(), password=passphrase)
    except Exception as exc:
        print(f"Could not load the key (wrong passphrase, or not this key file?): {exc}", file=sys.stderr)
        return 1
    if not isinstance(private_key, Ed25519PrivateKey):
        print("That key file is not an Ed25519 private key.", file=sys.stderr)
        return 1

    signature_text = rs.encode_signature(private_key.sign(manifest))

    stable_keys, _alpha_keys = read_configured_keys()
    ok, detail = rs.check_release_manifest(manifest, signature_text, args.tag, False, stable_keys, ())
    if not ok:
        print(f"Signed, but the signature does NOT verify: {detail}", file=sys.stderr)
        print("Not writing the .sig file. Is this the right key for this repository?", file=sys.stderr)
        return 1

    sig_path = manifest_path.with_name(rs.SIGNATURE_ASSET_NAME)
    sig_path.write_text(signature_text, encoding="ascii", newline="\n")
    print(f"Wrote {sig_path}")
    print(
        "Next: on the draft release's GitHub page, upload this file as an asset "
        f'(it must be named exactly "{rs.SIGNATURE_ASSET_NAME}"), then click "Publish release".'
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
