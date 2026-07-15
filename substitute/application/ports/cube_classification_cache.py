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

"""Define durable Cube Library picker classification cache contracts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class CubeClassificationCacheKey:
    """Identify one cached picker classification for a cube source version."""

    target_key: str
    catalog_revision: str
    cube_id: str
    cube_content_hash: str
    cube_version: str
    algorithm_version: int

    def stable_hash(self) -> str:
        """Return a deterministic SHA256 cache key for this classification."""

        payload = {
            "targetKey": self.target_key,
            "catalogRevision": self.catalog_revision,
            "cubeId": self.cube_id,
            "cubeContentHash": self.cube_content_hash,
            "cubeVersion": self.cube_version,
            "algorithmVersion": int(self.algorithm_version),
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class CachedCubeSearchTerm:
    """Represent one serialized cube picker search term."""

    text: str
    kind: str

    def to_json(self) -> dict[str, str]:
        """Return a JSON-native representation."""

        return {"text": self.text, "kind": self.kind}

    @classmethod
    def from_json(cls, payload: object) -> "CachedCubeSearchTerm":
        """Return a search term from a JSON-native payload."""

        if not isinstance(payload, dict):
            raise ValueError("Cached cube search term must be a JSON object.")
        text = payload.get("text")
        kind = payload.get("kind")
        if not isinstance(text, str) or not isinstance(kind, str):
            raise ValueError("Cached cube search term requires text and kind strings.")
        return cls(text=text, kind=kind)


@dataclass(frozen=True)
class CachedCubePickerClassification:
    """Carry one Qt-free cube picker classification cache payload."""

    input_count: int
    output_count: int
    role: str
    supported_models: tuple[str, ...] = ()
    search_terms: tuple[str, ...] = ()
    search_targets: tuple[CachedCubeSearchTerm, ...] = ()

    def to_json_text(self) -> str:
        """Return deterministic JSON for durable storage."""

        payload = {
            "inputCount": int(self.input_count),
            "outputCount": int(self.output_count),
            "role": self.role,
            "supportedModels": list(self.supported_models),
            "searchTerms": list(self.search_terms),
            "searchTargets": [target.to_json() for target in self.search_targets],
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json_text(cls, value: str) -> "CachedCubePickerClassification":
        """Return a cache payload from deterministic JSON text."""

        payload = json.loads(value)
        if not isinstance(payload, dict):
            raise ValueError("Cached cube classification must be a JSON object.")
        role = payload.get("role")
        if not isinstance(role, str):
            raise ValueError("Cached cube classification requires a role string.")
        return cls(
            input_count=_json_int(payload.get("inputCount")),
            output_count=_json_int(payload.get("outputCount")),
            role=role,
            supported_models=_json_string_tuple(payload.get("supportedModels")),
            search_terms=_json_string_tuple(payload.get("searchTerms")),
            search_targets=tuple(
                CachedCubeSearchTerm.from_json(item)
                for item in _json_list(payload.get("searchTargets"))
            ),
        )


@runtime_checkable
class CubeClassificationCacheRepository(Protocol):
    """Persist and retrieve Cube Library picker classifications."""

    def read_classification(
        self,
        key: CubeClassificationCacheKey,
    ) -> CachedCubePickerClassification | None:
        """Return one cached classification, or ``None`` when absent."""

    def write_classification(
        self,
        key: CubeClassificationCacheKey,
        classification: CachedCubePickerClassification,
    ) -> None:
        """Persist one classification payload."""

    def delete_for_target(self, target_key: str) -> int:
        """Delete all classification rows for one target key."""

    def delete_except_catalog_revision(
        self,
        target_key: str,
        catalog_revision: str,
    ) -> int:
        """Delete target rows not matching the active catalog revision."""

    def clear(self) -> int:
        """Delete all cached classifications."""

    def prune(self, *, maximum_rows: int) -> int:
        """Prune least recently accessed classifications over a row budget."""


def _json_int(value: object) -> int:
    """Return a safe integer value from decoded JSON."""

    if isinstance(value, int):
        return value
    raise ValueError("Cached cube classification count must be an integer.")


def _json_list(value: object) -> list[object]:
    """Return a JSON list value or an empty list when absent."""

    if value is None:
        return []
    if isinstance(value, list):
        return value
    raise ValueError("Cached cube classification field must be a list.")


def _json_string_tuple(value: object) -> tuple[str, ...]:
    """Return a tuple of strings from decoded JSON."""

    items = _json_list(value)
    if not all(isinstance(item, str) for item in items):
        raise ValueError("Cached cube classification list must contain strings.")
    return tuple(str(item) for item in items)


__all__ = [
    "CachedCubePickerClassification",
    "CachedCubeSearchTerm",
    "CubeClassificationCacheKey",
    "CubeClassificationCacheRepository",
]
