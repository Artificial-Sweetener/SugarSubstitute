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

"""Verify Output QPane display adaptation at composition boundaries."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from substitute.presentation.canvas.qpane.output_pane_adapter import (
    OutputQPaneRouteAdapter,
)


class _ComparisonPane:
    """Model QPane's composition-specific comparison-clear contract."""

    def __init__(self, *, composition_kind: str) -> None:
        """Create one active composition of the requested kind."""

        self.composition_id = uuid4()
        self.composition_kind = composition_kind
        self.clear_call_count = 0

    def currentCompositionID(self) -> UUID:  # noqa: N802
        """Return the active composition identifier."""

        return self.composition_id

    def getCompositionSnapshot(self) -> object:  # noqa: N802
        """Return the active public composition record."""

        return SimpleNamespace(
            current_composition_id=self.composition_id,
            compositions={
                self.composition_id: SimpleNamespace(kind=self.composition_kind)
            },
        )

    def clearComparisonImage(self) -> None:  # noqa: N802
        """Clear supported image compositions and reject layered scenes."""

        self.clear_call_count += 1
        if self.composition_kind == "layered-scene":
            raise RuntimeError("comparison images require an image composition")


def test_clear_comparison_treats_layered_scene_as_already_clear() -> None:
    """Avoid QPane's unsupported comparison command for layered scenes."""

    pane = _ComparisonPane(composition_kind="layered-scene")
    adapter = OutputQPaneRouteAdapter(pane)

    cleared = adapter.clear_comparison_image()

    assert cleared is True
    assert pane.clear_call_count == 0


def test_clear_comparison_delegates_for_image_composition() -> None:
    """Preserve QPane comparison clearing for image compositions."""

    pane = _ComparisonPane(composition_kind="default-image")
    adapter = OutputQPaneRouteAdapter(pane)

    cleared = adapter.clear_comparison_image()

    assert cleared is True
    assert pane.clear_call_count == 1
