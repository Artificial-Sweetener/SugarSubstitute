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

"""Provide shared Qt fixtures for projection-engine prompt-editor tests."""

from __future__ import annotations

from typing import Any, cast


from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptTokenWeightControls,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)
from substitute.presentation.editor.prompt_editor.projection.paint_state import (
    PromptProjectionPaintState,
)
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
    prompt_syntax_profile,
)
from tests.support.execution.runtime_support import (
    immediate_prompt_task_executor_factory,
)
from tests.support.qt.semantic_wait import (
    wait_for_qt_condition,
    wait_for_queued_qt_turn,
)


def wait_for_caret_geometry(
    box: PromptEditor,
    surface: PromptProjectionSurface,
    *,
    position: int,
    expected_x: float,
    expected_y: float,
    tolerance: float = 1.0,
) -> None:
    """Wait until source position and rendered caret geometry agree."""

    def caret_matches() -> bool:
        """Return whether the live caret matches the expected source geometry."""

        actual = box.cursorRect()
        expected_viewport_y = expected_y - surface.verticalScrollBar().value()
        return (
            surface.cursor_position == position
            and abs(actual.x() - expected_x) <= tolerance
            and abs(actual.y() - expected_viewport_y) <= tolerance
        )

    def caret_state() -> object:
        """Describe the authoritative source and rendered caret state."""

        actual = box.cursorRect()
        lines = cast(Any, surface)._layout.frame.output.snapshot.lines
        document = surface.projection_document()
        return {
            "position": surface.cursor_position,
            "caret": (actual.x(), actual.y(), actual.width(), actual.height()),
            "expected_position": position,
            "expected_document_xy": (expected_x, expected_y),
            "expected_viewport_y": (expected_y - surface.verticalScrollBar().value()),
            "text": box.toPlainText(),
            "pending_projection": surface.has_pending_projection_update(),
            "stale_geometry": surface.has_stale_projection_geometry(),
            "scroll_offset": surface.verticalScrollBar().value(),
            "lines": tuple(
                {
                    "source": (line.source_start, line.source_end),
                    "content": (line.source_content_start, line.source_content_end),
                    "geometry": (line.top, line.height),
                    "stops": tuple(
                        (stop.projection_position, stop.rect.x(), stop.rect.y())
                        for stop in line.caret_stops
                    ),
                }
                for line in lines
            ),
            "caret_stops": tuple(
                (
                    stop.projection_position,
                    stop.state.source_position,
                    stop.state.run_id,
                )
                for stop in document.caret_map.stops
            ),
            "runs": tuple(
                (run.run_id, run.source_start, run.source_end) for run in document.runs
            ),
        }

    wait_for_qt_condition(
        caret_matches,
        description="prompt caret geometry",
        state=caret_state,
    )


class StaticPromptWildcardCatalogGateway:
    """Return deterministic wildcard metadata rows for projection-engine tests."""

    def __init__(
        self,
        resolutions_by_reference: dict[
            tuple[str, str, str | None],
            PromptWildcardResolution,
        ],
    ) -> None:
        """Store deterministic wildcard rows keyed by identifier, form, and column."""

        self._resolutions_by_reference = dict(resolutions_by_reference)

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Return configured wildcard rows aligned with the requested order."""

        return tuple(
            self._resolutions_by_reference.get(
                (
                    reference.identifier,
                    reference.wildcard_form,
                    reference.csv_column,
                ),
                PromptWildcardResolution(
                    identifier=reference.identifier,
                    wildcard_form=reference.wildcard_form,
                    csv_column=reference.csv_column,
                    exists=False,
                ),
            )
            for reference in references
        )

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no wildcard autocomplete suggestions."""

        _ = (prefix, limit)
        return ()


def ensure_qapp() -> QApplication:
    """Return a running Qt application for prompt projection tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def process_events(app: QApplication) -> None:
    """Deliver callbacks queued by the immediately preceding controlled action."""

    wait_for_queued_qt_turn()


def show_prompt_editor(
    widgets: list[QWidget],
    *,
    text: str,
    width: int,
    wildcard_gateway: StaticPromptWildcardCatalogGateway | None = None,
    height: int = 340,
    syntaxes: tuple[str, ...] = ("emphasis", "wildcard"),
) -> PromptEditor:
    """Create, show, and populate one prompt editor using the projection engine."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(max(240, width + 48), height)
    gateway = (
        wildcard_gateway
        if wildcard_gateway is not None
        else StaticPromptWildcardCatalogGateway({})
    )
    box = PromptEditor(
        host,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=gateway,
        prompt_syntax_profile=prompt_syntax_profile(*syntaxes),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    box.setGeometry(20, 20, width, box.minimumEditorHeight())
    host.show()
    host.activateWindow()
    box.show()
    box.setFocus()
    box.setPlainText(text)
    process_events(app)
    widgets.extend([host, box])
    return box


def surface_for(box: PromptEditor) -> PromptProjectionSurface:
    """Return the live projection surface owned by one prompt editor."""

    return cast(PromptProjectionSurface, getattr(box, "_surface"))


def set_prompt_cursor_position(box: PromptEditor, position: int) -> None:
    """Move one prompt editor cursor to an exact raw source boundary."""

    cursor = box.textCursor()
    cursor.setPosition(position, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)


def projection_paint_state_for(box: PromptEditor) -> PromptProjectionPaintState:
    """Return geometry-neutral visual state from the projection layout owner."""

    return surface_for(box)._layout.frame.paint_state  # noqa: SLF001


def token_weight_controls_for(box: PromptEditor) -> PromptTokenWeightControls:
    """Return the live non-clipping token weight controls owned by one prompt editor."""

    return cast(
        PromptTokenWeightControls,
        getattr(box, "_token_weight_control_overlay"),
    )
