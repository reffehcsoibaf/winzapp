"""scripts/generate_release_manifest.py replaces the one step of the old CI
release pipeline (build-windows.yml's "Generate SHA256SUMS.txt for release
assets") that a purely local `build.py` run has no equivalent for, now that
releases are built and published by hand (see CLAUDE.md's "Manual release
process" section). This pins its output against the same parser the client
and the signing script both use, so a format drift here would be caught
before it ever reached a real release.
"""

import sys

sys.path.insert(0, "scripts")
import generate_release_manifest as genman  # noqa: E402

from core import release_signature as rs  # noqa: E402 — pytest.ini sets pythonpath=client


def _write(path, content: bytes):
    path.write_bytes(content)


class TestGeneratesAParsableManifest:
    def test_writes_the_version_header_first(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        _write(dist / "WinZappInstaller.exe", b"installer bytes")
        _write(dist / "WinZapp.zip", b"zip bytes")

        assert genman.main(["--dist-dir", str(dist), "--version", "1.2.3.4"]) == 0

        manifest = (dist / "SHA256SUMS.txt").read_bytes()
        first_line = manifest.decode("ascii").splitlines()[0]
        assert first_line == "# winzapp-version: 1.2.3.4"
        assert rs.manifest_version(manifest) == "1.2.3.4"

    def test_hashes_match_a_real_sha256_computation(self, tmp_path):
        import hashlib

        dist = tmp_path / "dist"
        dist.mkdir()
        installer_bytes = b"some installer content"
        zip_bytes = b"some zip content"
        _write(dist / "WinZappInstaller.exe", installer_bytes)
        _write(dist / "WinZapp.zip", zip_bytes)

        genman.main(["--dist-dir", str(dist), "--version", "1.0.0.0"])

        manifest = (dist / "SHA256SUMS.txt").read_text(encoding="ascii")
        expected_installer = hashlib.sha256(installer_bytes).hexdigest()
        expected_zip = hashlib.sha256(zip_bytes).hexdigest()
        assert f"{expected_installer}  WinZappInstaller.exe" in manifest
        assert f"{expected_zip}  WinZapp.zip" in manifest

    def test_defaults_the_version_to_client_version_py(self, tmp_path, monkeypatch):
        dist = tmp_path / "dist"
        dist.mkdir()
        _write(dist / "WinZappInstaller.exe", b"x")
        _write(dist / "WinZapp.zip", b"y")

        version_py = tmp_path / "client"
        version_py.mkdir()
        (version_py / "version.py").write_text('__version__ = "9.9.9.9"', encoding="utf-8")
        monkeypatch.setattr(genman, "ROOT", tmp_path)

        assert genman.main(["--dist-dir", str(dist)]) == 0
        manifest = (dist / "SHA256SUMS.txt").read_text(encoding="ascii")
        assert manifest.startswith("# winzapp-version: 9.9.9.9")

    def test_a_signature_over_this_manifest_is_accepted_by_check_release_manifest(self, tmp_path):
        """End-to-end: this is the exact shape release_signing.py ci_sign()/
        sign-stable and the installed client's own verification all read —
        proving the generator's output round-trips through the real signing
        and verification logic, not just its own parser."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        import base64

        dist = tmp_path / "dist"
        dist.mkdir()
        _write(dist / "WinZappInstaller.exe", b"installer")
        _write(dist / "WinZapp.zip", b"zip")
        genman.main(["--dist-dir", str(dist), "--version", "2.0.0.0"])
        manifest = (dist / "SHA256SUMS.txt").read_bytes()

        key = Ed25519PrivateKey.generate()
        signature = rs.encode_signature(key.sign(manifest))
        pub_b64 = base64.b64encode(
            key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        ).decode("ascii")

        ok, detail = rs.check_release_manifest(
            manifest, signature, "2.0.0.0", False, (pub_b64,), (),
        )
        assert ok, detail


class TestMissingBuildOutput:
    def test_refuses_when_the_installer_is_missing(self, tmp_path, capsys):
        dist = tmp_path / "dist"
        dist.mkdir()
        _write(dist / "WinZapp.zip", b"zip only")

        assert genman.main(["--dist-dir", str(dist), "--version", "1.0.0.0"]) == 1
        assert "does not exist" in capsys.readouterr().err
        assert not (dist / "SHA256SUMS.txt").exists()
