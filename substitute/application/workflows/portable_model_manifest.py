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

"""Persist portable model identity without changing executable Comfy graphs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Protocol

from substitute.domain.common import JsonObject

PORTABLE_MODEL_MANIFEST_KEY = "sugarsubstitute_model_manifest"
PORTABLE_MODEL_MANIFEST_SCHEMA_VERSION = 1
_SHA256_RE = re.compile(r"^[0-9A-Fa-f]{64}$")


class WorkflowModelManifestAnnotator(Protocol):
    """Add current portable model identity metadata to one detached graph."""

    def annotate(self, graph: JsonObject) -> object:
        """Replace portable model metadata for the graph's current values."""


@dataclass(frozen=True, slots=True)
class PortableModelReference:
    """Bind one SHA-256 model identity to a stable embedded Cube input."""

    instance_id: str
    node_symbol: str
    input_name: str
    kind: str
    value: str
    sha256: str

    def to_payload(self) -> JsonObject:
        """Return the versioned JSON record persisted in Comfy workflow metadata."""

        return {
            "instance_id": self.instance_id,
            "node_symbol": self.node_symbol,
            "input_name": self.input_name,
            "kind": self.kind,
            "value": self.value,
            "sha256": self.sha256.upper(),
        }


class PortableModelManifestCodec:
    """Read and replace Substitute-owned portable model metadata."""

    def read(self, graph: Mapping[str, object]) -> tuple[PortableModelReference, ...]:
        """Return valid references while ignoring malformed optional metadata."""

        extra = graph.get("extra")
        manifest = (
            extra.get(PORTABLE_MODEL_MANIFEST_KEY)
            if isinstance(extra, Mapping)
            else None
        )
        if not isinstance(manifest, Mapping):
            return ()
        if manifest.get("schema_version") != PORTABLE_MODEL_MANIFEST_SCHEMA_VERSION:
            return ()
        raw_references = manifest.get("references")
        if not isinstance(raw_references, Sequence) or isinstance(
            raw_references,
            (str, bytes, bytearray),
        ):
            return ()
        references: list[PortableModelReference] = []
        identities: set[tuple[str, str, str]] = set()
        for raw_reference in raw_references:
            reference = _parse_reference(raw_reference)
            if reference is None:
                continue
            identity = (
                reference.instance_id,
                reference.node_symbol,
                reference.input_name,
            )
            if identity in identities:
                continue
            identities.add(identity)
            references.append(reference)
        return tuple(references)

    def replace(
        self,
        graph: JsonObject,
        references: Sequence[PortableModelReference],
    ) -> None:
        """Replace the manifest atomically while preserving unrelated Comfy metadata."""

        extra_value = graph.get("extra")
        if extra_value is None:
            extra: JsonObject = {}
            graph["extra"] = extra
        elif isinstance(extra_value, dict):
            extra = extra_value
        else:
            raise ValueError("Comfy workflow extra metadata must be an object.")
        if not references:
            extra.pop(PORTABLE_MODEL_MANIFEST_KEY, None)
            if not extra:
                graph.pop("extra", None)
            return
        ordered = sorted(
            references,
            key=lambda item: (
                item.instance_id,
                item.node_symbol,
                item.input_name,
            ),
        )
        extra[PORTABLE_MODEL_MANIFEST_KEY] = {
            "schema_version": PORTABLE_MODEL_MANIFEST_SCHEMA_VERSION,
            "references": [reference.to_payload() for reference in ordered],
        }


def _parse_reference(value: object) -> PortableModelReference | None:
    """Return one validated reference from untrusted workflow metadata."""

    if not isinstance(value, Mapping):
        return None
    instance_id = _nonempty_text(value.get("instance_id"))
    node_symbol = _nonempty_text(value.get("node_symbol"))
    input_name = _nonempty_text(value.get("input_name"))
    kind = _nonempty_text(value.get("kind"))
    model_value = _nonempty_text(value.get("value"))
    sha256 = _nonempty_text(value.get("sha256"))
    if None in {instance_id, node_symbol, input_name, kind, model_value, sha256}:
        return None
    assert instance_id is not None
    assert node_symbol is not None
    assert input_name is not None
    assert kind is not None
    assert model_value is not None
    assert sha256 is not None
    if not _SHA256_RE.fullmatch(sha256):
        return None
    return PortableModelReference(
        instance_id=instance_id,
        node_symbol=node_symbol,
        input_name=input_name,
        kind=kind,
        value=model_value,
        sha256=sha256.upper(),
    )


def _nonempty_text(value: object) -> str | None:
    """Return stripped text when the metadata value is usable."""

    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


__all__ = [
    "PORTABLE_MODEL_MANIFEST_KEY",
    "PORTABLE_MODEL_MANIFEST_SCHEMA_VERSION",
    "PortableModelManifestCodec",
    "PortableModelReference",
    "WorkflowModelManifestAnnotator",
]
