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

"""Reconcile source-local scene-title edits with projected token metadata."""

from __future__ import annotations

from dataclasses import dataclass, replace

from substitute.domain.prompt import normalize_scene_title, parse_prompt_scene_document

from .caret_map_builder import build_prompt_projection_caret_map
from .model import (
    PromptProjectionDocument,
    PromptProjectionMapping,
    PromptProjectionRun,
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from .scene_title_projection import reconcile_scene_title_projection_run


@dataclass(frozen=True, slots=True)
class PromptSceneProjectionIncrementalResult:
    """Carry a canonical local scene document and its visible text edit."""

    document: PromptProjectionDocument
    projection_start: int
    projection_end: int
    projection_replacement_text: str


class PromptSceneProjectionIncrementalEditor:
    """Own classification and metadata repair for local scene-title edits."""

    def editable_title_run(
        self,
        *,
        previous_document: PromptProjectionDocument,
        start: int,
        end: int,
        replacement_text: str,
    ) -> PromptProjectionRun | None:
        """Return the scene-title run when an edit preserves its visible content."""

        if "\n" in replacement_text or "\r" in replacement_text:
            return None
        for token in previous_document.tokens:
            if not _edit_is_inside_scene_title(token, start=start, end=end):
                continue
            assert token.content_start is not None
            assert token.content_end is not None
            local_start = start - token.content_start
            local_end = end - token.content_start
            next_title = (
                token.display_text[:local_start]
                + replacement_text
                + token.display_text[local_end:]
            )
            if not next_title:
                return None
            runs = previous_document.runs_for_token(token.token_id)
            if len(runs) != 1 or not runs[0].is_text:
                return None
            return runs[0]
        return None

    def reconcile_document(
        self,
        document: PromptProjectionDocument,
        *,
        edited_token_id: str,
        previous_visible_text: str,
        scene_error_keys: frozenset[str],
    ) -> PromptSceneProjectionIncrementalResult | None:
        """Update scene values and duplicate styling after remapping source geometry."""

        edited_token = document.token_by_id(edited_token_id)
        if (
            edited_token is None
            or edited_token.kind is not PromptProjectionTokenKind.SCENE
            or edited_token.content_start is None
            or edited_token.content_end is None
        ):
            return None
        line_start = edited_token.source_start
        line_end = document.source_text.find("\n", line_start)
        if line_end < 0:
            line_end = len(document.source_text)
        local_scene_document = parse_prompt_scene_document(
            document.source_text[line_start:line_end]
        )
        if len(local_scene_document.scenes) != 1:
            return None
        marker = local_scene_document.scenes[0].marker
        next_title = marker.title
        next_key = normalize_scene_title(next_title)
        if not next_key:
            return None

        updated_tokens = tuple(
            replace(
                token,
                source_start=line_start + marker.line_range.start,
                source_end=line_start + marker.line_range.end,
                content_start=line_start + marker.title_range.start,
                content_end=line_start + marker.title_range.end,
                display_text=next_title,
                value_text=next_key,
            )
            if token.token_id == edited_token_id
            else token
            for token in document.tokens
        )
        styled_tokens = _apply_scene_duplicate_styles(
            updated_tokens,
            scene_error_keys=scene_error_keys,
        )
        tokens_by_id = {token.token_id: token for token in styled_tokens}
        edited_run = next(
            (
                run
                for run in document.runs
                if run.token_id == edited_token_id and run.is_text
            ),
            None,
        )
        if edited_run is None:
            return None
        next_visible_text = document.source_text[
            edited_token.content_start : edited_token.source_end
        ]
        projection_adjustment = len(next_visible_text) - len(edited_run.display_text)
        updated_runs = tuple(
            _reconcile_scene_title_run(
                run,
                edited_run=edited_run,
                projection_adjustment=projection_adjustment,
                tokens_by_id=tokens_by_id,
                source_text=document.source_text,
            )
            for run in document.runs
        )
        final_projection_text = (
            document.projection_text[: edited_run.projection_start]
            + next_visible_text
            + document.projection_text[edited_run.projection_end :]
        )
        mapping = PromptProjectionMapping(
            runs=updated_runs,
            source_length=len(document.source_text),
            projection_length=len(final_projection_text),
        )
        caret_map = build_prompt_projection_caret_map(
            runs=updated_runs,
            tokens=styled_tokens,
            source_length=len(document.source_text),
            projection_length=len(final_projection_text),
        )
        projection_prefix, previous_suffix, next_suffix = _single_text_edit_boundaries(
            previous_visible_text,
            next_visible_text,
        )
        return PromptSceneProjectionIncrementalResult(
            document=replace(
                document,
                projection_text=final_projection_text,
                tokens=styled_tokens,
                runs=updated_runs,
                mapping=mapping,
                caret_map=caret_map,
            ),
            projection_start=edited_run.projection_start + projection_prefix,
            projection_end=(
                edited_run.projection_start
                + len(previous_visible_text)
                - previous_suffix
            ),
            projection_replacement_text=next_visible_text[
                projection_prefix : len(next_visible_text) - next_suffix
                if next_suffix
                else len(next_visible_text)
            ],
        )


def _edit_is_inside_scene_title(
    token: PromptProjectionToken,
    *,
    start: int,
    end: int,
) -> bool:
    """Return whether one contiguous edit stays within scene-title boundaries."""

    return bool(
        token.kind is PromptProjectionTokenKind.SCENE
        and token.content_start is not None
        and token.content_end is not None
        and token.content_start <= start <= end <= token.source_end
    )


def _apply_scene_duplicate_styles(
    tokens: tuple[PromptProjectionToken, ...],
    *,
    scene_error_keys: frozenset[str],
) -> tuple[PromptProjectionToken, ...]:
    """Apply canonical first-seen duplicate and external scene-error styling."""

    seen_keys: set[str] = set()
    styled: list[PromptProjectionToken] = []
    for token in tokens:
        if token.kind is not PromptProjectionTokenKind.SCENE:
            styled.append(token)
            continue
        key = token.value_text or ""
        duplicate = key in seen_keys
        seen_keys.add(key)
        has_error = duplicate or key in scene_error_keys
        styled.append(
            replace(
                token,
                style_variant="scene_error" if has_error else "scene_title",
                exists=not has_error,
            )
        )
    return tuple(styled)


def _reconcile_scene_title_run(
    run: PromptProjectionRun,
    *,
    edited_run: PromptProjectionRun,
    projection_adjustment: int,
    tokens_by_id: dict[str, PromptProjectionToken],
    source_text: str,
) -> PromptProjectionRun:
    """Align a scene title run with its locally updated semantic token."""

    token = tokens_by_id.get(run.token_id or "")
    if run.run_id != edited_run.run_id:
        shifted_run = (
            run
            if run.projection_start < edited_run.projection_end
            else replace(
                run,
                projection_start=run.projection_start + projection_adjustment,
                projection_end=run.projection_end + projection_adjustment,
            )
        )
        if token is None or token.kind is not PromptProjectionTokenKind.SCENE:
            return shifted_run
        return replace(shifted_run, text_style_variant=token.style_variant)
    if token is None or token.kind is not PromptProjectionTokenKind.SCENE:
        return run
    return reconcile_scene_title_projection_run(
        run,
        token=token,
        source_text=source_text,
    )


def _single_text_edit_boundaries(
    previous_text: str,
    next_text: str,
) -> tuple[int, int, int]:
    """Return common prefix and previous/next suffix lengths for one text edit."""

    prefix = 0
    common_length = min(len(previous_text), len(next_text))
    while prefix < common_length and previous_text[prefix] == next_text[prefix]:
        prefix += 1
    previous_suffix = 0
    next_suffix = 0
    while (
        len(previous_text) - previous_suffix > prefix
        and len(next_text) - next_suffix > prefix
        and previous_text[len(previous_text) - previous_suffix - 1]
        == next_text[len(next_text) - next_suffix - 1]
    ):
        previous_suffix += 1
        next_suffix += 1
    return prefix, previous_suffix, next_suffix


__all__ = [
    "PromptSceneProjectionIncrementalEditor",
    "PromptSceneProjectionIncrementalResult",
]
