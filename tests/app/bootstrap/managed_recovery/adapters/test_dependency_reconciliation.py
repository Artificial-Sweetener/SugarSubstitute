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

"""Exercise one managed-recovery adapter behavior owner."""

from __future__ import annotations
from pathlib import Path
from typing import Any
import pytest
from substitute.app.bootstrap import managed_recovery_adapters
from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.domain.comfy_manager import ComfyManagerKind, ComfyManagerRuntime
from substitute.domain.onboarding import (
    ComfyTargetMode,
    ManagedRuntimeConfiguration,
)

from .support import (
    _target,
)


def test_reconcile_owned_dependencies_for_managed_target_runs_managed_setup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed-local recovery should forward to full managed setup."""

    calls: list[tuple[Path, frozenset[CoreNodepackId], object, object]] = []

    def fake_setup(**kwargs: Any) -> None:
        """Record managed setup arguments and emit through both log ports."""

        calls.append(
            (
                kwargs["workspace"],
                kwargs["refresh_core_nodepacks"],
                kwargs["on_status"],
                kwargs["on_log"],
            )
        )
        kwargs["on_status"]("status")
        kwargs["on_log"]("log")

    monkeypatch.setattr(
        managed_recovery_adapters,
        "ensure_managed_comfy_setup",
        fake_setup,
    )
    logs: list[str] = []

    managed_recovery_adapters.reconcile_owned_comfy_dependencies(
        _target(tmp_path, ComfyTargetMode.MANAGED_LOCAL),
        frozenset({CoreNodepackId.SUGARCUBES}),
        logs.append,
    )

    assert calls == [
        (
            tmp_path / "ComfyUI",
            frozenset({CoreNodepackId.SUGARCUBES}),
            logs.append,
            logs.append,
        )
    ]
    assert logs == ["status", "log"]


def test_managed_recovery_preserves_persisted_runtime_selection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed recovery should reuse the active runtime selection policy."""

    observed: dict[str, object] = {}

    def fake_setup(**kwargs: object) -> None:
        """Capture the managed setup policy supplied by recovery."""

        observed.update(kwargs)

    monkeypatch.setattr(
        managed_recovery_adapters,
        "ensure_managed_comfy_setup",
        fake_setup,
    )
    runtime_configuration = ManagedRuntimeConfiguration(
        force_cpu_mode=True,
        prefer_edge_torch=True,
        prefer_edge_comfy_channel=True,
    )

    managed_recovery_adapters.reconcile_owned_comfy_dependencies(
        _target(tmp_path, ComfyTargetMode.MANAGED_LOCAL),
        frozenset({CoreNodepackId.SUGARCUBES}),
        lambda _line: None,
        runtime_configuration=runtime_configuration,
    )

    assert observed["force_cpu_mode"] is True
    assert observed["prefer_edge_torch"] is True
    assert observed["prefer_edge_comfy_channel"] is True


def test_reconcile_owned_dependencies_for_attached_target_runs_nodepack_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Attached-local recovery should mutate only trusted Substitute nodepacks."""

    core_calls: list[tuple[Path, frozenset[CoreNodepackId], object]] = []
    baseline_calls: list[tuple[Path, object]] = []

    def fake_ensure_core_nodepacks(
        *,
        manager_runtime: ComfyManagerRuntime,
        refresh_nodepacks: frozenset[CoreNodepackId],
        on_log: object,
    ) -> None:
        """Record core nodepack reconciliation arguments."""

        core_calls.append((manager_runtime.workspace, refresh_nodepacks, on_log))
        assert manager_runtime.python_executable.name == "python.exe"
        assert callable(on_log)
        on_log("core ready")

    def fake_baseline_maintenance(
        workspace: Path,
        *,
        python_executable: Path,
        on_log: object,
    ) -> None:
        """Record SugarCubes baseline maintenance arguments."""

        baseline_calls.append((workspace, on_log))
        assert python_executable.name == "python.exe"
        assert callable(on_log)
        on_log("baseline ready")

    def fail_managed_setup(**_kwargs: Any) -> None:
        """Fail if attached-local recovery tries to run managed setup."""

        raise AssertionError("attached local target used managed setup")

    monkeypatch.setattr(
        managed_recovery_adapters,
        "ensure_core_comfy_nodepacks",
        fake_ensure_core_nodepacks,
    )
    monkeypatch.setattr(
        managed_recovery_adapters,
        "attempt_sugarcubes_startup_maintenance",
        fake_baseline_maintenance,
    )
    monkeypatch.setattr(
        managed_recovery_adapters,
        "ensure_managed_comfy_setup",
        fail_managed_setup,
    )
    monkeypatch.setattr(
        managed_recovery_adapters,
        "ensure_attached_workspace_manager",
        lambda workspace, python_executable, **_kwargs: ComfyManagerRuntime(
            kind=ComfyManagerKind.INTEGRATED,
            workspace=workspace,
            python_executable=python_executable,
            version="4.1",
        ),
    )
    logs: list[str] = []

    managed_recovery_adapters.reconcile_owned_comfy_dependencies(
        _target(tmp_path, ComfyTargetMode.ATTACHED_LOCAL),
        frozenset({CoreNodepackId.SUBSTITUTE_BACKEND}),
        logs.append,
    )

    assert core_calls == [
        (
            tmp_path / "ComfyUI",
            frozenset({CoreNodepackId.SUBSTITUTE_BACKEND}),
            logs.append,
        )
    ]
    assert baseline_calls == [(tmp_path / "ComfyUI", logs.append)]
    assert logs == [
        "Updating Substitute Comfy nodepacks.",
        "core ready",
        "Preparing Base-Cubes dependencies.",
        "baseline ready",
    ]


def test_reconcile_owned_dependencies_rejects_remote_target(tmp_path: Path) -> None:
    """Remote targets should not receive local nodepack mutation."""

    with pytest.raises(RuntimeError, match="launch-owned local workspace"):
        managed_recovery_adapters.reconcile_owned_comfy_dependencies(
            _target(tmp_path, ComfyTargetMode.REMOTE),
            frozenset({CoreNodepackId.SUGARCUBES}),
            lambda _line: None,
        )
