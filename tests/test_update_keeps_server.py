"""A WinZapp update must not put an older WPPConnect Server back.

The release ZIP carries api/package.json built from the bundled server tag.
The installer's xcopy writes it over the installed one, and the server version
is read from that file, so a server the user had already updated came back as
the old number and the same WPPConnect update was offered again.

core/update_keeps_server.py is plain functions over paths, so it is driven
directly against temporary directories here.
"""

import json
import os
from pathlib import Path

from core.update_keeps_server import (
    is_newer_server,
    keep_newer_installed_server,
    merged_package,
)

PINS = ["@wppconnect-team/wppconnect", "@wppconnect/wa-js"]


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _dirs(tmp_path: Path, installed, shipped):
    payload = tmp_path / "payload" / "api"
    installed_dir = tmp_path / "install" / "api"
    _write(payload / "package.json", shipped)
    if installed is not None:
        _write(installed_dir / "package.json", installed)
    return payload, installed_dir


def test_newer_installed_server_is_kept(tmp_path):
    shipped = {"name": "wppconnect-server", "version": "2.10.27",
               "dependencies": {"@wppconnect-team/wppconnect": "2.3.2", "zod": "3.0.0"}}
    installed = {"name": "wppconnect-server", "version": "2.10.30",
                 "dependencies": {"@wppconnect-team/wppconnect": "2.3.4", "axios": "1.0.0"}}
    payload, installed_dir = _dirs(tmp_path, installed, shipped)

    assert keep_newer_installed_server(str(payload), str(installed_dir), PINS) is True

    result = _read(payload / "package.json")
    assert result["version"] == "2.10.30"
    deps = result["dependencies"]
    # The library WinZapp patches is pinned by the release, so the drift check still fires.
    assert deps["@wppconnect-team/wppconnect"] == "2.3.2"
    # A dependency the release adds must not be dropped (its dist/ may need it).
    assert deps["zod"] == "3.0.0"
    # What was already installed stays.
    assert deps["axios"] == "1.0.0"


def test_installed_file_is_not_modified(tmp_path):
    shipped = {"version": "2.10.27", "dependencies": {"zod": "3.0.0"}}
    installed = {"version": "2.10.30", "dependencies": {"axios": "1.0.0"}}
    payload, installed_dir = _dirs(tmp_path, installed, shipped)
    before = (installed_dir / "package.json").read_text(encoding="utf-8")

    keep_newer_installed_server(str(payload), str(installed_dir), PINS)

    assert (installed_dir / "package.json").read_text(encoding="utf-8") == before


def test_same_version_is_left_alone(tmp_path):
    shipped = {"version": "2.10.27", "dependencies": {"zod": "3.0.0"}}
    installed = {"version": "2.10.27", "dependencies": {"axios": "1.0.0"}}
    payload, installed_dir = _dirs(tmp_path, installed, shipped)
    before = (payload / "package.json").read_text(encoding="utf-8")

    assert keep_newer_installed_server(str(payload), str(installed_dir), PINS) is False
    assert (payload / "package.json").read_text(encoding="utf-8") == before


def test_older_installed_server_gets_the_release(tmp_path):
    shipped = {"version": "2.10.30", "dependencies": {"zod": "3.0.0"}}
    installed = {"version": "2.10.27", "dependencies": {"axios": "1.0.0"}}
    payload, installed_dir = _dirs(tmp_path, installed, shipped)
    before = (payload / "package.json").read_text(encoding="utf-8")

    assert keep_newer_installed_server(str(payload), str(installed_dir), PINS) is False
    assert (payload / "package.json").read_text(encoding="utf-8") == before


def test_first_install_has_nothing_to_keep(tmp_path):
    shipped = {"version": "2.10.27"}
    payload, installed_dir = _dirs(tmp_path, None, shipped)
    assert keep_newer_installed_server(str(payload), str(installed_dir), PINS) is False


def test_unreadable_installed_file_never_breaks_the_update(tmp_path):
    shipped = {"version": "2.10.27"}
    payload, installed_dir = _dirs(tmp_path, "{ not json", shipped)
    before = (payload / "package.json").read_text(encoding="utf-8")

    assert keep_newer_installed_server(str(payload), str(installed_dir), PINS) is False
    assert (payload / "package.json").read_text(encoding="utf-8") == before


def test_no_temp_file_is_left_in_the_payload(tmp_path):
    shipped = {"version": "2.10.27", "dependencies": {}}
    installed = {"version": "2.10.30", "dependencies": {}}
    payload, installed_dir = _dirs(tmp_path, installed, shipped)

    keep_newer_installed_server(str(payload), str(installed_dir), PINS)

    assert sorted(os.listdir(payload)) == ["package.json"]


def test_is_newer_server_handles_odd_input():
    assert is_newer_server("2.10.30", "2.10.27")
    assert is_newer_server("v2.10.30", "2.10.27")
    assert is_newer_server("2.10.10", "2.10.9")          # numeric, not text, order
    assert not is_newer_server("2.10.27", "2.10.27")
    assert not is_newer_server("2.10.26", "2.10.27")
    assert not is_newer_server("", "2.10.27")
    assert not is_newer_server("2.10.30", "")
    assert not is_newer_server(None, "2.10.27")
    assert not is_newer_server("banana", "2.10.27")      # cannot tell -> not newer


def test_merged_package_without_dependency_blocks():
    merged = merged_package({"version": "2.10.30"}, {"version": "2.10.27"}, PINS)
    assert merged["version"] == "2.10.30"
    assert merged["dependencies"] == {}


def test_updater_runs_the_check_before_writing_the_installer_script():
    source = (Path(__file__).resolve().parent.parent / "client" / "updater.py").read_text(encoding="utf-8")
    body = source.split("def _run_batch_installer(", 1)[1]
    assert "_keep_newer_installed_server(source_dir, install_dir)" in body
    assert body.index("_keep_newer_installed_server(source_dir, install_dir)") < body.index("_build_installer_script(")
