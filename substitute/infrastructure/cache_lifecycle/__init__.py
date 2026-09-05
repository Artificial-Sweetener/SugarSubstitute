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

"""Expose persistent-cache adapters without import-time dependency cycles."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS = {
    "FilePersistentCacheStorage": (
        "substitute.infrastructure.cache_lifecycle.file_storage",
        "FilePersistentCacheStorage",
    ),
    "SemanticSourceFingerprintService": (
        "substitute.infrastructure.cache_lifecycle.semantic_fingerprint",
        "SemanticSourceFingerprintService",
    ),
}


def __getattr__(name: str) -> Any:
    """Load one public adapter only when a consumer requests it."""

    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as error:
        raise AttributeError(name) from error
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


__all__ = ["FilePersistentCacheStorage", "SemanticSourceFingerprintService"]
