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

from substitute.application.prompt_editor.document.visible_source import (
    map_prompt_source_for_display,
)
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
        """Interleave text and semantic tokens in source nesting order."""

        return _ProjectedRunStream(self, source_text, collapse_candidates).build()

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
        visible = map_prompt_source_for_display(
            source_text[start:end],
            source_start=start,
        )
        return PromptProjectionRun(
            run_id=f"text:{run_index}:{start}",
            kind=PromptProjectionRunKind.TEXT,
            source_start=start,
            source_end=end,
            display_text=visible.display_text,
            source_positions=visible.source_positions,
            projection_start=projection_position,
            projection_end=projection_position + len(visible.display_text),
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
            return _emphasis_runs(
                token,
                source_text=source_text,
                projection_position=projection_position,
            )
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
    source_text: str,
    projection_position: int,
) -> tuple[PromptProjectionRun, ...]:
    """Build decoration and text runs for one emphasis token."""

    assert token.content_start is not None
    assert token.content_end is not None
    visible = map_prompt_source_for_display(
        source_text[token.content_start : token.content_end],
        source_start=token.content_start,
    )
    if token.display_text != visible.display_text:
        raise ValueError("Emphasis token and visible source mapping disagree.")
    prefix_run = _emphasis_prefix_run(token, projection_position)
    content_run = PromptProjectionRun(
        run_id=f"emphasis-content:{token.token_id}",
        kind=PromptProjectionRunKind.TEXT,
        source_start=token.content_start,
        source_end=token.content_end,
        display_text=visible.display_text,
        source_positions=visible.source_positions,
        projection_start=prefix_run.projection_end,
        projection_end=prefix_run.projection_end + len(visible.display_text),
        token_id=token.token_id,
        active=token.active,
    )
    suffix_run = _emphasis_suffix_run(token, content_run.projection_end)
    return (prefix_run, content_run, suffix_run)


def _emphasis_prefix_run(
    token: PromptProjectionToken, projection_position: int
) -> PromptProjectionRun:
    """Build the leading decoration for one weighted source shell."""

    assert token.content_start is not None
    return PromptProjectionRun(
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


def _emphasis_suffix_run(
    token: PromptProjectionToken, projection_position: int
) -> PromptProjectionRun:
    """Build the trailing weighted decoration for one source shell."""

    assert token.content_end is not None
    return PromptProjectionRun(
        run_id=f"emphasis-suffix:{token.token_id}",
        kind=PromptProjectionRunKind.INLINE_OBJECT,
        source_start=token.content_end,
        source_end=token.source_end,
        display_text=token.value_text or "",
        source_positions=(token.content_end, token.source_end),
        projection_start=projection_position,
        projection_end=projection_position + 1,
        token_id=token.token_id,
        renderer_key=_EMPHASIS_SUFFIX_RENDERER_KEY,
        role=PromptProjectionRunRole.TOKEN_TRAILING_DECORATION,
        active=token.active,
    )


class _ProjectedRunStream:
    """Emit one flat run sequence while retaining nested emphasis decorations."""

    def __init__(
        self,
        builder: PromptProjectionRunBuilder,
        source_text: str,
        candidates: tuple[PromptProjectionCollapseCandidate, ...],
    ) -> None:
        """Store the ordered candidates and current stream positions."""

        self._builder = builder
        self._source_text = source_text
        self._candidates = candidates
        self._runs: list[PromptProjectionRun] = []
        self._projection_position = 0

    def build(self) -> tuple[PromptProjectionRun, ...]:
        """Emit each nested shell in one bounded pass without recursion."""

        source_position = 0
        open_shells: list[PromptProjectionToken] = []
        for index, candidate in enumerate(self._candidates):
            while (
                open_shells
                and open_shells[-1].content_end is not None
                and candidate.start >= open_shells[-1].content_end
            ):
                source_position = self._close_shell(open_shells.pop(), source_position)
            range_end = (
                open_shells[-1].content_end if open_shells else len(self._source_text)
            )
            assert range_end is not None
            if candidate.start < source_position or candidate.end > range_end:
                raise ValueError(
                    "Projection candidates have crossing source ranges: "
                    f"candidate={candidate.token.token_id} "
                    f"range=({candidate.start}, {candidate.end}) "
                    f"source_position={source_position} range_end={range_end} "
                    f"open_shells={[token.token_id for token in open_shells]}"
                )
            self._append_plain(source_position, candidate.start)
            token = candidate.token
            if token.kind is PromptProjectionTokenKind.EMPHASIS and self._has_child(
                index, token
            ):
                assert token.content_start is not None
                self._append_run(_emphasis_prefix_run(token, self._projection_position))
                open_shells.append(token)
                source_position = token.content_start
                continue
            for run in self._builder._projected_token_runs(
                token,
                source_text=self._source_text,
                projection_position=self._projection_position,
            ):
                self._append_run(run)
            source_position = candidate.end
        while open_shells:
            source_position = self._close_shell(open_shells.pop(), source_position)
        self._append_plain(source_position, len(self._source_text))
        return tuple(self._runs)

    def _has_child(self, index: int, token: PromptProjectionToken) -> bool:
        """Return whether the following candidate belongs inside this shell."""

        if index + 1 >= len(self._candidates):
            return False
        assert token.content_start is not None
        assert token.content_end is not None
        child = self._candidates[index + 1]
        return token.content_start <= child.start and child.end <= token.content_end

    def _close_shell(self, token: PromptProjectionToken, source_position: int) -> int:
        """Complete one nested content range and emit its trailing decoration."""

        assert token.content_end is not None
        self._append_plain(source_position, token.content_end)
        self._append_run(_emphasis_suffix_run(token, self._projection_position))
        return token.source_end

    def _append_plain(self, start: int, end: int) -> None:
        """Emit an undecorated source-backed text interval when nonempty."""

        run = self._builder._plain_text_run(
            self._source_text,
            start=start,
            end=end,
            run_index=len(self._runs),
            projection_position=self._projection_position,
        )
        if run is not None:
            self._append_run(run)

    def _append_run(self, run: PromptProjectionRun) -> None:
        """Advance the stream after one contiguous projected run."""

        if run.projection_start != self._projection_position:
            raise ValueError("Projection run boundaries are not contiguous.")
        self._runs.append(run)
        self._projection_position = run.projection_end


__all__ = ["PromptProjectionRunBuilder"]
