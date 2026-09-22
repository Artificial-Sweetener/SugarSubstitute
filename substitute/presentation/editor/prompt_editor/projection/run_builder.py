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

"""Build contiguous visible run streams from semantic collapse candidates."""

from __future__ import annotations

from collections.abc import Sequence

from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
    PromptProjectionRunKind,
    PromptProjectionRunRole,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.collapse_models import (
    PromptProjectionCollapseCandidate,
)
from substitute.presentation.editor.prompt_editor.projection.scene_title_projection import (
    build_scene_title_projection_run,
)

_EMPHASIS_PREFIX_RENDERER_KEY = "emphasis_prefix"
_EMPHASIS_SUFFIX_RENDERER_KEY = "emphasis_suffix"
_LORA_CHIP_RENDERER_KEY = "lora_chip"
_WILDCARD_CHIP_RENDERER_KEY = "wildcard_chip"


class PromptProjectionRunBuilder:
    """Own base text and semantic-token run construction."""

    def raw_runs(self, source_text: str) -> tuple[PromptProjectionRun, ...]:
        """Build the raw-mode run stream for exact stored source text."""

        if not source_text:
            return ()
        return (
            PromptProjectionRun(
                run_id="raw:0",
                kind=PromptProjectionRunKind.TEXT,
                source_start=0,
                source_end=len(source_text),
                display_text=source_text,
                source_positions=range(0, len(source_text) + 1),
                projection_start=0,
                projection_end=len(source_text),
            ),
        )

    def projected_runs(
        self,
        source_text: str,
        *,
        collapse_candidates: tuple[PromptProjectionCollapseCandidate, ...],
    ) -> tuple[PromptProjectionRun, ...]:
        """Interleave plain text with ordered semantic token runs."""

        collapse_by_start = {
            candidate.start: candidate for candidate in collapse_candidates
        }
        runs: list[PromptProjectionRun] = []
        run_index = 0
        projection_position = 0
        plain_start = 0
        source_index = 0
        for candidate in collapse_by_start.values():
            if candidate.start < source_index:
                continue
            plain_run = self._plain_text_run(
                source_text,
                start=plain_start,
                end=candidate.start,
                run_index=run_index,
                projection_position=projection_position,
            )
            if plain_run is not None:
                runs.append(plain_run)
                run_index += 1
                projection_position = plain_run.projection_end
            candidate_runs = self._projected_token_runs(
                candidate.token,
                source_text=source_text,
                projection_position=projection_position,
            )
            runs.extend(candidate_runs)
            if candidate_runs:
                run_index += len(candidate_runs)
                projection_position = candidate_runs[-1].projection_end
            source_index = candidate.end
            plain_start = source_index
        trailing_plain_run = self._plain_text_run(
            source_text,
            start=plain_start,
            end=len(source_text),
            run_index=run_index,
            projection_position=projection_position,
        )
        if trailing_plain_run is not None:
            runs.append(trailing_plain_run)
        return tuple(runs)

    def _plain_text_run(
        self,
        source_text: str,
        *,
        start: int,
        end: int,
        run_index: int,
        projection_position: int,
    ) -> PromptProjectionRun | None:
        """Build one visible plain-text run for a non-empty source range."""

        if end <= start:
            return None
        display_text, source_positions = _plain_run_text_and_source_positions(
            source_text[start:end],
            source_start=start,
        )
        return PromptProjectionRun(
            run_id=f"text:{run_index}:{start}",
            kind=PromptProjectionRunKind.TEXT,
            source_start=start,
            source_end=end,
            display_text=display_text,
            source_positions=source_positions,
            projection_start=projection_position,
            projection_end=projection_position + len(display_text),
        )

    def _projected_token_runs(
        self,
        token: PromptProjectionToken,
        *,
        source_text: str,
        projection_position: int,
    ) -> tuple[PromptProjectionRun, ...]:
        """Build visible runs for one semantic token."""

        if token.kind is PromptProjectionTokenKind.EMPHASIS:
            return _emphasis_runs(token, projection_position=projection_position)
        if token.kind is PromptProjectionTokenKind.SCENE:
            return (
                build_scene_title_projection_run(
                    token,
                    source_text=source_text,
                    projection_position=projection_position,
                ),
            )
        renderer_key = (
            _LORA_CHIP_RENDERER_KEY
            if token.kind is PromptProjectionTokenKind.LORA
            else _WILDCARD_CHIP_RENDERER_KEY
        )
        run_kind = (
            "lora-chip"
            if token.kind is PromptProjectionTokenKind.LORA
            else "wildcard-chip"
        )
        return (
            PromptProjectionRun(
                run_id=f"{run_kind}:{token.token_id}",
                kind=PromptProjectionRunKind.INLINE_OBJECT,
                source_start=token.source_start,
                source_end=token.source_end,
                display_text=token.display_text,
                source_positions=(token.source_start, token.source_end),
                projection_start=projection_position,
                projection_end=projection_position + 1,
                token_id=token.token_id,
                renderer_key=renderer_key,
                active=token.active,
            ),
        )


def _emphasis_runs(
    token: PromptProjectionToken,
    *,
    projection_position: int,
) -> tuple[PromptProjectionRun, ...]:
    """Build decoration and text runs for one emphasis token."""

    assert token.content_start is not None
    assert token.content_end is not None
    prefix_run = PromptProjectionRun(
        run_id=f"emphasis-prefix:{token.token_id}",
        kind=PromptProjectionRunKind.INLINE_OBJECT,
        source_start=token.source_start,
        source_end=token.content_start,
        display_text="(",
        source_positions=(token.source_start, token.content_start),
        projection_start=projection_position,
        projection_end=projection_position + 1,
        token_id=token.token_id,
        renderer_key=_EMPHASIS_PREFIX_RENDERER_KEY,
        role=PromptProjectionRunRole.TOKEN_LEADING_DECORATION,
        active=token.active,
    )
    content_run = PromptProjectionRun(
        run_id=f"emphasis-content:{token.token_id}",
        kind=PromptProjectionRunKind.TEXT,
        source_start=token.content_start,
        source_end=token.content_end,
        display_text=token.display_text,
        source_positions=tuple(range(token.content_start, token.content_end + 1)),
        projection_start=prefix_run.projection_end,
        projection_end=prefix_run.projection_end + len(token.display_text),
        token_id=token.token_id,
        active=token.active,
    )
    suffix_run = PromptProjectionRun(
        run_id=f"emphasis-suffix:{token.token_id}",
        kind=PromptProjectionRunKind.INLINE_OBJECT,
        source_start=token.content_end,
        source_end=token.source_end,
        display_text=token.value_text or "",
        source_positions=(token.content_end, token.source_end),
        projection_start=content_run.projection_end,
        projection_end=content_run.projection_end + 1,
        token_id=token.token_id,
        renderer_key=_EMPHASIS_SUFFIX_RENDERER_KEY,
        role=PromptProjectionRunRole.TOKEN_TRAILING_DECORATION,
        active=token.active,
    )
    return (prefix_run, content_run, suffix_run)


def _plain_run_text_and_source_positions(
    source_text: str,
    *,
    source_start: int,
) -> tuple[str, Sequence[int]]:
    """Return visible plain text and its exact source-boundary mapping."""

    if "\\(" not in source_text and "\\)" not in source_text:
        return source_text, range(source_start, source_start + len(source_text) + 1)
    display_characters: list[str] = []
    source_positions: list[int] = [source_start]
    relative_index = 0
    while relative_index < len(source_text):
        character = source_text[relative_index]
        if (
            character == "\\"
            and relative_index + 1 < len(source_text)
            and source_text[relative_index + 1] in "()"
        ):
            display_characters.append(source_text[relative_index + 1])
            relative_index += 2
            source_positions.append(source_start + relative_index)
            continue
        display_characters.append(character)
        relative_index += 1
        source_positions.append(source_start + relative_index)
    return "".join(display_characters), tuple(source_positions)


__all__ = ["PromptProjectionRunBuilder"]
