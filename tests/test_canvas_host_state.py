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

from typing import cast

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


def _app() -> QApplication:
    """Return the application required to create page wrappers."""

    instance = QApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def _entry(route_key: str, *, available: bool = True) -> CanvasHostEntry:
    """Create a small state entry for one route."""

    _app()
    return CanvasHostEntry(
        page=CanvasHostPage(route_key, app_text(route_key), QWidget()),
        wrapper=QWidget(),
        available=available,
    )


def test_state_rejects_duplicate_canvas_routes() -> None:
    """Each canvas concept must have exactly one authoritative entry."""

    with pytest.raises(ValueError, match="Duplicate canvas route key: Input"):
        CanvasHostState((_entry("Input"), _entry("Input")))


def test_state_preserves_order_and_selects_first_available_canvas() -> None:
    """Durable page order should drive selector order and initial selection."""

    state = CanvasHostState(
        (_entry("Input", available=False), _entry("Output"), _entry("Document"))
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


def test_unavailable_active_canvas_uses_configured_fallback() -> None:
    """Availability changes should keep one valid docked selection."""

    state = CanvasHostState((_entry("Input"), _entry("Output")))

    state.set_available("Input", False, fallback_route_key="Output")

    assert state.active_route_key == "Output"
    assert tuple(entry.route_key for entry in state.selectable_entries()) == ("Output",)


def test_detach_moves_selection_without_reordering_entries() -> None:
    """Detaching the active canvas should select the next durable entry."""

    input_entry = _entry("Input")
    output_entry = _entry("Output")
    state = CanvasHostState((input_entry, output_entry))

    assert state.prepare_detach("Input")
    state.complete_detach("Input", cast(FloatingCanvasWindow, object()))

    assert state.active_route_key == "Output"
    assert state.insertion_index("Output") == 0
    assert tuple(entry.route_key for entry in state) == ("Input", "Output")


def test_redock_restores_durable_position_and_activates_available_canvas() -> None:
    """A redocked canvas should return to its original selector and stack order."""

    input_entry = _entry("Input")
    output_entry = _entry("Output")
    state = CanvasHostState((input_entry, output_entry))
    state.prepare_detach("Input")
    state.complete_detach("Input", cast(FloatingCanvasWindow, object()))

    assert state.complete_attach("Input")
    assert state.active_route_key == "Input"
    assert state.insertion_index("Input") == 0
    assert state.insertion_index("Output") == 1
