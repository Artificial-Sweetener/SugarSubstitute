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

"""Define compact typed identities for prompt-editor snapshot lineage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

PromptSourceRevision = NewType("PromptSourceRevision", int)
PromptSemanticRevision = NewType("PromptSemanticRevision", int)
PromptProjectionRevision = NewType("PromptProjectionRevision", int)
PromptLayoutRevision = NewType("PromptLayoutRevision", int)
PromptViewportRevision = NewType("PromptViewportRevision", int)
PromptPaintStateRevision = NewType("PromptPaintStateRevision", int)


@dataclass(frozen=True, slots=True)
class PromptSourceIdentity:
    """Identify source state used to prepare commands and derived snapshots."""

    source_revision: int
    source_length: int | None = None

    def __post_init__(self) -> None:
        """Reject invalid source identity components at publication boundaries."""

        _require_non_negative(self.source_revision, field_name="source_revision")
        if self.source_length is not None:
            _require_non_negative(self.source_length, field_name="source_length")

    def matches(
        self,
        *,
        source_revision: int,
        source_length: int | None = None,
    ) -> bool:
        """Return whether this identity still matches supplied source state."""

        if self.source_revision != source_revision:
            return False
        if self.source_length is None or source_length is None:
            return True
        return self.source_length == source_length

    @property
    def revision(self) -> PromptSourceRevision:
        """Return the stage-typed source revision."""

        return PromptSourceRevision(self.source_revision)


@dataclass(frozen=True, slots=True)
class PromptSemanticIdentity:
    """Identify one semantic publication and its exact source input."""

    source: PromptSourceIdentity
    semantic_revision: PromptSemanticRevision

    def __post_init__(self) -> None:
        """Reject invalid semantic revisions before downstream publication."""

        _require_non_negative(
            self.semantic_revision,
            field_name="semantic_revision",
        )
        if self.source.source_length is None:
            raise ValueError("Semantic source identity must include source length.")


@dataclass(frozen=True, slots=True)
class PromptProjectionIdentity:
    """Identify one projection publication and its exact semantic input."""

    semantic: PromptSemanticIdentity
    projection_revision: PromptProjectionRevision

    def __post_init__(self) -> None:
        """Reject invalid projection revisions before layout publication."""

        _require_non_negative(
            self.projection_revision,
            field_name="projection_revision",
        )


@dataclass(frozen=True, slots=True)
class PromptLayoutIdentity:
    """Identify one geometry publication and its exact projection input."""

    projection: PromptProjectionIdentity
    layout_revision: PromptLayoutRevision

    def __post_init__(self) -> None:
        """Reject invalid layout revisions before geometry is consumed."""

        _require_non_negative(self.layout_revision, field_name="layout_revision")


@dataclass(frozen=True, slots=True)
class PromptViewportIdentity:
    """Identify one prepared viewport state."""

    viewport_revision: PromptViewportRevision

    def __post_init__(self) -> None:
        """Reject invalid viewport revisions before paint preparation."""

        _require_non_negative(
            self.viewport_revision,
            field_name="viewport_revision",
        )


@dataclass(frozen=True, slots=True)
class PromptPaintIdentity:
    """Identify prepared paint state and the layout and viewport it consumes."""

    layout: PromptLayoutIdentity
    viewport: PromptViewportIdentity
    paint_state_revision: PromptPaintStateRevision

    def __post_init__(self) -> None:
        """Reject invalid paint-state revisions before cache publication."""

        _require_non_negative(
            self.paint_state_revision,
            field_name="paint_state_revision",
        )


@dataclass(frozen=True, slots=True)
class PromptEditorRevisionGraph:
    """Expose current live and published snapshot lineage for inspection."""

    source: PromptSourceIdentity
    semantic: PromptSemanticIdentity
    projection: PromptProjectionIdentity
    frame_projection: PromptProjectionIdentity
    layout: PromptLayoutIdentity | None
    viewport: PromptViewportIdentity | None
    paint: PromptPaintIdentity | None

    def __post_init__(self) -> None:
        """Reject paint publication without the stages needed to inspect it."""

        if self.paint is not None:
            if self.layout is None or self.viewport is None:
                raise ValueError(
                    "Paint identity requires layout and viewport identities."
                )

    @property
    def semantic_is_current(self) -> bool:
        """Return whether semantic state represents the live source."""

        return self.semantic.source is self.source

    @property
    def layout_is_current(self) -> bool:
        """Return whether layout consumes the active frame projection."""

        return (
            self.layout is not None and self.layout.projection is self.frame_projection
        )

    @property
    def projection_is_current(self) -> bool:
        """Return whether projection consumes the current semantic publication."""

        return self.projection.semantic is self.semantic

    @property
    def frame_projection_is_current(self) -> bool:
        """Return whether the active frame consumes current semantic state."""

        return self.frame_projection.semantic is self.semantic

    @property
    def paint_is_current(self) -> bool:
        """Return whether paint consumes the current layout and viewport."""

        return (
            self.paint is not None
            and self.layout is not None
            and self.viewport is not None
            and self.paint.layout is self.layout
            and self.paint.viewport is self.viewport
        )


def prompt_source_revision(value: int) -> PromptSourceRevision:
    """Validate and return one source revision identity."""

    _require_non_negative(value, field_name="source_revision")
    return PromptSourceRevision(value)


def next_semantic_revision(
    current: PromptSemanticRevision,
) -> PromptSemanticRevision:
    """Return the next semantic publication revision."""

    return PromptSemanticRevision(int(current) + 1)


def next_projection_revision(
    current: PromptProjectionRevision,
) -> PromptProjectionRevision:
    """Return the next projection publication revision."""

    return PromptProjectionRevision(int(current) + 1)


def next_layout_revision(current: PromptLayoutRevision) -> PromptLayoutRevision:
    """Return the next layout publication revision."""

    return PromptLayoutRevision(int(current) + 1)


def next_viewport_revision(
    current: PromptViewportRevision,
) -> PromptViewportRevision:
    """Return the next viewport publication revision."""

    return PromptViewportRevision(int(current) + 1)


def next_paint_state_revision(
    current: PromptPaintStateRevision,
) -> PromptPaintStateRevision:
    """Return the next paint-state publication revision."""

    return PromptPaintStateRevision(int(current) + 1)


def _require_non_negative(value: int, *, field_name: str) -> None:
    """Reject a negative revision or length value."""

    if value < 0:
        raise ValueError(f"{field_name} must be non-negative.")


__all__ = [
    "PromptEditorRevisionGraph",
    "PromptLayoutIdentity",
    "PromptLayoutRevision",
    "PromptPaintIdentity",
    "PromptPaintStateRevision",
    "PromptProjectionIdentity",
    "PromptProjectionRevision",
    "PromptSemanticIdentity",
    "PromptSemanticRevision",
    "PromptSourceIdentity",
    "PromptSourceRevision",
    "PromptViewportIdentity",
    "PromptViewportRevision",
    "next_layout_revision",
    "next_paint_state_revision",
    "next_projection_revision",
    "next_semantic_revision",
    "next_viewport_revision",
    "prompt_source_revision",
]
