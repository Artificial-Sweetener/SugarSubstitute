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

"""Provide deterministic startup-warmup support ports."""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from typing import Any

from substitute.app.bootstrap.startup_model_metadata import (
    StartupModelMetadataRefreshHandleProtocol,
)
from substitute.app.bootstrap.startup_resources import ShutdownResource


PROJECT_ROOT = Path(__file__).resolve().parents[6]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
STARTUP_WARMUP_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_warmup_controller.py"
)
FORBIDDEN_STARTUP_WARMUP_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


class _ReadinessState:
    """Expose nonessential warmup backend-pending state."""

    nonessential_startup_warmups_pending_backend: bool = False


class _WarmupHandle:
    """Record warmup starts."""

    def __init__(self) -> None:
        """Create start records."""

        self.started = False

    def start(self) -> None:
        """Record start."""

        self.started = True

    def shutdown(self) -> None:
        """Accept registry shutdown."""


class _WarmupFactory:
    """Create one recording warmup handle."""

    def __init__(self) -> None:
        """Create factory records."""

        self.handle = _WarmupHandle()
        self.kwargs: dict[str, object] = {}

    def __call__(self, **kwargs: object) -> _WarmupHandle:
        """Record construction kwargs and return the handle."""

        self.kwargs = kwargs
        return self.handle


class _NoArgWarmupFactory:
    """Create one no-argument recording warmup handle."""

    def __init__(self) -> None:
        """Create factory records."""

        self.handle = _WarmupHandle()
        self.calls = 0

    def __call__(self) -> _WarmupHandle:
        """Record construction and return the handle."""

        self.calls += 1
        return self.handle


class _MetadataRefreshHandle:
    """Satisfy startup model metadata refresh handle protocol in tests."""

    def start(self) -> None:
        """Accept refresh start."""

    def cancel(self) -> None:
        """Accept refresh cancellation."""

    def shutdown(self) -> None:
        """Accept refresh shutdown."""


class _MetadataRefreshHandleFactory:
    """Create model metadata refresh handles with the production factory shape."""

    def __call__(
        self,
        *,
        service_factory: Any,
        progress_sink: Any,
        finished_callback: Callable[[], None] | None,
    ) -> StartupModelMetadataRefreshHandleProtocol:
        """Return one placeholder refresh handle."""

        _ = service_factory, progress_sink, finished_callback
        return _MetadataRefreshHandle()


class _Registry:
    """Record registered warmup handles."""

    def __init__(self) -> None:
        """Create empty registration records."""

        self.cube_icon_warmups: list[object] = []
        self.cutecanvas_sam_warmups: list[object] = []
        self.editor_warmups: list[object] = []

    def register_cube_icon_warmup(
        self,
        warmup: ShutdownResource,
    ) -> ShutdownResource:
        """Record cube icon warmup registration."""

        self.cube_icon_warmups.append(warmup)
        return warmup

    def register_cutecanvas_sam_warmup(
        self,
        warmup: ShutdownResource,
    ) -> ShutdownResource:
        """Record QPane SAM warmup registration."""

        self.cutecanvas_sam_warmups.append(warmup)
        return warmup

    def register_editor_startup_warmup(
        self,
        warmup: ShutdownResource,
    ) -> ShutdownResource:
        """Record editor warmup registration."""

        self.editor_warmups.append(warmup)
        return warmup


class _Signal:
    """Record signal callback wiring."""

    def __init__(self) -> None:
        """Create empty signal records."""

        self.callback: object | None = None
        self.connect_count = 0

    def connect(self, callback: object) -> None:
        """Record one connected callback."""

        self.callback = callback
        self.connect_count += 1

    def emit(self) -> None:
        """Invoke the connected callback."""

        assert callable(self.callback)
        self.callback()


class _MetadataBridge:
    """Record metadata coalescing requests."""

    def __init__(self) -> None:
        """Create empty coalescing records."""

        self.begin_calls = 0

    def begin_startup_coalescing(self) -> None:
        """Record coalescing start."""

        self.begin_calls += 1

    def timeout_startup_coalescing(self) -> None:
        """Accept coalescing timeout."""

    def emit_model_updated(self, event: object) -> None:
        """Accept model metadata update events."""

        _ = event
