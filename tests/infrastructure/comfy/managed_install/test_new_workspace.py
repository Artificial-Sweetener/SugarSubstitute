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

"""Verify new managed workspace provisioning and backend fallback behavior."""

from __future__ import annotations

from __future__ import annotations
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
from substitute.infrastructure.comfy import managed_install
from substitute.infrastructure.comfy import managed_torch_reconciliation
from substitute.infrastructure.comfy import managed_workspace_provisioning
from substitute.infrastructure.comfy.hardware_models import AcceleratorClass
from substitute.infrastructure.comfy.managed_validation import (
    workspace_main_path,
    workspace_python_path,
)
from substitute.infrastructure.comfy.torch_policy import TorchReleaseChannel
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneVariantId,
)
from sugarsubstitute_shared.external_scratch import ExternalScratchWorkspace

from .orchestration_support import (
    configure_managed_install,
)


def test_ensure_managed_comfy_setup_installs_and_marks_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Missing managed workspaces should install explicit backend and requirements."""

    configure_managed_install(monkeypatch, tmp_path)

    install_steps: list[str] = []
    provision_calls: list[Path] = []
    repo_sync_calls: list[Path] = []

    workspace_python = workspace_python_path(tmp_path)

    def _fake_sync_workspace(
        workspace: Path,
        on_log: object | None = None,
        env: object | None = None,
    ) -> None:
        _ = on_log, env
        workspace.mkdir(parents=True, exist_ok=True)
        workspace_main_path(workspace).write_text("main", encoding="utf-8")
        repo_sync_calls.append(workspace)

    monkeypatch.setattr(
        managed_workspace_provisioning,
        "sync_managed_workspace_repository",
        _fake_sync_workspace,
    )

    def _fake_ensure_workspace_virtualenv(
        workspace: Path,
        *,
        python_runtime: str | None = None,
        on_log: object | None = None,
        env: object | None = None,
    ) -> Path:
        _ = workspace, python_runtime, on_log, env
        workspace_python.parent.mkdir(parents=True, exist_ok=True)
        workspace_python.write_text("", encoding="utf-8")
        return workspace_python

    monkeypatch.setattr(
        managed_workspace_provisioning,
        "ensure_workspace_virtualenv",
        _fake_ensure_workspace_virtualenv,
    )
    monkeypatch.setattr(
        managed_workspace_provisioning,
        "upgrade_workspace_packaging_tools",
        lambda python_executable, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_workspace_provisioning,
        "install_selected_torch_backend",
        lambda python_executable, *, install_arguments, on_log=None, env=None: (
            install_steps.append("torch")
        ),
    )
    monkeypatch.setattr(
        managed_workspace_provisioning,
        "install_workspace_requirements",
        lambda python_executable, *, workspace, on_log=None, env=None: (
            install_steps.append("requirements")
        ),
    )

    def _fake_provision_workspace_manager(
        workspace: Path,
        on_log: object | None = None,
        env: object | None = None,
    ) -> Path:
        _ = on_log, env
        provision_calls.append(workspace)
        return workspace / "custom_nodes" / "ComfyUI-Manager" / "cm-cli.py"

    monkeypatch.setattr(
        managed_install,
        "ensure_managed_workspace_manager",
        _fake_provision_workspace_manager,
    )

    scratch_root = (
        tmp_path.parent
        / f"{tmp_path.name}-runtime"
        / "installer-temp"
        / "managed-comfy"
        / "tx-success"
    )
    scratch_root.parent.mkdir(parents=True)
    monkeypatch.setattr(
        managed_install,
        "allocate_managed_install_scratch",
        lambda _workspace: ExternalScratchWorkspace.reserve(scratch_root),
    )
    result = managed_install.ensure_managed_comfy_setup(workspace=tmp_path)

    assert result == workspace_python
    assert install_steps == ["torch", "requirements"]
    assert repo_sync_calls == [tmp_path]
    assert provision_calls == [tmp_path]
    assert not (tmp_path / ".comfy_installed").exists()
    assert workspace_main_path(tmp_path).exists()
    assert not scratch_root.exists()


def test_new_stable_workspace_uses_verified_standalone_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The stable first-run path should skip dynamic Python and torch assembly."""

    configure_managed_install(monkeypatch, tmp_path)

    workspace_python = workspace_python_path(tmp_path)
    provisioned: list[StandaloneVariantId] = []
    trace_events: list[str] = []

    class _TraceSpan:
        """Record deterministic new-workspace span entry and exit events."""

        def __init__(self, name: str) -> None:
            self._name = name

        def __enter__(self) -> None:
            trace_events.append(f"span:start:{self._name}")

        def __exit__(self, *_exc: object) -> None:
            trace_events.append(f"span:end:{self._name}")

    monkeypatch.setattr(
        managed_install,
        "trace_mark",
        lambda event, **_fields: trace_events.append(f"mark:{event}"),
    )
    monkeypatch.setattr(
        managed_install,
        "trace_span",
        lambda event, **_fields: _TraceSpan(event),
    )
    strategy = SimpleNamespace(
        target=SimpleNamespace(value="windows_nvidia"),
        python_runtime=SimpleNamespace(
            executable=sys.executable,
            selected_version="3.13",
            used_fallback=False,
        ),
        comfy_channel=SimpleNamespace(value="latest"),
        torch_policy=SimpleNamespace(
            install_arguments=("torch",),
            backend_key="cuda_cu130",
            release_channel=TorchReleaseChannel.STABLE,
            selection_reason="Verified standalone environment.",
            fallback_backend_key="cuda_nightly_cu132",
            fallback_install_arguments=("torch-nightly",),
            fallback_release_channel=TorchReleaseChannel.NIGHTLY,
            fallback_selection_reason="Fallback nightly.",
            validation_expected=AcceleratorClass.NVIDIA,
        ),
        standalone_variant=StandaloneVariantId.WINDOWS_NVIDIA,
        stability="stable",
    )
    monkeypatch.setattr(
        managed_install,
        "select_install_strategy",
        lambda **kwargs: strategy,
    )

    def fake_standalone_provision(
        workspace: Path,
        *,
        variant: StandaloneVariantId,
        on_log: object | None = None,
    ) -> Path:
        """Materialize the verified environment boundary for orchestration testing."""

        del on_log
        provisioned.append(variant)
        workspace_main_path(workspace).parent.mkdir(parents=True, exist_ok=True)
        workspace_main_path(workspace).write_text("main", encoding="utf-8")
        workspace_python.parent.mkdir(parents=True, exist_ok=True)
        workspace_python.write_text("", encoding="utf-8")
        return workspace_python

    monkeypatch.setattr(
        managed_install,
        "provision_verified_standalone_workspace",
        fake_standalone_provision,
    )
    monkeypatch.setattr(
        managed_install,
        "prepare_dynamic_workspace_environment",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError(f"Unexpected dynamic provisioning: {kwargs}")
        ),
    )
    monkeypatch.setattr(
        managed_install,
        "ensure_managed_workspace_manager",
        lambda workspace, on_log=None, env=None: (
            workspace / "custom_nodes" / "ComfyUI-Manager" / "cm-cli.py"
        ),
    )

    result = managed_install.ensure_managed_comfy_setup(workspace=tmp_path)

    assert result == workspace_python
    assert provisioned == [StandaloneVariantId.WINDOWS_NVIDIA]
    assert trace_events == [
        "span:start:managed_setup.scratch.create",
        "span:end:managed_setup.scratch.create",
        "mark:managed_setup.detect_hardware.start",
        "span:start:managed_setup.detect_hardware",
        "span:end:managed_setup.detect_hardware",
        "span:start:managed_setup.select_install_strategy",
        "span:end:managed_setup.select_install_strategy",
        "mark:managed_setup.standalone_workspace.start",
        "span:start:managed_setup.standalone_workspace",
        "span:end:managed_setup.standalone_workspace",
        "mark:managed_setup.manager.start",
        "span:start:managed_setup.manager",
        "span:end:managed_setup.manager",
        "mark:managed_setup.nodepacks.start",
        "span:start:managed_setup.nodepacks",
        "span:end:managed_setup.nodepacks",
        "mark:managed_setup.sugarcubes_baseline.start",
        "span:start:managed_setup.sugarcubes_baseline",
        "span:end:managed_setup.sugarcubes_baseline",
        "mark:managed_setup.torch_validation.start",
        "span:start:managed_setup.torch_validation",
        "span:end:managed_setup.torch_validation",
        "mark:managed_setup.acceleration.start",
        "span:start:managed_setup.acceleration",
        "span:end:managed_setup.acceleration",
        "mark:managed_setup.freshness_receipt.start",
        "span:start:managed_setup.freshness_receipt",
        "span:end:managed_setup.freshness_receipt",
        "span:start:managed_setup.scratch.cleanup",
        "span:end:managed_setup.scratch.cleanup",
    ]


def test_ensure_managed_comfy_setup_falls_back_to_stable_when_nightly_validation_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed install should retry the stable torch backend when nightly fails validation."""

    configure_managed_install(monkeypatch, tmp_path)

    workspace_python = workspace_python_path(tmp_path)
    install_arguments_seen: list[tuple[str, ...]] = []

    def _fake_sync_workspace(
        workspace: Path,
        on_log: object | None = None,
        env: object | None = None,
    ) -> None:
        _ = on_log, env
        workspace.mkdir(parents=True, exist_ok=True)
        workspace_main_path(workspace).write_text("main", encoding="utf-8")

    monkeypatch.setattr(
        managed_workspace_provisioning,
        "sync_managed_workspace_repository",
        _fake_sync_workspace,
    )

    def _fake_ensure_workspace_virtualenv(
        workspace: Path,
        *,
        python_runtime: str | None = None,
        on_log: object | None = None,
        env: object | None = None,
    ) -> Path:
        _ = workspace, python_runtime, on_log, env
        workspace_python.parent.mkdir(parents=True, exist_ok=True)
        workspace_python.write_text("", encoding="utf-8")
        return workspace_python

    monkeypatch.setattr(
        managed_workspace_provisioning,
        "ensure_workspace_virtualenv",
        _fake_ensure_workspace_virtualenv,
    )
    monkeypatch.setattr(
        managed_workspace_provisioning,
        "upgrade_workspace_packaging_tools",
        lambda python_executable, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_workspace_provisioning,
        "install_selected_torch_backend",
        lambda python_executable, *, install_arguments, on_log=None, env=None: (
            install_arguments_seen.append(tuple(install_arguments))
        ),
    )
    monkeypatch.setattr(
        managed_torch_reconciliation,
        "install_selected_torch_backend",
        lambda python_executable, *, install_arguments, on_log=None, env=None: (
            install_arguments_seen.append(tuple(install_arguments))
        ),
    )
    monkeypatch.setattr(
        managed_workspace_provisioning,
        "install_workspace_requirements",
        lambda python_executable, *, workspace, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_install,
        "ensure_managed_workspace_manager",
        lambda workspace, on_log=None, env=None: (
            workspace / "custom_nodes" / "ComfyUI-Manager" / "cm-cli.py"
        ),
    )
    validations = iter(
        (
            SimpleNamespace(
                success=False,
                detail="nightly failed",
                detected_torch_channel="nightly",
            ),
            SimpleNamespace(
                success=True,
                detail="ok",
                detected_torch_channel="stable",
            ),
        )
    )
    monkeypatch.setattr(
        managed_torch_reconciliation,
        "validate_managed_environment",
        lambda **kwargs: next(validations),
    )

    result = managed_install.ensure_managed_comfy_setup(
        workspace=tmp_path,
    )

    assert result == workspace_python
    assert install_arguments_seen == [("torch-nightly",), ("torch",)]


def test_ensure_managed_comfy_setup_accepts_owned_model_paths_bootstrap_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Owned model-path config should not make a fresh managed workspace dirty."""

    configure_managed_install(monkeypatch, tmp_path)

    (tmp_path / "extra_model_paths.yaml").write_text(
        "substitute_shared_models:\n  base_path: E:/models\n",
        encoding="utf-8",
    )
    workspace_python = workspace_python_path(tmp_path)
    repo_sync_calls: list[Path] = []
    model_root_calls: list[tuple[Path, Path, Path | None]] = []

    def _fake_sync_workspace(
        workspace: Path,
        on_log: object | None = None,
        env: object | None = None,
    ) -> None:
        _ = on_log, env
        workspace.mkdir(parents=True, exist_ok=True)
        workspace_main_path(workspace).write_text("main", encoding="utf-8")
        repo_sync_calls.append(workspace)

    monkeypatch.setattr(
        managed_workspace_provisioning,
        "sync_managed_workspace_repository",
        _fake_sync_workspace,
    )

    def _fake_ensure_workspace_virtualenv(
        workspace: Path,
        *,
        python_runtime: str | None = None,
        on_log: object | None = None,
        env: object | None = None,
    ) -> Path:
        _ = workspace, python_runtime, on_log, env
        workspace_python.parent.mkdir(parents=True, exist_ok=True)
        workspace_python.write_text("", encoding="utf-8")
        return workspace_python

    monkeypatch.setattr(
        managed_workspace_provisioning,
        "ensure_workspace_virtualenv",
        _fake_ensure_workspace_virtualenv,
    )
    monkeypatch.setattr(
        managed_workspace_provisioning,
        "upgrade_workspace_packaging_tools",
        lambda python_executable, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_workspace_provisioning,
        "install_selected_torch_backend",
        lambda python_executable, *, install_arguments, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_workspace_provisioning,
        "install_workspace_requirements",
        lambda python_executable, *, workspace, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_install,
        "ensure_managed_workspace_manager",
        lambda workspace, on_log=None, env=None: (
            workspace / "custom_nodes" / "ComfyUI-Manager" / "cm-cli.py"
        ),
    )
    monkeypatch.setattr(
        managed_install,
        "configure_backend_model_root",
        lambda *, workspace, python_executable, model_root: model_root_calls.append(
            (workspace, python_executable, model_root)
        ),
    )

    result = managed_install.ensure_managed_comfy_setup(
        workspace=tmp_path,
        managed_model_root=tmp_path / "models",
        configure_model_root=True,
    )

    assert result == workspace_python
    assert repo_sync_calls == [tmp_path]
    assert model_root_calls == [(tmp_path, workspace_python, tmp_path / "models")]
    assert workspace_main_path(tmp_path).exists()
