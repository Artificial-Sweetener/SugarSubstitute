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

"""Own process-local Qt application access and deterministic object teardown."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from typing import Protocol, cast

from cutecanvas import CuteCanvas
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import delete, isValid


class _CanvasInteractionPort(Protocol):
    """Describe the external input lifecycle released before canvas deletion."""

    def shutdown(self) -> None:
        """Detach application-wide input observation for the canvas."""


def ensure_qt_application() -> QApplication:
    """Return the process QApplication, creating it when this worker has none."""

    application = QApplication.instance()
    if application is None:
        return QApplication([])
    if not isinstance(application, QApplication):
        raise RuntimeError("Qt tests require a QApplication event dispatcher.")
    return application


def destroy_qt_object(candidate: QObject) -> None:
    """Destroy one Qt owner synchronously and verify its native state is gone."""

    _shutdown_cute_canvas_interactions(candidate)
    delete(candidate)
    assert not isValid(candidate)


def _shutdown_cute_canvas_interactions(candidate: QObject) -> None:
    """Detach canvas-wide input hooks before any containing Qt owner is deleted."""

    canvases = tuple(candidate.findChildren(CuteCanvas))
    if isinstance(candidate, CuteCanvas):
        canvases = (candidate, *canvases)
    for canvas in canvases:
        interaction = cast(_CanvasInteractionPort, getattr(canvas, "interaction"))
        interaction.shutdown()


def destroy_widget_roots(candidates: Iterable[QWidget]) -> None:
    """Synchronously destroy each owned top-level widget exactly once."""

    widgets = tuple(candidates)
    owned_widget_ids = {id(widget) for widget in widgets}
    roots = tuple(
        widget
        for widget in widgets
        if widget.parentWidget() is None
        or id(widget.parentWidget()) not in owned_widget_ids
    )
    for widget in reversed(roots):
        if isValid(widget):
            widget.close()
            destroy_qt_object(widget)


@contextmanager
def widget_root_scope() -> Iterator[None]:
    """Destroy top-level widgets created within one test-owned Qt scope."""

    application = ensure_qt_application()
    existing_widget_ids = {id(widget) for widget in application.topLevelWidgets()}
    try:
        yield
    finally:
        created_roots = tuple(
            widget
            for widget in application.topLevelWidgets()
            if id(widget) not in existing_widget_ids and isinstance(widget, QWidget)
        )
        destroy_widget_roots(created_roots)


def activate_widget_layouts(*widgets: QWidget) -> None:
    """Resolve mounted widget geometry without draining unrelated Qt events."""

    for widget in widgets:
        widget.ensurePolished()
        layout = widget.layout()
        if layout is not None:
            layout.activate()


__all__ = [
    "activate_widget_layouts",
    "destroy_widget_roots",
    "destroy_qt_object",
    "ensure_qt_application",
    "widget_root_scope",
]
