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

"""Verify existing managed-workspace reconciliation behavior."""

from __future__ import annotations

from __future__ import annotations
from pathlib import Path
import pytest
from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.domain.comfy_manager import ComfyManagerRuntime
from substitute.infrastructure.comfy import managed_install
from substitute.infrastructure.comfy import managed_existing_setup
from substitute.infrastructure.comfy import managed_existing_setup_operations
from substitute.infrastructure.comfy.managed_validation import (
    workspace_python_path,
)
from sugarsubstitute_shared.startup_remote_access import (
    STARTUP_REMOTE_DEGRADED_ENV,
)

from .orchestration_support import (
    configure_managed_install,
    manager_runtime,
    managed_setup_record_path,
)


def test_ensure_managed_comfy_setup_reuses_installed_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Installed managed workspaces should skip reinstall and refresh the manager."""

    configure_managed_install(monkeypatch, tmp_path)

    python_path = workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    (tmp_path / "main.py").write_text("main", encoding="utf-8")
    provision_calls: list[Path] = []
    refresh_targets: list[frozenset[CoreNodepackId]] = []
    trace_events: list[str] = []
    mutation_order: list[str] = []

    class _TraceSpan:
        """Record deterministic setup span entry and exit events."""

        def __init__(self, name: str) -> None:
            self._name = name

        def __enter__(self) -> None:
            trace_events.append(f"span:start:{self._name}")

        def __exit__(self, *_exc: object) -> None:
            trace_events.append(f"span:end:{self._name}")

    def trace_span(event: str, **_fields: object) -> _TraceSpan:
        """Record setup trace spans."""

        return _TraceSpan(event)

    def _fake_provision_workspace_manager(
        workspace: Path,
        on_log: object | None = None,
        env: object | None = None,
    ) -> ComfyManagerRuntime:
        _ = on_log, env
        provision_calls.append(workspace)
        return manager_runtime(workspace)

    def _record_nodepack_install(
        manager_runtime: ComfyManagerRuntime,
        refresh_nodepacks: frozenset[CoreNodepackId] = frozenset(),
        on_log: object | None = None,
        env: object | None = None,
    ) -> None:
        """Record nodepack convergence before model-root configuration."""

        _ = manager_runtime, on_log, env
        refresh_targets.append(frozenset(refresh_nodepacks))
        mutation_order.append("nodepacks")

    monkeypatch.setattr(
        managed_install,
        "trace_span",
        trace_span,
    )
    monkeypatch.setattr(managed_existing_setup, "trace_span", trace_span)
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "ensure_managed_workspace_manager",
        _fake_provision_workspace_manager,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "ensure_core_comfy_nodepacks",
        _record_nodepack_install,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "configure_backend_model_root",
        lambda *, workspace, python_executable, model_root: mutation_order.append(
            "model_root"
        ),
    )
    result = managed_install.ensure_managed_comfy_setup(
        workspace=tmp_path,
        managed_model_root=tmp_path / "models",
        configure_model_root=True,
        refresh_core_nodepacks={CoreNodepackId.SUBSTITUTE_BACKEND},
    )

    assert result == python_path
    assert provision_calls == [tmp_path]
    assert refresh_targets == [frozenset({CoreNodepackId.SUBSTITUTE_BACKEND})]
    assert mutation_order == ["nodepacks", "model_root"]
    assert trace_events == [
        "span:start:managed_setup.scratch.create",
        "span:end:managed_setup.scratch.create",
        "span:start:managed_setup.existing.reconcile_dependencies",
        "span:end:managed_setup.existing.reconcile_dependencies",
        "span:start:managed_setup.existing.provision_manager",
        "span:end:managed_setup.existing.provision_manager",
        "span:start:managed_setup.detect_hardware",
        "span:end:managed_setup.detect_hardware",
        "span:start:managed_setup.select_install_strategy",
        "span:end:managed_setup.select_install_strategy",
        "span:start:managed_setup.existing.ensure_nodepacks",
        "span:end:managed_setup.existing.ensure_nodepacks",
        "span:start:managed_setup.existing.sugarcubes_baseline",
        "span:end:managed_setup.existing.sugarcubes_baseline",
        "span:start:managed_setup.existing.configure_model_root",
        "span:end:managed_setup.existing.configure_model_root",
        "span:start:managed_setup.existing.validate_torch",
        "span:end:managed_setup.existing.validate_torch",
        "span:start:managed_setup.existing.acceleration",
        "span:end:managed_setup.existing.acceleration",
        "span:start:managed_setup.scratch.cleanup",
        "span:end:managed_setup.scratch.cleanup",
    ]


def test_existing_managed_setup_skips_remote_work_after_launcher_degradation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An inherited launch fallback must cover every remote setup decision."""

    configure_managed_install(monkeypatch, tmp_path)

    python_path = workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    (tmp_path / "main.py").write_text("main", encoding="utf-8")
    monkeypatch.setenv(STARTUP_REMOTE_DEGRADED_ENV, "1")

    def unexpected_remote_work(*_args: object, **_kwargs: object) -> None:
        """Fail if an inherited fallback permits later remote work."""

        pytest.fail("degraded startup attempted downstream remote work")

    monkeypatch.setattr(
        managed_existing_setup_operations,
        "reconcile_managed_workspace_dependencies",
        unexpected_remote_work,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "ensure_managed_workspace_manager",
        unexpected_remote_work,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "ensure_core_comfy_nodepacks",
        unexpected_remote_work,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "attempt_sugarcubes_startup_maintenance",
        unexpected_remote_work,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "reconcile_managed_acceleration_stack",
        unexpected_remote_work,
    )

    result = managed_install.ensure_managed_comfy_setup(workspace=tmp_path)

    assert result == python_path
    assert not managed_setup_record_path(tmp_path).exists()


def test_existing_managed_setup_latches_first_remote_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The first remote failure must suppress downstream work for this launch."""

    configure_managed_install(monkeypatch, tmp_path)

    python_path = workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    (tmp_path / "main.py").write_text("main", encoding="utf-8")
    downstream_calls: list[str] = []

    def fail_first_remote_step(**_kwargs: object) -> None:
        """Represent one unavailable prerequisite at the first remote boundary."""

        raise ConnectionError("network unavailable")

    def record_downstream_remote_step(*_args: object, **_kwargs: object) -> None:
        """Record work that must remain suppressed after degradation."""

        downstream_calls.append("remote")

    monkeypatch.setattr(
        managed_existing_setup_operations,
        "reconcile_managed_workspace_dependencies",
        fail_first_remote_step,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "ensure_managed_workspace_manager",
        record_downstream_remote_step,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "ensure_core_comfy_nodepacks",
        record_downstream_remote_step,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "attempt_sugarcubes_startup_maintenance",
        record_downstream_remote_step,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "reconcile_managed_acceleration_stack",
        record_downstream_remote_step,
    )

    result = managed_install.ensure_managed_comfy_setup(workspace=tmp_path)

    assert result == python_path
    assert downstream_calls == []
    assert not managed_setup_record_path(tmp_path).exists()


def test_existing_managed_setup_preserves_non_connectivity_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A local failure must not masquerade as offline launch degradation."""

    configure_managed_install(monkeypatch, tmp_path)

    python_path = workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    (tmp_path / "main.py").write_text("main", encoding="utf-8")

    def fail_local_output(**_kwargs: object) -> None:
        """Represent the Windows console failure observed in upgrade CI."""

        raise UnicodeEncodeError("cp1252", "\u2588", 0, 1, "cannot encode")

    monkeypatch.setattr(
        managed_existing_setup_operations,
        "reconcile_managed_workspace_dependencies",
        fail_local_output,
    )

    with pytest.raises(UnicodeEncodeError):
        managed_install.ensure_managed_comfy_setup(workspace=tmp_path)
