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

"""Tests for cross-platform CivitAI credential storage adapters."""

from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType

import pytest

from substitute.application.ports.civitai_credential_store import (
    CredentialStorageUnavailableError,
)
from substitute.infrastructure.security import civitai_credential_store_factory
from substitute.infrastructure.security.keyring_civitai_credential_store import (
    KeyringCivitaiCredentialStore,
)
from substitute.infrastructure.security.unavailable_civitai_credential_store import (
    UnavailableCivitaiCredentialStore,
)
from substitute.infrastructure.security.windows_civitai_credential_store import (
    WindowsCivitaiCredentialStore,
)


def test_unavailable_civitai_credential_store_fails_closed() -> None:
    """Unavailable storage should never persist plaintext credentials."""

    store = UnavailableCivitaiCredentialStore(
        backend_name="Linux Secret Service/KWallet",
        reason="No compatible keyring is available.",
        remediation="Install a Secret Service-compatible keyring.",
    )

    status = store.status()

    assert status.available is False
    assert store.has_api_key() is False
    assert store.load_api_key() is None
    with pytest.raises(CredentialStorageUnavailableError, match="unavailable"):
        store.save_api_key("secret-token")
    store.clear_api_key()


def test_keyring_civitai_credential_store_saves_loads_and_clears() -> None:
    """Keyring-backed storage should delegate persistence to the OS keyring."""

    keyring = _FakeKeyringModule()
    store = KeyringCivitaiCredentialStore.for_linux(keyring)

    assert store.status().available is True

    store.save_api_key("secret-token")
    assert store.load_api_key() == "secret-token"
    assert store.has_api_key() is True

    store.clear_api_key()
    assert store.load_api_key() is None


def test_keyring_civitai_credential_store_reports_unusable_backend() -> None:
    """Fail/null keyring backends should be reported as unavailable."""

    keyring = _FakeKeyringModule(backend=_FailKeyring())
    store = KeyringCivitaiCredentialStore.for_linux(keyring)

    status = store.status()

    assert status.available is False
    assert status.backend_name == "Linux Secret Service/KWallet"
    assert "GNOME Keyring" in (status.remediation or "")
    with pytest.raises(CredentialStorageUnavailableError):
        store.save_api_key("secret-token")


def test_keyring_civitai_credential_store_wraps_runtime_failures() -> None:
    """Runtime keyring write failures should raise controlled storage errors."""

    keyring = _FakeKeyringModule(fail_writes=True)
    store = KeyringCivitaiCredentialStore.for_macos(keyring)

    with pytest.raises(CredentialStorageUnavailableError, match="rejected"):
        store.save_api_key("secret-token")


def test_windows_civitai_credential_store_status_is_platform_guarded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Windows DPAPI status should not claim availability off Windows."""

    monkeypatch.setattr(sys, "platform", "linux")

    status = WindowsCivitaiCredentialStore(tmp_path).status()

    assert status.available is False
    assert status.backend_name == "Windows DPAPI"


def test_civitai_credential_store_factory_selects_windows_dpapi(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Windows should keep the DPAPI credential store."""

    monkeypatch.setattr(sys, "platform", "win32")

    store = civitai_credential_store_factory.build_civitai_credential_store(tmp_path)

    assert isinstance(store, WindowsCivitaiCredentialStore)


def test_civitai_credential_store_factory_selects_macos_keyring(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """macOS should use the keyring-backed Keychain adapter."""

    sentinel = KeyringCivitaiCredentialStore.for_macos(_FakeKeyringModule())
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(
        KeyringCivitaiCredentialStore,
        "for_macos",
        staticmethod(lambda: sentinel),
    )

    store = civitai_credential_store_factory.build_civitai_credential_store(tmp_path)

    assert store is sentinel


def test_civitai_credential_store_factory_reports_linux_missing_keyring(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Linux without keyring should fail closed with actionable remediation."""

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        KeyringCivitaiCredentialStore,
        "for_linux",
        staticmethod(_raise_import_error),
    )

    store = civitai_credential_store_factory.build_civitai_credential_store(tmp_path)
    status = store.status()

    assert status.available is False
    assert "GNOME Keyring" in (status.remediation or "")
    assert "package manager" in (status.remediation or "")


def test_civitai_credential_store_factory_reports_unsupported_platform(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Unsupported platforms should use the fail-closed unavailable store."""

    monkeypatch.setattr(sys, "platform", "plan9")

    store = civitai_credential_store_factory.build_civitai_credential_store(tmp_path)

    assert store.status().available is False


class _KeyringErrors:
    """Keyring exception namespace used by the fake module."""

    class KeyringError(Exception):
        """Base fake keyring error."""

    class NoKeyringError(KeyringError):
        """Fake missing-backend error."""

    class PasswordDeleteError(KeyringError):
        """Fake missing-password delete error."""


class _UsableKeyring:
    """Represent a usable fake keyring backend."""


class _FailKeyring:
    """Represent keyring's fail backend."""

    __module__ = "keyring.backends.fail"


class _FakeKeyringModule(ModuleType):
    """In-memory keyring module double."""

    def __init__(
        self,
        *,
        backend: object | None = None,
        fail_writes: bool = False,
    ) -> None:
        """Initialize fake keyring state."""

        super().__init__("keyring")
        self.errors = _KeyringErrors
        self._backend = backend or _UsableKeyring()
        self._fail_writes = fail_writes
        self._passwords: dict[tuple[str, str], str] = {}

    def get_keyring(self) -> object:
        """Return the configured fake backend."""

        return self._backend

    def get_password(self, service_name: str, username: str) -> str | None:
        """Return a stored password."""

        return self._passwords.get((service_name, username))

    def set_password(self, service_name: str, username: str, password: str) -> None:
        """Store a password or raise a fake keyring error."""

        if self._fail_writes:
            raise self.errors.KeyringError("backend locked")
        self._passwords[(service_name, username)] = password

    def delete_password(self, service_name: str, username: str) -> None:
        """Delete a password or raise the fake missing-password error."""

        try:
            del self._passwords[(service_name, username)]
        except KeyError as error:
            raise self.errors.PasswordDeleteError("missing") from error


def _raise_import_error() -> KeyringCivitaiCredentialStore:
    """Raise an import error for factory tests."""

    raise ImportError("missing keyring")
