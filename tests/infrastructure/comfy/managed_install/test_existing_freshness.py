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

"""Verify existing workspace freshness and explicit repair behavior."""

from __future__ import annotations

from __future__ import annotations
from collections.abc import Callable
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import cast
import pytest
from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.infrastructure.comfy import managed_install
from substitute.infrastructure.comfy import managed_existing_setup_operations
from substitute.infrastructure.comfy import managed_setup_freshness_cache
from substitute.infrastructure.comfy import managed_torch_reconciliation
from substitute.infrastructure.comfy.hardware_models import AcceleratorClass
from substitute.infrastructure.comfy.managed_validation import (
    workspace_python_path,
)
from substitute.infrastructure.comfy.torch_policy import TorchReleaseChannel

from .orchestration_support import (
    configure_managed_install,
    managed_setup_record_path,
)


def test_ensure_managed_comfy_setup_skips_fresh_installed_checks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Fresh setup evidence should bypass every recurring setup operation."""

    configure_managed_install(monkeypatch, tmp_path)

    python_path = workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    (python_path.parent.parent / "Lib" / "site-packages").mkdir(parents=True)
    (tmp_path / "main.py").write_text("main", encoding="utf-8")
    manager_dir = tmp_path / "custom_nodes" / "ComfyUI-Manager"
    manager_dir.mkdir(parents=True)
    (manager_dir / "cm-cli.py").write_text("cli", encoding="utf-8")

    calls: list[str] = []
    detection_calls: list[str] = []
    strategy_calls: list[str] = []
    refresh_targets: list[frozenset[CoreNodepackId]] = []
    strategy = SimpleNamespace(
        target=SimpleNamespace(value="windows_nvidia"),
        python_runtime=SimpleNamespace(
            executable=sys.executable,
            selected_version="3.13",
            used_fallback=False,
        ),
        comfy_channel=SimpleNamespace(value="latest"),
        torch_policy=SimpleNamespace(
            install_arguments=("torch-nightly",),
            backend_key="cuda_nightly_cu130",
            release_channel=TorchReleaseChannel.NIGHTLY,
            selection_reason="NVIDIA installs default to nightly torch.",
            fallback_backend_key="cuda_cu130",
            fallback_install_arguments=("torch",),
            fallback_release_channel=TorchReleaseChannel.STABLE,
            fallback_selection_reason="Nightly torch failed validation.",
            validation_expected=AcceleratorClass.NVIDIA,
        ),
        stability="experimental",
    )

    def _fake_detect_hardware() -> object:
        """Record hardware detection."""

        detection_calls.append("detect")
        return object()

    def _fake_select_install_strategy(**_kwargs: object) -> object:
        """Record install strategy selection."""

        strategy_calls.append("strategy")
        return strategy

    def _fake_provision_workspace_manager(
        workspace: Path,
        on_log: object | None = None,
        env: object | None = None,
    ) -> Path:
        """Record manager provisioning."""

        _ = on_log, env
        calls.append("manager")
        return workspace / "custom_nodes" / "ComfyUI-Manager" / "cm-cli.py"

    def _fake_ensure_core_comfy_nodepacks(
        workspace: Path,
        refresh_nodepacks: object = frozenset(),
        on_log: object | None = None,
        env: object | None = None,
    ) -> None:
        """Record nodepack reconciliation."""

        _ = workspace, on_log, env
        calls.append("nodepacks")
        refresh_targets.append(frozenset(cast(set[CoreNodepackId], refresh_nodepacks)))

    def _fake_sugarcubes_baseline(
        workspace: Path,
        on_log: object | None = None,
        env: object | None = None,
    ) -> bool:
        """Record SugarCubes baseline maintenance."""

        _ = workspace, on_log, env
        calls.append("sugarcubes")
        return True

    def _fake_validate(**_kwargs: object) -> SimpleNamespace:
        """Record torch validation."""

        calls.append("validate")
        return SimpleNamespace(
            success=True,
            detail="ok",
            detected_backend="nvidia",
            detected_torch_channel="nightly",
            torch_version="2.9.0.dev",
        )

    def _fake_acceleration(**_kwargs: object) -> None:
        """Record managed acceleration reconciliation."""

        calls.append("acceleration")

    monkeypatch.setattr(
        managed_existing_setup_operations,
        "detect_hardware",
        _fake_detect_hardware,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "select_install_strategy",
        _fake_select_install_strategy,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "ensure_managed_workspace_manager",
        _fake_provision_workspace_manager,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "ensure_core_comfy_nodepacks",
        _fake_ensure_core_comfy_nodepacks,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "attempt_sugarcubes_startup_maintenance",
        _fake_sugarcubes_baseline,
    )
    monkeypatch.setattr(
        managed_torch_reconciliation,
        "validate_managed_environment",
        _fake_validate,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "reconcile_managed_acceleration_stack",
        _fake_acceleration,
    )

    first = managed_install.ensure_managed_comfy_setup(workspace=tmp_path)
    second = managed_install.ensure_managed_comfy_setup(workspace=tmp_path)
    freshness_path = managed_setup_record_path(tmp_path)
    stale_payload = json.loads(freshness_path.read_text(encoding="utf-8"))
    acceleration_fingerprint = stale_payload["key"]["managed_acceleration"][
        "policy_fingerprint"
    ]
    assert isinstance(acceleration_fingerprint, str)
    assert len(acceleration_fingerprint) == 64
    stale_payload["schema_version"] = 1
    freshness_path.write_text(json.dumps(stale_payload), encoding="utf-8")
    revalidated = managed_install.ensure_managed_comfy_setup(workspace=tmp_path)
    refreshed = managed_install.ensure_managed_comfy_setup(
        workspace=tmp_path,
        refresh_core_nodepacks={CoreNodepackId.SUBSTITUTE_BACKEND},
    )

    assert first == python_path
    assert second == python_path
    assert revalidated == python_path
    assert refreshed == python_path
    assert calls == [
        "manager",
        "nodepacks",
        "sugarcubes",
        "validate",
        "acceleration",
        "manager",
        "nodepacks",
        "sugarcubes",
        "validate",
        "acceleration",
        "manager",
        "nodepacks",
        "sugarcubes",
        "validate",
        "acceleration",
    ]
    assert detection_calls == ["detect", "detect", "detect"]
    assert strategy_calls == ["strategy", "strategy", "strategy"]
    assert refresh_targets == [
        frozenset(),
        frozenset(),
        frozenset({CoreNodepackId.SUBSTITUTE_BACKEND}),
    ]


def test_existing_setup_repairs_torch_only_when_explicitly_authorized(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed probe must not mutate Torch outside an explicit repair flow."""

    configure_managed_install(monkeypatch, tmp_path)

    python_path = workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    (python_path.parent.parent / "Lib" / "site-packages").mkdir(parents=True)
    (tmp_path / "main.py").write_text("main", encoding="utf-8")
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "ensure_managed_workspace_manager",
        lambda workspace, on_log=None, env=None: workspace / "manager.py",
    )

    first = managed_install.ensure_managed_comfy_setup(workspace=tmp_path)
    repair_calls: list[Path] = []
    failed_validation = SimpleNamespace(
        success=False,
        detail="Torch device execution probe exited with 0xC0000005.",
        detected_backend=None,
        detected_torch_channel=None,
        torch_version=None,
        device_name=None,
    )
    repaired_validation = SimpleNamespace(
        success=True,
        detail="Managed workspace validation succeeded.",
        detected_backend="nvidia",
        detected_torch_channel="stable",
        torch_version="2.13.1+cu130",
        device_name="NVIDIA GeForce RTX 5090",
    )
    resolved_backend = SimpleNamespace(
        backend_key="cuda_cu130",
        release_channel=TorchReleaseChannel.STABLE,
        selection_reason="NVIDIA stable runtime.",
        fallback_used=False,
    )

    monkeypatch.setattr(
        managed_existing_setup_operations,
        "validate_existing_torch_backend",
        lambda **_kwargs: (resolved_backend, failed_validation),
    )

    def _repair_runtime(**kwargs: object) -> tuple[object, object]:
        """Record repair and return independently validated runtime evidence."""

        workspace = cast(Path, kwargs["workspace"])
        repair_calls.append(workspace)
        return resolved_backend, repaired_validation

    monkeypatch.setattr(
        managed_existing_setup_operations,
        "install_and_validate_selected_torch_backend",
        _repair_runtime,
    )

    freshness_path = managed_setup_record_path(tmp_path)
    stale_payload = json.loads(freshness_path.read_text(encoding="utf-8"))
    stale_payload["schema_version"] = 1
    freshness_path.write_text(json.dumps(stale_payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="0xC0000005"):
        managed_install.ensure_managed_comfy_setup(workspace=tmp_path)

    second = managed_install.ensure_managed_comfy_setup(
        workspace=tmp_path,
        repair_existing_runtime=True,
    )

    assert first == python_path
    assert second == python_path
    assert repair_calls == [tmp_path]
    freshness_payload = json.loads(freshness_path.read_text(encoding="utf-8"))
    assert freshness_payload["success"] is True
    assert freshness_payload["validation"]["torch_version"] == "2.13.1+cu130"


def test_ensure_managed_comfy_setup_retries_after_state_commit_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed success-state commit should leave reconciliation retryable."""

    configure_managed_install(monkeypatch, tmp_path)

    python_path = workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    (python_path.parent.parent / "Lib" / "site-packages").mkdir(parents=True)
    (tmp_path / "main.py").write_text("main", encoding="utf-8")
    manager_dir = tmp_path / "custom_nodes" / "ComfyUI-Manager"
    manager_dir.mkdir(parents=True)
    (manager_dir / "cm-cli.py").write_text("cli", encoding="utf-8")

    reconciliation_calls: list[str] = []

    def _record_sugarcubes_maintenance(
        workspace: Path,
        on_log: object | None = None,
        env: object | None = None,
    ) -> object:
        """Record one successful SugarCubes maintenance result."""

        _ = workspace, on_log, env
        reconciliation_calls.append("sugarcubes")
        return object()

    monkeypatch.setattr(
        managed_existing_setup_operations,
        "ensure_managed_workspace_manager",
        lambda workspace, on_log=None, env=None: manager_dir / "cm-cli.py",
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "ensure_core_comfy_nodepacks",
        lambda workspace, refresh_nodepacks=frozenset(), on_log=None, env=None: (
            reconciliation_calls.append("nodepacks")
        ),
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "attempt_sugarcubes_startup_maintenance",
        _record_sugarcubes_maintenance,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "reconcile_managed_acceleration_stack",
        lambda **kwargs: reconciliation_calls.append("acceleration"),
    )

    atomic_write = cast(
        "Callable[[Path, dict[str, object]], None]",
        getattr(managed_setup_freshness_cache, "write_json_object_atomic"),
    )
    commit_attempts = 0

    def _fail_first_state_commit(path: Path, payload: dict[str, object]) -> None:
        """Fail once before delegating later commits to the atomic writer."""

        nonlocal commit_attempts
        commit_attempts += 1
        if commit_attempts == 1:
            raise OSError("injected state commit failure")
        atomic_write(path, payload)

    monkeypatch.setattr(
        managed_setup_freshness_cache,
        "write_json_object_atomic",
        _fail_first_state_commit,
    )

    with pytest.raises(OSError, match="injected state commit failure"):
        managed_install.ensure_managed_comfy_setup(workspace=tmp_path)

    freshness_path = managed_setup_record_path(tmp_path)
    assert not freshness_path.exists()

    retried = managed_install.ensure_managed_comfy_setup(workspace=tmp_path)
    cached = managed_install.ensure_managed_comfy_setup(workspace=tmp_path)

    assert retried == python_path
    assert cached == python_path
    assert commit_attempts == 2
    assert reconciliation_calls == [
        "nodepacks",
        "sugarcubes",
        "acceleration",
        "nodepacks",
        "sugarcubes",
        "acceleration",
    ]
