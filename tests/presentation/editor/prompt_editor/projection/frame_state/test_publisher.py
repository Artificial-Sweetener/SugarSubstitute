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

"""Verify prompt-editor frame-state publication reuse and lineage contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptLayoutWidthKey,
    PromptViewportKey,
    PromptViewportSnapshot,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptViewportIdentity,
    PromptViewportRevision,
)
from substitute.presentation.editor.prompt_editor.projection.frame_state import (
    PromptProjectionFrameStatePublisher,
)
from tests.presentation.editor.prompt_editor.core.state.revision_state_support import (
    SourceValue,
    state,
)


@dataclass(frozen=True, slots=True)
class PreparedLayout:
    """Provide immutable layout inputs for frame-publication tests."""

    projection_document: SourceValue
    snapshot: str
    width_key: PromptLayoutWidthKey
    paint_state: str


class SingleReadWidthLayout:
    """Expose a width key that fails if unchanged publication reads it again."""

    def __init__(
        self,
        *,
        projection_document: SourceValue,
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


class ViewportPublicationState:
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


def test_frame_publisher_reuses_exact_layout_viewport_and_paint_references() -> None:
    """Publish prepared frame lineage without work on unchanged inputs."""

    editor_state = state()
    publisher = PromptProjectionFrameStatePublisher(cast(Any, editor_state))
    layout = PreparedLayout(
        projection_document=editor_state.projection.document,
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
    publisher.publish_prepared_paint(cast(Any, layout), cast(Any, layout.paint_state))
    layout_snapshot = editor_state.layout
    viewport_snapshot = editor_state.viewport
    paint_snapshot = editor_state.paint

    assert first_layout_identity is not None
    assert publisher.publish_layout(cast(Any, layout)) is first_layout_identity
    publisher.publish_viewport(
        width=500,
        height=200,
        horizontal_scroll=0,
        vertical_scroll=0,
        device_pixel_ratio=1.0,
    )
    publisher.publish_prepared_paint(cast(Any, layout), cast(Any, layout.paint_state))
    assert editor_state.layout is layout_snapshot
    assert editor_state.viewport is viewport_snapshot
    assert editor_state.paint is paint_snapshot


def test_frame_publisher_skips_warm_layout_key_and_viewport_publication_work() -> None:
    """Keep unchanged frame synchronization on primitive and reference comparisons."""

    editor_state = state()
    publisher = PromptProjectionFrameStatePublisher(cast(Any, editor_state))
    layout = SingleReadWidthLayout(
        projection_document=editor_state.projection.document,
        snapshot="geometry",
        width_key=PromptLayoutWidthKey(500.0, 4.0, 4.0, "font"),
        paint_state="paint",
    )

    publisher.publish_layout(cast(Any, layout))
    publisher.publish_layout(cast(Any, layout))

    assert layout.width_key_reads == 1

    viewport_state = ViewportPublicationState()
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

    editor_state = state()
    publisher = PromptProjectionFrameStatePublisher(cast(Any, editor_state))
    unrelated_layout = PreparedLayout(
        projection_document=SourceValue("alpha", "unrelated"),
        snapshot="geometry",
        width_key=PromptLayoutWidthKey(500.0, 4.0, 4.0, "font"),
        paint_state="paint",
    )

    layout_identity = publisher.publish_layout(cast(Any, unrelated_layout))

    assert layout_identity is not None
    assert editor_state.layout is not None
    assert (
        editor_state.frame_projection.document is unrelated_layout.projection_document
    )
    assert editor_state.frame_projection.identity != editor_state.projection.identity
    assert editor_state.revisions.layout_is_current
