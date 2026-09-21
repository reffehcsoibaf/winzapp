"""Runs the test suite as several separate pytest processes instead of one.

Why: tests marked `wxgui` (see pytest.ini) construct a real top-level wx
dialog/window. The CI workflows run hundreds of them with --run-wx-gui, all
inside a single pytest process, and by the time enough of them have run in
that one process it starts failing in ways that have nothing to do with
WinZapp's own code:

    wx._core.wxAssertionError: ... GetLayoutDirection(): invalid window
    wx._core.wxAssertionError: ... Failed to create dialog. Incorrect DLGTEMPLATE?
    a wx.TextCtrl silently keeping an empty value after SetValue()
    wx.Notebook.FindPage()/GetPageText() disagreeing with the tab that was
    actually just added

All of these showed up investigating the aa7ab95 CI run, each in a
different, otherwise-unrelated test file, each passing in isolation. That
combination points at an exhausted native Windows resource for the one
process, not a bug in the test or the app.

BATCH_COUNT started at 2 (see git history for that version's writeup), on
the theory that GDI/USER handles — a strictly per-process quota — were the
constraint. Splitting into 2 processes measurably helped (batch 1, the
first ~half alphabetically, now passes clean) but did not fully fix it:
batch 2 still failed, and specifically in its back half, where the
dialog-heavy Settings/Update/Video test files happen to cluster
alphabetically — a *partial* recovery mid-process is not what a hard
per-process handle ceiling would produce; it reads more like Windows'
"desktop heap", which is shared across all processes on the same
interactive desktop (session-wide, not per-process) and degrades
gradually rather than failing outright at a fixed count. Raising
BATCH_COUNT still helps either way — fewer real dialogs get built before
each process exits and its share of the heap is freed — it just isn't
the clean "per-process quota" fix the first version described.

Splitting by whole file (never inside a file) means every test still runs
exactly once; nothing is skipped or duplicated.

Usage: same arguments you'd pass to `pytest` directly.

    python scripts/run_pytest_in_batches.py --run-wx-gui
    python scripts/run_pytest_in_batches.py --run-wx-gui -m "not docs"

Went 2 -> 4 -> 8 chasing this: 2 left failures scattered across the back
half of whichever batch a dialog-heavy file landed in; 4 narrowed it down
to just the single heaviest file (SettingsDialog — many tabs plus nested
sub-dialogs, easily the most native windows any one test in this suite
creates) still landing late enough in its batch to hit the ceiling. If the
number below stops being enough (the same flaky wx failures come back —
see the list above), raise it again before reaching for anything fancier.

8 -> 12 when the Settings > Transcricoes e Descricoes page moved each AI provider
into its own dialog: five more real top-level windows per SettingsDialog, and
tests/test_settings_files_saving_tab.py went from all-pass to its last 11 tests
failing with 'Failed to create dialog' at 8 batches.
"""
import glob
import subprocess
import sys

BATCH_COUNT = 12


def main(argv):
    files = sorted(glob.glob("tests/**/test_*.py", recursive=True))
    if not files:
        print("run_pytest_in_batches: no tests/test_*.py files found", file=sys.stderr)
        return 1

    batch_size = -(-len(files) // BATCH_COUNT)  # ceil division
    batches = [
        files[i : i + batch_size] for i in range(0, len(files), batch_size)
    ]

    for index, batch in enumerate(batches, start=1):
        print(
            f"\n=== run_pytest_in_batches: batch {index}/{len(batches)} "
            f"({len(batch)} files) ===",
            flush=True,
        )
        # sys.executable, not the bare "pytest" command: this only has to
        # find pytest on PATH if the venv is *activated*, and running the
        # script as `venv\Scripts\python.exe scripts\run_pytest_in_batches.py`
        # (correct — matches the CI workflows, which never activate a venv
        # either) does not put venv\Scripts on PATH. -m pytest always runs
        # the pytest installed for the interpreter already running this
        # script, venv or not.
        result = subprocess.run([sys.executable, "-m", "pytest", *argv, *batch])
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
