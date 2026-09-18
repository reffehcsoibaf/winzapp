"""Sign dist/SHA256SUMS.txt with your offline stable key.

Run this after make_release_manifest.py. Asks for the passphrase on your
private key file interactively (it is never printed, written to a file, or
sent anywhere by this script) and writes dist/SHA256SUMS.txt.sig next to the
manifest.

Before writing anything, it also checks the signature against
client/core/release_keys.py using the exact same function the app's updater
uses (check_release_manifest) - so a wrong key, a stale manifest, or a
mismatch with what's committed is caught here instead of shipping a release
the updater would silently reject.
"""

from __future__ import annotations

import argparse
import getpass
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
sys.path.insert(0, str(ROOT / "client"))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from core import release_keys  # noqa: E402
from core import release_signature as rs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--key", required=True, help="Path to stable-primary.pem (or stable-backup.pem)")
    parser.add_argument("--manifest", default=str(DIST / "SHA256SUMS.txt"))
    args = parser.parse_args()

    manifest_path = pathlib.Path(args.manifest)
    if not manifest_path.is_file():
        print(f"{manifest_path} does not exist - run make_release_manifest.py first.", file=sys.stderr)
        return 1
    manifest = manifest_path.read_bytes()

    declared = rs.manifest_version(manifest)
    if not declared:
        print("The manifest has no '# winzapp-version:' line - regenerate it with make_release_manifest.py.",
              file=sys.stderr)
        return 1

    key_path = pathlib.Path(args.key).expanduser()
    if not key_path.is_file():
        print(f"{key_path} does not exist.", file=sys.stderr)
        return 1

    passphrase = getpass.getpass(f"Passphrase for {key_path.name}: ").encode("utf-8")
    try:
        private_key = serialization.load_pem_private_key(key_path.read_bytes(), password=passphrase)
    except Exception as exc:
        print(f"Could not open the key (wrong passphrase, or not the right file?): {exc}", file=sys.stderr)
        return 1
    if not isinstance(private_key, Ed25519PrivateKey):
        print("That file is not an Ed25519 private key.", file=sys.stderr)
        return 1

    signature = rs.encode_signature(private_key.sign(manifest))

    ok, detail = rs.check_release_manifest(
        manifest, signature, declared, False,
        release_keys.STABLE_PUBLIC_KEYS, release_keys.ALPHA_PUBLIC_KEYS,
    )
    if not ok:
        print(f"Not writing the signature - the updater would reject it: {detail}", file=sys.stderr)
        return 1

    sig_path = manifest_path.with_name(rs.SIGNATURE_ASSET_NAME)
    sig_path.write_text(signature, encoding="ascii", newline="\n")
    print(f"Signed and verified for version {declared} -> {sig_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
