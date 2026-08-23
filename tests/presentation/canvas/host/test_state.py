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

"""Verify authoritative canvas host state independently from Qt selectors."""

from __future__ import annotations

from collections.abc import Generator
from typing import Protocol, cast

from PySide6.QtWidgets import QApplication, QWidget
import pytest
from sugarsubstitute_shared.presentation.localization import app_text

from substitute.presentation.canvas.host.canvas_host_state import (
    CanvasHostEntry,
    CanvasHostPage,
    CanvasHostState,
)
from substitute.presentation.canvas.host.floating_canvas_window import (
    FloatingCanvasWindow,
)


class CanvasEntryFactory(Protocol):
    """Build a canvas-host entry with an optional availability state."""

    def __call__(self, route_key: str, available: bool = True) -> CanvasHostEntry:
        """Return an entry for the requested durable canvas route."""


@pytest.fixture
def entry_owner(
    qt_application_owner: QApplication,
) -> Generator[CanvasEntryFactory, None, None]:
    """Create and release the widgets owned by canvas-state test entries."""

    _ = qt_application_owner
    widgets: list[QWidget] = []

    def create(route_key: str, available: bool = True) -> CanvasHostEntry:
        """Build one small state entry for a durable canvas route."""

        canvas = QWidget()
        wrapper = QWidget()
        widgets.extend((canvas, wrapper))
        return CanvasHostEntry(
            page=CanvasHostPage(route_key, app_text(route_key), canvas),
            wrapper=wrapper,
            available=available,
        )

    yield create

    for widget in widgets:
        widget.deleteLater()


def test_state_rejects_duplicate_canvas_routes(
    entry_owner: CanvasEntryFactory,
) -> None:
    """Each canvas concept must have exactly one authoritative entry."""

    with pytest.raises(ValueError, match="Duplicate canvas route key: Input"):
        CanvasHostState((entry_owner("Input"), entry_owner("Input")))


def test_state_preserves_order_and_selects_first_available_canvas(
    entry_owner: CanvasEntryFactory,
) -> None:
    """Durable page order should drive selector order and initial selection."""

    state = CanvasHostState(
        (entry_owner("Input", False), entry_owner("Output"), entry_owner("Document"))
    )

    assert tuple(entry.route_key for entry in state) == (
        "Input",
        "Output",
        "Document",
    )
    assert tuple(entry.route_key for entry in state.selectable_entries()) == (
        "Output",
        "Document",
    )
    assert state.active_route_key == "Output"


def test_unavailable_active_canvas_uses_configured_fallback(
    entry_owner: CanvasEntryFactory,
) -> None:
    """Availability changes should keep one valid docked selection."""

    state = CanvasHostState((entry_owner("Input"), entry_owner("Output")))

    state.set_available("Input", False, fallback_route_key="Output")

    assert state.active_route_key == "Output"
    assert tuple(entry.route_key for entry in state.selectable_entries()) == ("Output",)


def test_detach_moves_selection_without_reordering_entries(
    entry_owner: CanvasEntryFactory,
) -> None:
    """Detaching the active canvas should select the next durable entry."""

    input_entry = entry_owner("Input")
    output_entry = entry_owner("Output")
    state = CanvasHostState((input_entry, output_entry))

    assert state.prepare_detach("Input")
    state.complete_detach("Input", cast(FloatingCanvasWindow, object()))

    assert state.active_route_key == "Output"
    assert state.insertion_index("Output") == 0
    assert tuple(entry.route_key for entry in state) == ("Input", "Output")


def test_redock_restores_durable_position_and_activates_available_canvas(
    entry_owner: CanvasEntryFactory,
) -> None:
    """A redocked canvas should return to its original selector and stack order."""

    input_entry = entry_owner("Input")
    output_entry = entry_owner("Output")
    state = CanvasHostState((input_entry, output_entry))
    state.prepare_detach("Input")
    state.complete_detach("Input", cast(FloatingCanvasWindow, object()))

    assert state.complete_attach("Input")
    assert state.active_route_key == "Input"
    assert state.insertion_index("Input") == 0
    assert state.insertion_index("Output") == 1


def test_release_floating_window_clears_only_the_exact_owner(
    entry_owner: CanvasEntryFactory,
) -> None:
    """Teardown cleanup must not release a newer replacement window by route alone."""

    state = CanvasHostState((entry_owner("Input"), entry_owner("Output")))
    first = cast(FloatingCanvasWindow, object())
    replacement = cast(FloatingCanvasWindow, object())
    state.prepare_detach("Input")
    state.complete_detach("Input", first)

    assert not state.release_floating_window("Input", replacement)
    assert state.require_entry("Input").floating_window is first
    assert state.release_floating_window("Input", first)
    assert state.require_entry("Input").floating_window is None
