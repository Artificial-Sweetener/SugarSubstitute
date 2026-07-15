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

"""Test support for importing WorkspaceController without full Qt surfaces."""

from __future__ import annotations

import importlib
import sys
import types
from dataclasses import dataclass
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest


class _Signal:
    """Capture emitted Qt-like signal payloads for assertions."""

    def __init__(self) -> None:
        """Initialize an empty signal emission list."""

        self.calls: list[tuple[object, ...]] = []

    def emit(self, *args: object) -> None:
        """Record emitted signal args."""

        self.calls.append(args)


def _module(name: str) -> ModuleType:
    """Return an existing module or an empty module with the requested name."""

    existing = sys.modules.get(name)
    if isinstance(existing, ModuleType):
        return existing
    return types.ModuleType(name)


def import_workspace_controller_module(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Import workspace controller with lightweight Qt and shell stubs installed."""

    import PySide6.QtCore  # noqa: F401
    import PySide6.QtGui  # noqa: F401
    import PySide6.QtWidgets  # noqa: F401
    import qfluentwidgets  # type: ignore[import-untyped]  # noqa: F401

    if "PySide6" not in sys.modules:
        monkeypatch.setitem(sys.modules, "PySide6", types.ModuleType("PySide6"))

    qtcore = _module("PySide6.QtCore")
    qtcore_any: Any = qtcore
    if not hasattr(qtcore_any, "QSize"):
        qtcore_any.QSize = type("QSize", (), {})
    if not hasattr(qtcore_any, "Qt"):
        qtcore_any.Qt = type("Qt", (), {})
    if not hasattr(qtcore_any, "QCoreApplication"):
        qtcore_any.QCoreApplication = type(
            "QCoreApplication",
            (),
            {"postEvent": staticmethod(lambda *_a, **_k: None)},
        )
    if not hasattr(qtcore_any, "QEvent"):

        class _QEvent:
            """Minimal QEvent stub for queue imports."""

            class Type(int):
                """Minimal QEvent.Type stub."""

            @staticmethod
            def registerEventType() -> int:
                """Return a deterministic custom event type."""

                return 1000

            def __init__(self, *_args: object, **_kwargs: object) -> None:
                """Accept the same loose construction shape as QEvent."""

                return None

        qtcore_any.QEvent = _QEvent
    if not hasattr(qtcore_any, "QTimer"):

        class _QTimer:
            """Minimal timer stub for controller contract tests."""

            def __init__(self, *_args: object, **_kwargs: object) -> None:
                """Expose a signal-like timeout object."""

                self.timeout = SimpleNamespace(connect=lambda _callback: None)

            @staticmethod
            def singleShot(_ms: object, fn: Any) -> None:
                """Execute the callback synchronously."""

                fn()

            def setSingleShot(self, _value: object) -> None:
                """Accept single-shot configuration."""

                return None

            def setInterval(self, _value: object) -> None:
                """Accept interval configuration."""

                return None

            def start(self, *_args: object) -> None:
                """Accept timer start requests."""

                return None

            def stop(self) -> None:
                """Accept timer stop requests."""

                return None

        qtcore_any.QTimer = _QTimer
    if not hasattr(qtcore_any, "QEventLoop"):
        qtcore_any.QEventLoop = type(
            "QEventLoop",
            (),
            {
                "exec": lambda self: 0,
                "quit": lambda self: None,
            },
        )
    if not hasattr(qtcore_any, "QObject"):
        qtcore_any.QObject = type(
            "QObject",
            (),
            {
                "__init__": lambda self, *_args, **_kwargs: None,
                "event": lambda self, _event: False,
            },
        )
    if not hasattr(qtcore_any, "Signal"):
        qtcore_any.Signal = lambda *_args, **_kwargs: _Signal()
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore)

    qtgui = _module("PySide6.QtGui")
    qtgui_any: Any = qtgui
    if not hasattr(qtgui_any, "QImage"):
        qtgui_any.QImage = type("QImage", (), {})
    if not hasattr(qtgui_any, "QImageReader"):
        qtgui_any.QImageReader = type("QImageReader", (), {})
    if not hasattr(qtgui_any, "QIcon"):
        qtgui_any.QIcon = type("QIcon", (), {})
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui)

    qtwidgets = _module("PySide6.QtWidgets")
    qtwidgets_any: Any = qtwidgets
    if not hasattr(qtwidgets_any, "QFileDialog"):
        qtwidgets_any.QFileDialog = type("QFileDialog", (), {})
    if not hasattr(qtwidgets_any, "QApplication"):
        qtwidgets_any.QApplication = type(
            "QApplication",
            (),
            {"activeWindow": staticmethod(lambda: None)},
        )
    if not hasattr(qtwidgets_any, "QInputDialog"):
        qtwidgets_any.QInputDialog = type("QInputDialog", (), {})
    if not hasattr(qtwidgets_any, "QMessageBox"):
        qtwidgets_any.QMessageBox = type("QMessageBox", (), {})
    if not hasattr(qtwidgets_any, "QWidget"):
        qtwidgets_any.QWidget = type("QWidget", (), {})
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets)

    sys.modules.pop("substitute.presentation.canvas", None)
    sys.modules.pop("substitute.presentation.canvas.shared.types", None)
    sys.modules.pop(
        "substitute.presentation.shell.workflow_workspace_coordinator",
        None,
    )
    sys.modules.pop("substitute.presentation.shell.workspace_controller", None)

    recipe_model_flow = types.ModuleType(
        "substitute.presentation.shell.recipe_model_resolution_flow"
    )

    @dataclass(frozen=True, slots=True)
    class DeferredRecipeModelDownload:
        """Test stub for approved recipe model download requests."""

        service: object
        required: object
        api_key_override: str | None = None

    recipe_model_flow_any: Any = recipe_model_flow
    recipe_model_flow_any.DeferredRecipeModelDownload = DeferredRecipeModelDownload
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.shell.recipe_model_resolution_flow",
        recipe_model_flow,
    )

    canvas_pkg = types.ModuleType("substitute.presentation.canvas")
    canvas_pkg_any: Any = canvas_pkg
    canvas_pkg_any.__path__ = []
    canvas_types = types.ModuleType("substitute.presentation.canvas.shared.types")
    canvas_types_any: Any = canvas_types
    canvas_types_any.OutputImageMeta = object
    canvas_pkg_any.types = canvas_types
    monkeypatch.setitem(sys.modules, "substitute.presentation.canvas", canvas_pkg)
    monkeypatch.setitem(
        sys.modules, "substitute.presentation.canvas.shared.types", canvas_types
    )

    coordinator_module = types.ModuleType(
        "substitute.presentation.shell.workflow_workspace_coordinator"
    )

    class WorkflowWorkspaceCoordinator:
        """Minimal workspace coordinator stub for controller contract imports."""

        def __init__(self, view: object) -> None:
            """Store the shell view."""

            self.view = view

        def activate_workflow(self, *_args: object, **_kwargs: object) -> None:
            """Accept workflow activation requests."""

            return None

        def reconcile_active_workflow_after_structural_mutation(self) -> None:
            """Accept structural reconciliation requests."""

            return None

        def rename_workflow(self, *_args: object, **_kwargs: object) -> None:
            """Accept workflow rename requests."""

            return None

        def add_workflow(self) -> None:
            """Accept workflow add requests."""

            return None

        def close_workflow(self, *_args: object, **_kwargs: object) -> None:
            """Accept workflow close requests."""

            return None

        def reopen_latest_closed_workflow(self) -> bool:
            """Report that no closed workflow is available."""

            return False

        def duplicate_workflow(
            self,
            *_args: object,
            **_kwargs: object,
        ) -> str | None:
            """Report that no duplicate workflow was created."""

            return None

    coordinator_any: Any = coordinator_module
    coordinator_any.WorkflowWorkspaceCoordinator = WorkflowWorkspaceCoordinator
    coordinator_any.WorkflowWorkspaceView = object
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.shell.workflow_workspace_coordinator",
        coordinator_module,
    )

    return importlib.import_module("substitute.presentation.shell.workspace_controller")
