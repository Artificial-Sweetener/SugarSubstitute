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

"""Tests for startup restore-plan preparation."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from substitute.app.bootstrap.startup_restore_plan import (
    StartupRestorePlanPreparation,
    prepare_startup_restore_plan,
)
from tests.execution_testing import ImmediateTaskSubmitter
from substitute.application.workspace_state import InitialWorkspaceRestorePlan
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.domain.workspace_snapshot import WorkspaceSnapshot

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESTORE_PLAN_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_restore_plan.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
FORBIDDEN_RESTORE_PLAN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
)


def test_prepare_startup_restore_plan_builds_plan_and_starts_preload(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Restore preparation should build, trace, register, and start preload."""

    trace_events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "substitute.app.bootstrap.startup_restore_plan.trace_mark",
        lambda name, **fields: trace_events.append((name, fields)),
    )
    workspace = cast(
        WorkspaceSnapshot,
        SimpleNamespace(active_workflow_id="wf-a", workflows=()),
    )
    plan = cast(
        InitialWorkspaceRestorePlan,
        SimpleNamespace(
            workspace=workspace,
            shell_placement=object(),
            provisional_restore_projection=object(),
        ),
    )
    runtime_services = SimpleNamespace(
        session_snapshot_repository=object(),
        restore_projection_cache_repository=object(),
        execution_runtime=object(),
    )
    timer_events: list[str] = []
    registry = _RestoreRegistry()
    preload = _RestorePreload()
    service_calls: list[dict[str, object]] = []

    preparation = prepare_startup_restore_plan(
        startup_timer=cast(Any, _RecordingTimer(timer_events)),
        installation_context=_context(tmp_path),
        runtime_services=runtime_services,
        startup_resources=registry,
        restore_projection_target_key_for_context=lambda context: (
            f"target:{context.comfy_target.endpoint.port}"
        ),
        plan_service_factory=lambda **kwargs: _record_service(
            service_calls,
            kwargs,
            plan,
        ),
        preload_handle_factory=lambda snapshot: _record_preload_factory(
            preload,
            snapshot,
            workspace,
        ),
    )

    assert preparation == StartupRestorePlanPreparation(
        restore_plan=plan,
        restore_asset_preload=preload,
    )
    assert timer_events == ["startup.build_initial_restore_plan", "restore_plan_built"]
    assert (
        service_calls[0]["repository"] is runtime_services.session_snapshot_repository
    )
    assert (
        service_calls[0]["restore_projection_repository"]
        is runtime_services.restore_projection_cache_repository
    )
    assert service_calls[0]["restore_projection_target_key"] == "target:8188"
    assert registry.preloads == [preload]
    assert preload.started is True
    assert trace_events == [
        (
            "startup.restore_plan.built",
            {
                "workspace_present": True,
                "shell_placement_present": True,
                "workflow_count": 0,
                "provisional_restore_projection_present": True,
            },
        )
    ]


def test_prepare_startup_restore_plan_skips_preload_without_workspace(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Restore preparation should not allocate preload resources without a workspace."""

    trace_events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "substitute.app.bootstrap.startup_restore_plan.trace_mark",
        lambda name, **fields: trace_events.append((name, fields)),
    )
    plan = cast(
        InitialWorkspaceRestorePlan,
        SimpleNamespace(
            workspace=None,
            shell_placement=None,
            provisional_restore_projection=None,
        ),
    )
    registry = _RestoreRegistry()

    preparation = prepare_startup_restore_plan(
        startup_timer=cast(Any, _RecordingTimer([])),
        installation_context=_context(tmp_path),
        runtime_services=SimpleNamespace(
            session_snapshot_repository=object(),
            restore_projection_cache_repository=object(),
            execution_runtime=object(),
        ),
        startup_resources=registry,
        restore_projection_target_key_for_context=lambda _context: "target",
        plan_service_factory=lambda **_kwargs: _RestorePlanService(plan),
        preload_handle_factory=lambda _snapshot: _fail_preload_factory(),
    )

    assert preparation == StartupRestorePlanPreparation(
        restore_plan=plan,
        restore_asset_preload=None,
    )
    assert registry.preloads == []
    assert trace_events[0][1]["workspace_present"] is False


def test_prepare_startup_restore_plan_default_preload_uses_disk_io_lane(
    tmp_path: Path,
) -> None:
    """Default restore preload construction should use the execution runtime lane."""

    workspace = cast(
        WorkspaceSnapshot,
        SimpleNamespace(active_workflow_id="wf-a", workflows=()),
    )
    plan = cast(
        InitialWorkspaceRestorePlan,
        SimpleNamespace(
            workspace=workspace,
            shell_placement=None,
            provisional_restore_projection=None,
        ),
    )
    submitter = _ClosableImmediateSubmitter()
    execution_runtime = _RestoreExecutionRuntime(submitter)
    runtime_services = SimpleNamespace(
        session_snapshot_repository=object(),
        restore_projection_cache_repository=object(),
        execution_runtime=execution_runtime,
    )
    registry = _RestoreRegistry()

    preparation = prepare_startup_restore_plan(
        startup_timer=cast(Any, _RecordingTimer([])),
        installation_context=_context(tmp_path),
        runtime_services=runtime_services,
        startup_resources=registry,
        restore_projection_target_key_for_context=lambda _context: "target",
        plan_service_factory=lambda **_kwargs: _RestorePlanService(plan),
    )

    assert preparation.restore_plan is plan
    assert preparation.restore_asset_preload is registry.preloads[0]
    assert execution_runtime.submitter_calls == [
        {
            "name": "disk_io_low_priority",
            "owner_id": "workspace_restore_asset_preload",
        }
    ]
    assert submitter.close_calls == 0


def test_startup_restore_plan_imports_no_forbidden_boundaries() -> None:
    """Startup restore-plan preparation should stay free of GUI/process boundaries."""

    imported_modules = _imported_module_names(RESTORE_PLAN_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_RESTORE_PLAN_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_restore_plan_preparation() -> None:
    """Startup should not own restore-plan construction or preload startup."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")

    assert "prepare_startup_restore_plan(" in source
    assert "InitialWorkspaceRestorePlanService(" not in source
    assert "SnapshotNormalizationService(" not in source
    assert "WorkspaceRestoreAssetPreloadHandle(" not in source
    assert "startup.build_initial_restore_plan" not in source
    assert "startup.restore_plan.built" not in source
    assert "register_workspace_restore_asset_preload(" not in source


class _RecordingTimer:
    """Record startup restore-plan timer activity."""

    def __init__(self, events: list[str]) -> None:
        """Store a shared event sink."""

        self._events = events

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        """Record one phase entry."""

        self._events.append(name)
        yield

    def mark(self, name: str) -> None:
        """Record one milestone mark."""

        self._events.append(name)


class _RestorePlanService:
    """Return one configured restore plan."""

    def __init__(self, plan: InitialWorkspaceRestorePlan) -> None:
        """Store the configured plan."""

        self._plan = plan

    def build(self) -> InitialWorkspaceRestorePlan:
        """Return the configured restore plan."""

        return self._plan


class _RestorePreload:
    """Restore asset preload test double."""

    def __init__(self) -> None:
        """Initialize call recording."""

        self.started = False

    def start(self) -> None:
        """Record preload start."""

        self.started = True

    def shutdown(self) -> None:
        """Satisfy the preload handle protocol."""


class _RestoreRegistry:
    """Startup resource registry test double."""

    def __init__(self) -> None:
        """Initialize preload recording."""

        self.preloads: list[object] = []

    def register_workspace_restore_asset_preload(self, preload: object) -> object:
        """Record one registered preload."""

        self.preloads.append(preload)
        return preload


class _ClosableImmediateSubmitter(ImmediateTaskSubmitter):
    """Run restore preload work immediately while recording close calls."""

    def __init__(self) -> None:
        """Initialize close tracking."""

        self.close_calls = 0

    def close(self) -> None:
        """Record one close request."""

        self.close_calls += 1


class _RestoreExecutionRuntime:
    """Record restore preload submitter requests."""

    def __init__(self, submitter: _ClosableImmediateSubmitter) -> None:
        """Store the submitter to return for runtime calls."""

        self._submitter = submitter
        self.submitter_calls: list[dict[str, object]] = []

    def submitter(
        self,
        name: str,
        *,
        owner_id: str,
        dispatcher: object,
    ) -> _ClosableImmediateSubmitter:
        """Record and return the configured submitter."""

        self.submitter_calls.append(
            {
                "name": name,
                "owner_id": owner_id,
            }
        )
        assert dispatcher is not None
        return self._submitter


def _record_service(
    calls: list[dict[str, object]],
    kwargs: dict[str, object],
    plan: InitialWorkspaceRestorePlan,
) -> _RestorePlanService:
    """Record restore-plan service construction."""

    calls.append(kwargs)
    return _RestorePlanService(plan)


def _record_preload_factory(
    preload: _RestorePreload,
    snapshot: WorkspaceSnapshot,
    expected_snapshot: WorkspaceSnapshot,
) -> _RestorePreload:
    """Verify restore preload construction receives the planned workspace."""

    assert snapshot is expected_snapshot
    return preload


def _fail_preload_factory() -> _RestorePreload:
    """Fail if preload construction is unexpectedly requested."""

    raise AssertionError("preload factory should not be called")


def _context(tmp_path: Path) -> InstallationContext:
    """Build one installation context for restore-plan tests."""

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
