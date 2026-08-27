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

"""Provide a deterministic mounted PromptEditor sizing harness."""

# ruff: noqa: F401

from __future__ import annotations
import math
from collections.abc import Callable, Iterator
from typing import Any, cast
import pytest
from PySide6.QtCore import QPoint, QPointF, Qt, qInstallMessageHandler
from PySide6.QtGui import QTextCursor, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTextEdit, QVBoxLayout, QWidget
from qfluentwidgets import TextEdit as QFluentTextEdit  # type: ignore[import-untyped]
from qfluentwidgets.common.smooth_scroll import (  # type: ignore[import-untyped]
    SmoothMode,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.shell import (
    sizing_controller as sizing_controller_module,
)
from substitute.presentation.editor.prompt_editor.shell import (
    scroll_delegate as scroll_delegate_module,
)
from substitute.presentation.editor.panel.widgets.scroll_surface import (
    EditorPanelScrollSurface,
)
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)
from tests.support.execution import immediate_prompt_task_executor_factory
from tests.support.qt.lifecycle import destroy_widget_roots
from tests.support.qt import semantic_wait

__all__ = (
    "math",
    "Any",
    "Callable",
    "cast",
    "pytest",
    "QPoint",
    "QPointF",
    "Qt",
    "qInstallMessageHandler",
    "QTextCursor",
    "QWheelEvent",
    "QTest",
    "QApplication",
    "QTextEdit",
    "QVBoxLayout",
    "QWidget",
    "QFluentTextEdit",
    "SmoothMode",
    "PromptEditor",
    "EditorPanelScrollSurface",
    "EmptyPromptAutocompleteGateway",
    "EmptyPromptWildcardCatalogGateway",
    "prompt_syntax_profile",
    "immediate_prompt_task_executor_factory",
    "destroy_widget_roots",
    "semantic_wait",
    "sizing_controller_module",
    "scroll_delegate_module",
    "ensure_qapp",
    "process_events",
    "prompt_editors",
    "show_prompt_editor",
    "wait_for_prompt_sizing_idle",
    "height_padding",
    "default_scroll_height",
    "resize_handle_for",
    "set_manual_scroll_height",
    "fill_plane_for",
    "delay_projection_update_scheduler",
    "flush_projection_update_scheduler",
    "flush_semantic_refresh",
    "widget_has_ancestor",
    "ManualResizeScrollHost",
)


def ensure_qapp() -> QApplication:
    """Return a running Qt application for prompt-editor widget tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def process_events(app: QApplication) -> None:
    """Deliver callbacks queued by the immediately preceding controlled action."""

    semantic_wait.wait_for_queued_qt_turn()


@pytest.fixture()
def prompt_editors() -> Iterator[list[PromptEditor]]:
    """Track prompt editors created during one test and dispose them safely afterward."""

    boxes: list[PromptEditor] = []
    yield boxes
    app = ensure_qapp()
    for box in boxes:
        box.close()
        box.deleteLater()
    process_events(app)


def show_prompt_editor(
    prompt_editors: list[PromptEditor], *, text: str, width: int
) -> PromptEditor:
    """Create, size, and show one prompt editor for sizing assertions."""

    ensure_qapp()
    box = PromptEditor(
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    box.resize(width, 100)
    box.setPlainText(text)
    box.show()
    wait_for_prompt_sizing_idle(box)
    prompt_editors.append(box)
    return box


def wait_for_prompt_sizing_idle(box: PromptEditor) -> None:
    """Wait until projection, shell sizing, and host geometry have settled."""

    editor = cast(Any, box)
    sizing = editor._sizing
    scroll_delegate = editor._scroll_delegate
    surface = editor._surface
    semantic_wait.wait_for_qt_condition(
        lambda: (
            not surface.has_pending_projection_update()
            and not surface.has_stale_projection_geometry()
            and not sizing.layout_work_pending
            and not scroll_delegate.geometry_sync_pending
            and not scroll_delegate.geometry_follow_up_pending
        )
    )


def height_padding(box: PromptEditor) -> int:
    """Return the current prompt-editor height padding above its document height."""

    return box.minimumEditorHeight() - box.lineHeight()


def default_scroll_height(box: PromptEditor) -> int:
    """Return the default prompt-editor scroll-mode height."""

    return box.lineHeight() * 10 + height_padding(box)


def resize_handle_for(box: PromptEditor) -> QWidget:
    """Return the prompt editor's private resize handle for contract tests."""

    return cast(QWidget, getattr(box, "_resize_handle"))


def set_manual_scroll_height(box: PromptEditor, height: int) -> None:
    """Set the prompt editor's private manual scroll height for contract tests."""

    setter = cast(Any, getattr(box, "setManualScrollHeight"))
    setter(height)


def fill_plane_for(box: PromptEditor) -> QWidget:
    """Return the prompt editor's private fill plane."""

    return cast(QWidget, getattr(box, "_fill_plane"))


def delay_projection_update_scheduler(box: PromptEditor) -> None:
    """Keep safe-typing projection updates pending until a test flushes them."""

    surface = cast(Any, getattr(box, "_surface"))
    scheduler = surface._projection_freshness_controller.update_scheduler  # noqa: SLF001
    scheduler._fixed_interval_ms = 1000  # noqa: SLF001
    scheduler._interval_ms = 1000  # noqa: SLF001
    scheduler._timer.setInterval(1000)  # noqa: SLF001


def flush_projection_update_scheduler(box: PromptEditor) -> None:
    """Apply any delayed safe-typing projection update before test cleanup."""

    surface = cast(Any, getattr(box, "_surface"))
    surface._projection_freshness_controller.update_scheduler.flush_now(reason="test")  # noqa: SLF001


def flush_semantic_refresh(box: PromptEditor) -> None:
    """Apply queued semantic prompt state before projection scheduling assertions."""

    cast(Any, box)._interaction_controller.flush_pending_semantic_refresh(  # noqa: SLF001
        reason="test"
    )


def widget_has_ancestor(widget: QWidget, ancestor: QWidget) -> bool:
    """Return whether one widget is parented under another widget."""

    parent = widget.parentWidget()
    while parent is not None:
        if parent is ancestor:
            return True
        parent = parent.parentWidget()
    return False


class ManualResizeScrollHost(QWidget):
    """Host an editor scroll surface with the panel API PromptEditor discovers."""

    def __init__(self) -> None:
        """Create the scroll host expected by prompt-editor resize bounds."""

        super().__init__()
        self.scroll_surface = EditorPanelScrollSurface(self)
        setattr(self, "scroll", self.scroll_surface)

    def handle_external_wheel(self, event: QWheelEvent) -> None:
        """Accept bubbled wheel events in tests without changing scroll state."""

        event.ignore()
