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

"""Shared assertions for incremental prompt-projection editing contracts."""

from __future__ import annotations

from typing import Any, cast

from substitute.presentation.editor.prompt_editor.core.editing.source_buffer import (
    PromptSourceSnapshot,
)
from substitute.presentation.editor.prompt_editor.layout.models import (
    PromptProjectionLineSnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)
from substitute.presentation.editor.prompt_editor.projection.transient_edit_overlays import (
    PromptProjectionTransientDeletionOverlay,
)


def _projection_line_texts(surface: PromptProjectionSurface) -> tuple[str, ...]:
    """Return visible text grouped by projection visual line."""

    snapshot = cast(Any, surface)._layout.frame.output.snapshot
    return tuple(
        "".join(
            fragment.text for fragment in line.fragments if hasattr(fragment, "text")
        )
        for line in snapshot.lines
    )


def _publish_test_source(
    surface: PromptProjectionSurface,
    source_text: str,
) -> None:
    """Advance authoritative source state before applying prepared semantics."""

    surface.editor_state.publish_source(
        PromptSourceSnapshot(
            source_text=source_text,
            source_revision=surface.editor_state.source.source_revision + 1,
        )
    )


def _projection_lines(
    surface: PromptProjectionSurface,
) -> tuple[PromptProjectionLineSnapshot, ...]:
    """Return the live projection visual-line snapshots for geometry assertions."""

    return cast(
        tuple[PromptProjectionLineSnapshot, ...],
        cast(Any, surface)._layout.frame.output.snapshot.lines,
    )


def _valid_transient_deletion_overlay(
    surface: PromptProjectionSurface,
) -> PromptProjectionTransientDeletionOverlay | None:
    """Return controller-owned transient deletion overlay state for assertions."""

    return surface._transient_edit_overlays.valid_deletion_overlay(  # noqa: SLF001
        freshness_is_stale_safe=surface.has_stale_projection_geometry(),
        source_identity=surface.editor_state.source_identity,
    )
