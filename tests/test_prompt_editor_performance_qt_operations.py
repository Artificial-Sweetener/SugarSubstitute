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

"""Tests for prompt editor performance Qt operation timings."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.prompt_editor import PromptSpellingDiagnosticPayload
from substitute.devtools.prompt_editor_performance.metrics import Instrumentation
from substitute.devtools.prompt_editor_performance.qt_operations import (
    QT_REORDER_ARROW_KEYS,
    operation_key,
    process_events,
    prompt_key_target,
    run_scenario_operations,
    send_prompt_alt_event,
    spelling_diagnostic_for_text,
    time_key_click,
    wait_for_current_reorder_overlay,
)
from substitute.devtools.prompt_editor_performance.scenarios import (
    Scenario,
    ScenarioOperation,
)
from substitute.presentation.editor.prompt_editor import PromptEditor


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QT_OPERATIONS_MODULE = (
    PROJECT_ROOT
    / "substitute"
    / "devtools"
    / "prompt_editor_performance"
    / "qt_operations.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "qfluentwidgets",
    "qframelesswindow",
    "tests",
    "tools",
)


class _EventApp:
    """Count processEvents calls for bounded event-flush coverage."""

    def __init__(self) -> None:
        """Initialize the event-flush counter."""

        self.process_event_count = 0

    def processEvents(self) -> None:
        """Record one event-loop flush."""

        self.process_event_count += 1


class _KeyEventRecorder(QWidget):
    """Record modifier events delivered through the benchmark focus route."""

    def __init__(self) -> None:
        """Initialize recorded key event tuples."""

        super().__init__()
        self.events: list[tuple[QEvent.Type, int, Qt.KeyboardModifier]] = []

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Record one Alt press."""

        self.events.append((event.type(), event.key(), event.modifiers()))

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Record one Alt release."""

        self.events.append((event.type(), event.key(), event.modifiers()))


def test_prompt_editor_performance_qt_operations_imports_no_tools() -> None:
    """Qt operations may use Qt and presentation, but not tests or tools."""

    imported_modules = _imported_module_names(
        ast.parse(QT_OPERATIONS_MODULE.read_text(encoding="utf-8"))
    )

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_operation_key_maps_supported_edit_operations() -> None:
    """Edit operation names should map to the intended Qt keys."""

    assert operation_key("backspace") == Qt.Key.Key_Backspace
    assert operation_key("delete") == Qt.Key.Key_Delete
    assert operation_key("enter") == Qt.Key.Key_Return
    assert QT_REORDER_ARROW_KEYS == {
        "left": Qt.Key.Key_Left,
        "right": Qt.Key.Key_Right,
        "up": Qt.Key.Key_Up,
        "down": Qt.Key.Key_Down,
    }


def test_operation_key_rejects_non_key_operation() -> None:
    """Unsupported key-operation routing should fail before touching Qt widgets."""

    with pytest.raises(ValueError, match="Unsupported key operation"):
        operation_key("type")


def test_time_key_click_requires_character_or_key() -> None:
    """Key timing should reject ambiguous calls before emitting Qt events."""

    with pytest.raises(ValueError, match="character or key"):
        time_key_click(
            cast(QApplication, object()),
            cast(PromptEditor, object()),
        )


def test_spelling_diagnostic_for_text_uses_misspelling_when_present() -> None:
    """Diagnostic cache measurement should target the deterministic word."""

    diagnostic = spelling_diagnostic_for_text("alpha mispelled beta")

    assert diagnostic.diagnostic_id == "spelling:6:15:mispelled"
    assert diagnostic.source_start == 6
    assert diagnostic.source_end == 15
    assert isinstance(diagnostic.payload, PromptSpellingDiagnosticPayload)
    assert diagnostic.payload.word == "mispelled"


def test_process_events_flushes_bounded_cycles() -> None:
    """Event flushing should perform the requested number of bounded cycles."""

    app = _EventApp()

    process_events(cast(QApplication, app), cycles=5)

    assert app.process_event_count == 5


def test_prompt_key_target_uses_the_production_focus_proxy() -> None:
    """Benchmark key events must follow the same focus route as user input."""

    app = QApplication.instance() or QApplication([])
    editor = QWidget()
    proxy = QWidget(editor)
    editor.setFocusProxy(proxy)

    assert prompt_key_target(cast(PromptEditor, editor)) is proxy
    editor.close()
    app.processEvents()


def test_prompt_alt_events_traverse_the_focus_widget_once() -> None:
    """Modifier setup must avoid QTest's platform-dependent standalone Alt path."""

    app = QApplication.instance() or QApplication([])
    target = _KeyEventRecorder()

    send_prompt_alt_event(target, QEvent.Type.KeyPress)
    send_prompt_alt_event(target, QEvent.Type.KeyRelease)

    assert target.events == [
        (
            QEvent.Type.KeyPress,
            int(Qt.Key.Key_Alt),
            Qt.KeyboardModifier.NoModifier,
        ),
        (
            QEvent.Type.KeyRelease,
            int(Qt.Key.Key_Alt),
            Qt.KeyboardModifier.AltModifier,
        ),
    ]
    target.close()
    app.processEvents()


def test_prompt_alt_event_rejects_non_key_event() -> None:
    """Modifier delivery must remain constrained to key press and release."""

    app = QApplication.instance() or QApplication([])
    target = QWidget()

    with pytest.raises(ValueError, match="key press or release"):
        send_prompt_alt_event(target, QEvent.Type.MouseMove)

    target.close()
    app.processEvents()


def test_reorder_overlay_waits_for_bounded_observable_event_turns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Overlay setup may cross queued turns without repeating the Alt input."""

    app = _EventApp()
    overlay = object()
    attempts = 0

    def fake_current_reorder_overlay(editor: PromptEditor) -> object:
        """Publish the overlay after two queued event turns."""

        nonlocal attempts
        _ = editor
        attempts += 1
        if attempts < 3:
            raise RuntimeError("not ready")
        return overlay

    monkeypatch.setattr(
        "substitute.devtools.prompt_editor_performance.qt_operations."
        "current_reorder_overlay",
        fake_current_reorder_overlay,
    )

    result = wait_for_current_reorder_overlay(
        cast(QApplication, app),
        cast(PromptEditor, object()),
    )

    assert result is overlay
    assert app.process_event_count == 2


def test_reorder_overlay_wait_rejects_unbounded_configuration() -> None:
    """Overlay setup must retain a positive bounded event-turn budget."""

    with pytest.raises(ValueError, match="must be positive"):
        wait_for_current_reorder_overlay(
            cast(QApplication, _EventApp()),
            cast(PromptEditor, object()),
            event_cycles=0,
        )


def test_run_scenario_operations_rejects_unsupported_operation() -> None:
    """Operation dispatch should fail closed for unknown scenario operations."""

    scenario = Scenario(
        "unsupported",
        "",
        operation=cast(ScenarioOperation, "unsupported"),
    )

    with pytest.raises(ValueError, match="Unsupported performance operation"):
        run_scenario_operations(
            app=cast(QApplication, object()),
            editor=cast(PromptEditor, object()),
            scenario=scenario,
            instrumentation=Instrumentation.create(),
            extra_counts={},
        )


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return all imported module names from one Python source tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
