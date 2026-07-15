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

"""Expose platform security adapters."""

from substitute.infrastructure.security.civitai_credential_store_factory import (
    build_civitai_credential_store,
)
from substitute.infrastructure.security.keyring_civitai_credential_store import (
    KeyringCivitaiCredentialStore,
)
from substitute.infrastructure.security.unavailable_civitai_credential_store import (
    UnavailableCivitaiCredentialStore,
)
from substitute.infrastructure.security.windows_civitai_credential_store import (
    WindowsCivitaiCredentialStore,
)

__all__ = [
    "KeyringCivitaiCredentialStore",
    "UnavailableCivitaiCredentialStore",
    "WindowsCivitaiCredentialStore",
    "build_civitai_credential_store",
]
