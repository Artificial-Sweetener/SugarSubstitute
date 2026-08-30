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

"""Verify core prompt-editor publication and source-lineage contracts."""

from __future__ import annotations

import pytest

from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptLayoutWidthKey,
    PromptViewportKey,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)
from tests.presentation.editor.prompt_editor.core.state.revision_state_support import (
    SourceSnapshot,
    SourceValue,
    state,
)


def test_revisioned_state_records_exact_publication_lineage() -> None:
    """Keep every derived identity linked to the exact upstream publication."""

    editor_state = state()
    semantic = editor_state.publish_semantic(
        SourceValue("alpha", "semantic-1"),
        "render-1",
        source_identity=editor_state.source_identity,
    )
    editor_state.stage_edit_semantic(semantic)
    projection = editor_state.publish_projection(SourceValue("alpha", "projection-1"))
    editor_state.publish_frame_projection(projection.document)
    layout = editor_state.publish_layout(
        "geometry-1",
        projection=projection.identity,
        width_key=PromptLayoutWidthKey(640.0, 4.0, 4.0, "font"),
    )
    viewport = editor_state.publish_viewport(PromptViewportKey(640, 320, 0, 10, 1.0))
    paint = editor_state.publish_paint(
        "paint-1", layout=layout.identity, viewport=viewport.identity
    )

    graph = editor_state.revisions
    assert semantic.identity.source == editor_state.source_identity
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

    editor_state = state()
    initial_semantic = editor_state.semantic
    initial_projection = editor_state.projection

    editor_state.publish_source(SourceSnapshot("alpha!", 1))

    assert editor_state.semantic is initial_semantic
    assert editor_state.projection is initial_projection
    assert (
        editor_state.publish_frame_projection(initial_projection.document)
        is initial_projection
    )
    assert editor_state.revisions.source.source_revision == 1
    assert not editor_state.revisions.semantic_is_current
    assert editor_state.revisions.projection_is_current


def test_source_identity_reads_reuse_one_cached_reference() -> None:
    """Keep ordinary identity inspection allocation-free until source advances."""

    editor_state = state()
    initial_identity = editor_state.source_identity

    assert editor_state.source_identity is initial_identity
    assert editor_state.revisions.source is initial_identity
    assert editor_state.publish_source(SourceSnapshot("alpha", 0)) is initial_identity
    assert editor_state.source_identity is initial_identity

    next_identity = editor_state.publish_source(SourceSnapshot("alpha!", 1))

    assert next_identity is editor_state.source_identity
    assert next_identity is editor_state.revisions.source
    assert next_identity is not initial_identity


def test_deferred_edit_keeps_live_semantics_separate_from_committed_projection() -> (
    None
):
    """Retain optimistic edit input without relabeling committed projection."""

    editor_state = state()
    committed_projection_semantic = editor_state.projection_semantic
    committed_projection = editor_state.projection
    editor_state.publish_source(SourceSnapshot("alpha!", 1))
    optimistic = editor_state.prepare_semantic(
        SourceValue("alpha!", "optimistic"),
        "optimistic-render",
        source_identity=editor_state.source_identity,
    )

    editor_state.stage_edit_semantic(optimistic)
    transient_frame = editor_state.publish_frame_projection(
        SourceValue("alpha", "transient-frame")
    )
    editor_state.restore_projection(committed_projection)
    editor_state.restore_projection_semantic(committed_projection_semantic)

    assert editor_state.edit_semantic is optimistic
    assert transient_frame.identity.semantic == committed_projection_semantic.identity
    assert editor_state.projection_semantic is committed_projection_semantic
    assert editor_state.projection is committed_projection
    assert (
        editor_state.projection.identity.semantic
        == committed_projection_semantic.identity
    )


def test_projection_publication_atomically_consumes_staged_edit_semantics() -> None:
    """Link projection to staged input only when projection publication succeeds."""

    editor_state = state()
    editor_state.publish_source(SourceSnapshot("alpha!", 1))
    optimistic = editor_state.prepare_semantic(
        SourceValue("alpha!", "optimistic"),
        "optimistic-render",
        source_identity=editor_state.source_identity,
    )
    editor_state.stage_edit_semantic(optimistic)

    projection = editor_state.publish_projection(SourceValue("alpha!", "projection"))

    assert editor_state.projection_semantic is optimistic
    assert projection.identity.semantic == optimistic.identity


def test_publication_rejects_text_from_the_wrong_upstream_snapshot() -> None:
    """Reject mixed-source semantic and projection publication."""

    editor_state = state()

    with pytest.raises(ValueError, match="Semantic publication"):
        editor_state.publish_semantic(
            SourceValue("other", "semantic"),
            "render",
            source_identity=PromptSourceIdentity(99, len("other")),
        )

    editor_state.publish_source(SourceSnapshot("beta", 1))
    semantic = editor_state.publish_semantic(
        SourceValue("beta", "semantic"),
        "render",
        source_identity=editor_state.source_identity,
    )
    editor_state.stage_edit_semantic(semantic)
    with pytest.raises(ValueError, match="Projection publication"):
        editor_state.publish_projection(SourceValue("alpha", "projection"))

    with pytest.raises(ValueError, match="Frame projection publication"):
        editor_state.publish_frame_projection(SourceValue("beta", "frame"))
