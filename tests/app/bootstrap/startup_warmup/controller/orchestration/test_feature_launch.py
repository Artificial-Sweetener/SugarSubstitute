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

"""Test startup-warmup behavior owners."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from substitute.app.bootstrap.startup_warmup_controller import (
    StartupWarmupState,
    start_backend_editor_startup_warmup,
    start_cube_icon_startup_warmup,
    start_local_editor_startup_warmup,
    start_cutecanvas_sam_startup_warmup,
)


from .support import (
    _WarmupFactory,
    _NoArgWarmupFactory,
    _Registry,
)

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


def test_start_cube_icon_startup_warmup_registers_and_starts_handle() -> None:
    """Cube icon warmup should use shell dependencies and start once."""

    state = StartupWarmupState()
    registry = _Registry()
    factory = _WarmupFactory()
    shell_frame = object()
    cube_load_service = object()
    cube_icon_factory = object()
    main_window = SimpleNamespace(
        cube_load_service=cube_load_service,
        cube_icon_factory=cube_icon_factory,
    )

    start_cube_icon_startup_warmup(
        state=state,
        startup_cancelled=False,
        shell_frame=shell_frame,
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else None
        ),
        registry=registry,
        trace_fields=lambda: {"workflow_id": "wf-a"},
        warmup_factory=factory,
    )

    assert state.cube_icon_started is True
    assert registry.cube_icon_warmups == [factory.handle]
    assert factory.kwargs == {
        "cube_load_service": cube_load_service,
        "cube_icon_factory": cube_icon_factory,
    }
    assert factory.handle.started is True


def test_start_cutecanvas_sam_startup_warmup_registers_and_starts_handle() -> None:
    """QPane SAM warmup should register its handle and start once."""

    state = StartupWarmupState()
    registry = _Registry()
    factory = _NoArgWarmupFactory()

    start_cutecanvas_sam_startup_warmup(
        state=state,
        startup_cancelled=False,
        registry=registry,
        trace_fields=lambda: {"workflow_id": "wf-a"},
        warmup_factory=factory,
    )
    start_cutecanvas_sam_startup_warmup(
        state=state,
        startup_cancelled=False,
        registry=registry,
        trace_fields=lambda: {"workflow_id": "wf-a"},
        warmup_factory=factory,
    )

    assert state.cutecanvas_sam_started is True
    assert registry.cutecanvas_sam_warmups == [factory.handle]
    assert factory.calls == 1
    assert factory.handle.started is True


def test_start_cutecanvas_sam_startup_warmup_skips_cancelled_startup() -> None:
    """QPane SAM warmup should not start after startup cancellation."""

    state = StartupWarmupState()
    registry = _Registry()
    factory = _NoArgWarmupFactory()

    start_cutecanvas_sam_startup_warmup(
        state=state,
        startup_cancelled=True,
        registry=registry,
        trace_fields=lambda: {},
        warmup_factory=factory,
    )

    assert state.cutecanvas_sam_started is False
    assert registry.cutecanvas_sam_warmups == []
    assert factory.calls == 0


def test_start_cube_icon_startup_warmup_skips_missing_dependencies() -> None:
    """Cube icon warmup should not start without required shell collaborators."""

    state = StartupWarmupState()
    registry = _Registry()

    start_cube_icon_startup_warmup(
        state=state,
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: SimpleNamespace(cube_load_service=None),
        registry=registry,
        trace_fields=lambda: {},
        warmup_factory=_WarmupFactory(),
    )

    assert state.cube_icon_started is False
    assert registry.cube_icon_warmups == []


def test_start_local_editor_startup_warmup_registers_and_starts_handle() -> None:
    """Local editor warmup should pass backend-independent shell collaborators."""

    state = StartupWarmupState()
    registry = _Registry()
    factory = _WarmupFactory()
    main_window = SimpleNamespace(
        prompt_autocomplete_gateway=object(),
        prompt_wildcard_catalog_gateway=object(),
        prompt_lora_catalog_service=object(),
        prompt_spellcheck_service=object(),
    )

    start_local_editor_startup_warmup(
        state=state,
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: main_window,
        registry=registry,
        trace_fields=lambda: {},
        warmup_factory=factory,
    )

    assert state.local_editor_started is True
    assert registry.editor_warmups == [factory.handle]
    assert set(factory.kwargs) == {
        "prompt_autocomplete_gateway",
        "prompt_wildcard_catalog_gateway",
        "prompt_lora_catalog_service",
        "prompt_spellcheck_service",
    }
    assert factory.handle.started is True


def test_start_backend_editor_startup_warmup_registers_and_starts_handle() -> None:
    """Backend editor warmup should pass Comfy-dependent shell collaborators."""

    state = StartupWarmupState()
    registry = _Registry()
    factory = _WarmupFactory()
    main_window = SimpleNamespace(
        node_definition_gateway=object(),
        model_choice_resolver=object(),
    )

    start_backend_editor_startup_warmup(
        state=state,
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: main_window,
        registry=registry,
        trace_fields=lambda: {},
        warmup_factory=factory,
    )

    assert state.backend_editor_started is True
    assert registry.editor_warmups == [factory.handle]
    assert set(factory.kwargs) == {
        "node_definition_gateway",
        "model_choice_resolver",
    }
    assert factory.handle.started is True


def test_startup_warmups_skip_cancelled_or_repeated_requests() -> None:
    """Warmups should stay single-flight and honor startup cancellation."""

    state = StartupWarmupState(local_editor_started=True)
    registry = _Registry()

    start_local_editor_startup_warmup(
        state=state,
        startup_cancelled=False,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: SimpleNamespace(),
        registry=registry,
        trace_fields=lambda: {},
        warmup_factory=_WarmupFactory(),
    )
    start_backend_editor_startup_warmup(
        state=state,
        startup_cancelled=True,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: SimpleNamespace(),
        registry=registry,
        trace_fields=lambda: {},
        warmup_factory=_WarmupFactory(),
    )

    assert registry.editor_warmups == []
