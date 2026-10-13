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

"""Refresh retained numeric controls when their owning surface becomes visible."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from PySide6.QtCore import QEvent, QObject, QSignalBlocker

from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.editor.panel.numeric_field_reveal_projection")


class NumericFieldRevealProjection(QObject):
    """Project current numeric authority without emitting an editing command.

    Hidden node fields remain mounted while global overrides update their
    backing values. Tie projection to the control's visibility lifecycle so
    revealing a cached row cannot expose its pre-override value. The widget
    owns this filter's lifetime, and the supplied reader resolves current state
    rather than retaining a superseded workflow projection.
    """

    def __init__(
        self,
        widget: QObject,
        *,
        read_value: Callable[[], object],
        current_value: Callable[[], object],
        set_value: Callable[[object], None],
    ) -> None:
        """Attach a widget-owned reveal projection to an existing numeric binding."""

        super().__init__(widget)
        self._read_value = read_value
        self._current_value = current_value
        self._set_value = set_value
        widget.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Refresh on reveal while leaving event delivery and user state intact."""

        if event.type() == QEvent.Type.Show:
            value = self._read_value()
            if value is not None and value != self._current_value():
                blocker = QSignalBlocker(watched)
                try:
                    self._set_value(value)
                except (TypeError, ValueError) as error:
                    metadata = watched.property("input_metadata")
                    fields = metadata if isinstance(metadata, Mapping) else {}
                    log_warning(
                        _LOGGER,
                        "Could not project current numeric value on reveal",
                        widget_type=watched.__class__.__name__,
                        cube_alias=fields.get("cube_alias"),
                        node_name=fields.get("node_name"),
                        field_key=fields.get("key"),
                        error_type=type(error).__name__,
                    )
                finally:
                    del blocker
        return False
