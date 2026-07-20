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

"""Store CivitAI credentials using Windows DPAPI-protected data."""

from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys

from sugarsubstitute_shared.localization import app_text

from substitute.application.ports.civitai_credential_store import (
    CivitaiCredentialStore,
    CredentialStoreStatus,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.security.civitai_credentials")
_CREDENTIAL_FILE_NAME = "civitai_api_key.dpapi"
_CRYPTPROTECT_UI_FORBIDDEN = 0x01


class _DataBlob(ctypes.Structure):
    """Mirror the Windows DATA_BLOB structure used by DPAPI."""

    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class WindowsCivitaiCredentialStore(CivitaiCredentialStore):
    """Persist CivitAI API keys with user-scoped Windows DPAPI protection."""

    def __init__(self, settings_dir: Path) -> None:
        """Store the credential file location."""

        self._settings_dir = settings_dir

    def status(self) -> CredentialStoreStatus:
        """Return whether Windows DPAPI credential persistence is available."""

        if sys.platform == "win32":
            return CredentialStoreStatus(
                available=True,
                backend_name="Windows DPAPI",
            )
        return CredentialStoreStatus(
            available=False,
            backend_name="Windows DPAPI",
            reason=app_text("Windows DPAPI is unavailable on this platform."),
            remediation=app_text(
                "Use a supported operating-system credential store, then restart Substitute."
            ),
        )

    def has_api_key(self) -> bool:
        """Return whether encrypted API key material exists and can decrypt."""

        return self.load_api_key() is not None

    def load_api_key(self) -> str | None:
        """Decrypt and return the configured API key when available."""

        path = self._path()
        if not path.exists():
            return None
        try:
            encrypted = base64.b64decode(path.read_text(encoding="ascii"))
            return _dpapi_unprotect(encrypted).decode("utf-8")
        except (OSError, ValueError, UnicodeDecodeError) as error:
            log_warning(
                _LOGGER,
                "Failed to load CivitAI API key from secure storage.",
                path=path,
                error=repr(error),
            )
            return None

    def save_api_key(self, api_key: str) -> None:
        """Encrypt and persist a CivitAI API key."""

        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        encrypted = _dpapi_protect(api_key.encode("utf-8"))
        path.write_text(base64.b64encode(encrypted).decode("ascii"), encoding="ascii")

    def clear_api_key(self) -> None:
        """Remove encrypted CivitAI API key material."""

        path = self._path()
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            log_warning(
                _LOGGER,
                "Failed to clear CivitAI API key from secure storage.",
                path=path,
                error=repr(error),
            )

    def _path(self) -> Path:
        """Return the DPAPI-protected credential file path."""

        return self._settings_dir / _CREDENTIAL_FILE_NAME


def _dpapi_protect(data: bytes) -> bytes:
    """Protect bytes with the current Windows user DPAPI scope."""

    if sys.platform != "win32":
        raise OSError("Windows DPAPI is unavailable on this platform.")
    input_buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    input_blob = _DataBlob(len(data), input_buffer)
    output_blob = _DataBlob()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    ):
        raise OSError("CryptProtectData failed.")
    return _consume_output_blob(output_blob)


def _dpapi_unprotect(data: bytes) -> bytes:
    """Unprotect bytes with the current Windows user DPAPI scope."""

    if sys.platform != "win32":
        raise OSError("Windows DPAPI is unavailable on this platform.")
    input_buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    input_blob = _DataBlob(len(data), input_buffer)
    output_blob = _DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    ):
        raise OSError("CryptUnprotectData failed.")
    return _consume_output_blob(output_blob)


def _consume_output_blob(blob: _DataBlob) -> bytes:
    """Copy DPAPI output bytes and release the Windows allocation."""

    try:
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob.pbData)


__all__ = ["WindowsCivitaiCredentialStore"]
