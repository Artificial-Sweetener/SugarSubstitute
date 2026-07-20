#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Build platform-appropriate CivitAI credential stores."""

from __future__ import annotations

from pathlib import Path
import sys

from sugarsubstitute_shared.localization import app_text

from substitute.application.ports.civitai_credential_store import CivitaiCredentialStore
from substitute.infrastructure.security.keyring_civitai_credential_store import (
    KeyringCivitaiCredentialStore,
)
from substitute.infrastructure.security.unavailable_civitai_credential_store import (
    UnavailableCivitaiCredentialStore,
)
from substitute.infrastructure.security.windows_civitai_credential_store import (
    WindowsCivitaiCredentialStore,
)

_LINUX_REMEDIATION = app_text(
    "Install and enable GNOME Keyring, KWallet, or another "
    "Secret Service-compatible keyring through your distribution's package manager, "
    "then sign in or unlock it and restart Substitute."
)
_MACOS_REMEDIATION = app_text(
    "Enable or unlock macOS Keychain access for this user, then restart Substitute."
)
_GENERIC_REMEDIATION = app_text(
    "Enable a supported operating-system credential store, then restart Substitute."
)


def build_civitai_credential_store(settings_dir: Path) -> CivitaiCredentialStore:
    """Return the best secure CivitAI credential store for this platform."""

    if sys.platform == "win32":
        return WindowsCivitaiCredentialStore(settings_dir)
    if sys.platform == "darwin":
        return _keyring_store_for_macos()
    if sys.platform.startswith("linux"):
        return _keyring_store_for_linux()
    return UnavailableCivitaiCredentialStore(
        backend_name="Operating-system credential store",
        reason=app_text(
            "Unsupported platform for secure CivitAI credential storage: %1.",
            sys.platform,
        ),
        remediation=_GENERIC_REMEDIATION,
    )


def _keyring_store_for_macos() -> CivitaiCredentialStore:
    """Return a macOS keyring store or a fail-closed unavailable store."""

    try:
        return KeyringCivitaiCredentialStore.for_macos()
    except ImportError:
        return UnavailableCivitaiCredentialStore(
            backend_name="macOS Keychain",
            reason=app_text("The Python keyring package is not installed."),
            remediation=_MACOS_REMEDIATION,
        )


def _keyring_store_for_linux() -> CivitaiCredentialStore:
    """Return a Linux keyring store or a fail-closed unavailable store."""

    try:
        return KeyringCivitaiCredentialStore.for_linux()
    except ImportError:
        return UnavailableCivitaiCredentialStore(
            backend_name="Linux Secret Service/KWallet",
            reason=app_text("The Python keyring package is not installed."),
            remediation=_LINUX_REMEDIATION,
        )


__all__ = ["build_civitai_credential_store"]
