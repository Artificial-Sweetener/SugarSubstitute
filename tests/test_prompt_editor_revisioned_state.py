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

"""Verify typed prompt-editor revision lineage and publication invariants."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

import pytest

from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptEditorState,
    PromptLayoutWidthKey,
    PromptViewportKey,
    PromptViewportSnapshot,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
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
    PromptSourceRevision,
    PromptViewportIdentity,
    PromptViewportRevision,
)
from substitute.presentation.editor.prompt_editor.projection.frame_state import (
    PromptProjectionFrameStatePublisher,
)


@dataclass(frozen=True, slots=True)
class _SourceSnapshot:
    """Provide immutable source input for focused state-owner tests."""

    source_text: str
    source_revision: int
    _identity: PromptSourceIdentity = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Cache the identity owned by this immutable source."""

        object.__setattr__(
            self,
            "_identity",
            PromptSourceIdentity(self.source_revision, len(self.source_text)),
        )

    @property
    def identity(self) -> PromptSourceIdentity:
        """Return the source-owned identity."""

        return self._identity

    @property
    def source_length(self) -> int:
        """Return the source length."""

        return len(self.source_text)


@dataclass(frozen=True, slots=True)
class _SourceValue:
    """Provide a source-derived semantic or projection value."""

    source_text: str
    marker: str


@dataclass(frozen=True, slots=True)
class _PreparedLayout:
    """Provide immutable layout inputs for frame-publication tests."""

    projection_document: _SourceValue
    snapshot: str
    width_key: PromptLayoutWidthKey
    paint_state: str


class _SingleReadWidthLayout:
    """Expose a width key that fails if unchanged publication reads it again."""

    def __init__(
        self,
        *,
        projection_document: _SourceValue,
        snapshot: str,
        width_key: PromptLayoutWidthKey,
        paint_state: str,
    ) -> None:
        """Store one prepared layout and its width-key read budget."""

        self.projection_document = projection_document
        self.snapshot = snapshot
        self._width_key = width_key
        self.paint_state = paint_state
        self.width_key_reads = 0

    @property
    def width_key(self) -> PromptLayoutWidthKey:
        """Return the width key once and reject warm-path reconstruction."""

        self.width_key_reads += 1
        if self.width_key_reads > 1:
            raise AssertionError("Warm layout publication read width_key.")
        return self._width_key


class _ViewportPublicationState:
    """Record viewport publications behind the frame-state owner."""

    def __init__(self) -> None:
        """Initialize an unpublished viewport."""

        self.viewport: PromptViewportSnapshot | None = None
        self.publish_count = 0

    def publish_viewport(self, key: PromptViewportKey) -> PromptViewportSnapshot:
        """Record one changed viewport publication."""

        self.publish_count += 1
        self.viewport = PromptViewportSnapshot(
            identity=PromptViewportIdentity(PromptViewportRevision(self.publish_count)),
            key=key,
        )
        return self.viewport


def _state() -> PromptEditorState[_SourceValue, str, _SourceValue, str, str]:
    """Return a revision owner with one valid initial chain."""

    return PromptEditorState(
        source=_SourceSnapshot("alpha", 0),
        semantic_document=_SourceValue("alpha", "semantic-0"),
        render_plan="render-0",
        projection_document=_SourceValue("alpha", "projection-0"),
    )


def test_revisioned_state_records_exact_publication_lineage() -> None:
    """Keep every derived identity linked to the exact upstream publication."""

    state = _state()

    semantic = state.publish_semantic(
        _SourceValue("alpha", "semantic-1"),
        "render-1",
        source_identity=state.source_identity,
    )
    state.stage_edit_semantic(semantic)
    projection = state.publish_projection(_SourceValue("alpha", "projection-1"))
    state.publish_frame_projection(projection.document)
    layout = state.publish_layout(
        "geometry-1",
        projection=projection.identity,
        width_key=PromptLayoutWidthKey(640.0, 4.0, 4.0, "font"),
    )
    viewport = state.publish_viewport(PromptViewportKey(640, 320, 0, 10, 1.0))
    paint = state.publish_paint(
        "paint-1",
        layout=layout.identity,
        viewport=viewport.identity,
    )

    graph = state.revisions
    assert semantic.identity.source == state.source_identity
    assert projection.identity.semantic == semantic.identity
    assert layout.identity.projection == projection.identity
    assert paint.identity.layout == layout.identity
    assert paint.identity.viewport == viewport.identity
    assert graph.semantic_is_current
    assert graph.projection_is_current
    assert graph.layout_is_current
    assert graph.paint_is_current


def test_source_advance_exposes_stale_derived_state_without_republishing_it() -> None:
    """Represent deferred semantic and geometry work as inspectable lineage."""

    state = _state()
    initial_semantic = state.semantic
    initial_projection = state.projection

    state.publish_source(_SourceSnapshot("alpha!", 1))

    assert state.semantic is initial_semantic
    assert state.projection is initial_projection
    assert (
        state.publish_frame_projection(initial_projection.document)
        is initial_projection
    )
    assert state.revisions.source.source_revision == 1
    assert not state.revisions.semantic_is_current
    assert state.revisions.projection_is_current


def test_source_identity_reads_reuse_one_cached_reference() -> None:
    """Keep ordinary identity inspection allocation-free until source advances."""

    state = _state()
    initial_identity = state.source_identity

    assert state.source_identity is initial_identity
    assert state.revisions.source is initial_identity
    assert state.publish_source(_SourceSnapshot("alpha", 0)) is initial_identity
    assert state.source_identity is initial_identity

    next_identity = state.publish_source(_SourceSnapshot("alpha!", 1))

    assert next_identity is state.source_identity
    assert next_identity is state.revisions.source
    assert next_identity is not initial_identity


def test_deferred_edit_keeps_live_semantics_separate_from_committed_projection() -> (
    None
):
    """Retain optimistic edit input without relabeling committed projection."""

    state = _state()
    committed_projection_semantic = state.projection_semantic
    committed_projection = state.projection
    state.publish_source(_SourceSnapshot("alpha!", 1))
    optimistic = state.prepare_semantic(
        _SourceValue("alpha!", "optimistic"),
        "optimistic-render",
        source_identity=state.source_identity,
    )

    state.stage_edit_semantic(optimistic)
    transient_frame = state.publish_frame_projection(
        _SourceValue("alpha", "transient-frame")
    )
    state.restore_projection(committed_projection)
    state.restore_projection_semantic(committed_projection_semantic)

    assert state.edit_semantic is optimistic
    assert transient_frame.identity.semantic == committed_projection_semantic.identity
    assert state.projection_semantic is committed_projection_semantic
    assert state.projection is committed_projection
    assert state.projection.identity.semantic == committed_projection_semantic.identity


def test_projection_publication_atomically_consumes_staged_edit_semantics() -> None:
    """Link projection to staged input only when projection publication succeeds."""

    state = _state()
    state.publish_source(_SourceSnapshot("alpha!", 1))
    optimistic = state.prepare_semantic(
        _SourceValue("alpha!", "optimistic"),
        "optimistic-render",
        source_identity=state.source_identity,
    )
    state.stage_edit_semantic(optimistic)

    projection = state.publish_projection(_SourceValue("alpha!", "projection"))

    assert state.projection_semantic is optimistic
    assert projection.identity.semantic == optimistic.identity


def test_publication_rejects_text_from_the_wrong_upstream_snapshot() -> None:
    """Reject mixed-source semantic and projection publication."""

    state = _state()

    with pytest.raises(ValueError, match="Semantic publication"):
        state.publish_semantic(
            _SourceValue("other", "semantic"),
            "render",
            source_identity=PromptSourceIdentity(99, len("other")),
        )

    state.publish_source(_SourceSnapshot("beta", 1))
    semantic = state.publish_semantic(
        _SourceValue("beta", "semantic"),
        "render",
        source_identity=state.source_identity,
    )
    state.stage_edit_semantic(semantic)
    with pytest.raises(ValueError, match="Projection publication"):
        state.publish_projection(_SourceValue("alpha", "projection"))

    with pytest.raises(ValueError, match="Frame projection publication"):
        state.publish_frame_projection(_SourceValue("beta", "frame"))


def test_layout_and_paint_publication_reject_noncurrent_upstream_identities() -> None:
    """Reject geometry or paint assembled from a different published frame."""

    state = _state()
    unrelated_semantic = PromptSemanticIdentity(
        state.source_identity,
        PromptSemanticRevision(99),
    )
    unrelated_projection = PromptProjectionIdentity(
        unrelated_semantic,
        PromptProjectionRevision(99),
    )

    with pytest.raises(ValueError, match="active frame projection"):
        state.publish_layout(
            "geometry",
            projection=unrelated_projection,
            width_key=PromptLayoutWidthKey(500.0, 4.0, 4.0, "font"),
        )

    layout = state.publish_layout(
        "geometry",
        projection=state.projection.identity,
        width_key=PromptLayoutWidthKey(500.0, 4.0, 4.0, "font"),
    )
    viewport = state.publish_viewport(PromptViewportKey(500, 200, 0, 0, 1.0))
    with pytest.raises(ValueError, match="current layout"):
        state.publish_paint(
            "paint",
            layout=PromptLayoutIdentity(
                unrelated_projection,
                PromptLayoutRevision(99),
            ),
            viewport=viewport.identity,
        )
    with pytest.raises(ValueError, match="current viewport"):
        state.publish_paint(
            "paint",
            layout=layout.identity,
            viewport=PromptViewportIdentity(PromptViewportRevision(99)),
        )


def test_source_publication_rejects_regression_and_identity_collision() -> None:
    """Reject source rollback and same-identity text replacement."""

    state = _state()
    copied_initial_text = "".join(("al", "pha"))
    assert copied_initial_text == "alpha"
    assert copied_initial_text is not state.source.source_text
    with pytest.raises(ValueError, match="exact source reference"):
        state.publish_source(_SourceSnapshot(copied_initial_text, 0))

    state.publish_source(_SourceSnapshot("beta", 2))

    with pytest.raises(ValueError, match="advance source revision"):
        state.publish_source(_SourceSnapshot("alpha", 1))
    with pytest.raises(ValueError, match="exact source reference"):
        state.publish_source(_SourceSnapshot("other", 2))


def test_viewport_and_paint_publication_reuses_noop_identity() -> None:
    """Avoid revision work when prepared viewport and paint state are unchanged."""

    state = _state()
    layout = state.publish_layout(
        "geometry",
        projection=state.projection.identity,
        width_key=PromptLayoutWidthKey(500.0, 4.0, 4.0, "font"),
    )
    viewport_key = PromptViewportKey(500, 200, 0, 0, 1.0)
    viewport = state.publish_viewport(viewport_key)
    paint = state.publish_paint(
        "paint",
        layout=layout.identity,
        viewport=viewport.identity,
    )

    assert state.publish_viewport(viewport_key) is viewport
    assert (
        state.publish_paint(
            "paint",
            layout=layout.identity,
            viewport=viewport.identity,
        )
        is paint
    )


def test_frame_publisher_reuses_exact_layout_viewport_and_paint_references() -> None:
    """Publish prepared frame lineage without work on unchanged inputs."""

    state = _state()
    publisher = PromptProjectionFrameStatePublisher(cast(Any, state))
    layout = _PreparedLayout(
        projection_document=state.projection.document,
        snapshot="geometry",
        width_key=PromptLayoutWidthKey(500.0, 4.0, 4.0, "font"),
        paint_state="paint",
    )

    first_layout_identity = publisher.publish_layout(cast(Any, layout))
    publisher.publish_viewport(
        width=500,
        height=200,
        horizontal_scroll=0,
        vertical_scroll=0,
        device_pixel_ratio=1.0,
    )
    publisher.publish_prepared_paint(cast(Any, layout))
    layout_snapshot = state.layout
    viewport_snapshot = state.viewport
    paint_snapshot = state.paint

    assert first_layout_identity is not None
    assert publisher.publish_layout(cast(Any, layout)) is first_layout_identity
    publisher.publish_viewport(
        width=500,
        height=200,
        horizontal_scroll=0,
        vertical_scroll=0,
        device_pixel_ratio=1.0,
    )
    publisher.publish_prepared_paint(cast(Any, layout))
    assert state.layout is layout_snapshot
    assert state.viewport is viewport_snapshot
    assert state.paint is paint_snapshot


def test_frame_publisher_skips_warm_layout_key_and_viewport_publication_work() -> None:
    """Keep unchanged frame synchronization on primitive and reference comparisons."""

    state = _state()
    publisher = PromptProjectionFrameStatePublisher(cast(Any, state))
    layout = _SingleReadWidthLayout(
        projection_document=state.projection.document,
        snapshot="geometry",
        width_key=PromptLayoutWidthKey(500.0, 4.0, 4.0, "font"),
        paint_state="paint",
    )

    publisher.publish_layout(cast(Any, layout))
    publisher.publish_layout(cast(Any, layout))

    assert layout.width_key_reads == 1

    viewport_state = _ViewportPublicationState()
    viewport_publisher = PromptProjectionFrameStatePublisher(cast(Any, viewport_state))
    viewport_publisher.publish_viewport(
        width=500,
        height=200,
        horizontal_scroll=0,
        vertical_scroll=10,
        device_pixel_ratio=1.0,
    )
    viewport_publisher.publish_viewport(
        width=500,
        height=200,
        horizontal_scroll=0,
        vertical_scroll=10,
        device_pixel_ratio=1.0,
    )

    assert viewport_state.publish_count == 1


def test_frame_publisher_assigns_distinct_lineage_to_transient_projection() -> None:
    """Keep transient active geometry distinct from the canonical projection."""

    state = _state()
    publisher = PromptProjectionFrameStatePublisher(cast(Any, state))
    unrelated_layout = _PreparedLayout(
        projection_document=_SourceValue("alpha", "unrelated"),
        snapshot="geometry",
        width_key=PromptLayoutWidthKey(500.0, 4.0, 4.0, "font"),
        paint_state="paint",
    )

    layout_identity = publisher.publish_layout(cast(Any, unrelated_layout))

    assert layout_identity is not None
    assert state.layout is not None
    assert state.frame_projection.document is unrelated_layout.projection_document
    assert state.frame_projection.identity != state.projection.identity
    assert state.revisions.layout_is_current


def test_equivalent_semantic_rebase_preserves_exact_downstream_values() -> None:
    """Rebind retained frame values without rebuilding equivalent downstream work."""

    state = _state()
    layout = state.publish_layout(
        "geometry",
        projection=state.projection.identity,
        width_key=PromptLayoutWidthKey(500.0, 4.0, 4.0, "font"),
    )
    viewport = state.publish_viewport(PromptViewportKey(500, 200, 0, 0, 1.0))
    paint = state.publish_paint(
        "paint",
        layout=layout.identity,
        viewport=viewport.identity,
    )
    semantic_document = state.semantic.document
    render_plan = state.semantic.render_plan
    projection_document = state.projection.document
    geometry = layout.geometry
    paint_state = paint.state

    state.publish_source(_SourceSnapshot("alpha", 1))
    semantic = state.publish_semantic(
        semantic_document,
        render_plan,
        source_identity=state.source_identity,
    )

    assert state.rebase_equivalent_downstream(semantic)
    assert state.projection.document is projection_document
    assert state.frame_projection.document is projection_document
    assert state.layout is not None
    assert state.layout.geometry is geometry
    assert state.paint is not None
    assert state.paint.state is paint_state
    assert state.revisions.semantic_is_current
    assert state.revisions.projection_is_current
    assert state.revisions.frame_projection_is_current
    assert state.revisions.layout_is_current
    assert state.revisions.paint_is_current


def test_semantic_restore_preserves_prior_identity_after_failed_adoption() -> None:
    """Restore the exact prior semantic snapshot without reusing its revision."""

    state = _state()
    previous = state.semantic
    failed_candidate = state.publish_semantic(
        _SourceValue("alpha", "candidate"),
        "candidate-render",
        source_identity=state.source_identity,
    )

    state.restore_semantic(previous)
    accepted = state.publish_semantic(
        _SourceValue("alpha", "accepted"),
        "accepted-render",
        source_identity=state.source_identity,
    )

    assert state.semantic is accepted
    assert (
        accepted.identity.semantic_revision
        > failed_candidate.identity.semantic_revision
    )
    assert previous.identity.semantic_revision == 0


def test_revision_graph_accepts_stale_stages_but_requires_paint_dependencies() -> None:
    """Keep stale lineage inspectable while rejecting incomplete paint graphs."""

    source = PromptSourceIdentity(PromptSourceRevision(2), 4)
    old_source = PromptSourceIdentity(PromptSourceRevision(1), 3)
    semantic = PromptSemanticIdentity(old_source, PromptSemanticRevision(1))
    projection = PromptProjectionIdentity(semantic, PromptProjectionRevision(1))
    layout = PromptLayoutIdentity(projection, PromptLayoutRevision(1))
    viewport = PromptViewportIdentity(PromptViewportRevision(1))
    paint = PromptPaintIdentity(layout, viewport, PromptPaintStateRevision(1))

    graph = PromptEditorRevisionGraph(
        source=source,
        semantic=semantic,
        projection=projection,
        frame_projection=projection,
        layout=layout,
        viewport=viewport,
        paint=paint,
    )

    assert not graph.semantic_is_current
    assert graph.projection_is_current
    assert graph.layout_is_current
    assert graph.paint_is_current
    with pytest.raises(ValueError, match="requires layout and viewport"):
        PromptEditorRevisionGraph(
            source=source,
            semantic=semantic,
            projection=projection,
            frame_projection=projection,
            layout=None,
            viewport=None,
            paint=paint,
        )
