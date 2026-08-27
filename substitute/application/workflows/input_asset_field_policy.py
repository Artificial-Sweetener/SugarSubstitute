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

"""Own typed semantics for Comfy input fields that name external assets."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from substitute.domain.workflow import InputAssetCardinality, InputAssetRole

_IMAGE_TYPE = "IMAGE"
_MASK_TYPE = "MASK"


@dataclass(frozen=True, slots=True)
class _LegacyInputAssetContract:
    """Describe a bounded fallback for a host class usable before metadata arrives."""

    field_key: str
    output_types: tuple[str, ...]
    cardinality: InputAssetCardinality = InputAssetCardinality.SCALAR


_LEGACY_CONTRACTS: Mapping[str, _LegacyInputAssetContract] = {
    "LoadImage": _LegacyInputAssetContract("image", (_IMAGE_TYPE, _MASK_TYPE)),
    "LoadImageMask": _LegacyInputAssetContract("image", (_MASK_TYPE,)),
    "SimpleSyrup.LoadMaskBatch": _LegacyInputAssetContract(
        "image",
        (_MASK_TYPE,),
        InputAssetCardinality.ORDERED,
    ),
}


@dataclass(frozen=True, slots=True)
class InputAssetFieldSemantics:
    """Describe transport and role semantics for one external asset input field."""

    field_key: str
    output_types: tuple[str, ...]
    preferred_role: InputAssetRole
    cardinality: InputAssetCardinality

    def role_for_output_index(self, output_index: int) -> InputAssetRole | None:
        """Return the editable asset role exposed by one typed output socket."""

        if not 0 <= output_index < len(self.output_types):
            return None
        output_type = self.output_types[output_index]
        if output_type == _IMAGE_TYPE:
            return InputAssetRole.IMAGE
        if output_type == _MASK_TYPE:
            return InputAssetRole.MASK
        return None


class InputAssetFieldPolicy:
    """Resolve live Comfy metadata with narrow restore-safe host fallbacks."""

    def fields_for_node(
        self,
        class_type: str,
        definition: Mapping[str, object],
    ) -> tuple[InputAssetFieldSemantics, ...]:
        """Return every input-folder asset field declared by one node class."""

        output_types = self.output_types(class_type, definition)
        discovered: list[InputAssetFieldSemantics] = []
        for field_key, field_info in _input_fields(definition):
            if not self.is_asset_field(
                class_type=class_type,
                field_key=field_key,
                field_info=field_info,
            ):
                continue
            discovered.append(
                InputAssetFieldSemantics(
                    field_key=field_key,
                    output_types=output_types,
                    preferred_role=_preferred_role(output_types),
                    cardinality=self.cardinality(
                        class_type=class_type,
                        field_key=field_key,
                        field_info=field_info,
                    ),
                )
            )
        if discovered:
            return tuple(discovered)

        legacy = _LEGACY_CONTRACTS.get(class_type)
        if legacy is None:
            return ()
        return (
            InputAssetFieldSemantics(
                field_key=legacy.field_key,
                output_types=legacy.output_types,
                preferred_role=_preferred_role(legacy.output_types),
                cardinality=legacy.cardinality,
            ),
        )

    def is_asset_field(
        self,
        *,
        class_type: str,
        field_key: str,
        field_info: object,
    ) -> bool:
        """Return whether one field is governed by external asset staging."""

        metadata = field_metadata(field_info)
        folder = metadata.get("image_folder")
        if metadata.get("image_upload") is True and folder in {None, "input"}:
            return True
        legacy = _LEGACY_CONTRACTS.get(class_type)
        return legacy is not None and field_key == legacy.field_key

    def output_types(
        self,
        class_type: str,
        definition: Mapping[str, object],
    ) -> tuple[str, ...]:
        """Return exact live output types or a bounded host fallback."""

        output = definition.get("output")
        if isinstance(output, (list, tuple)):
            return tuple(str(value).upper() for value in output)
        legacy = _LEGACY_CONTRACTS.get(class_type)
        return legacy.output_types if legacy is not None else ()

    def cardinality(
        self,
        *,
        class_type: str,
        field_key: str,
        field_info: object,
    ) -> InputAssetCardinality:
        """Return scalar or ordered transport semantics for one asset field."""

        metadata = field_metadata(field_info)
        if metadata.get("allow_batch") is True or metadata.get("multiselect") is True:
            return InputAssetCardinality.ORDERED
        legacy = _LEGACY_CONTRACTS.get(class_type)
        if legacy is not None and field_key == legacy.field_key:
            return legacy.cardinality
        return InputAssetCardinality.SCALAR


def field_metadata(field_info: object) -> Mapping[str, object]:
    """Return metadata from one normalized Comfy input field definition."""

    if isinstance(field_info, (list, tuple)) and len(field_info) > 1:
        metadata = field_info[1]
        if isinstance(metadata, Mapping):
            return metadata
    return {}


def declared_input_type(
    definition: Mapping[str, object],
    field_key: str,
) -> str | None:
    """Return one normalized declared input socket type when available."""

    field_info = next(
        (
            candidate
            for candidate_key, candidate in _input_fields(definition)
            if candidate_key == field_key
        ),
        None,
    )
    if not isinstance(field_info, (list, tuple)) or not field_info:
        return None
    declared = field_info[0]
    return declared.upper() if isinstance(declared, str) else None


def _input_fields(
    definition: Mapping[str, object],
) -> tuple[tuple[str, object], ...]:
    """Return required and optional input definitions in declared order."""

    input_groups = definition.get("input", {})
    if not isinstance(input_groups, Mapping):
        return ()
    fields: list[tuple[str, object]] = []
    for group_name in ("required", "optional"):
        group = input_groups.get(group_name, {})
        if not isinstance(group, Mapping):
            continue
        fields.extend(
            (str(field_key), field_info) for field_key, field_info in group.items()
        )
    return tuple(fields)


def _preferred_role(output_types: tuple[str, ...]) -> InputAssetRole:
    """Choose typed source ownership without using topology as a transport gate."""

    if _IMAGE_TYPE in output_types:
        return InputAssetRole.IMAGE
    if _MASK_TYPE in output_types:
        return InputAssetRole.MASK
    return InputAssetRole.IMAGE


__all__ = [
    "InputAssetFieldPolicy",
    "InputAssetFieldSemantics",
    "declared_input_type",
    "field_metadata",
]
