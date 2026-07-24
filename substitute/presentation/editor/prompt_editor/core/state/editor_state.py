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

"""Own immutable prompt-editor snapshot references and their publication lineage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from .revisions import (
    PromptEditorRevisionGraph,
    PromptLayoutIdentity,
    PromptLayoutRevision,
    PromptPaintIdentity,
    PromptPaintStateRevision,
    PromptProjectionIdentity,
    PromptProjectionRevision,
    PromptSemanticIdentity,
    PromptSemanticRevision,
    PromptSourceIdentity,
    PromptViewportIdentity,
    PromptViewportRevision,
    next_layout_revision,
    next_paint_state_revision,
    next_projection_revision,
    next_semantic_revision,
    next_viewport_revision,
    prompt_source_revision,
)


class PromptSourceSnapshotReference(Protocol):
    """Describe immutable source state needed by the revision owner."""

    @property
    def identity(self) -> PromptSourceIdentity:
        """Return the source-owned cached identity."""

    @property
    def source_text(self) -> str:
        """Return the immutable source text reference."""

    @property
    def source_revision(self) -> int:
        """Return the source revision."""

    @property
    def source_length(self) -> int:
        """Return the source length without copying text."""


class PromptSourceTextReference(Protocol):
    """Describe a derived immutable value that records its source text."""

    @property
    def source_text(self) -> str:
        """Return the source text represented by this value."""


TSemanticDocument = TypeVar(
    "TSemanticDocument",
    bound=PromptSourceTextReference,
)
TRenderPlan = TypeVar("TRenderPlan")
TProjectionDocument = TypeVar(
    "TProjectionDocument",
    bound=PromptSourceTextReference,
)
TLayoutGeometry = TypeVar("TLayoutGeometry")
TPaintState = TypeVar("TPaintState")


@dataclass(frozen=True, slots=True)
class PromptSemanticSnapshot(Generic[TSemanticDocument, TRenderPlan]):
    """Reference one atomically published document and render plan."""

    identity: PromptSemanticIdentity
    document: TSemanticDocument
    render_plan: TRenderPlan


@dataclass(frozen=True, slots=True)
class PromptProjectionSnapshot(Generic[TProjectionDocument]):
    """Reference one projection document and its semantic lineage."""

    identity: PromptProjectionIdentity
    document: TProjectionDocument


@dataclass(frozen=True, slots=True)
class PromptLayoutWidthKey:
    """Identify layout-affecting width and font state without widget access."""

    text_width: float
    content_left_inset: float
    document_margin: float
    font_key: str


@dataclass(frozen=True, slots=True)
class PromptLayoutSnapshot(Generic[TLayoutGeometry]):
    """Reference immutable geometry and the projection that produced it."""

    identity: PromptLayoutIdentity
    width_key: PromptLayoutWidthKey
    geometry: TLayoutGeometry


@dataclass(frozen=True, slots=True)
class PromptViewportKey:
    """Identify prepared viewport geometry used by paint composition."""

    width: int
    height: int
    horizontal_scroll: int
    vertical_scroll: int
    device_pixel_ratio: float

    def __post_init__(self) -> None:
        """Reject invalid viewport geometry before paint publication."""

        if self.width < 0 or self.height < 0:
            raise ValueError("Viewport dimensions must be non-negative.")
        if self.device_pixel_ratio <= 0.0:
            raise ValueError("Device pixel ratio must be positive.")

    def matches(
        self,
        *,
        width: int,
        height: int,
        horizontal_scroll: int,
        vertical_scroll: int,
        device_pixel_ratio: float,
    ) -> bool:
        """Return whether primitive viewport state matches this prepared key."""

        return (
            self.width == width
            and self.height == height
            and self.horizontal_scroll == horizontal_scroll
            and self.vertical_scroll == vertical_scroll
            and self.device_pixel_ratio == device_pixel_ratio
        )


@dataclass(frozen=True, slots=True)
class PromptViewportSnapshot:
    """Reference one prepared viewport key and its identity."""

    identity: PromptViewportIdentity
    key: PromptViewportKey


@dataclass(frozen=True, slots=True)
class PromptPaintSnapshot(Generic[TPaintState]):
    """Reference prepared paint state and its layout and viewport lineage."""

    identity: PromptPaintIdentity
    state: TPaintState


class PromptEditorDocumentState(
    Protocol[
        TSemanticDocument,
        TRenderPlan,
        TProjectionDocument,
    ]
):
    """Expose source, semantic, and projection publication to core collaborators."""

    @property
    def source(self) -> PromptSourceSnapshotReference:
        """Return the live source snapshot."""

    @property
    def source_identity(self) -> PromptSourceIdentity:
        """Return the cached live source identity."""

    @property
    def semantic(self) -> PromptSemanticSnapshot[TSemanticDocument, TRenderPlan]:
        """Return the latest semantic publication."""

    @property
    def projection_semantic(
        self,
    ) -> PromptSemanticSnapshot[TSemanticDocument, TRenderPlan]:
        """Return the exact semantic input consumed by current projection."""

    @property
    def edit_semantic(
        self,
    ) -> PromptSemanticSnapshot[TSemanticDocument, TRenderPlan]:
        """Return the latest optimistic semantic input for live source edits."""

    @property
    def projection(self) -> PromptProjectionSnapshot[TProjectionDocument]:
        """Return the latest projection publication."""

    @property
    def revisions(self) -> PromptEditorRevisionGraph:
        """Return the current immutable revision graph."""

    def publish_source(
        self,
        source: PromptSourceSnapshotReference,
    ) -> PromptSourceIdentity:
        """Publish one newer source snapshot."""

    def publish_semantic(
        self,
        document: TSemanticDocument,
        render_plan: TRenderPlan,
        *,
        source_identity: PromptSourceIdentity,
    ) -> PromptSemanticSnapshot[TSemanticDocument, TRenderPlan]:
        """Publish semantic state derived from the live source."""

    def prepare_semantic(
        self,
        document: TSemanticDocument,
        render_plan: TRenderPlan,
        *,
        source_identity: PromptSourceIdentity,
    ) -> PromptSemanticSnapshot[TSemanticDocument, TRenderPlan]:
        """Prepare semantic state without making it current."""

    def adopt_semantic(
        self,
        snapshot: PromptSemanticSnapshot[TSemanticDocument, TRenderPlan],
    ) -> None:
        """Adopt semantic state from its authoritative owner."""

    def restore_semantic(
        self,
        snapshot: PromptSemanticSnapshot[TSemanticDocument, TRenderPlan],
    ) -> None:
        """Restore a previously published semantic snapshot."""

    def stage_edit_semantic(
        self,
        snapshot: PromptSemanticSnapshot[TSemanticDocument, TRenderPlan],
    ) -> None:
        """Stage optimistic semantic input for live edits and projection work."""

    def restore_projection_semantic(
        self,
        snapshot: PromptSemanticSnapshot[TSemanticDocument, TRenderPlan],
    ) -> None:
        """Restore semantic input paired with retained projection state."""

    def publish_projection(
        self,
        document: TProjectionDocument,
    ) -> PromptProjectionSnapshot[TProjectionDocument]:
        """Publish projection state derived from current semantic state."""

    def restore_projection(
        self,
        snapshot: PromptProjectionSnapshot[TProjectionDocument],
    ) -> None:
        """Restore a previously published projection snapshot."""

    def rebase_equivalent_downstream(
        self,
        snapshot: PromptSemanticSnapshot[TSemanticDocument, TRenderPlan],
    ) -> bool:
        """Rebind exact downstream references to equivalent semantic identity."""


class PromptEditorState(
    Generic[
        TSemanticDocument,
        TRenderPlan,
        TProjectionDocument,
        TLayoutGeometry,
        TPaintState,
    ]
):
    """Publish prompt-editor state references through one validated revision graph."""

    def __init__(
        self,
        *,
        source: PromptSourceSnapshotReference,
        semantic_document: TSemanticDocument,
        render_plan: TRenderPlan,
        projection_document: TProjectionDocument,
    ) -> None:
        """Publish the initial source, semantic, and projection chain."""

        self._source = source
        source_identity = _source_identity(source)
        self._source_identity = source_identity
        _require_source_length(
            semantic_document,
            source_identity,
            publication_name="semantic",
        )
        _require_source_length(
            projection_document,
            source_identity,
            publication_name="projection",
        )
        semantic_identity = PromptSemanticIdentity(
            source=source_identity,
            semantic_revision=PromptSemanticRevision(0),
        )
        self._semantic = PromptSemanticSnapshot(
            identity=semantic_identity,
            document=semantic_document,
            render_plan=render_plan,
        )
        self._projection_semantic = self._semantic
        self._edit_semantic = self._semantic
        projection_identity = PromptProjectionIdentity(
            semantic=semantic_identity,
            projection_revision=PromptProjectionRevision(0),
        )
        self._projection = PromptProjectionSnapshot(
            identity=projection_identity,
            document=projection_document,
        )
        self._frame_projection = self._projection
        self._layout: PromptLayoutSnapshot[TLayoutGeometry] | None = None
        self._viewport: PromptViewportSnapshot | None = None
        self._paint: PromptPaintSnapshot[TPaintState] | None = None
        self._semantic_revision = PromptSemanticRevision(0)
        self._projection_revision = PromptProjectionRevision(0)
        self._layout_revision = PromptLayoutRevision(0)
        self._viewport_revision = PromptViewportRevision(0)
        self._paint_state_revision = PromptPaintStateRevision(0)

    @property
    def source(self) -> PromptSourceSnapshotReference:
        """Return the live source snapshot reference."""

        return self._source

    @property
    def source_identity(self) -> PromptSourceIdentity:
        """Return the cached live source identity."""

        return self._source_identity

    @property
    def semantic(self) -> PromptSemanticSnapshot[TSemanticDocument, TRenderPlan]:
        """Return the latest published semantic snapshot."""

        return self._semantic

    @property
    def projection_semantic(
        self,
    ) -> PromptSemanticSnapshot[TSemanticDocument, TRenderPlan]:
        """Return the exact semantic input consumed by current projection."""

        return self._projection_semantic

    @property
    def edit_semantic(
        self,
    ) -> PromptSemanticSnapshot[TSemanticDocument, TRenderPlan]:
        """Return the latest optimistic semantic input for live source edits."""

        return self._edit_semantic

    @property
    def projection(self) -> PromptProjectionSnapshot[TProjectionDocument]:
        """Return the latest published projection snapshot."""

        return self._projection

    @property
    def frame_projection(self) -> PromptProjectionSnapshot[TProjectionDocument]:
        """Return the projection currently represented by frame geometry."""

        return self._frame_projection

    @property
    def layout(self) -> PromptLayoutSnapshot[TLayoutGeometry] | None:
        """Return the latest published layout snapshot."""

        return self._layout

    @property
    def viewport(self) -> PromptViewportSnapshot | None:
        """Return the latest prepared viewport snapshot."""

        return self._viewport

    @property
    def paint(self) -> PromptPaintSnapshot[TPaintState] | None:
        """Return the latest prepared paint snapshot."""

        return self._paint

    @property
    def current_paint(self) -> PromptPaintSnapshot[TPaintState] | None:
        """Return paint only when it consumes current layout and viewport state."""

        paint = self._paint
        layout = self._layout
        viewport = self._viewport
        if (
            paint is None
            or layout is None
            or viewport is None
            or paint.identity.layout is not layout.identity
            or paint.identity.viewport is not viewport.identity
        ):
            return None
        return paint

    @property
    def revisions(self) -> PromptEditorRevisionGraph:
        """Return one immutable, inspectable view of current revision lineage."""

        return PromptEditorRevisionGraph(
            source=self.source_identity,
            semantic=self._semantic.identity,
            projection=self._projection.identity,
            frame_projection=self._frame_projection.identity,
            layout=None if self._layout is None else self._layout.identity,
            viewport=None if self._viewport is None else self._viewport.identity,
            paint=None if self._paint is None else self._paint.identity,
        )

    def publish_source(
        self,
        source: PromptSourceSnapshotReference,
    ) -> PromptSourceIdentity:
        """Publish a newer editing-session source snapshot by reference."""

        current_identity = self.source_identity
        next_identity = _source_identity(source)
        if next_identity.source_revision == current_identity.source_revision:
            if (
                next_identity != current_identity
                or source.source_text is not self._source.source_text
            ):
                raise ValueError(
                    "Equal source identities must retain the exact source reference."
                )
            self._source = source
            return current_identity
        if next_identity.source_revision <= current_identity.source_revision:
            raise ValueError("Source publication must advance source revision.")
        self._source = source
        self._source_identity = next_identity
        return next_identity

    def publish_semantic(
        self,
        document: TSemanticDocument,
        render_plan: TRenderPlan,
        *,
        source_identity: PromptSourceIdentity,
    ) -> PromptSemanticSnapshot[TSemanticDocument, TRenderPlan]:
        """Publish semantic references derived from the live source."""

        snapshot = self.prepare_semantic(
            document,
            render_plan,
            source_identity=source_identity,
        )
        self._semantic = snapshot
        return snapshot

    def prepare_semantic(
        self,
        document: TSemanticDocument,
        render_plan: TRenderPlan,
        *,
        source_identity: PromptSourceIdentity,
    ) -> PromptSemanticSnapshot[TSemanticDocument, TRenderPlan]:
        """Prepare semantic references while preserving current publication."""

        if source_identity is not self.source_identity:
            raise ValueError("Semantic publication must match live source identity.")
        _require_source_length(
            document,
            source_identity,
            publication_name="semantic",
        )
        self._semantic_revision = next_semantic_revision(self._semantic_revision)
        snapshot = PromptSemanticSnapshot(
            identity=PromptSemanticIdentity(
                source=self.source_identity,
                semantic_revision=self._semantic_revision,
            ),
            document=document,
            render_plan=render_plan,
        )
        return snapshot

    def adopt_semantic(
        self,
        snapshot: PromptSemanticSnapshot[TSemanticDocument, TRenderPlan],
    ) -> None:
        """Adopt a semantic publication created by the authoritative semantic owner."""

        if snapshot.identity.source is not self.source_identity:
            raise ValueError("Semantic identity must match live source identity.")
        _require_source_length(
            snapshot.document,
            snapshot.identity.source,
            publication_name="semantic",
        )
        if snapshot.identity.semantic_revision < self._semantic_revision:
            raise ValueError("Semantic publication must not regress semantic revision.")
        if snapshot.identity is self._semantic.identity:
            if (
                snapshot.document is not self._semantic.document
                or snapshot.render_plan is not self._semantic.render_plan
            ):
                raise ValueError(
                    "Equal semantic identities cannot contain different references."
                )
        self._semantic_revision = snapshot.identity.semantic_revision
        self._semantic = snapshot

    def restore_semantic(
        self,
        snapshot: PromptSemanticSnapshot[TSemanticDocument, TRenderPlan],
    ) -> None:
        """Restore a previously published semantic reference after failed adoption."""

        self._semantic = snapshot

    def publish_projection(
        self,
        document: TProjectionDocument,
    ) -> PromptProjectionSnapshot[TProjectionDocument]:
        """Publish projection state derived from its staged semantic input."""

        if (
            self._projection.document is document
            and self._projection.identity.semantic is self._edit_semantic.identity
        ):
            return self._projection
        _require_source_length(
            document,
            self._edit_semantic.identity.source,
            publication_name="projection",
        )
        self._projection_revision = next_projection_revision(self._projection_revision)
        snapshot = PromptProjectionSnapshot(
            identity=PromptProjectionIdentity(
                semantic=self._edit_semantic.identity,
                projection_revision=self._projection_revision,
            ),
            document=document,
        )
        self._projection = snapshot
        self._projection_semantic = self._edit_semantic
        return snapshot

    def stage_edit_semantic(
        self,
        snapshot: PromptSemanticSnapshot[TSemanticDocument, TRenderPlan],
    ) -> None:
        """Stage optimistic semantic input for live edits and projection work."""

        if snapshot.identity.source is not self.source_identity:
            raise ValueError("Projection semantic input must match live source.")
        _require_source_length(
            snapshot.document,
            snapshot.identity.source,
            publication_name="projection semantic",
        )
        self._edit_semantic = snapshot

    def restore_projection_semantic(
        self,
        snapshot: PromptSemanticSnapshot[TSemanticDocument, TRenderPlan],
    ) -> None:
        """Restore semantic input paired with the retained projection."""

        if snapshot.identity is not self._projection.identity.semantic:
            raise ValueError(
                "Restored projection semantic input must match projection lineage."
            )
        self._projection_semantic = snapshot

    def restore_projection(
        self,
        snapshot: PromptProjectionSnapshot[TProjectionDocument],
    ) -> None:
        """Restore a previously published projection after failed adoption."""

        self._projection = snapshot

    def publish_frame_projection(
        self,
        document: TProjectionDocument,
    ) -> PromptProjectionSnapshot[TProjectionDocument]:
        """Publish the base or transient projection represented by active geometry."""

        if document is self._projection.document:
            self._frame_projection = self._projection
            return self._frame_projection
        current = self._frame_projection
        semantic = self._projection_semantic
        if (
            current.document is document
            and current.identity.semantic is semantic.identity
        ):
            return current
        _require_source_length(
            document,
            semantic.identity.source,
            publication_name="frame projection",
        )
        self._projection_revision = next_projection_revision(self._projection_revision)
        self._frame_projection = PromptProjectionSnapshot(
            identity=PromptProjectionIdentity(
                semantic=semantic.identity,
                projection_revision=self._projection_revision,
            ),
            document=document,
        )
        return self._frame_projection

    def rebase_equivalent_downstream(
        self,
        snapshot: PromptSemanticSnapshot[TSemanticDocument, TRenderPlan],
    ) -> bool:
        """Rebind exact projection, layout, and paint references without rebuilding."""

        if snapshot is not self._semantic:
            raise ValueError(
                "Equivalent rebase requires the current semantic snapshot."
            )
        projection_semantic = self._projection_semantic
        if (
            snapshot.document is not projection_semantic.document
            or snapshot.render_plan is not projection_semantic.render_plan
        ):
            return False

        previous_projection = self._projection
        previous_frame_projection = self._frame_projection
        previous_layout = self._layout
        previous_paint = self._paint
        self._edit_semantic = snapshot
        if previous_projection.identity.semantic is not snapshot.identity:
            self._projection_revision = next_projection_revision(
                self._projection_revision
            )
            self._projection = PromptProjectionSnapshot(
                identity=PromptProjectionIdentity(
                    semantic=snapshot.identity,
                    projection_revision=self._projection_revision,
                ),
                document=previous_projection.document,
            )
        self._projection_semantic = snapshot

        if previous_frame_projection.document is previous_projection.document:
            self._frame_projection = self._projection
        elif previous_frame_projection.identity.semantic is not snapshot.identity:
            self._projection_revision = next_projection_revision(
                self._projection_revision
            )
            self._frame_projection = PromptProjectionSnapshot(
                identity=PromptProjectionIdentity(
                    semantic=snapshot.identity,
                    projection_revision=self._projection_revision,
                ),
                document=previous_frame_projection.document,
            )

        if (
            previous_layout is not None
            and previous_layout.identity.projection
            is previous_frame_projection.identity
        ):
            current_layout = self.publish_layout(
                previous_layout.geometry,
                projection=self._frame_projection.identity,
                width_key=previous_layout.width_key,
            )
            if (
                previous_paint is not None
                and self._viewport is not None
                and previous_paint.identity.layout is previous_layout.identity
            ):
                self.publish_paint(
                    previous_paint.state,
                    layout=current_layout.identity,
                    viewport=self._viewport.identity,
                )
        return True

    def publish_layout(
        self,
        geometry: TLayoutGeometry,
        *,
        projection: PromptProjectionIdentity,
        width_key: PromptLayoutWidthKey,
    ) -> PromptLayoutSnapshot[TLayoutGeometry]:
        """Publish immutable geometry for an exact projection identity."""

        if projection is not self._frame_projection.identity:
            raise ValueError(
                "Layout publication must consume the active frame projection."
            )
        current = self._layout
        if (
            current is not None
            and current.geometry is geometry
            and current.identity.projection is projection
            and current.width_key == width_key
        ):
            return current
        self._layout_revision = next_layout_revision(self._layout_revision)
        snapshot = PromptLayoutSnapshot(
            identity=PromptLayoutIdentity(
                projection=projection,
                layout_revision=self._layout_revision,
            ),
            width_key=width_key,
            geometry=geometry,
        )
        self._layout = snapshot
        return snapshot

    def publish_viewport(self, key: PromptViewportKey) -> PromptViewportSnapshot:
        """Publish changed viewport state or reuse its existing identity."""

        if self._viewport is not None and self._viewport.key == key:
            return self._viewport
        self._viewport_revision = next_viewport_revision(self._viewport_revision)
        snapshot = PromptViewportSnapshot(
            identity=PromptViewportIdentity(self._viewport_revision),
            key=key,
        )
        self._viewport = snapshot
        return snapshot

    def publish_paint(
        self,
        state: TPaintState,
        *,
        layout: PromptLayoutIdentity,
        viewport: PromptViewportIdentity,
    ) -> PromptPaintSnapshot[TPaintState]:
        """Publish paint state for exact prepared layout and viewport identities."""

        if self._layout is None or layout is not self._layout.identity:
            raise ValueError("Paint publication must consume current layout identity.")
        if self._viewport is None or viewport is not self._viewport.identity:
            raise ValueError(
                "Paint publication must consume current viewport identity."
            )
        current = self._paint
        if (
            current is not None
            and current.identity.layout is layout
            and current.identity.viewport is viewport
            and (current.state is state or current.state == state)
        ):
            return current
        self._paint_state_revision = next_paint_state_revision(
            self._paint_state_revision
        )
        snapshot = PromptPaintSnapshot(
            identity=PromptPaintIdentity(
                layout=layout,
                viewport=viewport,
                paint_state_revision=self._paint_state_revision,
            ),
            state=state,
        )
        self._paint = snapshot
        return snapshot


def _source_identity(source: PromptSourceSnapshotReference) -> PromptSourceIdentity:
    """Validate and return the source-owned identity without reallocating it."""

    identity = source.identity
    if (
        identity.source_revision != prompt_source_revision(source.source_revision)
        or identity.source_length != source.source_length
    ):
        raise ValueError("Source identity must match its immutable source snapshot.")
    return identity


def _require_source_length(
    derived: PromptSourceTextReference,
    source_identity: PromptSourceIdentity,
    *,
    publication_name: str,
) -> None:
    """Reject derived state whose length contradicts its typed source identity."""

    source_length = source_identity.source_length
    if source_length is None or len(derived.source_text) != source_length:
        raise ValueError(
            f"{publication_name.capitalize()} publication must match source identity length."
        )


__all__ = [
    "PromptEditorDocumentState",
    "PromptEditorState",
    "PromptLayoutSnapshot",
    "PromptLayoutWidthKey",
    "PromptPaintSnapshot",
    "PromptProjectionSnapshot",
    "PromptSemanticSnapshot",
    "PromptSourceSnapshotReference",
    "PromptSourceTextReference",
    "PromptViewportKey",
    "PromptViewportSnapshot",
]
