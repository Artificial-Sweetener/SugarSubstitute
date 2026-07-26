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

"""Build projection documents for bounded trailing plain-text edits."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.mapping import (
    PromptProjectionMapping,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
)

from .caret_map_builder import build_prompt_projection_caret_map
from .render_plan_ranges import projection_affecting_render_plan_ranges


class PromptTrailingDocumentEditor:
    """Build the four supported trailing projection-document transitions."""

    def plain_insert(
        self,
        *,
        previous_document: PromptProjectionDocument,
        next_text: str,
        render_plan: PromptSyntaxRenderPlan,
    ) -> PromptProjectionDocument | None:
        """Return a projection document for a trailing plain-text insert."""

        previous_text = previous_document.source_text
        previous_length = len(previous_text)
        appended_text = next_text[previous_length:]
        if (
            len(next_text) <= previous_length
            or not next_text.startswith(previous_text)
            or not previous_document.runs
            or any(
                span_end > previous_length
                for _span_start, span_end in projection_affecting_render_plan_ranges(
                    render_plan
                )
            )
        ):
            return None
        if any(character in {"\n", "\r"} for character in appended_text):
            return None
        last_run = previous_document.runs[-1]
        if not _run_supports_trailing_edit(
            last_run,
            source_end=previous_length,
            projection_end=previous_document.mapping.projection_length,
        ):
            return None

        appended_length = len(appended_text)
        next_projection_length = (
            previous_document.mapping.projection_length + appended_length
        )
        next_run = replace(
            last_run,
            source_end=previous_length + appended_length,
            display_text=last_run.display_text + appended_text,
            source_positions=_extend_contiguous_source_positions(
                last_run.source_positions,
                source_start=last_run.source_start,
                previous_source_end=previous_length,
                next_source_end=previous_length + appended_length,
            ),
            projection_end=last_run.projection_end + appended_length,
        )
        next_runs = tuple(previous_document.runs[:-1]) + (next_run,)
        return _replace_trailing_document(
            previous_document,
            next_text=next_text,
            next_projection_text=previous_document.projection_text + appended_text,
            next_runs=next_runs,
            next_projection_length=next_projection_length,
        )

    def newline_insert(
        self,
        *,
        previous_document: PromptProjectionDocument,
        previous_text: str,
        next_text: str,
        start: int,
        end: int,
        render_plan: PromptSyntaxRenderPlan,
    ) -> PromptProjectionDocument | None:
        """Return a projection document for a trailing hard-line insert."""

        previous_length = len(previous_text)
        if (
            start != previous_length
            or end != previous_length
            or next_text != f"{previous_text}\n"
            or previous_document.source_text != previous_text
            or not previous_document.runs
            or any(
                span_end > previous_length
                for _span_start, span_end in projection_affecting_render_plan_ranges(
                    render_plan
                )
            )
        ):
            return None
        last_run = previous_document.runs[-1]
        if not _run_supports_trailing_edit(
            last_run,
            source_end=previous_length,
            projection_end=previous_document.mapping.projection_length,
        ):
            return None

        next_projection_length = previous_document.mapping.projection_length + 1
        next_run = replace(
            last_run,
            source_end=previous_length + 1,
            display_text=f"{last_run.display_text}\n",
            source_positions=_extend_contiguous_source_positions(
                last_run.source_positions,
                source_start=last_run.source_start,
                previous_source_end=previous_length,
                next_source_end=previous_length + 1,
            ),
            projection_end=last_run.projection_end + 1,
        )
        next_runs = tuple(previous_document.runs[:-1]) + (next_run,)
        return _replace_trailing_document(
            previous_document,
            next_text=next_text,
            next_projection_text=f"{previous_document.projection_text}\n",
            next_runs=next_runs,
            next_projection_length=next_projection_length,
        )

    def plain_delete(
        self,
        *,
        previous_document: PromptProjectionDocument,
        previous_text: str,
        next_text: str,
        start: int,
        end: int,
    ) -> PromptProjectionDocument | None:
        """Return a projection document for a one-character trailing deletion."""

        if (
            start != len(previous_text) - 1
            or end != len(previous_text)
            or next_text != previous_text[:start]
            or previous_document.source_text != previous_text
            or not previous_document.runs
            or previous_document.projection_text == ""
        ):
            return None
        last_run = previous_document.runs[-1]
        if (
            not _run_supports_trailing_delete(
                last_run,
                start=start,
                end=end,
                projection_end=previous_document.mapping.projection_length,
            )
            or not last_run.display_text
        ):
            return None
        return _delete_trailing_character(
            previous_document,
            next_text=next_text,
            next_projection_text=previous_document.projection_text[:-1],
            start=start,
            last_run=last_run,
        )

    def newline_delete(
        self,
        *,
        previous_document: PromptProjectionDocument,
        previous_text: str,
        next_text: str,
        start: int,
        end: int,
    ) -> PromptProjectionDocument | None:
        """Return a projection document for a trailing hard-line deletion."""

        if (
            start != len(previous_text) - 1
            or end != len(previous_text)
            or not previous_text.endswith("\n")
            or next_text != previous_text[:-1]
            or previous_document.source_text != previous_text
            or not previous_document.runs
            or not previous_document.projection_text.endswith("\n")
        ):
            return None
        last_run = previous_document.runs[-1]
        if not _run_supports_trailing_delete(
            last_run,
            start=start,
            end=end,
            projection_end=previous_document.mapping.projection_length,
        ) or not last_run.display_text.endswith("\n"):
            return None
        return _delete_trailing_character(
            previous_document,
            next_text=next_text,
            next_projection_text=previous_document.projection_text[:-1],
            start=start,
            last_run=last_run,
        )


def _run_supports_trailing_edit(
    run: PromptProjectionRun,
    *,
    source_end: int,
    projection_end: int,
) -> bool:
    """Return whether one source-backed text run can extend at its trailing edge."""

    return bool(
        run.is_text
        and run.source_backed
        and run.token_id is None
        and run.source_end == source_end
        and run.projection_end == projection_end
        and len(run.source_positions) >= 1
        and run.source_positions[-1] == source_end
    )


def _run_supports_trailing_delete(
    run: PromptProjectionRun,
    *,
    start: int,
    end: int,
    projection_end: int,
) -> bool:
    """Return whether one source-backed text run can lose its final character."""

    source_positions = run.source_positions
    return bool(
        _run_supports_trailing_edit(
            run,
            source_end=end,
            projection_end=projection_end,
        )
        and len(source_positions) >= 2
        and source_positions[-2] == start
    )


def _delete_trailing_character(
    previous_document: PromptProjectionDocument,
    *,
    next_text: str,
    next_projection_text: str,
    start: int,
    last_run: PromptProjectionRun,
) -> PromptProjectionDocument:
    """Return a document with the final source-backed character removed."""

    next_display_text = last_run.display_text[:-1]
    next_run = replace(
        last_run,
        source_end=start,
        display_text=next_display_text,
        source_positions=last_run.source_positions[:-1],
        projection_end=last_run.projection_end - 1,
    )
    next_runs = (
        tuple(previous_document.runs[:-1]) + (next_run,)
        if next_display_text
        else tuple(previous_document.runs[:-1])
    )
    return _replace_trailing_document(
        previous_document,
        next_text=next_text,
        next_projection_text=next_projection_text,
        next_runs=next_runs,
        next_projection_length=len(next_projection_text),
    )


def _replace_trailing_document(
    previous_document: PromptProjectionDocument,
    *,
    next_text: str,
    next_projection_text: str,
    next_runs: tuple[PromptProjectionRun, ...],
    next_projection_length: int,
) -> PromptProjectionDocument:
    """Return a projection document with one validated trailing run transition."""

    next_caret_map = build_prompt_projection_caret_map(
        runs=next_runs,
        tokens=tuple(previous_document.tokens),
        source_length=len(next_text),
        projection_length=next_projection_length,
    )
    return replace(
        previous_document,
        source_text=next_text,
        projection_text=next_projection_text,
        runs=next_runs,
        mapping=PromptProjectionMapping(
            runs=next_runs,
            source_length=len(next_text),
            projection_length=next_projection_length,
        ),
        caret_map=next_caret_map,
    )


def _extend_contiguous_source_positions(
    source_positions: Sequence[int],
    *,
    source_start: int,
    previous_source_end: int,
    next_source_end: int,
) -> Sequence[int]:
    """Return source positions after extending one trailing contiguous text run."""

    if (
        len(source_positions) == previous_source_end - source_start + 1
        and source_positions[0] == source_start
        and source_positions[-1] == previous_source_end
    ):
        return range(source_start, next_source_end + 1)
    return tuple(source_positions) + tuple(
        range(previous_source_end + 1, next_source_end + 1)
    )


__all__ = ["PromptTrailingDocumentEditor"]
