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

"""Own stable button layout and active-indicator projection for a tool strip."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QFrame, QVBoxLayout

from .model import CanvasToolPresentation
from .tool_button import CANVAS_TOOL_BUTTON_SIZE, CanvasToolButton
from .tool_strip_indicator import CanvasToolStripIndicator

_STRIP_BORDER_WIDTH = 1
_STRIP_INNER_MARGIN = 2
_STRIP_SPACING = 2
_SECTION_GAP = 5
_StructureSignature = tuple[tuple[str, str, str], ...]


class CanvasToolStripProjection:
    """Keep qfluent buttons stable while palette state and catalogs change."""

    def __init__(
        self,
        *,
        strip: QFrame,
        request_tool: Callable[[str], None],
    ) -> None:
        """Create the owned layout, button catalog, and selection indicator."""

        self._strip = strip
        self._request_tool = request_tool
        self._layout = QVBoxLayout(strip)
        self._layout.setContentsMargins(
            _STRIP_INNER_MARGIN,
            _STRIP_INNER_MARGIN,
            _STRIP_INNER_MARGIN,
            _STRIP_INNER_MARGIN,
        )
        self._layout.setSpacing(_STRIP_SPACING)
        self._buttons: dict[str, CanvasToolButton] = {}
        self._structure_signature: _StructureSignature = ()
        self._active_tool_id: str | None = None
        self.indicator = CanvasToolStripIndicator(strip)

    def button_for(self, tool_id: str) -> CanvasToolButton | None:
        """Return one current qfluent button by stable tool identity."""

        return self._buttons.get(tool_id)

    def tool_buttons(self) -> tuple[CanvasToolButton, ...]:
        """Return current qfluent buttons in palette order."""

        return tuple(self._buttons.values())

    def requires_structure(
        self,
        presentations: tuple[CanvasToolPresentation, ...],
    ) -> bool:
        """Return whether a snapshot requires button widget replacement."""

        return self._signature(presentations) != self._structure_signature

    def apply(
        self,
        presentations: tuple[CanvasToolPresentation, ...],
        *,
        animate_selection: bool,
    ) -> None:
        """Update stable buttons or rebuild only for a catalog structure change."""

        if self.requires_structure(presentations):
            self._rebuild_structure(presentations)
            animate_selection = False
        else:
            for presentation in presentations:
                button = self._buttons.get(presentation.tool_id)
                if button is not None:
                    button.apply_presentation(presentation)
        self._sync_indicator(presentations, animated=animate_selection)
        self._strip.raise_()

    def sync_geometry(self) -> None:
        """Realign the marker after Qt finalizes strip layout or geometry."""

        self._layout.activate()
        self.indicator.sync_geometry()
        self._realign_indicator()

    def _rebuild_structure(
        self,
        presentations: tuple[CanvasToolPresentation, ...],
    ) -> None:
        """Replace buttons for an actual runtime catalog structure change."""

        self._strip.setUpdatesEnabled(False)
        try:
            self._clear_layout()
            previous_section: str | None = None
            section_gap_count = 0
            for presentation in presentations:
                if (
                    previous_section is not None
                    and presentation.section != previous_section
                ):
                    self._layout.addSpacing(_SECTION_GAP)
                    section_gap_count += 1
                button = CanvasToolButton(presentation, self._strip)
                button.clicked.connect(
                    lambda _checked=False, tool_id=presentation.tool_id: (
                        self._request_tool(tool_id)
                    )
                )
                self._buttons[presentation.tool_id] = button
                self._layout.addWidget(button)
                previous_section = presentation.section
            self._structure_signature = self._signature(presentations)
            self._layout.invalidate()
            self._layout.activate()
            self._strip.setFixedSize(
                self._content_size(
                    button_count=len(presentations),
                    section_gap_count=section_gap_count,
                )
            )
            self._strip.setVisible(bool(presentations))
        finally:
            self._strip.setUpdatesEnabled(True)
        self.indicator.sync_geometry()
        self._strip.update()

    def _sync_indicator(
        self,
        presentations: tuple[CanvasToolPresentation, ...],
        *,
        animated: bool,
    ) -> None:
        """Move the marker to the authoritative active mode without rebuilding."""

        active = next(
            (presentation for presentation in presentations if presentation.active),
            None,
        )
        previous_active = self._active_tool_id
        self._active_tool_id = None if active is None else active.tool_id
        if active is None:
            self.indicator.clear()
            return
        button = self._buttons.get(active.tool_id)
        if button is None:
            self.indicator.clear()
            return
        self.indicator.move_to(
            button,
            animated=(
                animated
                and previous_active is not None
                and previous_active != active.tool_id
            ),
        )

    def _realign_indicator(self) -> None:
        """Realign the active marker after Qt finalizes hidden-strip layout."""

        if self._active_tool_id is None:
            self.indicator.clear()
            return
        button = self._buttons.get(self._active_tool_id)
        if button is None:
            self.indicator.clear()
            return
        self.indicator.move_to(button, animated=False)

    def _clear_layout(self) -> None:
        """Remove prior structural widgets without retaining stale identities."""

        self.indicator.clear()
        while (item := self._layout.takeAt(0)) is not None:
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._buttons.clear()
        self._active_tool_id = None

    @staticmethod
    def _signature(
        presentations: tuple[CanvasToolPresentation, ...],
    ) -> _StructureSignature:
        """Return the runtime structure that requires widget replacement."""

        return tuple(
            (
                presentation.tool_id,
                presentation.kind.value,
                presentation.section,
            )
            for presentation in presentations
        )

    @staticmethod
    def _content_size(*, button_count: int, section_gap_count: int) -> QSize:
        """Calculate stable content geometry independently of reentrant Qt layout."""

        if button_count == 0:
            empty_extent = 2 * (_STRIP_BORDER_WIDTH + _STRIP_INNER_MARGIN)
            return QSize(empty_extent, empty_extent)
        chrome_extent = 2 * (_STRIP_BORDER_WIDTH + _STRIP_INNER_MARGIN)
        width = CANVAS_TOOL_BUTTON_SIZE + chrome_extent
        height = (
            CANVAS_TOOL_BUTTON_SIZE * button_count
            + _STRIP_SPACING * (button_count - 1)
            + _SECTION_GAP * section_gap_count
            + chrome_extent
        )
        return QSize(width, height)


__all__ = ["CanvasToolStripProjection"]
