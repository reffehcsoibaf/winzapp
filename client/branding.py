"""The name the user sees, in one place.

The project is now TeleZapp (a fork of WinZapp). Only what a person reads or
hears changes; identifiers that other code, the OS or an already-installed copy
depend on keep their old WinZapp spelling for now:

* the executable and ZIP file names (an installed copy's updater relaunches
  ``WinZapp.exe`` and looks for ``WinZapp.zip``),
* the Windows AppUserModelID / registry keys / autostart value / mutex and IPC
  names (renaming them would orphan settings and allow two instances),
* the release manifest header (``# winzapp-version:``), which older installs
  verify.

``LEGACY_APP_NAME`` is still recognised wherever the app name is compared, so a
saved account that was named "WinZapp", or a window opened by a copy that has
not updated yet, keeps behaving as the default account / the app's own window.
"""

APP_NAME = "TeleZapp"
LEGACY_APP_NAME = "WinZapp"
APP_NAMES = (APP_NAME, LEGACY_APP_NAME)


def is_default_account_name(name) -> bool:
    """True for "no custom account name": unset, or either spelling of the app."""
    return not name or name in APP_NAMES


def is_app_window_title(title) -> bool:
    """Whether a top-level window title belongs to this app (either spelling)."""
    return isinstance(title, str) and title.startswith(APP_NAMES)
