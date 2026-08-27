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

"""Validate stable prompt-editor geometry across real-shell transitions."""

from __future__ import annotations

from collections.abc import Sequence

from tests.support.prompt_editor.real_shell.input_driver import (
    source_insert_position,
    source_inserted_text,
)
from tests.support.prompt_editor.real_shell.models import (
    PromptEditorStateSnapshot,
    PromptEditorVisibleTextFragment,
)


def action_should_leave_caret_visible(
    action_name: str,
    *,
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
) -> bool:
    """Return whether one completed action should settle with a visible caret."""

    return action_name in {
        "prefix",
        "space",
        "backspace",
        "delete",
        "caret",
        "selection",
        "selection_replace",
        "paste",
        "undo_redo",
    } and (
        before.source_text != after.source_text
        or before.cursor_position != after.cursor_position
        or before.selection_range != after.selection_range
    )


def transition_geometry_violations(
    *,
    action_name: str,
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
) -> tuple[str, ...]:
    """Return layout and chrome violations for one settled editor transition."""

    return (
        *_stable_single_character_content_height_violations(
            action_name=action_name, before=before, after=after
        ),
        *_non_uniform_visible_row_shift_violations(before=before, after=after),
        *_non_uniform_visible_fragment_shift_violations(
            action_name=action_name, before=before, after=after
        ),
        *_stable_single_character_geometry_violations(
            action_name=action_name, before=before, after=after
        ),
    )


def _non_uniform_visible_row_shift_violations(
    *, before: PromptEditorStateSnapshot, after: PromptEditorStateSnapshot
) -> tuple[str, ...]:
    """Return violations when stable visible rows move by different amounts."""

    if before.projection_has_stale_geometry or after.projection_has_stale_geometry:
        return ()
    if before.layout_line_count != after.layout_line_count:
        return ()
    if abs(before.layout_content_height - after.layout_content_height) > 0.5:
        return ()
    before_rows = {row.row_index: row for row in before.visible_layout_rows}
    after_rows = {row.row_index: row for row in after.visible_layout_rows}
    shared_indexes = tuple(
        index for index in sorted(before_rows) if index in after_rows
    )
    if len(shared_indexes) < 2:
        return ()
    row_deltas = tuple(
        (index, after_rows[index].viewport_top - before_rows[index].viewport_top)
        for index in shared_indexes
    )
    delta_values = tuple(delta for _index, delta in row_deltas)
    if max(delta_values) - min(delta_values) <= 0.75:
        return ()
    return (
        "non_uniform_visible_row_shift:"
        f"rows={_format_row_delta_summary(row_deltas)}:"
        f"scroll_delta={after.scroll_values['editor_vertical'] - before.scroll_values['editor_vertical']}:"
        f"editor_height_delta={_geometry_height_delta(before, after, 'editor')}:"
        f"viewport_height_delta={_geometry_height_delta(before, after, 'viewport')}",
    )


def _stable_single_character_content_height_violations(
    *,
    action_name: str,
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
) -> tuple[str, ...]:
    """Return violations when a stable one-character edit changes content height."""

    if action_name not in {"space", "type_text"}:
        return ()
    inserted_text = source_inserted_text(before.source_text, after.source_text)
    if len(inserted_text) != 1 or inserted_text in "\r\n\t":
        return ()
    if before.projection_has_stale_geometry or after.projection_has_stale_geometry:
        return ()
    if before.layout_line_count != after.layout_line_count:
        return ()
    content_height_delta = after.layout_content_height - before.layout_content_height
    if abs(content_height_delta) <= 0.75:
        return ()
    return (
        "stable_single_character_content_height_shift:"
        f"inserted={inserted_text!r}:"
        f"content_height_delta={content_height_delta:.2f}:"
        f"line_count={before.layout_line_count}:"
        f"rows={_format_changed_row_geometry_summary(before=before, after=after)}:"
        f"editor_height_delta={_geometry_height_delta(before, after, 'editor')}:"
        f"viewport_height_delta={_geometry_height_delta(before, after, 'viewport')}",
    )


def _stable_single_character_geometry_violations(
    *,
    action_name: str,
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
) -> tuple[str, ...]:
    """Return violations when stable one-character edits move editor chrome."""

    if before.projection_has_stale_geometry or after.projection_has_stale_geometry:
        return ()
    inserted_text = source_inserted_text(before.source_text, after.source_text)
    if action_name not in {"space", "type_text"} or len(inserted_text) != 1:
        return ()
    if inserted_text in "\r\n\t" or before.layout_line_count != after.layout_line_count:
        return ()
    if abs(before.layout_content_width - after.layout_content_width) > 0.5:
        return ()
    if abs(before.layout_content_height - after.layout_content_height) > 0.5:
        return ()
    changed_geometry = tuple(
        (key, _geometry_height_delta(before, after, key))
        for key in ("panel", "editor", "viewport")
        if _geometry_height_delta(before, after, key) not in (None, 0)
    )
    if not changed_geometry:
        return ()
    return (
        "stable_single_character_geometry_shift:"
        f"inserted={inserted_text!r}:"
        f"geometry_height_delta={','.join(f'{key}:{delta}' for key, delta in changed_geometry)}:"
        f"line_count={before.layout_line_count}:"
        f"content_height={before.layout_content_height:.2f}",
    )


def _format_changed_row_geometry_summary(
    *, before: PromptEditorStateSnapshot, after: PromptEditorStateSnapshot
) -> str:
    """Return visible rows whose top or height changed across one transition."""

    before_rows = {row.row_index: row for row in before.visible_layout_rows}
    after_rows = {row.row_index: row for row in after.visible_layout_rows}
    changed_rows: list[str] = []
    for index in sorted(before_rows):
        after_row = after_rows.get(index)
        if after_row is None:
            continue
        before_row = before_rows[index]
        top_delta = after_row.viewport_top - before_row.viewport_top
        height_delta = after_row.height - before_row.height
        if abs(top_delta) <= 0.25 and abs(height_delta) <= 0.25:
            continue
        changed_rows.append(f"{index}:{top_delta:.2f}/{height_delta:.2f}")
        if len(changed_rows) >= 12:
            break
    return ",".join(changed_rows)


def _non_uniform_visible_fragment_shift_violations(
    *,
    action_name: str,
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
) -> tuple[str, ...]:
    """Return violations when stable visible text fragments move unevenly."""

    if action_name not in {"space", "type_text"}:
        return ()
    inserted_text = source_inserted_text(before.source_text, after.source_text)
    if len(inserted_text) != 1 or inserted_text in "\r\n\t":
        return ()
    if before.projection_has_stale_geometry or after.projection_has_stale_geometry:
        return ()
    if before.layout_line_count != after.layout_line_count:
        return ()
    if not _visible_row_source_ranges_are_stable(before=before, after=after):
        return ()
    if abs(before.layout_content_width - after.layout_content_width) > 0.5:
        return ()
    if abs(before.layout_content_height - after.layout_content_height) > 0.5:
        return ()
    insert_position = source_insert_position(before.source_text, after.source_text)
    if insert_position is None:
        return ()
    before_fragments = _stable_visible_fragment_map(
        before.visible_text_fragments, insert_position=insert_position
    )
    after_fragments = {
        _visible_fragment_key(fragment): fragment
        for fragment in after.visible_text_fragments
    }
    shared_keys = tuple(key for key in before_fragments if key in after_fragments)
    if len(shared_keys) < 2:
        return ()
    fragment_deltas = tuple(
        (
            before_fragments[key].fragment_index,
            after_fragments[key].viewport_baseline
            - before_fragments[key].viewport_baseline,
        )
        for key in shared_keys
    )
    delta_values = tuple(delta for _index, delta in fragment_deltas)
    if max(delta_values) - min(delta_values) <= 0.75:
        return ()
    return (
        "non_uniform_visible_fragment_shift:"
        f"fragments={_format_fragment_delta_summary(fragment_deltas)}:"
        f"scroll_delta={after.scroll_values['editor_vertical'] - before.scroll_values['editor_vertical']}:"
        f"editor_height_delta={_geometry_height_delta(before, after, 'editor')}:"
        f"viewport_height_delta={_geometry_height_delta(before, after, 'viewport')}",
    )


def _stable_visible_fragment_map(
    fragments: Sequence[PromptEditorVisibleTextFragment], *, insert_position: int
) -> dict[tuple[int, int, str], PromptEditorVisibleTextFragment]:
    """Return visible fragments outside the insertion span keyed by post-edit source."""

    stable_fragments: dict[tuple[int, int, str], PromptEditorVisibleTextFragment] = {}
    for fragment in fragments:
        if fragment.source_start < insert_position < fragment.source_end:
            continue
        key = (
            (fragment.source_start + 1, fragment.source_end + 1, fragment.text)
            if fragment.source_start >= insert_position
            else _visible_fragment_key(fragment)
        )
        stable_fragments[key] = fragment
    return stable_fragments


def _visible_row_source_ranges_are_stable(
    *, before: PromptEditorStateSnapshot, after: PromptEditorStateSnapshot
) -> bool:
    """Return whether shared visible rows still cover the same logical text."""

    insert_position = source_insert_position(before.source_text, after.source_text)
    before_rows = {row.row_index: row for row in before.visible_layout_rows}
    after_rows = {row.row_index: row for row in after.visible_layout_rows}
    shared_indexes = tuple(index for index in before_rows if index in after_rows)
    if len(shared_indexes) < 2:
        return False
    for index in shared_indexes:
        before_row = before_rows[index]
        after_row = after_rows[index]
        expected_start, expected_end = before_row.source_start, before_row.source_end
        if insert_position is not None and before_row.source_start >= insert_position:
            expected_start, expected_end = expected_start + 1, expected_end + 1
        elif (
            insert_position is not None
            and before_row.source_start < insert_position <= before_row.source_end
        ):
            expected_end += 1
        if (after_row.source_start, after_row.source_end) != (
            expected_start,
            expected_end,
        ):
            return False
    return True


def _visible_fragment_key(
    fragment: PromptEditorVisibleTextFragment,
) -> tuple[int, int, str]:
    """Return the stable source/text identity for one visible text fragment."""

    return fragment.source_start, fragment.source_end, fragment.text


def _format_fragment_delta_summary(fragment_deltas: Sequence[tuple[int, float]]) -> str:
    """Return a compact fragment-delta summary for artifact diagnostics."""

    return ",".join(f"{index}:{delta:.2f}" for index, delta in fragment_deltas[:12])


def _format_row_delta_summary(row_deltas: Sequence[tuple[int, float]]) -> str:
    """Return a compact row-delta summary for artifact diagnostics."""

    return ",".join(f"{index}:{delta:.2f}" for index, delta in row_deltas[:12])


def _geometry_height_delta(
    before: PromptEditorStateSnapshot, after: PromptEditorStateSnapshot, key: str
) -> int | None:
    """Return one captured geometry height delta when both snapshots have it."""

    before_rect, after_rect = before.geometries.get(key), after.geometries.get(key)
    return (
        None
        if before_rect is None or after_rect is None
        else after_rect[3] - before_rect[3]
    )
