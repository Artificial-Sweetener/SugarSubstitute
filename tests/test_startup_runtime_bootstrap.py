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

"""Verify startup runtime bootstrap construction ownership."""

from __future__ import annotations

import ast
from collections.abc import Iterator, Sequence
from contextlib import contextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from substitute.app.bootstrap import startup_runtime_bootstrap
from substitute.app.bootstrap.startup_runtime_bootstrap import (
    build_startup_runtime_bootstrap,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_RUNTIME_BOOTSTRAP_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_runtime_bootstrap.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
FORBIDDEN_RUNTIME_BOOTSTRAP_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
    "substitute.infrastructure",
)


def test_build_startup_runtime_bootstrap_creates_runtime_objects(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Runtime bootstrap should own app/theme/runtime-service sequencing."""

    context = _build_context(tmp_path)
    timer = _RecordingTimer()
    events: list[object] = []
    trace_events: list[tuple[str, dict[str, object]]] = []
    trace_spans: list[str] = []
    output_stream = cast(TerminalOutputStream, object())
    app = object()
    appearance_runtime = object()
    resolved_appearance = SimpleNamespace(
        effective_theme_mode=SimpleNamespace(value="dark"),
        effective_backdrop_mode="mica",
    )
    runtime_services = object()

    def record_trace(event_name: str, **fields: object) -> None:
        """Record one startup runtime trace mark."""

        trace_events.append((event_name, fields))

    @contextmanager
    def record_trace_span(name: str) -> Iterator[None]:
        """Record one startup runtime trace span."""

        trace_spans.append(name)
        yield

    def create_application(cli_args: Sequence[str]) -> object:
        """Record app construction."""

        events.append(("create_application", tuple(cli_args)))
        return app

    def build_appearance_runtime(
        installation_context: InstallationContext,
    ) -> object:
        """Record appearance runtime construction."""

        events.append(("build_appearance_runtime", installation_context))
        return appearance_runtime

    def configure_theme(runtime: object) -> object:
        """Record theme configuration."""

        events.append(("configure_theme", runtime))
        return resolved_appearance

    def build_runtime_services(**kwargs: object) -> object:
        """Record runtime service construction."""

        events.append(("build_runtime_services", kwargs))
        return runtime_services

    monkeypatch.setattr(startup_runtime_bootstrap, "trace_mark", record_trace)
    monkeypatch.setattr(startup_runtime_bootstrap, "trace_span", record_trace_span)
    monkeypatch.setattr(
        startup_runtime_bootstrap,
        "suppress_qfluentwidgets_import_banner",
        nullcontext,
    )

    result = build_startup_runtime_bootstrap(
        cli_args=("main.py", "--no-comfy"),
        installation_context=context,
        startup_timer=timer,
        create_application=create_application,
        build_appearance_runtime=build_appearance_runtime,
        configure_theme=configure_theme,
        build_application_runtime_services=build_runtime_services,
        output_stream_factory=lambda: output_stream,
    )

    assert result.app is app
    assert result.appearance_runtime is appearance_runtime
    assert result.resolved_appearance is resolved_appearance
    assert result.comfy_output_stream is output_stream
    assert result.runtime_services is runtime_services
    assert timer.phases == [
        "startup.create_application",
        "startup.build_appearance_runtime",
        "startup.configure_theme",
    ]
    assert trace_events == [
        ("startup.application.created", {"app_type": "object"}),
        (
            "startup.theme.configured",
            {"theme_mode": "dark", "backdrop_mode": "mica"},
        ),
        ("startup.runtime_services.built", {}),
    ]
    assert trace_spans == [
        "startup.create_application",
        "startup.build_appearance_runtime",
        "startup.configure_theme",
        "startup.runtime_services.build",
    ]
    assert events == [
        ("create_application", ("main.py", "--no-comfy")),
        ("build_appearance_runtime", context),
        ("configure_theme", appearance_runtime),
        (
            "build_runtime_services",
            {
                "context": context,
                "comfy_output_stream": output_stream,
                "appearance_runtime": appearance_runtime,
            },
        ),
    ]


def test_runtime_bootstrap_can_defer_theme_configuration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed startup can build runtime services before applying QFluent theme."""

    context = _build_context(tmp_path)
    timer = _RecordingTimer()
    events: list[str] = []
    trace_events: list[tuple[str, dict[str, object]]] = []
    trace_spans: list[str] = []
    appearance_runtime = object()
    output_stream = cast(TerminalOutputStream, object())
    resolved_appearance = SimpleNamespace(
        effective_theme_mode=SimpleNamespace(value="dark"),
        effective_backdrop_mode="mica",
    )

    @contextmanager
    def record_trace_span(name: str) -> Iterator[None]:
        """Record one startup runtime trace span."""

        trace_spans.append(name)
        yield

    monkeypatch.setattr(
        startup_runtime_bootstrap,
        "trace_mark",
        lambda event_name, **fields: trace_events.append((event_name, fields)),
    )
    monkeypatch.setattr(startup_runtime_bootstrap, "trace_span", record_trace_span)
    monkeypatch.setattr(
        startup_runtime_bootstrap,
        "suppress_qfluentwidgets_import_banner",
        nullcontext,
    )

    def create_application(_cli_args: Sequence[str]) -> object:
        """Record deferred app construction."""

        events.append("app")
        return object()

    def build_appearance_runtime(_context: InstallationContext) -> object:
        """Record deferred appearance runtime construction."""

        events.append("appearance")
        return appearance_runtime

    def configure_theme(_runtime: object) -> object:
        """Record deferred theme configuration."""

        events.append("theme")
        return resolved_appearance

    def build_runtime_services(**_kwargs: object) -> object:
        """Record deferred runtime service construction."""

        events.append("runtime")
        return object()

    result = build_startup_runtime_bootstrap(
        cli_args=("main.py",),
        installation_context=context,
        startup_timer=timer,
        create_application=create_application,
        build_appearance_runtime=build_appearance_runtime,
        configure_theme=configure_theme,
        build_application_runtime_services=build_runtime_services,
        output_stream_factory=lambda: output_stream,
        configure_theme_immediately=False,
    )

    assert result.resolved_appearance is None
    assert events == ["app", "appearance", "runtime"]
    assert result.configure_theme() is resolved_appearance
    assert result.configure_theme() is resolved_appearance
    assert events == ["app", "appearance", "runtime", "theme"]
    assert timer.phases == [
        "startup.create_application",
        "startup.build_appearance_runtime",
        "startup.configure_theme",
    ]
    assert trace_events[-1] == (
        "startup.theme.configured",
        {"theme_mode": "dark", "backdrop_mode": "mica"},
    )
    assert trace_spans == [
        "startup.create_application",
        "startup.build_appearance_runtime",
        "startup.runtime_services.build",
        "startup.configure_theme",
    ]


def test_startup_runtime_bootstrap_imports_no_forbidden_boundaries() -> None:
    """Runtime bootstrap adapter should avoid Qt bindings and infrastructure."""

    imported_modules = _imported_module_names(STARTUP_RUNTIME_BOOTSTRAP_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_RUNTIME_BOOTSTRAP_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_runtime_bootstrap() -> None:
    """Startup should delegate app/theme/runtime service construction."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")

    assert "build_startup_runtime_bootstrap(" in source
    assert "TerminalOutputStream" not in source
    assert '"startup.create_application"' not in source
    assert '"startup.theme.configured"' not in source
    assert '"startup.runtime_services.build"' not in source


class _RecordingTimer:
    """Record startup timer phase names."""

    def __init__(self) -> None:
        """Initialize recorded phases."""

        self.phases: list[str] = []

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        """Record one timed phase."""

        self.phases.append(name)
        yield


def _build_context(tmp_path: Path) -> InstallationContext:
    """Build a deterministic startup context for runtime bootstrap tests."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.REMOTE,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=None,
        install_owned=False,
        launch_owned=False,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=target,
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
