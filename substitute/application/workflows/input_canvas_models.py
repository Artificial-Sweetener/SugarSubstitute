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

"""Define application results for workflow Input canvas operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


@dataclass(frozen=True)
class MaskMaterializationResult:
    """Describe one mask layer materialized for an input image binding."""

    association_key: tuple[str, str]
    image_id: UUID
    mask_id: UUID
    resolved_path: Path
    source: str


@dataclass(frozen=True)
class InputCanvasMaterializationResult:
    """Describe one canvas surface load plus any materialized bound masks."""

    section_key: str
    surface_key: str
    image_id: UUID | None
    mask_results: tuple[MaskMaterializationResult, ...] = ()

    @property
    def first_mask_id(self) -> UUID | None:
        """Return the first materialized mask identifier when available."""

        if not self.mask_results:
            return None
        return self.mask_results[0].mask_id


@dataclass(frozen=True)
class UserSelectedInputMaskResult:
    """Describe application handling for one user-selected mask file."""

    applied: bool
    rejection_reason: str = ""
    cube_alias: str = ""
    node_name: str = ""
    mask_path: str = ""
    selected_dimensions: tuple[int, int] | None = None
    required_dimensions: tuple[int, int] | None = None
    materialization_result: InputCanvasMaterializationResult | None = None

    @classmethod
    def rejected(
        cls,
        reason: str,
        *,
        cube_alias: str,
        node_name: str,
        mask_path: str,
        selected_dimensions: tuple[int, int] | None = None,
        required_dimensions: tuple[int, int] | None = None,
    ) -> "UserSelectedInputMaskResult":
        """Return a rejected selected-mask application result."""

        return cls(
            applied=False,
            rejection_reason=reason,
            cube_alias=cube_alias,
            node_name=node_name,
            mask_path=mask_path,
            selected_dimensions=selected_dimensions,
            required_dimensions=required_dimensions,
        )

    @classmethod
    def accepted(
        cls,
        *,
        cube_alias: str,
        node_name: str,
        mask_path: str,
        materialization_result: InputCanvasMaterializationResult | None,
    ) -> "UserSelectedInputMaskResult":
        """Return a successful selected-mask application result."""

        return cls(
            applied=True,
            cube_alias=cube_alias,
            node_name=node_name,
            mask_path=mask_path,
            materialization_result=materialization_result,
        )


@dataclass(frozen=True)
class LoadedInputCanvasImageIdentityResolution:
    """Describe how an existing QPane image maps to a workflow input node."""

    cube_alias: str | None
    image_node_name: str | None
    input_key: str | None
    rejection_reason: str | None = None

    @property
    def accepted(self) -> bool:
        """Return whether the loaded image has a concrete graph input identity."""

        return (
            self.cube_alias is not None
            and self.image_node_name is not None
            and self.input_key is not None
            and self.rejection_reason is None
        )

    @classmethod
    def mapped(
        cls,
        *,
        cube_alias: str,
        image_node_name: str,
    ) -> "LoadedInputCanvasImageIdentityResolution":
        """Return a graph identity resolved from workflow input state."""

        return cls(
            cube_alias=cube_alias,
            image_node_name=image_node_name,
            input_key=f"{cube_alias}:{image_node_name}",
        )

    @classmethod
    def rejected(
        cls,
        reason: str,
        *,
        input_key: str | None = None,
    ) -> "LoadedInputCanvasImageIdentityResolution":
        """Return a rejected graph identity lookup."""

        return cls(
            cube_alias=None,
            image_node_name=None,
            input_key=input_key,
            rejection_reason=reason,
        )


__all__ = [
    "InputCanvasMaterializationResult",
    "LoadedInputCanvasImageIdentityResolution",
    "MaskMaterializationResult",
    "UserSelectedInputMaskResult",
]
