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

"""Tests for managed-local Comfy installation orchestration."""

from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import cast

import pytest

from substitute.application.onboarding.managed_runtime_service import (
    ManagedRuntimeService,
)
from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.infrastructure.comfy import managed_install
from substitute.infrastructure.comfy import managed_install_commands
from substitute.infrastructure.comfy import managed_install_failures
from substitute.infrastructure.comfy import managed_install_scratch
from substitute.infrastructure.comfy import managed_workspace_operations
from substitute.infrastructure.comfy.hardware_models import AcceleratorClass
from substitute.infrastructure.comfy.managed_validation import (
    workspace_main_path,
    workspace_nested_main_path,
    workspace_python_path,
)
from substitute.infrastructure.comfy.torch_policy import TorchReleaseChannel
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneVariantId,
)
from tests.repository_service_test_double import RecordingRepositoryService
from sugarsubstitute_shared.windows_long_paths import subprocess_path


@pytest.fixture(autouse=True)
def _disable_shared_models_link(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable explicit shared-model configuration for isolated setup tests."""

    monkeypatch.delenv("SUGARSUB_SHARED_MODELS_ROOT", raising=False)
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
        standalone_variant=None,
        stability="experimental",
    )
    monkeypatch.setattr(managed_install, "detect_hardware", lambda: object())
    monkeypatch.setattr(
        managed_install,
        "select_install_strategy",
        lambda **kwargs: strategy,
    )
    monkeypatch.setattr(
        ManagedRuntimeService,
        "detect_and_select",
        lambda self, **kwargs: SimpleNamespace(
            detected_platform="windows",
            detected_accelerator="nvidia",
            install_target="windows_nvidia",
            python_version="3.13",
            comfy_channel="latest",
            backend_policy="cuda_nightly_cu130",
            torch_release_channel="nightly",
            torch_selection_reason="NVIDIA installs default to nightly torch.",
            stability=SimpleNamespace(value="experimental"),
        ),
    )
    monkeypatch.setattr(
        managed_install,
        "validate_managed_environment",
        lambda **kwargs: SimpleNamespace(
            success=True,
            detail="ok",
            detected_torch_channel="nightly",
        ),
    )
    monkeypatch.setattr(
        ManagedRuntimeService,
        "record_validation",
        lambda self, **kwargs: None,
    )
    monkeypatch.setattr(
        ManagedRuntimeService,
        "record_torch_resolution",
        lambda self, **kwargs: None,
    )
    monkeypatch.setattr(
        managed_install,
        "ensure_core_comfy_nodepacks",
        lambda workspace, refresh_nodepacks=frozenset(), on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_install,
        "run_sugarcubes_baseline_maintenance",
        lambda workspace, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_install,
        "reconcile_managed_acceleration_stack",
        lambda **kwargs: None,
    )


def test_ensure_managed_comfy_setup_reuses_installed_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Installed managed workspaces should skip reinstall and refresh the manager."""

    python_path = workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    (tmp_path / "main.py").write_text("main", encoding="utf-8")
    provision_calls: list[Path] = []
    refresh_targets: list[frozenset[CoreNodepackId]] = []
    trace_events: list[str] = []

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
    ) -> Path:
        _ = on_log, env
        provision_calls.append(workspace)
        return workspace / "custom_nodes" / "ComfyUI-Manager" / "cm-cli.py"

    monkeypatch.setattr(
        managed_install,
        "trace_span",
        trace_span,
    )
    monkeypatch.setattr(
        managed_install,
        "provision_workspace_manager",
        _fake_provision_workspace_manager,
    )
    monkeypatch.setattr(
        managed_install,
        "ensure_core_comfy_nodepacks",
        lambda workspace, refresh_nodepacks=frozenset(), on_log=None, env=None: (
            refresh_targets.append(frozenset(refresh_nodepacks))
        ),
    )

    result = managed_install.ensure_managed_comfy_setup(
        workspace=tmp_path,
        refresh_core_nodepacks={CoreNodepackId.SUBSTITUTE_BACKEND},
    )

    assert result == python_path
    assert provision_calls == [tmp_path]
    assert refresh_targets == [frozenset({CoreNodepackId.SUBSTITUTE_BACKEND})]
    assert trace_events == [
        "span:start:managed_setup.scratch.create",
        "span:end:managed_setup.scratch.create",
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
        "span:start:managed_setup.existing.validate_torch",
        "span:end:managed_setup.existing.validate_torch",
        "span:start:managed_setup.existing.acceleration",
        "span:end:managed_setup.existing.acceleration",
        "span:start:managed_setup.scratch.cleanup",
        "span:end:managed_setup.scratch.cleanup",
    ]


def test_ensure_managed_comfy_setup_skips_fresh_installed_checks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Fresh installed-workspace evidence should skip repeated setup checks."""

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
    ) -> None:
        """Record SugarCubes baseline maintenance."""

        _ = workspace, on_log, env
        calls.append("sugarcubes")

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

    monkeypatch.setattr(managed_install, "detect_hardware", _fake_detect_hardware)
    monkeypatch.setattr(
        managed_install,
        "select_install_strategy",
        _fake_select_install_strategy,
    )
    monkeypatch.setattr(
        managed_install,
        "provision_workspace_manager",
        _fake_provision_workspace_manager,
    )
    monkeypatch.setattr(
        managed_install,
        "ensure_core_comfy_nodepacks",
        _fake_ensure_core_comfy_nodepacks,
    )
    monkeypatch.setattr(
        managed_install,
        "run_sugarcubes_baseline_maintenance",
        _fake_sugarcubes_baseline,
    )
    monkeypatch.setattr(
        managed_install,
        "validate_managed_environment",
        _fake_validate,
    )
    monkeypatch.setattr(
        managed_install,
        "reconcile_managed_acceleration_stack",
        _fake_acceleration,
    )

    first = managed_install.ensure_managed_comfy_setup(workspace=tmp_path)
    second = managed_install.ensure_managed_comfy_setup(workspace=tmp_path)
    freshness_path = tmp_path / ".substitute" / "managed_setup_freshness.json"
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


def test_ensure_workspace_virtualenv_creates_workspace_python(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed install should create the workspace-local virtualenv explicitly."""

    observed: list[list[str]] = []
    venv_python = workspace_python_path(tmp_path)

    def _fake_stream_command(
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        on_line: Callable[[str], None] | None = None,
        creationflags: int = 0,
    ) -> int:
        _ = cwd, env, on_line, creationflags
        observed.append(command)
        venv_python.parent.mkdir(parents=True, exist_ok=True)
        venv_python.write_text("", encoding="utf-8")
        return 0

    monkeypatch.setattr(
        managed_install_commands, "stream_command", _fake_stream_command
    )

    result = managed_install_commands.ensure_workspace_virtualenv(tmp_path)

    assert result == venv_python
    assert observed == [
        [sys.executable, "-m", "venv", subprocess_path(tmp_path / ".venv")]
    ]


def test_pip_install_raises_when_streamed_install_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Streamed pip installs should fail closed on non-zero exit codes."""

    monkeypatch.setattr(
        managed_install_commands,
        "stream_command",
        lambda *args, **kwargs: 1,
    )

    with pytest.raises(RuntimeError):
        managed_install_commands.pip_install(
            tmp_path / "python.exe",
            "comfy-cli",
            on_log=lambda message: None,
        )


def test_managed_install_scratch_routes_temp_and_cache_under_root(
    tmp_path: Path,
) -> None:
    """Managed install scratch should keep temp and pip cache under its run root."""

    scratch_root = tmp_path / "runtime" / "installer-temp" / "managed-comfy" / "tx-1"
    scratch = managed_install_scratch.ManagedInstallScratch(scratch_root)

    scratch.create()
    env = scratch.apply_to({"PATH": "C:\\Tools"})

    assert env["TEMP"] == str(scratch_root / "temp")
    assert env["TMP"] == str(scratch_root / "temp")
    assert env["PIP_CACHE_DIR"] == str(scratch_root / "pip-cache")
    assert env["PIP_DISABLE_PIP_VERSION_CHECK"] == "1"
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8:replace"
    assert env["PATH"] == "C:\\Tools"
    assert scratch.temp_dir.is_dir()
    assert scratch.pip_cache_dir.is_dir()

    scratch.cleanup()

    assert not scratch_root.exists()


def test_pip_install_classifies_storage_failure_and_keeps_managed_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Pip storage errors should not be reported as generic package failures."""

    observed_env: list[dict[str, str] | None] = []
    managed_env = {"TEMP": str(tmp_path / "temp")}

    def _fake_stream_command(
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        on_line: Callable[[str], None] | None = None,
        creationflags: int = 0,
    ) -> int:
        _ = command, cwd, creationflags
        observed_env.append(env)
        assert callable(on_line)
        on_line("OSError: [Errno 28] No space left on device")
        return 1

    monkeypatch.setattr(
        managed_install_commands, "stream_command", _fake_stream_command
    )

    with pytest.raises(managed_install_failures.ManagedInstallStorageError):
        managed_install_commands.pip_install(
            tmp_path / ".venv" / "Scripts" / "python.exe",
            "torch",
            on_log=lambda _message: None,
            env=managed_env,
        )

    assert observed_env == [managed_env]


def test_ensure_workspace_virtualenv_uses_managed_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Workspace venv creation should inherit install-root temp/cache routing."""

    observed_env: list[dict[str, str] | None] = []
    managed_env = {"TEMP": str(tmp_path / "temp")}
    venv_python = workspace_python_path(tmp_path)

    def _fake_stream_command(
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        on_line: Callable[[str], None] | None = None,
        creationflags: int = 0,
    ) -> int:
        _ = command, cwd, on_line, creationflags
        observed_env.append(env)
        venv_python.parent.mkdir(parents=True, exist_ok=True)
        venv_python.write_text("", encoding="utf-8")
        return 0

    monkeypatch.setattr(
        managed_install_commands, "stream_command", _fake_stream_command
    )

    result = managed_install_commands.ensure_workspace_virtualenv(
        tmp_path, env=managed_env
    )

    assert result == venv_python
    assert observed_env == [managed_env]


def test_ensure_managed_comfy_setup_cleans_scratch_after_clone_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed setup should delete scratch files even when provisioning fails."""

    monkeypatch.setenv("SUGARSUB_FORCE_MANAGED_FAILURE_STAGE", "clone")
    scratch_root = tmp_path / "runtime" / "installer-temp" / "managed-comfy" / "tx-2"

    with pytest.raises(RuntimeError, match="download ComfyUI"):
        managed_install.ensure_managed_comfy_setup(
            workspace=tmp_path / "comfyui",
            installer_temp_root=scratch_root,
        )

    assert not scratch_root.exists()


def test_ensure_managed_comfy_setup_keeps_original_failure_when_cleanup_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Scratch cleanup warnings should not replace the real provisioning error."""

    monkeypatch.setenv("SUGARSUB_FORCE_MANAGED_FAILURE_STAGE", "clone")

    def _raise_cleanup_error(
        self: managed_install_scratch.ManagedInstallScratch,
    ) -> None:
        _ = self
        raise RuntimeError("cleanup failed")

    monkeypatch.setattr(
        managed_install_scratch.ManagedInstallScratch,
        "cleanup",
        _raise_cleanup_error,
    )

    with pytest.raises(RuntimeError, match="download ComfyUI"):
        managed_install.ensure_managed_comfy_setup(
            workspace=tmp_path / "comfyui",
            installer_temp_root=tmp_path
            / "runtime"
            / "installer-temp"
            / "managed-comfy"
            / "tx-cleanup",
        )


def test_ensure_managed_comfy_setup_does_not_fallback_after_storage_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Torch fallback should not run when preferred install exhausts storage."""

    workspace = tmp_path / "comfyui"
    workspace_python = workspace_python_path(workspace)
    install_attempts: list[tuple[str, ...]] = []

    def _fake_sync_workspace(
        workspace: Path,
        on_log: object | None = None,
        env: object | None = None,
    ) -> None:
        _ = on_log, env
        workspace.mkdir(parents=True, exist_ok=True)
        workspace_main_path(workspace).write_text("main", encoding="utf-8")

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

    def _raise_storage_error(
        python_executable: Path,
        *,
        install_arguments: tuple[str, ...],
        on_log: object | None = None,
        env: object | None = None,
    ) -> None:
        _ = python_executable, on_log, env
        install_attempts.append(tuple(install_arguments))
        raise managed_install_failures.ManagedInstallStorageError(
            "No space left on device"
        )

    monkeypatch.setattr(
        managed_install,
        "sync_managed_workspace_repository",
        _fake_sync_workspace,
    )
    monkeypatch.setattr(
        managed_install,
        "ensure_workspace_virtualenv",
        _fake_ensure_workspace_virtualenv,
    )
    monkeypatch.setattr(
        managed_install,
        "upgrade_workspace_packaging_tools",
        lambda python_executable, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_install,
        "install_selected_torch_backend",
        _raise_storage_error,
    )

    with pytest.raises(managed_install_failures.ManagedInstallStorageError):
        managed_install.ensure_managed_comfy_setup(
            workspace=workspace,
            installer_temp_root=tmp_path
            / "runtime"
            / "installer-temp"
            / "managed-comfy"
            / "tx-3",
        )

    assert install_attempts == [("torch-nightly",)]


def test_ensure_managed_comfy_setup_installs_and_marks_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Missing managed workspaces should install explicit backend and requirements."""

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
        managed_install,
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
        managed_install,
        "ensure_workspace_virtualenv",
        _fake_ensure_workspace_virtualenv,
    )
    monkeypatch.setattr(
        managed_install,
        "upgrade_workspace_packaging_tools",
        lambda python_executable, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_install,
        "install_selected_torch_backend",
        lambda python_executable, *, install_arguments, on_log=None, env=None: (
            install_steps.append("torch")
        ),
    )
    monkeypatch.setattr(
        managed_install,
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
        "provision_workspace_manager",
        _fake_provision_workspace_manager,
    )

    scratch_root = (
        tmp_path.parent
        / f"{tmp_path.name}-runtime"
        / "installer-temp"
        / "managed-comfy"
        / "tx-success"
    )
    result = managed_install.ensure_managed_comfy_setup(
        workspace=tmp_path,
        installer_temp_root=scratch_root,
    )

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

    workspace_python = workspace_python_path(tmp_path)
    provisioned: list[StandaloneVariantId] = []
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
        "provision_workspace_manager",
        lambda workspace, on_log=None, env=None: (
            workspace / "custom_nodes" / "ComfyUI-Manager" / "cm-cli.py"
        ),
    )

    result = managed_install.ensure_managed_comfy_setup(workspace=tmp_path)

    assert result == workspace_python
    assert provisioned == [StandaloneVariantId.WINDOWS_NVIDIA]


def test_ensure_managed_comfy_setup_falls_back_to_stable_when_nightly_validation_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed install should retry the stable torch backend when nightly fails validation."""

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
        managed_install,
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
        managed_install,
        "ensure_workspace_virtualenv",
        _fake_ensure_workspace_virtualenv,
    )
    monkeypatch.setattr(
        managed_install,
        "upgrade_workspace_packaging_tools",
        lambda python_executable, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_install,
        "install_selected_torch_backend",
        lambda python_executable, *, install_arguments, on_log=None, env=None: (
            install_arguments_seen.append(tuple(install_arguments))
        ),
    )
    monkeypatch.setattr(
        managed_install,
        "install_workspace_requirements",
        lambda python_executable, *, workspace, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_install,
        "provision_workspace_manager",
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
        managed_install,
        "validate_managed_environment",
        lambda **kwargs: next(validations),
    )

    result = managed_install.ensure_managed_comfy_setup(
        workspace=tmp_path,
    )

    assert result == workspace_python
    assert install_arguments_seen == [("torch-nightly",), ("torch",)]


def test_ensure_managed_comfy_setup_removes_incomplete_workspace_before_install(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Leftover bootstrap artifacts should be cleared before explicit install steps."""

    stale_python = workspace_python_path(tmp_path)
    stale_python.parent.mkdir(parents=True, exist_ok=True)
    stale_python.write_text("", encoding="utf-8")

    new_python = workspace_python_path(tmp_path)
    repo_sync_calls: list[Path] = []

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
        managed_install,
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
        new_python.parent.mkdir(parents=True, exist_ok=True)
        new_python.write_text("", encoding="utf-8")
        return new_python

    monkeypatch.setattr(
        managed_install,
        "ensure_workspace_virtualenv",
        _fake_ensure_workspace_virtualenv,
    )
    monkeypatch.setattr(
        managed_install,
        "upgrade_workspace_packaging_tools",
        lambda python_executable, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_install,
        "install_selected_torch_backend",
        lambda python_executable, *, install_arguments, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_install,
        "install_workspace_requirements",
        lambda python_executable, *, workspace, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_install,
        "provision_workspace_manager",
        lambda workspace, on_log=None, env=None: (
            workspace / "custom_nodes" / "ComfyUI-Manager" / "cm-cli.py"
        ),
    )

    result = managed_install.ensure_managed_comfy_setup(
        workspace=tmp_path,
    )

    assert result == new_python
    assert repo_sync_calls == [tmp_path]


def test_ensure_managed_comfy_setup_accepts_owned_model_paths_bootstrap_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Owned model-path config should not make a fresh managed workspace dirty."""

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
        managed_install,
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
        managed_install,
        "ensure_workspace_virtualenv",
        _fake_ensure_workspace_virtualenv,
    )
    monkeypatch.setattr(
        managed_install,
        "upgrade_workspace_packaging_tools",
        lambda python_executable, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_install,
        "install_selected_torch_backend",
        lambda python_executable, *, install_arguments, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_install,
        "install_workspace_requirements",
        lambda python_executable, *, workspace, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_install,
        "provision_workspace_manager",
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


def test_ensure_managed_comfy_setup_rejects_nonempty_unmanaged_workspace(
    tmp_path: Path,
) -> None:
    """Managed install should fail closed when the selected folder already has unrelated files."""

    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "notes.txt").write_text("unexpected", encoding="utf-8")

    with pytest.raises(RuntimeError, match="already contains files"):
        managed_install.ensure_managed_comfy_setup(
            workspace=tmp_path,
        )


def test_ensure_managed_comfy_setup_migrates_legacy_nested_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Legacy nested managed installs should migrate into the canonical workspace root."""

    python_path = workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    (tmp_path / ".comfy_installed").write_text("ok", encoding="utf-8")
    nested_main = workspace_nested_main_path(tmp_path)
    nested_main.parent.mkdir(parents=True, exist_ok=True)
    nested_main.write_text("main", encoding="utf-8")

    monkeypatch.setattr(
        managed_install,
        "provision_workspace_manager",
        lambda workspace, on_log=None, env=None: (
            workspace / "custom_nodes" / "ComfyUI-Manager" / "cm-cli.py"
        ),
    )

    result = managed_install.ensure_managed_comfy_setup(
        workspace=tmp_path,
    )

    assert result == python_path
    assert workspace_main_path(tmp_path).exists()
    assert not (tmp_path / "ComfyUI").exists()


def test_clone_managed_workspace_honors_forced_failure_stage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed install should support deterministic clone-failure injection."""

    monkeypatch.setenv("SUGARSUB_FORCE_MANAGED_FAILURE_STAGE", "clone")

    with pytest.raises(RuntimeError, match="couldn't download ComfyUI"):
        managed_workspace_operations.clone_managed_workspace(tmp_path)


def test_clone_managed_workspace_uses_self_contained_repository_service(
    tmp_path: Path,
) -> None:
    """Managed Comfy cloning should not route through process execution."""

    repositories = RecordingRepositoryService()

    managed_workspace_operations.clone_managed_workspace(
        tmp_path, repositories=repositories
    )

    assert repositories.calls == [
        (
            "clone",
            ("https://github.com/comfyanonymous/ComfyUI.git", tmp_path),
        )
    ]


def test_sync_managed_workspace_uses_self_contained_fast_forward(
    tmp_path: Path,
) -> None:
    """Managed Comfy updates should delegate one fail-closed fast-forward."""

    (tmp_path / ".git").mkdir(parents=True)
    repositories = RecordingRepositoryService()

    managed_workspace_operations.sync_managed_workspace_repository(
        tmp_path,
        repositories=repositories,
    )

    assert repositories.calls == [("sync_fast_forward", tmp_path)]


def test_ensure_managed_comfy_setup_honors_dependency_failure_stage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed install should fail during the comfy-cli install stage when injected."""

    monkeypatch.setenv("SUGARSUB_FORCE_MANAGED_FAILURE_STAGE", "dependency_install")

    def _fake_clone_workspace(
        workspace: Path,
        on_log: object | None = None,
        env: object | None = None,
    ) -> None:
        _ = on_log, env
        workspace.mkdir(parents=True, exist_ok=True)
        workspace_main_path(workspace).write_text("main", encoding="utf-8")

    workspace_python = workspace_python_path(tmp_path)

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
        managed_install,
        "sync_managed_workspace_repository",
        lambda workspace, on_log=None, env=None: _fake_clone_workspace(
            workspace,
            on_log,
            env,
        ),
    )
    monkeypatch.setattr(
        managed_install,
        "ensure_workspace_virtualenv",
        _fake_ensure_workspace_virtualenv,
    )
    monkeypatch.setattr(
        managed_install,
        "upgrade_workspace_packaging_tools",
        lambda python_executable, on_log=None, env=None: None,
    )
    monkeypatch.setattr(
        managed_install,
        "install_selected_torch_backend",
        lambda python_executable, *, install_arguments, on_log=None, env=None: (
            managed_install_failures.raise_forced_managed_failure("dependency_install")
        ),
    )

    with pytest.raises(RuntimeError, match="Python packages"):
        managed_install.ensure_managed_comfy_setup(
            workspace=tmp_path,
        )
