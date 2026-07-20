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

"""Persist one active-only Comfy node localization generation safely."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import cast

from substitute.domain.onboarding import ComfyEndpoint

_CACHE_SCHEMA_VERSION = 2
_MAX_CACHE_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class CachedComfyI18nBranches:
    """Carry raw English plus one active nodeDefs branch from disk."""

    active_alias: str
    active_node_definitions: dict[str, object]
    english_node_definitions: dict[str, object] | None


class ComfyI18nCache:
    """Read and atomically replace a bounded target-specific catalog cache."""

    def __init__(self, cache_root: Path, endpoint: ComfyEndpoint) -> None:
        """Derive a non-sensitive cache path from the Comfy endpoint identity."""

        fingerprint = sha256(
            f"{endpoint.host.casefold()}:{endpoint.port}".encode("utf-8")
        ).hexdigest()[:24]
        self._directory = cache_root / "comfy_i18n"
        self._path = self._directory / f"{fingerprint}.json"
        self._temp_path = self._directory / f"{fingerprint}.tmp"

    def load(self, *, active_alias: str) -> CachedComfyI18nBranches | None:
        """Load a cache only when it matches the requested active alias."""

        if not self._path.is_file():
            return None
        size = self._path.stat().st_size
        if size <= 0 or size > _MAX_CACHE_BYTES:
            return None
        try:
            with self._path.open("r", encoding="utf-8", errors="strict") as stream:
                raw = json.load(stream)
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        if not isinstance(raw, dict):
            return None
        if raw.get("schema_version") != _CACHE_SCHEMA_VERSION:
            return None
        if raw.get("active_alias") != active_alias:
            return None
        active_node_definitions = raw.get("active_node_defs")
        english_node_definitions = raw.get("english_node_defs")
        if not isinstance(active_node_definitions, dict):
            return None
        if english_node_definitions is not None and not isinstance(
            english_node_definitions, dict
        ):
            return None
        return CachedComfyI18nBranches(
            active_alias=active_alias,
            active_node_definitions=cast(dict[str, object], active_node_definitions),
            english_node_definitions=cast(
                dict[str, object] | None,
                english_node_definitions,
            ),
        )

    def save(
        self,
        *,
        active_alias: str,
        active_node_definitions: dict[str, object],
        english_node_definitions: dict[str, object] | None,
    ) -> None:
        """Atomically persist only the active and English nodeDefs branches."""

        payload = json.dumps(
            {
                "schema_version": _CACHE_SCHEMA_VERSION,
                "active_alias": active_alias,
                "active_node_defs": active_node_definitions,
                "english_node_defs": english_node_definitions,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(payload) > _MAX_CACHE_BYTES:
            raise ValueError("Comfy node localization cache exceeds the size limit.")
        self._directory.mkdir(parents=True, exist_ok=True)
        try:
            with self._temp_path.open("wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(self._temp_path, self._path)
        finally:
            try:
                self._temp_path.unlink(missing_ok=True)
            except OSError:
                pass


__all__ = ["CachedComfyI18nBranches", "ComfyI18nCache"]
