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

"""Verify Output grid context commands and projection-wide comparison access."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from cutecanvas import CanvasContentKind, CanvasContentReference
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from substitute.presentation.canvas.output.output_grid_context_menu import (
    OutputGridContextMenu,
)
from substitute.presentation.resources.fluent_app_icon import AppIcon
from substitute.presentation.widgets.menu_model import MenuItem


def test_grid_menu_preserves_the_original_icon_assignments() -> None:
    """Keep addressed grid actions visually identical to their established actions."""

    actions = _actions(_grid_menu(compare_available=False))

    assert actions["output_canvas.copy"].icon is FIF.COPY
    assert actions["output_canvas.open_current_external"].icon is FIF.PHOTO
    assert (
        actions["output_canvas.reveal_current_asset"].icon
        is AppIcon.FOLDER_OPEN_20_REGULAR
    )
    assert actions["output_canvas.dock_action"].icon is FIF.FULL_SCREEN


def test_grid_menu_exposes_compare_for_a_comparable_projection() -> None:
    """Scene and source grids must retain the projection-wide Compare command."""

    compare_requests: list[bool] = []
    actions = _actions(
        _grid_menu(
            compare_available=True,
            set_compare_enabled=compare_requests.append,
        )
    )

    compare = actions["output_canvas.compare_outputs"]
    assert compare.checkable is True
    assert compare.checked is False
    assert compare.checked_callback is not None
    compare.checked_callback(True)
    assert compare_requests == [True]


def _grid_menu(
    *,
    compare_available: bool,
    set_compare_enabled: Callable[[bool], None] | None = None,
) -> OutputGridContextMenu:
    """Build one deterministic target-addressed Output menu."""

    return OutputGridContextMenu(
        parent=object(),  # type: ignore[arg-type]
        request_copy=lambda _reference: None,
        image_id_for_reference=lambda _reference: None,
        image_payload=lambda _image_id: None,
        image_metadata=lambda _image_id: None,
        image_is_authorized=lambda _image_id: False,
        open_single_editor=None,
        reveal_asset=None,
        compare_available=lambda: compare_available,
        compare_enabled=lambda: False,
        set_compare_enabled=set_compare_enabled or _ignore_compare_enabled,
        canvas_detached=lambda: False,
        request_dock_action=lambda: None,
    )


def _actions(menu: OutputGridContextMenu) -> dict[str, MenuItem]:
    """Return grid action items keyed by stable action identity."""

    reference = CanvasContentReference(
        document_id=uuid4(),
        kind=CanvasContentKind.COMPOSITION,
        composition_id=uuid4(),
    )
    return {
        entry.action_id: entry
        for entry in menu.menu_model(reference).entries
        if isinstance(entry, MenuItem)
    }


def _ignore_compare_enabled(_enabled: bool) -> None:
    """Accept an unused Compare toggle in tests without recording it."""
