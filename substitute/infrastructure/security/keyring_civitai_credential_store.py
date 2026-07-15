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

"""Store CivitAI credentials in OS keychains through keyring."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from types import ModuleType

from substitute.application.ports.civitai_credential_store import (
    CivitaiCredentialStore,
    CredentialStorageUnavailableError,
    CredentialStoreStatus,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.security.civitai_keyring")
_SERVICE_NAME = "SugarSubstitute.CivitAI"
_ACCOUNT_NAME = "api_key"
_LINUX_REMEDIATION = (
    "Install and enable GNOME Keyring, KWallet, or another "
    "Secret Service-compatible keyring through your distribution's package manager, "
    "then sign in or unlock it and restart Substitute."
)
_MACOS_REMEDIATION = (
    "Enable or unlock macOS Keychain access for this user, then restart Substitute."
)


@dataclass(frozen=True, slots=True)
class KeyringCivitaiCredentialStore(CivitaiCredentialStore):
    """Persist CivitAI API keys through a platform keyring backend."""

    keyring_module: ModuleType
    backend_name: str
    remediation: str

    @classmethod
    def for_linux(
        cls,
        keyring_module: ModuleType | None = None,
    ) -> KeyringCivitaiCredentialStore:
        """Create a Linux Secret Service/KWallet credential store."""

        return cls(
            keyring_module=keyring_module or _import_keyring(),
            backend_name="Linux Secret Service/KWallet",
            remediation=_LINUX_REMEDIATION,
        )

    @classmethod
    def for_macos(
        cls,
        keyring_module: ModuleType | None = None,
    ) -> KeyringCivitaiCredentialStore:
        """Create a macOS Keychain credential store."""

        return cls(
            keyring_module=keyring_module or _import_keyring(),
            backend_name="macOS Keychain",
            remediation=_MACOS_REMEDIATION,
        )

    def status(self) -> CredentialStoreStatus:
        """Return keyring backend availability and remediation."""

        reason = self._unavailable_reason()
        return CredentialStoreStatus(
            available=reason is None,
            backend_name=self.backend_name,
            reason=reason,
            remediation=None if reason is None else self.remediation,
        )

    def has_api_key(self) -> bool:
        """Return whether the OS keyring currently stores an API key."""

        return self.load_api_key() is not None

    def load_api_key(self) -> str | None:
        """Load the CivitAI API key from the OS keyring when available."""

        if not self.status().available:
            return None
        try:
            value = self.keyring_module.get_password(_SERVICE_NAME, _ACCOUNT_NAME)
        except Exception as error:
            if self._is_keyring_error(error):
                log_warning(
                    _LOGGER,
                    "Failed to load CivitAI API key from OS credential storage.",
                    backend=self.backend_name,
                    error=repr(error),
                )
                return None
            raise
        return value if isinstance(value, str) and value.strip() else None

    def save_api_key(self, api_key: str) -> None:
        """Save the CivitAI API key in the OS keyring."""

        status = self.status()
        if not status.available:
            raise CredentialStorageUnavailableError(_status_message(status))
        try:
            self.keyring_module.set_password(_SERVICE_NAME, _ACCOUNT_NAME, api_key)
        except Exception as error:
            if self._is_keyring_error(error):
                raise CredentialStorageUnavailableError(
                    _status_message(
                        CredentialStoreStatus(
                            available=False,
                            backend_name=self.backend_name,
                            reason="The operating-system credential store rejected the key.",
                            remediation=self.remediation,
                        )
                    )
                ) from error
            raise

    def clear_api_key(self) -> None:
        """Remove the CivitAI API key from the OS keyring if present."""

        if not self.status().available:
            return
        try:
            self.keyring_module.delete_password(_SERVICE_NAME, _ACCOUNT_NAME)
        except Exception as error:
            if self._is_missing_key_error(error):
                return
            if self._is_keyring_error(error):
                log_warning(
                    _LOGGER,
                    "Failed to clear CivitAI API key from OS credential storage.",
                    backend=self.backend_name,
                    error=repr(error),
                )
                return
            raise

    def _unavailable_reason(self) -> str | None:
        """Return why the active keyring backend cannot securely store secrets."""

        get_keyring = getattr(self.keyring_module, "get_keyring", None)
        if not callable(get_keyring):
            return "The keyring package did not expose a credential backend."
        try:
            backend = get_keyring()
        except Exception as error:
            if self._is_keyring_error(error):
                return "No compatible operating-system credential store is available."
            raise
        backend_type = type(backend)
        backend_module = backend_type.__module__.casefold()
        backend_name = backend_type.__name__.casefold()
        if "keyring.backends.fail" in backend_module or backend_name == "failkeyring":
            return "No compatible operating-system credential store is available."
        if "keyring.backends.null" in backend_module or backend_name == "keyring":
            return "No compatible operating-system credential store is available."
        return None

    def _is_keyring_error(self, error: BaseException) -> bool:
        """Return whether an exception came from keyring error types."""

        errors = getattr(self.keyring_module, "errors", None)
        if errors is None:
            return False
        keyring_error = getattr(errors, "KeyringError", None)
        no_keyring_error = getattr(errors, "NoKeyringError", None)
        delete_error = getattr(errors, "PasswordDeleteError", None)
        error_types = tuple(
            item
            for item in (keyring_error, no_keyring_error, delete_error)
            if isinstance(item, type) and issubclass(item, BaseException)
        )
        return bool(error_types) and isinstance(error, error_types)

    def _is_missing_key_error(self, error: BaseException) -> bool:
        """Return whether keyring reported an already-missing password."""

        errors = getattr(self.keyring_module, "errors", None)
        delete_error = getattr(errors, "PasswordDeleteError", None)
        return (
            isinstance(delete_error, type)
            and issubclass(delete_error, BaseException)
            and isinstance(error, delete_error)
        )


def _import_keyring() -> ModuleType:
    """Import keyring lazily so unsupported platforms can fail closed cleanly."""

    return importlib.import_module("keyring")


def _status_message(status: CredentialStoreStatus) -> str:
    """Return a user-safe unavailable storage message."""

    parts = ["Secure credential storage is unavailable."]
    if status.reason:
        parts.append(status.reason)
    if status.remediation:
        parts.append(status.remediation)
    return " ".join(parts)


__all__ = ["KeyringCivitaiCredentialStore"]
