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

"""Define graph-derived Input canvas plans independently from presentation state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from substitute.domain.common import ImageIdentity, MaskAssociationKey
from substitute.domain.workflow.canvas_models import InputAssetEndpoint


class InputCanvasSurfaceKind(StrEnum):
    """Identify how one Input canvas obtains its backing image."""

    AUTHORED_IMAGE = "authored_image"
    SYNTHETIC = "synthetic"


class CanvasDimensionResolutionKind(StrEnum):
    """Describe whether graph semantics establish one safe canvas size."""

    RESOLVED = "resolved"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class CanvasDimensions:
    """Store validated positive pixel dimensions."""

    width: int
    height: int

    def __post_init__(self) -> None:
        """Reject invalid dimensions at the domain boundary."""

        if self.width <= 0 or self.height <= 0:
            raise ValueError("Canvas dimensions must be positive.")


@dataclass(frozen=True, slots=True)
class CanvasDimensionAuthority:
    """Record the graph evidence that authoritatively establishes a canvas size."""

    dimensions: CanvasDimensions
    node_names: tuple[str, ...]
    field_pairs: tuple[tuple[str, str], ...]
    convergence_node_names: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class CanvasDimensionResolution:
    """Return a resolved authority or an explicit conservative rejection."""

    kind: CanvasDimensionResolutionKind
    authority: CanvasDimensionAuthority | None = None
    reason: str = ""
    candidate_node_names: tuple[str, ...] = ()

    @classmethod
    def resolved(
        cls,
        authority: CanvasDimensionAuthority,
    ) -> CanvasDimensionResolution:
        """Build one successful resolution."""

        return cls(
            kind=CanvasDimensionResolutionKind.RESOLVED,
            authority=authority,
            candidate_node_names=authority.node_names,
        )

    @classmethod
    def missing(cls, reason: str) -> CanvasDimensionResolution:
        """Build one missing-authority result."""

        return cls(kind=CanvasDimensionResolutionKind.MISSING, reason=reason)

    @classmethod
    def ambiguous(
        cls,
        reason: str,
        candidate_node_names: tuple[str, ...],
    ) -> CanvasDimensionResolution:
        """Build one ambiguous-authority result."""

        return cls(
            kind=CanvasDimensionResolutionKind.AMBIGUOUS,
            reason=reason,
            candidate_node_names=candidate_node_names,
        )


@dataclass(frozen=True, slots=True)
class InputCanvasSurface:
    """Describe one authored or synthetic image surface exposed by a graph section."""

    section_key: str
    surface_key: str
    kind: InputCanvasSurfaceKind
    image_endpoint: InputAssetEndpoint | None = None
    dimension_authority: CanvasDimensionAuthority | None = None

    def __post_init__(self) -> None:
        """Enforce mutually exclusive authored and synthetic surface ownership."""

        if self.kind is InputCanvasSurfaceKind.AUTHORED_IMAGE:
            if self.image_endpoint is None or self.dimension_authority is not None:
                raise ValueError("Authored surfaces require only an image endpoint.")
        elif self.image_endpoint is not None or self.dimension_authority is None:
            raise ValueError("Synthetic surfaces require only a dimension authority.")

    @property
    def identity(self) -> ImageIdentity:
        """Return the stable workflow-local canvas surface identity."""

        return (self.section_key, self.surface_key)

    @property
    def input_key(self) -> str:
        """Return the durable string key used by workflow canvas state."""

        return f"{self.section_key}:{self.surface_key}"

    @property
    def dimensions(self) -> CanvasDimensions | None:
        """Return dimensions when the surface is graph-derived."""

        authority = self.dimension_authority
        return authority.dimensions if authority is not None else None


@dataclass(frozen=True, slots=True)
class InputCanvasMaskBinding:
    """Bind one authored mask endpoint to an Input canvas surface."""

    surface: InputCanvasSurface
    mask_endpoint: InputAssetEndpoint
    consumer_node_name: str

    @property
    def section_key(self) -> str:
        """Return the graph section owning both the surface and mask endpoint."""

        return self.surface.section_key

    @property
    def surface_key(self) -> str:
        """Return the stable authored or synthetic surface key."""

        return self.surface.surface_key

    @property
    def mask_node_name(self) -> str:
        """Return the authored mask node name."""

        return self.mask_endpoint.node_name

    @property
    def mask_field_key(self) -> str:
        """Return the authored mask upload widget field."""

        return self.mask_endpoint.field_key

    @property
    def association_key(self) -> MaskAssociationKey:
        """Return the workflow mask-association key for this binding."""

        return (self.mask_endpoint.section_key, self.mask_endpoint.node_name)


@dataclass(frozen=True, slots=True)
class InputCanvasPlanRejection:
    """Explain why one authored mask endpoint has no safe canvas surface."""

    mask_endpoint: InputAssetEndpoint
    kind: CanvasDimensionResolutionKind
    reason: str
    candidate_node_names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InputCanvasPlan:
    """Describe all safe canvas surfaces and rejected mask-only endpoints in a section."""

    section_key: str
    surfaces: tuple[InputCanvasSurface, ...] = ()
    mask_bindings: tuple[InputCanvasMaskBinding, ...] = ()
    rejections: tuple[InputCanvasPlanRejection, ...] = ()

    @property
    def exposes_input_canvas(self) -> bool:
        """Return whether the graph section offers at least one usable surface."""

        return bool(self.surfaces)

    @property
    def image_endpoints(self) -> tuple[InputAssetEndpoint, ...]:
        """Return authored image endpoints represented by plan surfaces."""

        return tuple(
            surface.image_endpoint
            for surface in self.surfaces
            if surface.image_endpoint is not None
        )

    @property
    def rejected_mask_nodes(self) -> tuple[str, ...]:
        """Return authored mask node names rejected by conservative planning."""

        return tuple(rejection.mask_endpoint.node_name for rejection in self.rejections)

    def bindings_for_surface(
        self,
        surface: InputCanvasSurface,
    ) -> tuple[InputCanvasMaskBinding, ...]:
        """Return ordered mask bindings owned by one surface."""

        return tuple(
            binding for binding in self.mask_bindings if binding.surface == surface
        )

    def surface_for_key(self, surface_key: str) -> InputCanvasSurface | None:
        """Return one unambiguous surface by its stable section-local key."""

        candidates = tuple(
            surface for surface in self.surfaces if surface.surface_key == surface_key
        )
        return candidates[0] if len(candidates) == 1 else None

    def bindings_for_surface_key(
        self,
        surface_key: str,
    ) -> tuple[InputCanvasMaskBinding, ...]:
        """Return mask bindings owned by one stable surface key."""

        surface = self.surface_for_key(surface_key)
        return self.bindings_for_surface(surface) if surface is not None else ()

    def image_endpoint_for_node(self, node_name: str) -> InputAssetEndpoint | None:
        """Return the authored image endpoint for one graph node when present."""

        surface = self.surface_for_key(node_name)
        return surface.image_endpoint if surface is not None else None

    def binding_for_mask(
        self,
        mask_node_name: str,
    ) -> InputCanvasMaskBinding | None:
        """Return one unambiguous mask binding by authored node name."""

        candidates = tuple(
            binding
            for binding in self.mask_bindings
            if binding.mask_endpoint.node_name == mask_node_name
        )
        return candidates[0] if len(candidates) == 1 else None


__all__ = [
    "CanvasDimensionAuthority",
    "CanvasDimensionResolution",
    "CanvasDimensionResolutionKind",
    "CanvasDimensions",
    "InputCanvasMaskBinding",
    "InputCanvasPlan",
    "InputCanvasPlanRejection",
    "InputCanvasSurface",
    "InputCanvasSurfaceKind",
]
