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

"""Verify prompt-editor revision-state rejection and restoration contracts."""

from __future__ import annotations

import pytest

from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptLayoutWidthKey,
    PromptViewportKey,
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
from tests.presentation.editor.prompt_editor.core.state.revision_state_support import (
    SourceSnapshot,
    SourceValue,
    state,
)


def test_layout_and_paint_publication_reject_noncurrent_upstream_identities() -> None:
    """Reject geometry or paint assembled from a different published frame."""

    editor_state = state()
    unrelated_semantic = PromptSemanticIdentity(
        editor_state.source_identity, PromptSemanticRevision(99)
    )
    unrelated_projection = PromptProjectionIdentity(
        unrelated_semantic, PromptProjectionRevision(99)
    )

    with pytest.raises(ValueError, match="active frame projection"):
        editor_state.publish_layout(
            "geometry",
            projection=unrelated_projection,
            width_key=PromptLayoutWidthKey(500.0, 4.0, 4.0, "font"),
        )

    layout = editor_state.publish_layout(
        "geometry",
        projection=editor_state.projection.identity,
        width_key=PromptLayoutWidthKey(500.0, 4.0, 4.0, "font"),
    )
    viewport = editor_state.publish_viewport(PromptViewportKey(500, 200, 0, 0, 1.0))
    with pytest.raises(ValueError, match="current layout"):
        editor_state.publish_paint(
            "paint",
            layout=PromptLayoutIdentity(unrelated_projection, PromptLayoutRevision(99)),
            viewport=viewport.identity,
        )
    with pytest.raises(ValueError, match="current viewport"):
        editor_state.publish_paint(
            "paint",
            layout=layout.identity,
            viewport=PromptViewportIdentity(PromptViewportRevision(99)),
        )


def test_source_publication_rejects_regression_and_identity_collision() -> None:
    """Reject source rollback and same-identity text replacement."""

    editor_state = state()
    copied_initial_text = "".join(("al", "pha"))
    assert copied_initial_text == "alpha"
    assert copied_initial_text is not editor_state.source.source_text
    with pytest.raises(ValueError, match="exact source reference"):
        editor_state.publish_source(SourceSnapshot(copied_initial_text, 0))

    editor_state.publish_source(SourceSnapshot("beta", 2))

    with pytest.raises(ValueError, match="advance source revision"):
        editor_state.publish_source(SourceSnapshot("alpha", 1))
    with pytest.raises(ValueError, match="exact source reference"):
        editor_state.publish_source(SourceSnapshot("other", 2))


def test_viewport_and_paint_publication_reuses_noop_identity() -> None:
    """Avoid revision work when prepared viewport and paint state are unchanged."""

    editor_state = state()
    layout = editor_state.publish_layout(
        "geometry",
        projection=editor_state.projection.identity,
        width_key=PromptLayoutWidthKey(500.0, 4.0, 4.0, "font"),
    )
    viewport_key = PromptViewportKey(500, 200, 0, 0, 1.0)
    viewport = editor_state.publish_viewport(viewport_key)
    paint = editor_state.publish_paint(
        "paint", layout=layout.identity, viewport=viewport.identity
    )

    assert editor_state.publish_viewport(viewport_key) is viewport
    assert (
        editor_state.publish_paint(
            "paint", layout=layout.identity, viewport=viewport.identity
        )
        is paint
    )


def test_equivalent_semantic_rebase_preserves_exact_downstream_values() -> None:
    """Rebind retained frame values without rebuilding equivalent downstream work."""

    editor_state = state()
    layout = editor_state.publish_layout(
        "geometry",
        projection=editor_state.projection.identity,
        width_key=PromptLayoutWidthKey(500.0, 4.0, 4.0, "font"),
    )
    viewport = editor_state.publish_viewport(PromptViewportKey(500, 200, 0, 0, 1.0))
    paint = editor_state.publish_paint(
        "paint", layout=layout.identity, viewport=viewport.identity
    )
    semantic_document = editor_state.semantic.document
    render_plan = editor_state.semantic.render_plan
    projection_document = editor_state.projection.document
    geometry = layout.geometry
    paint_state = paint.state

    editor_state.publish_source(SourceSnapshot("alpha", 1))
    semantic = editor_state.publish_semantic(
        semantic_document, render_plan, source_identity=editor_state.source_identity
    )

    assert editor_state.rebase_equivalent_downstream(semantic)
    assert editor_state.projection.document is projection_document
    assert editor_state.frame_projection.document is projection_document
    assert editor_state.layout is not None
    assert editor_state.layout.geometry is geometry
    assert editor_state.paint is not None
    assert editor_state.paint.state is paint_state
    assert editor_state.revisions.semantic_is_current
    assert editor_state.revisions.projection_is_current
    assert editor_state.revisions.frame_projection_is_current
    assert editor_state.revisions.layout_is_current
    assert editor_state.revisions.paint_is_current


def test_semantic_restore_preserves_prior_identity_after_failed_adoption() -> None:
    """Restore the exact prior semantic snapshot without reusing its revision."""

    editor_state = state()
    previous = editor_state.semantic
    failed_candidate = editor_state.publish_semantic(
        SourceValue("alpha", "candidate"),
        "candidate-render",
        source_identity=editor_state.source_identity,
    )

    editor_state.restore_semantic(previous)
    accepted = editor_state.publish_semantic(
        SourceValue("alpha", "accepted"),
        "accepted-render",
        source_identity=editor_state.source_identity,
    )

    assert editor_state.semantic is accepted
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
