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

"""Validate projection-derived state snapshots from a real prompt-editor shell."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.support.prompt_editor.real_shell.models import (
        PromptEditorStateSnapshot,
        PromptEditorVisibleLayoutRow,
        PromptEditorVisibleTextFragment,
    )


def accepted_selected_text_for_source(source_text: str) -> tuple[str, str]:
    """Return accepted editor selected-text representations for a source slice."""

    return source_text, source_text.replace("\n", "\u2029")


def autocomplete_state_is_owned_or_visible(
    snapshot: PromptEditorStateSnapshot,
) -> bool:
    """Return whether any autocomplete owner or surface remains active."""

    return bool(
        snapshot.autocomplete_preview_active
        or snapshot.autocomplete_has_active_session
        or snapshot.autocomplete_presenter_panel_visible
        or snapshot.popup_state_visible
    )


def projection_metrics_contract_violations(
    snapshot: PromptEditorStateSnapshot,
) -> tuple[str, ...]:
    """Return geometry mismatches against the projection metrics authority."""

    violations: list[str] = []
    for row in snapshot.visible_layout_rows:
        if row.expected_height is not None and not _float_close(
            row.height,
            row.expected_height,
        ):
            violations.append(
                "structural_row_height_mismatch"
                if row.is_structural
                else (
                    "text_only_row_height_mismatch"
                    if not row.has_inline_object
                    else "inline_row_height_mismatch"
                )
            )
        if (
            not row.is_structural
            and not row.has_inline_object
            and row.expected_text_baseline is not None
            and not _row_contains_fragment_with_baseline(
                row=row,
                fragments=snapshot.visible_text_fragments,
                baseline=row.expected_text_baseline,
            )
            and row.text.strip("\r\n")
        ):
            violations.append(f"text_only_row_baseline_mismatch:{row.row_index}")
    for fragment in snapshot.visible_text_fragments:
        if fragment.expected_height is not None and not _float_close(
            fragment.viewport_rect[3],
            fragment.expected_height,
        ):
            violations.append(
                f"text_fragment_height_mismatch:{fragment.fragment_index}"
            )
        if fragment.expected_document_baseline is not None and not _float_close(
            fragment.document_baseline,
            fragment.expected_document_baseline,
        ):
            violations.append(
                f"text_fragment_baseline_mismatch:{fragment.fragment_index}"
            )
    if snapshot.projection_metrics_content_height is not None and not _float_close(
        snapshot.layout_content_height,
        snapshot.projection_metrics_content_height,
    ):
        violations.append(
            "content_height_contract_mismatch:"
            f"{snapshot.layout_content_height:.3f}:"
            f"{snapshot.projection_metrics_content_height:.3f}"
        )
    violations.extend(_shell_height_contract_violations(snapshot))
    return tuple(violations)


def _row_contains_fragment_with_baseline(
    *,
    row: PromptEditorVisibleLayoutRow,
    fragments: tuple[PromptEditorVisibleTextFragment, ...],
    baseline: float,
) -> bool:
    """Return whether one row has a text fragment at the expected baseline."""

    row_bottom = row.document_top + row.height
    for fragment in fragments:
        fragment_top = fragment.document_rect[1]
        if fragment_top < row.document_top - 0.5 or fragment_top > row_bottom + 0.5:
            continue
        if _float_close(fragment.document_baseline, baseline):
            return True
    return False


def _shell_height_contract_violations(
    snapshot: PromptEditorStateSnapshot,
) -> tuple[str, ...]:
    """Return shell sizing mismatches against projection metrics and padding."""

    if (
        snapshot.projection_metrics_text_line_height is None
        or snapshot.shell_document_vertical_padding is None
        or snapshot.shell_outer_vertical_padding is None
        or snapshot.shell_natural_height is None
        or snapshot.shell_natural_height <= 0
    ):
        return ()
    minimum_document_height = math.ceil(
        snapshot.projection_metrics_text_line_height
        + snapshot.shell_document_vertical_padding
    )
    expected_natural_height = (
        max(math.ceil(snapshot.layout_content_height), minimum_document_height)
        + snapshot.shell_outer_vertical_padding
    )
    if abs(snapshot.shell_natural_height - expected_natural_height) <= 1:
        return ()
    return (
        "shell_height_contract_mismatch:"
        f"{snapshot.shell_natural_height}:{expected_natural_height}",
    )


def caret_row_height_contract_violations(
    snapshot: PromptEditorStateSnapshot,
) -> tuple[str, ...]:
    """Return caret height mismatches against the row containing the caret."""

    if snapshot.caret_rect is None:
        return ()
    caret_y = snapshot.caret_rect[1]
    caret_height = snapshot.caret_rect[3]
    for row in snapshot.visible_layout_rows:
        if row.is_structural:
            continue
        if row.viewport_top - 0.5 <= caret_y <= row.viewport_top + row.height + 0.5:
            if not _float_close(caret_height, row.height):
                return (
                    f"caret_rect_height_mismatch:{caret_height:.3f}:{row.height:.3f}",
                )
            return ()
    return ()


def _float_close(first: float, second: float, *, tolerance: float = 0.51) -> bool:
    """Return whether two geometry floats are equivalent for harness assertions."""

    return abs(first - second) <= tolerance
