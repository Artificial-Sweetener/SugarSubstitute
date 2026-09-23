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

"""Project portable model bindings between canonical graphs and resolution data."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import cast

from substitute.application.recipes.model_hash_lookup import RecipeModelHashLookup
from substitute.domain.common import JsonObject
from substitute.domain.recipes import ParsedSugarScript, SugarBufferMap

from .portable_model_manifest import (
    PortableModelManifestCodec,
    PortableModelReference,
)
from .portable_model_graph import (
    copy_model_field,
    cube_document_bindings,
    document_field_value,
    empty_resolver_buffer,
    model_fields,
    resolver_buffer_field_value,
    set_composed_override_value,
    set_document_field_value,
    unique_resolver_alias,
)


@dataclass(frozen=True, slots=True)
class CanonicalModelResolutionProjection:
    """Carry recipe-neutral graph bindings through the shared model resolver."""

    parsed_script: ParsedSugarScript
    instance_id_by_field: Mapping[tuple[str, str, str], str]
    reference_by_field: Mapping[tuple[str, str, str], PortableModelReference]


class PortableModelManifestService:
    """Create and consume portable model references for canonical Cube workflows."""

    def __init__(
        self,
        model_hash_lookup: RecipeModelHashLookup,
        *,
        codec: PortableModelManifestCodec | None = None,
    ) -> None:
        """Store cache-only hash evidence and the versioned manifest codec."""

        self._model_hash_lookup = model_hash_lookup
        self._codec = codec or PortableModelManifestCodec()

    def annotate(self, graph: JsonObject) -> tuple[PortableModelReference, ...]:
        """Replace graph metadata with hashes for its current model picker values."""

        lookup = _lookup_session(self._model_hash_lookup)
        references: list[PortableModelReference] = []
        for binding in cube_document_bindings(graph):
            for field in model_fields(binding.document):
                identity = _unique_known_identity(
                    lookup,
                    kind_candidates=field.kind_candidates,
                    value=field.value,
                )
                if identity is None:
                    continue
                kind, sha256 = identity
                references.append(
                    PortableModelReference(
                        instance_id=binding.instance_id,
                        node_symbol=field.node_symbol,
                        input_name=field.input_name,
                        kind=kind,
                        value=field.value,
                        sha256=sha256.upper(),
                    )
                )
        self._codec.replace(graph, references)
        return tuple(references)

    def project_for_resolution(
        self,
        graph: Mapping[str, object],
    ) -> CanonicalModelResolutionProjection | None:
        """Return resolver input for valid bindings whose values remain current."""

        references = self._codec.read(graph)
        if not references:
            return None
        bindings = {
            binding.instance_id: binding for binding in cube_document_bindings(graph)
        }
        buffers: SugarBufferMap = OrderedDict()
        hashes: dict[tuple[str, str, str], str] = {}
        instance_id_by_field: dict[tuple[str, str, str], str] = {}
        reference_by_field: dict[tuple[str, str, str], PortableModelReference] = {}
        aliases: set[str] = set()
        alias_by_instance_id: dict[str, str] = {}
        for reference in references:
            binding = bindings.get(reference.instance_id)
            if binding is None:
                continue
            alias = alias_by_instance_id.get(binding.instance_id)
            if alias is None:
                alias = unique_resolver_alias(
                    binding.alias,
                    binding.instance_id,
                    aliases,
                )
                alias_by_instance_id[binding.instance_id] = alias
            field_value = document_field_value(
                binding.document,
                node_symbol=reference.node_symbol,
                input_name=reference.input_name,
            )
            if field_value != reference.value:
                continue
            key = (alias, reference.node_symbol, reference.input_name)
            buffer = buffers.setdefault(
                alias,
                empty_resolver_buffer(binding.document),
            )
            copy_model_field(
                buffer,
                document=binding.document,
                node_symbol=reference.node_symbol,
                input_name=reference.input_name,
            )
            hashes[key] = reference.sha256
            instance_id_by_field[key] = reference.instance_id
            reference_by_field[key] = reference
        if not hashes:
            return None
        return CanonicalModelResolutionProjection(
            parsed_script=ParsedSugarScript(
                buffers=buffers,
                global_overrides={},
                global_override_selections={},
                field_control_states_by_alias={},
                override_control_states={},
                model_hashes_by_field=hashes,
                prompt_lora_hashes_by_field={},
                project_name=None,
            ),
            instance_id_by_field=instance_id_by_field,
            reference_by_field=reference_by_field,
        )

    def apply_resolved_script(
        self,
        graph: JsonObject,
        *,
        projection: CanonicalModelResolutionProjection,
        parsed_script: ParsedSugarScript,
    ) -> None:
        """Write resolved Backend values into canonical documents and refresh metadata."""

        bindings = {
            binding.instance_id: binding for binding in cube_document_bindings(graph)
        }
        refreshed_references: list[PortableModelReference] = []
        for field, instance_id in projection.instance_id_by_field.items():
            alias, node_symbol, input_name = field
            value = resolver_buffer_field_value(
                parsed_script.buffers,
                alias=alias,
                node_symbol=node_symbol,
                input_name=input_name,
            )
            binding = bindings.get(instance_id)
            if value is None or binding is None:
                continue
            set_document_field_value(
                binding.document,
                node_symbol=node_symbol,
                input_name=input_name,
                value=value,
            )
            set_composed_override_value(
                graph,
                instance_id=instance_id,
                node_symbol=node_symbol,
                input_name=input_name,
                value=value,
            )
            refreshed_references.append(
                replace(projection.reference_by_field[field], value=value)
            )
        self._codec.replace(graph, refreshed_references)


def _lookup_session(lookup: RecipeModelHashLookup) -> RecipeModelHashLookup:
    """Return a request-scoped lookup when the collaborator supports sessions."""

    create_session = getattr(lookup, "create_session", None)
    return (
        cast(RecipeModelHashLookup, create_session())
        if callable(create_session)
        else lookup
    )


def _unique_known_identity(
    lookup: RecipeModelHashLookup,
    *,
    kind_candidates: tuple[str, ...],
    value: str,
) -> tuple[str, str] | None:
    """Return one unambiguous catalog-backed kind and hash for a literal value."""

    matches = tuple(
        (kind, sha256.upper())
        for kind in kind_candidates
        if (sha256 := lookup.hash_for_model_value(kind=kind, value=value)) is not None
    )
    return matches[0] if len(matches) == 1 else None


__all__ = [
    "CanonicalModelResolutionProjection",
    "PortableModelManifestService",
]
