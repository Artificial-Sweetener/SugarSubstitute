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

"""Contract tests for speculative prompt projection incremental edits."""

from __future__ import annotations

from collections.abc import Sequence
from typing import overload


from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.document.views import (
    PromptRegionStructureView,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.projection.builder import (
    PromptProjectionBuilder,
)
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretMap,
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
    PromptProjectionCaretStop,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.mapping import (
    PromptProjectionMapping,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
    PromptProjectionRunKind,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)


def _scene_projection_document(text: str) -> PromptProjectionDocument:
    """Build canonical scene projection state for incremental edit tests."""

    return PromptProjectionBuilder().build_projection(
        PromptDocumentService().build_document_view(text),
        PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
    )


def _plain_text_projection_document(
    text: str,
    *,
    stops: Sequence[PromptProjectionCaretStop] | None = None,
) -> PromptProjectionDocument:
    """Return a simple projected document containing one source-backed text run."""

    run = PromptProjectionRun(
        run_id="run-1",
        kind=PromptProjectionRunKind.TEXT,
        source_start=0,
        source_end=len(text),
        display_text=text,
        source_positions=range(0, len(text) + 1),
        projection_start=0,
        projection_end=len(text),
    )
    return _plain_text_projection_document_with_run(text, run=run, stops=stops)


def _plain_text_projection_document_with_run(
    text: str,
    *,
    run: PromptProjectionRun,
    stops: Sequence[PromptProjectionCaretStop] | None = None,
) -> PromptProjectionDocument:
    """Return a projected document for one supplied text run."""

    caret_stops = stops
    if caret_stops is None:
        caret_stops = tuple(_plain_text_caret_stops(text, run_id=run.run_id))
    return PromptProjectionDocument(
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        source_text=text,
        projection_text=text,
        runs=(run,),
        tokens=(),
        mapping=PromptProjectionMapping(
            runs=(run,),
            source_length=len(text),
            projection_length=len(text),
        ),
        caret_map=PromptProjectionCaretMap(
            stops=caret_stops,
            tokens=(),
            source_length=len(text),
            projection_length=len(text),
        ),
        region_structure=PromptRegionStructureView.empty(len(text)),
    )


def _plain_text_caret_stops(
    text: str,
    *,
    run_id: str,
) -> tuple[PromptProjectionCaretStop, ...]:
    """Return plain text caret stops for each source boundary."""

    return tuple(
        PromptProjectionCaretStop(
            visual_index=index,
            projection_position=index,
            state=PromptProjectionCaretState(
                source_position=index,
                placement=PromptProjectionCaretPlacement.PLAIN_TEXT,
                run_id=run_id,
            ),
        )
        for index in range(len(text) + 1)
    )


class _CountingCaretStopSequence(Sequence[PromptProjectionCaretStop]):
    """Count item access while providing optimized projection membership."""

    def __init__(self, stops: tuple[PromptProjectionCaretStop, ...]) -> None:
        """Store base stops and precompute cheap membership."""

        self._stops = stops
        self._projection_positions = frozenset(
            stop.projection_position for stop in stops
        )
        self._projection_position_by_state = {
            stop.state: stop.projection_position for stop in stops
        }
        self._first_state_by_projection_position: dict[
            int,
            PromptProjectionCaretState,
        ] = {}
        self._last_state_by_projection_position: dict[
            int,
            PromptProjectionCaretState,
        ] = {}
        self._first_state_by_source_position: dict[int, PromptProjectionCaretState] = {}
        self._last_state_by_source_position: dict[int, PromptProjectionCaretState] = {}
        for stop in stops:
            self._first_state_by_projection_position.setdefault(
                stop.projection_position,
                stop.state,
            )
            self._last_state_by_projection_position[stop.projection_position] = (
                stop.state
            )
            self._first_state_by_source_position.setdefault(
                stop.state.source_position,
                stop.state,
            )
            self._last_state_by_source_position[stop.state.source_position] = stop.state
        self.item_access_count = 0

    def __len__(self) -> int:
        """Return the base stop count."""

        return len(self._stops)

    @overload
    def __getitem__(self, index: int) -> PromptProjectionCaretStop: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[PromptProjectionCaretStop, ...]: ...

    def __getitem__(
        self,
        index: int | slice,
    ) -> PromptProjectionCaretStop | tuple[PromptProjectionCaretStop, ...]:
        """Return base stops while counting materializing access."""

        self.item_access_count += 1
        return self._stops[index]

    def has_projection_position(self, projection_position: int) -> bool:
        """Return membership without item access."""

        return projection_position in self._projection_positions

    def projection_position_for_state(
        self,
        state: PromptProjectionCaretState,
    ) -> int | None:
        """Return a state projection boundary without item access."""

        return self._projection_position_by_state.get(state)

    def index_for_state(
        self,
        state: PromptProjectionCaretState,
    ) -> int | None:
        """Return visual index for a state without item access."""

        projection_position = self.projection_position_for_state(state)
        return projection_position

    def state_for_projection_position(
        self,
        projection_position: int,
        *,
        prefer_after: bool = False,
    ) -> PromptProjectionCaretState | None:
        """Return a projection-position state without item access."""

        if prefer_after:
            return self._last_state_by_projection_position.get(projection_position)
        return self._first_state_by_projection_position.get(projection_position)

    def state_for_source_position(
        self,
        source_position: int,
        *,
        prefer_after: bool = False,
    ) -> PromptProjectionCaretState | None:
        """Return a source-position state without item access."""

        if prefer_after:
            return self._last_state_by_source_position.get(source_position)
        return self._first_state_by_source_position.get(source_position)

    def resolve_state(
        self,
        state: PromptProjectionCaretState,
    ) -> PromptProjectionCaretState | None:
        """Resolve a caret state without item access."""

        if state in self._projection_position_by_state:
            return state
        return self.state_for_source_position(
            state.source_position,
            prefer_after=state.placement
            is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE,
        )

    def reset_counts(self) -> None:
        """Reset materialization counters."""

        self.item_access_count = 0
