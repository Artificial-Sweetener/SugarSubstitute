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

"""Inspect production prompt-editor freshness and transient visual ownership."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, cast

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRunKind,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.plain_edit_caret_sequence import (
    MAX_PLAIN_EDIT_CARET_TRANSFORM_DEPTH,
)
from substitute.presentation.editor.prompt_editor.layout.models import (
    PromptProjectionInlineObjectFragment,
    PromptProjectionTextFragment,
)


@dataclass(frozen=True, slots=True)
class PromptAbuseOwnerState:
    """Describe whether canonical or transient owners represent live source."""

    projection_current: bool | None
    semantic_current: bool | None
    visible_source_current: bool | None
    visible_caret_current: bool | None
    active_projection_ownership_valid: bool | None
    layout_projection_ownership_valid: bool | None
    caret_transform_depth: int | None
    caret_transform_depth_valid: bool | None
    transient_overlay_kind: str | None
    projection_freshness: str | None
    layout_fragment_ownership_valid: bool | None = None
    layout_fragment_ownership_mismatch: str | None = None


def capture_prompt_cursor_positions(editor: object) -> tuple[int, int]:
    """Return the authoritative source cursor and anchor positions."""

    prompt_editor = cast(Any, editor)
    surface = prompt_editor._surface
    return int(surface.cursor_position), int(surface.anchor_position)


def capture_prompt_editor_owner_state(editor: object) -> PromptAbuseOwnerState:
    """Return immediate owner agreement without processing queued events."""

    prompt_editor = cast(Any, editor)
    source_text = str(prompt_editor.toPlainText())
    surface = getattr(prompt_editor, "_surface", None)
    editor_state = getattr(surface, "editor_state", None)
    projection_snapshot = getattr(editor_state, "projection", None)
    projection_document = getattr(projection_snapshot, "document", None)
    projection_source = getattr(projection_document, "source_text", None)
    semantic_snapshot = getattr(editor_state, "semantic", None)
    document_view = getattr(semantic_snapshot, "document", None)
    semantic_source = getattr(document_view, "source_text", None)
    projection_current = (
        None if projection_source is None else projection_source == source_text
    )
    caret_transform_depth = _caret_transform_depth(projection_document)
    caret_transform_depth_valid = (
        None
        if caret_transform_depth is None
        else caret_transform_depth <= MAX_PLAIN_EDIT_CARET_TRANSFORM_DEPTH
    )
    semantic_current = (
        None if semantic_source is None else semantic_source == source_text
    )
    fragment_ownership_valid, fragment_ownership_mismatch = _layout_fragment_ownership(
        surface
    )
    if projection_current is None or surface is None:
        return PromptAbuseOwnerState(
            projection_current=projection_current,
            semantic_current=semantic_current,
            visible_source_current=None,
            visible_caret_current=None,
            active_projection_ownership_valid=None,
            layout_projection_ownership_valid=None,
            caret_transform_depth=caret_transform_depth,
            caret_transform_depth_valid=caret_transform_depth_valid,
            transient_overlay_kind=None,
            projection_freshness=None,
            layout_fragment_ownership_valid=fragment_ownership_valid,
            layout_fragment_ownership_mismatch=fragment_ownership_mismatch,
        )
    if projection_current:
        return PromptAbuseOwnerState(
            projection_current=True,
            semantic_current=semantic_current,
            visible_source_current=True,
            visible_caret_current=_fresh_projection_maps_current_caret(
                surface,
                projection_document,
            ),
            active_projection_ownership_valid=(
                _active_projection_ownership_is_valid(surface, projection_document)
            ),
            layout_projection_ownership_valid=(
                _layout_projection_ownership_is_valid(surface, projection_document)
            ),
            caret_transform_depth=caret_transform_depth,
            caret_transform_depth_valid=caret_transform_depth_valid,
            transient_overlay_kind=None,
            projection_freshness="fresh",
            layout_fragment_ownership_valid=fragment_ownership_valid,
            layout_fragment_ownership_mismatch=fragment_ownership_mismatch,
        )
    return _capture_transient_owner_state(
        prompt_editor,
        surface,
        source_text=source_text,
        projection_source=str(projection_source),
        semantic_current=semantic_current,
        caret_transform_depth=caret_transform_depth,
        caret_transform_depth_valid=caret_transform_depth_valid,
        layout_fragment_ownership_valid=fragment_ownership_valid,
        layout_fragment_ownership_mismatch=fragment_ownership_mismatch,
    )


def _capture_transient_owner_state(
    editor: Any,
    surface: Any,
    *,
    source_text: str,
    projection_source: str,
    semantic_current: bool | None,
    caret_transform_depth: int | None,
    caret_transform_depth_valid: bool | None,
    layout_fragment_ownership_valid: bool | None,
    layout_fragment_ownership_mismatch: str | None,
) -> PromptAbuseOwnerState:
    """Return whether stale projection geometry is completed by valid overlays."""

    freshness = surface._projection_freshness_controller
    overlays = surface._transient_edit_overlays
    stale_safe = bool(freshness.has_stale_projection_geometry())
    freshness_name = str(freshness.freshness.value)
    source_identity = surface.editor_state.source_identity
    insertion = overlays.valid_insertion_overlay(
        freshness_is_stale_safe=stale_safe,
        source_identity=source_identity,
    )
    deletion = overlays.valid_deletion_overlay(
        freshness_is_stale_safe=stale_safe,
        source_identity=source_identity,
    )
    cursor = editor.textCursor()
    caret = overlays.valid_caret_geometry(
        freshness_is_stale_safe=stale_safe,
        source_identity=source_identity,
        cursor_position=int(cursor.position()),
        anchor_position=int(surface.anchor_position),
    )
    visible_source_current = False
    overlay_kind: str | None = None
    if insertion is not None:
        overlay_kind = "insertion"
        visible_source_current = (
            projection_source[: insertion.source_start]
            + insertion.text
            + projection_source[insertion.source_start :]
            == source_text
        )
    elif deletion is not None:
        overlay_kind = "deletion"
        visible_source_current = (
            projection_source[: deletion.source_start]
            + projection_source[deletion.source_end :]
            == source_text
        )
    elif overlays.insertion_overlay is not None:
        overlay_kind = "invalid_insertion"
    elif overlays.deletion_overlay is not None:
        overlay_kind = "invalid_deletion"
    return PromptAbuseOwnerState(
        projection_current=False,
        semantic_current=semantic_current,
        visible_source_current=visible_source_current,
        visible_caret_current=caret is not None,
        active_projection_ownership_valid=None,
        layout_projection_ownership_valid=None,
        caret_transform_depth=caret_transform_depth,
        caret_transform_depth_valid=caret_transform_depth_valid,
        transient_overlay_kind=overlay_kind,
        projection_freshness=freshness_name,
        layout_fragment_ownership_valid=layout_fragment_ownership_valid,
        layout_fragment_ownership_mismatch=layout_fragment_ownership_mismatch,
    )


def _layout_fragment_ownership(surface: Any) -> tuple[bool | None, str | None]:
    """Validate that every paint fragment resolves in its owning document."""

    if surface is None:
        return None, None
    layout = getattr(surface, "_layout", None)
    frames = [None if layout is None else getattr(layout, "frame", None)]
    preview_projection = getattr(surface, "_reorder_preview_projection", None)
    preview_frame = getattr(preview_projection, "preview_frame", None)
    if preview_frame is not None:
        frames.append(preview_frame)
    for layout_name, frame in zip(("base", "preview"), frames, strict=False):
        if frame is None:
            continue
        document = frame.output.projection_document
        region_mismatch = _region_projection_ownership(
            surface,
            frame,
            layout_name=layout_name,
        )
        if region_mismatch is not None:
            return False, region_mismatch
        for line_index, line in enumerate(frame.output.snapshot.lines):
            for fragment_index, fragment in enumerate(line.fragments):
                run = document.run_by_id(fragment.run_id)
                location = f"{layout_name}:{line_index}:{fragment_index}"
                if run is None:
                    return False, f"{location}:missing_run:{fragment.run_id}"
                if isinstance(fragment, PromptProjectionTextFragment):
                    local_start = fragment.projection_start - run.projection_start
                    local_end = fragment.projection_end - run.projection_start
                    if (
                        local_start < 0
                        or local_end > len(run.display_text)
                        or run.display_text[local_start:local_end] != fragment.text
                    ):
                        return False, f"{location}:text_run_slice_mismatch:{run.run_id}"
                    if fragment.token_id != run.token_id:
                        return False, f"{location}:text_token_mismatch:{run.run_id}"
                    continue
                if isinstance(fragment, PromptProjectionInlineObjectFragment):
                    if (
                        run.renderer_key != fragment.renderer_key
                        or fragment.token_id != run.token_id
                        or document.token_by_id(fragment.token_id) is None
                    ):
                        return False, f"{location}:inline_owner_mismatch:{run.run_id}"
    return True, None


def _region_projection_ownership(
    surface: Any,
    frame: Any,
    *,
    layout_name: str,
) -> str | None:
    """Return a cross-layer regional projection mismatch for one live layout."""

    output = frame.output
    document = output.projection_document
    if document.display_mode is not PromptProjectionDisplayMode.PROJECTED:
        return _raw_region_projection_mismatch(
            surface,
            frame,
            layout_name=layout_name,
        )
    separators = document.region_structure.separators
    expected_token_ranges = tuple(
        (separator.token_start, separator.token_end) for separator in separators
    )
    region_tokens = tuple(
        token
        for token in document.tokens
        if token.kind is PromptProjectionTokenKind.REGION_SEPARATOR
    )
    actual_token_ranges = tuple(
        (token.source_start, token.source_end) for token in region_tokens
    )
    if actual_token_ranges != expected_token_ranges:
        return (
            f"{layout_name}:region_token_ranges:"
            f"actual={actual_token_ranges!r}:expected={expected_token_ranges!r}"
        )
    for caret_name, state in (
        ("cursor", getattr(surface, "_cursor_state", None)),
        ("anchor", getattr(surface, "_anchor_state", None)),
    ):
        source_position = getattr(state, "source_position", None)
        if isinstance(source_position, int) and any(
            start < source_position < end for start, end in expected_token_ranges
        ):
            return (
                f"{layout_name}:region_{caret_name}_inside_hidden_source:"
                f"{source_position}"
            )

    structural_runs = tuple(
        run
        for run in document.runs
        if run.kind is PromptProjectionRunKind.STRUCTURAL_ROW
    )
    expected_line_ranges = tuple(
        (separator.line_start, separator.line_end) for separator in separators
    )
    actual_line_ranges = tuple(
        (run.source_start, run.source_end) for run in structural_runs
    )
    if actual_line_ranges != expected_line_ranges:
        return (
            f"{layout_name}:region_run_ranges:"
            f"actual={actual_line_ranges!r}:expected={expected_line_ranges!r}"
        )

    token_ids = {token.token_id for token in region_tokens}
    for run in structural_runs:
        location = f"{layout_name}:region_run:{run.run_id}"
        if run.token_id not in token_ids:
            return f"{location}:missing_region_token:{run.token_id}"
        if (
            document.projection_text[run.projection_start : run.projection_end]
            != "\ufffc"
        ):
            return f"{location}:missing_structural_projection_slot"
        matching_lines = tuple(
            line
            for line in output.snapshot.lines
            if (line.source_start, line.source_end)
            == (run.source_start, run.source_end)
        )
        if len(matching_lines) != 1:
            return f"{location}:layout_line_count:{len(matching_lines)}"
        structural_line = matching_lines[0]
        if structural_line.fragments:
            return f"{location}:structural_fragments_present"
        if structural_line.caret_stops:
            return f"{location}:structural_caret_stops_present"

    chrome = getattr(surface, "_region_chrome", None)
    snapshot = None if chrome is None else chrome.snapshot_for(output)
    if not separators:
        if snapshot is not None:
            return f"{layout_name}:ordinary_region_chrome_snapshot_present"
        return None
    if snapshot is None:
        return f"{layout_name}:region_chrome_snapshot_missing"
    if len(snapshot.divider_lines) != len(separators):
        return (
            f"{layout_name}:region_divider_count:"
            f"actual={len(snapshot.divider_lines)}:expected={len(separators)}"
        )
    expected_rail_count = sum(
        not partition.is_global for partition in document.region_structure.partitions
    )
    if len(snapshot.rail_lines) != expected_rail_count:
        return (
            f"{layout_name}:region_rail_count:"
            f"actual={len(snapshot.rail_lines)}:expected={expected_rail_count}"
        )
    metrics = output.configuration.metrics
    expected_center = metrics.content_left + metrics.content_width / 2.0
    if any(
        abs(divider.center().x() - expected_center) > 0.001
        for divider in snapshot.divider_lines
    ):
        return f"{layout_name}:region_divider_not_centered"
    return None


def _raw_region_projection_mismatch(
    surface: Any,
    frame: Any,
    *,
    layout_name: str,
) -> str | None:
    """Return raw-mode structure or chrome that should not have been prepared."""

    output = frame.output
    document = output.projection_document
    region_tokens = tuple(
        token
        for token in document.tokens
        if token.kind is PromptProjectionTokenKind.REGION_SEPARATOR
    )
    if region_tokens:
        return f"{layout_name}:raw_region_tokens_present:{len(region_tokens)}"
    structural_runs = tuple(
        run
        for run in document.runs
        if run.kind is PromptProjectionRunKind.STRUCTURAL_ROW
    )
    if structural_runs:
        return f"{layout_name}:raw_structural_runs_present:{len(structural_runs)}"
    if document.projection_text != document.source_text:
        return f"{layout_name}:raw_projection_not_literal"
    chrome = getattr(surface, "_region_chrome", None)
    snapshot = None if chrome is None else chrome.snapshot_for(output)
    if snapshot is None:
        return None
    if snapshot.paint_lines or snapshot.divider_lines or snapshot.rail_lines:
        return f"{layout_name}:raw_region_chrome_present"
    if snapshot.visited_line_count != 0:
        return (
            f"{layout_name}:raw_region_chrome_lines_visited:"
            f"{snapshot.visited_line_count}"
        )
    return None


def _caret_transform_depth(projection_document: Any) -> int | None:
    """Return unresolved plain-edit transform depth when one is active."""

    caret_map = getattr(projection_document, "caret_map", None)
    stops = getattr(caret_map, "stops", None)
    depth = getattr(stops, "transform_depth", None)
    return int(depth) if isinstance(depth, int) else None


def _fresh_projection_maps_current_caret(
    surface: Any,
    projection_document: Any,
) -> bool:
    """Return whether fresh layout geometry owns a visible live-source caret."""

    cursor_state = surface._cursor_state
    cursor_position = int(surface.cursor_position)
    if int(cursor_state.source_position) != cursor_position:
        return False
    resolved_state = projection_document.caret_map.resolve_state(cursor_state)
    caret_rect = surface._layout.frame.geometry.caret.cursor_rect(
        resolved_state,
        scroll_offset=0.0,
    )
    return (
        all(
            isfinite(value)
            for value in (
                caret_rect.left(),
                caret_rect.top(),
                caret_rect.width(),
                caret_rect.height(),
            )
        )
        and caret_rect.width() >= 1.0
        and caret_rect.height() > 0.0
    )


def _active_projection_ownership_is_valid(
    surface: Any,
    projection_document: Any,
) -> bool:
    """Return whether active projection divergence has a live transient owner."""

    active_projection = surface.active_projection_document()
    if bool(surface._active_projection_requires_layout()):
        return str(active_projection.source_text) == str(
            projection_document.source_text
        )
    return str(active_projection.projection_text) == str(
        projection_document.projection_text
    )


def _layout_projection_ownership_is_valid(
    surface: Any,
    projection_document: Any,
) -> bool:
    """Return whether layout divergence has an active transient or reorder owner."""

    layout_projection = surface._layout.frame.output.projection_document
    reorder_preview_active = bool(surface._reorder_preview_projection.is_active())
    if reorder_preview_active:
        return True
    if bool(surface._active_projection_requires_layout()):
        return layout_projection is surface.active_projection_document()
    return str(layout_projection.projection_text) == str(
        projection_document.projection_text
    )


__all__ = [
    "PromptAbuseOwnerState",
    "capture_prompt_cursor_positions",
    "capture_prompt_editor_owner_state",
]
