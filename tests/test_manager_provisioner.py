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

"""Tests for capability-driven ComfyUI Manager provisioning."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
import stat

import pytest

from substitute.domain.comfy_manager import (
    ComfyManagerCapabilities,
    ComfyManagerKind,
    ComfyManagerProvisioningAction,
    ComfyManagerRuntime,
    select_attached_manager_action,
)
from substitute.infrastructure.comfy import manager_provisioner
from substitute.infrastructure.comfy.manager_contract import ComfyManagerContract
from substitute.infrastructure.comfy.legacy_manager_installer import (
    LegacyComfyManagerInstaller,
)
from substitute.infrastructure.comfy.manager_runtime_probe import (
    ComfyManagerProbeResult,
    ComfyManagerRuntimeProbe,
)
from substitute.infrastructure.comfy.manager_requirements_installer import (
    ComfyManagerRequirementsInstaller,
)
from substitute.infrastructure.comfy.python_requirements_probe import (
    PythonRequirementIssue,
    PythonRequirementsAssessment,
)
from tests.repository_service_test_double import RecordingRepositoryService


class _RecordingProbe(ComfyManagerRuntimeProbe):
    """Return configured Manager evidence while recording backend requests."""

    def __init__(
        self,
        *,
        integrated: list[ComfyManagerProbeResult],
        legacy: list[ComfyManagerProbeResult] | None = None,
        pygit2: ComfyManagerProbeResult | None = None,
    ) -> None:
        """Store ordered probe results."""

        self.integrated_results = integrated
        self.legacy_results = legacy or []
        self.pygit2_result = pygit2
        self.pygit2_calls = 0

    def integrated(
        self,
        *,
        workspace: Path,
        python_executable: Path,
        env: Mapping[str, str] | None = None,
    ) -> ComfyManagerProbeResult:
        """Return the next integrated probe result."""

        del workspace, python_executable, env
        return self.integrated_results.pop(0)

    def legacy(
        self,
        *,
        workspace: Path,
        python_executable: Path,
        env: Mapping[str, str] | None = None,
    ) -> ComfyManagerProbeResult:
        """Return the next legacy probe result."""

        del workspace, python_executable, env
        return self.legacy_results.pop(0)

    def pygit2_backend(
        self,
        runtime: ComfyManagerRuntime,
        *,
        env: Mapping[str, str] | None = None,
    ) -> ComfyManagerProbeResult:
        """Return configured backend validation evidence."""

        del runtime, env
        self.pygit2_calls += 1
        assert self.pygit2_result is not None
        return self.pygit2_result


class _RecordingInstaller(ComfyManagerRequirementsInstaller):
    """Record Manager dependency transactions without invoking pip."""

    def __init__(self) -> None:
        """Create an empty transaction log."""

        self.calls: list[tuple[str, Path | None]] = []

    def install_requirements(
        self,
        *,
        workspace: Path,
        python_executable: Path,
        requirements_path: Path,
        on_log: Callable[[str], None] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        """Record an authoritative requirements install."""

        del workspace, python_executable, on_log, env
        self.calls.append(("requirements", requirements_path))

    def install_pygit2_backend(
        self,
        *,
        workspace: Path,
        python_executable: Path,
        on_log: Callable[[str], None] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        """Record an optional pygit2 install."""

        del workspace, python_executable, on_log, env
        self.calls.append(("pygit2", None))


class _RecordingRequirementsProbe:
    """Return ordered Manager requirement assessments."""

    def __init__(self, *assessments: PythonRequirementsAssessment) -> None:
        """Store assessment evidence or default to satisfied."""

        self.assessments = list(assessments)
        self.calls = 0

    def assess(
        self,
        *,
        requirements_path: Path,
        python_executable: Path,
        workspace: Path,
        env: Mapping[str, str] | None = None,
    ) -> PythonRequirementsAssessment:
        """Return the next configured assessment."""

        del requirements_path, python_executable, workspace, env
        self.calls += 1
        if self.assessments:
            return self.assessments.pop(0)
        return PythonRequirementsAssessment()


@pytest.mark.parametrize(
    ("capabilities", "expected"),
    (
        (
            ComfyManagerCapabilities(True, True, True),
            ComfyManagerProvisioningAction.USE_INTEGRATED,
        ),
        (
            ComfyManagerCapabilities(True, False, True),
            ComfyManagerProvisioningAction.USE_LEGACY,
        ),
        (
            ComfyManagerCapabilities(True, False, False),
            ComfyManagerProvisioningAction.INSTALL_INTEGRATED,
        ),
        (
            ComfyManagerCapabilities(False, False, False),
            ComfyManagerProvisioningAction.INSTALL_LEGACY,
        ),
    ),
)
def test_attached_manager_policy_matrix(
    capabilities: ComfyManagerCapabilities,
    expected: ComfyManagerProvisioningAction,
) -> None:
    """Attached policy should prefer healthy existing routes before installing."""

    assert select_attached_manager_action(capabilities) is expected


def test_managed_manager_installs_exact_requirements_then_optional_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed setup should honor ComfyUI before adding a supported backend."""

    python = _prepare_integrated_contract(tmp_path, "comfyui_manager==4.2.2")
    contract = ComfyManagerContract(tmp_path)
    contract.legacy_directory.mkdir(parents=True)
    (contract.legacy_directory / "user-data.json").write_text(
        "owned fixture",
        encoding="utf-8",
    )
    baseline = _integrated_runtime(tmp_path, python, version="4.2.2", supports=True)
    backend = _integrated_runtime(
        tmp_path,
        python,
        version="4.2.2",
        supports=True,
        uses=True,
    )
    probe = _RecordingProbe(
        integrated=[ComfyManagerProbeResult(None, "missing"), baseline],
        pygit2=backend,
    )
    installer = _RecordingInstaller()
    _install_doubles(monkeypatch, probe, installer)

    runtime = manager_provisioner.ensure_managed_workspace_manager(
        tmp_path,
        python_executable=python,
    )

    assert runtime == backend.runtime
    assert installer.calls == [
        ("requirements", contract.integrated_requirements_path),
    ]
    assert probe.pygit2_calls == 1
    assert not contract.legacy_directory.exists()


def test_managed_manager_4_1_never_installs_or_forces_pygit2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Manager 4.1 should validate without its absent git compatibility API."""

    python = _prepare_integrated_contract(tmp_path, "comfyui_manager==4.1")
    runtime = _integrated_runtime(tmp_path, python, version="4.1")
    probe = _RecordingProbe(
        integrated=[ComfyManagerProbeResult(None, "missing"), runtime]
    )
    installer = _RecordingInstaller()
    _install_doubles(monkeypatch, probe, installer)

    result = manager_provisioner.ensure_managed_workspace_manager(
        tmp_path,
        python_executable=python,
    )

    assert result.version == "4.1"
    assert result.supports_pygit2 is False
    assert result.uses_pygit2 is False
    assert installer.calls == [
        ("requirements", ComfyManagerContract(tmp_path).integrated_requirements_path)
    ]
    assert probe.pygit2_calls == 0


def test_managed_manager_installs_missing_supported_pygit2_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A capable Manager should receive pygit2 only after backend validation fails."""

    python = _prepare_integrated_contract(tmp_path, "comfyui_manager==4.2.2")
    baseline = _integrated_runtime(tmp_path, python, version="4.2.2", supports=True)
    backend = _integrated_runtime(
        tmp_path,
        python,
        version="4.2.2",
        supports=True,
        uses=True,
    )
    probe = _RecordingProbe(
        integrated=[baseline],
        pygit2=ComfyManagerProbeResult(None, "pygit2 missing"),
    )
    installer = _RecordingInstaller()
    _install_doubles(monkeypatch, probe, installer)

    def backend_after_install(
        _runtime: ComfyManagerRuntime,
        **_kwargs: object,
    ) -> ComfyManagerProbeResult:
        """Fail once, then validate the installed backend."""

        probe.pygit2_calls += 1
        return (
            ComfyManagerProbeResult(None, "pygit2 missing")
            if probe.pygit2_calls == 1
            else backend
        )

    monkeypatch.setattr(probe, "pygit2_backend", backend_after_install)

    result = manager_provisioner.ensure_managed_workspace_manager(
        tmp_path,
        python_executable=python,
    )

    assert result.uses_pygit2 is True
    assert installer.calls == [("pygit2", None)]


def test_managed_manager_replaces_healthy_but_stale_distribution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Checkout requirements should outrank an importable older Manager."""

    python = _prepare_integrated_contract(tmp_path, "comfyui_manager==4.2.1")
    stale = _integrated_runtime(tmp_path, python, version="4.1")
    current = _integrated_runtime(tmp_path, python, version="4.2.1", supports=True)
    probe = _RecordingProbe(integrated=[stale, current], pygit2=current)
    installer = _RecordingInstaller()
    requirements_probe = _RecordingRequirementsProbe(
        _manager_version_mismatch("4.1", "4.2.1"),
        PythonRequirementsAssessment(),
    )
    _install_doubles(monkeypatch, probe, installer, requirements_probe)

    result = manager_provisioner.ensure_managed_workspace_manager(
        tmp_path,
        python_executable=python,
    )

    assert result.version == "4.2.1"
    assert installer.calls == [
        ("requirements", ComfyManagerContract(tmp_path).integrated_requirements_path)
    ]
    assert requirements_probe.calls == 2


def test_attached_manager_replaces_stale_integrated_without_touching_legacy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Attached setup should reconcile owned Manager packages, not repository data."""

    python = _prepare_integrated_contract(tmp_path, "comfyui_manager==4.2.1")
    contract = ComfyManagerContract(tmp_path)
    contract.legacy_cli_path.parent.mkdir(parents=True)
    marker = contract.legacy_directory / "user-data.json"
    marker.write_text("preserve", encoding="utf-8")
    stale = _integrated_runtime(tmp_path, python, version="4.1")
    current = _integrated_runtime(tmp_path, python, version="4.2.1", supports=True)
    probe = _RecordingProbe(
        integrated=[stale, current],
        legacy=[_legacy_runtime(tmp_path, python)],
        pygit2=current,
    )
    installer = _RecordingInstaller()
    _install_doubles(
        monkeypatch,
        probe,
        installer,
        _RecordingRequirementsProbe(
            _manager_version_mismatch("4.1", "4.2.1"),
            PythonRequirementsAssessment(),
        ),
    )

    result = manager_provisioner.ensure_attached_workspace_manager(
        tmp_path,
        python_executable=python,
    )

    assert result.version == "4.2.1"
    assert installer.calls == [("requirements", contract.integrated_requirements_path)]
    assert marker.read_text(encoding="utf-8") == "preserve"


def test_managed_manager_preserves_legacy_until_replacement_validates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed migration must retain old code when integrated validation fails."""

    python = _prepare_integrated_contract(tmp_path, "comfyui_manager==4.2.2")
    contract = ComfyManagerContract(tmp_path)
    contract.legacy_directory.mkdir(parents=True)
    probe = _RecordingProbe(
        integrated=[
            ComfyManagerProbeResult(None, "missing"),
            ComfyManagerProbeResult(None, "No module named 'aiohttp'"),
        ]
    )
    _install_doubles(monkeypatch, probe, _RecordingInstaller())

    with pytest.raises(RuntimeError, match="No module named 'aiohttp'"):
        manager_provisioner.ensure_managed_workspace_manager(
            tmp_path,
            python_executable=python,
        )

    assert contract.legacy_directory.is_dir()


@pytest.mark.platforms("windows")
def test_managed_manager_removes_readonly_legacy_git_packs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed migration should remove real Windows read-only Git pack files."""

    python = _prepare_integrated_contract(tmp_path, "comfyui_manager==4.1")
    contract = ComfyManagerContract(tmp_path)
    pack_root = contract.legacy_directory / ".git" / "objects" / "pack"
    pack_root.mkdir(parents=True)
    pack_file = pack_root / "pack-fixture.idx"
    pack_file.write_bytes(b"pack fixture")
    pack_file.chmod(stat.S_IREAD)
    probe = _RecordingProbe(
        integrated=[_integrated_runtime(tmp_path, python, version="4.1")]
    )
    _install_doubles(monkeypatch, probe, _RecordingInstaller())

    manager_provisioner.ensure_managed_workspace_manager(
        tmp_path,
        python_executable=python,
    )

    assert not contract.legacy_directory.exists()


def test_attached_manager_prefers_integrated_and_preserves_user_legacy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Attached setup should use integrated Manager without deleting user files."""

    python = _prepare_integrated_contract(tmp_path, "comfyui_manager==4.1")
    contract = ComfyManagerContract(tmp_path)
    contract.legacy_cli_path.parent.mkdir(parents=True)
    contract.legacy_cli_path.write_text("# fixture", encoding="utf-8")
    integrated = _integrated_runtime(tmp_path, python, version="4.1")
    legacy = _legacy_runtime(tmp_path, python)
    probe = _RecordingProbe(integrated=[integrated], legacy=[legacy])
    _install_doubles(monkeypatch, probe, _RecordingInstaller())

    runtime = manager_provisioner.ensure_attached_workspace_manager(
        tmp_path,
        python_executable=python,
    )

    assert runtime.kind is ComfyManagerKind.INTEGRATED
    assert contract.legacy_cli_path.is_file()


def test_attached_legacy_install_preserves_checkout_owned_by_user(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Pre-integrated attached Comfy should receive one non-destructive legacy clone."""

    python = tmp_path / "python.exe"
    python.write_text("", encoding="utf-8")
    contract = ComfyManagerContract(tmp_path)
    legacy = _legacy_runtime(tmp_path, python)
    probe = _RecordingProbe(
        integrated=[ComfyManagerProbeResult(None, "unsupported")],
        legacy=[ComfyManagerProbeResult(None, "missing"), legacy],
    )
    installer = _RecordingInstaller()
    _install_doubles(monkeypatch, probe, installer)

    def materialize(_url: str, destination: Path) -> None:
        """Create the files produced by one legacy Manager clone."""

        destination.mkdir(parents=True)
        (destination / "cm-cli.py").write_text("# fixture", encoding="utf-8")
        (destination / "requirements.txt").write_text("typer", encoding="utf-8")

    repositories = RecordingRepositoryService(clone_callback=materialize)

    runtime = manager_provisioner.ensure_attached_workspace_manager(
        tmp_path,
        python_executable=python,
        repositories=repositories,
    )

    assert runtime.kind is ComfyManagerKind.LEGACY_CUSTOM_NODE
    assert contract.legacy_cli_path.is_file()
    assert installer.calls == [
        ("requirements", contract.legacy_directory / "requirements.txt")
    ]


def test_existing_invalid_legacy_checkout_is_never_replaced(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Attached setup should fail closed around an existing user Manager directory."""

    python = tmp_path / "python.exe"
    python.write_text("", encoding="utf-8")
    contract = ComfyManagerContract(tmp_path)
    contract.legacy_directory.mkdir(parents=True)
    marker = contract.legacy_directory / "user-data.json"
    marker.write_text("preserve", encoding="utf-8")
    probe = _RecordingProbe(
        integrated=[ComfyManagerProbeResult(None, "unsupported")],
        legacy=[ComfyManagerProbeResult(None, "invalid")],
    )
    _install_doubles(monkeypatch, probe, _RecordingInstaller())

    with pytest.raises(RuntimeError, match="left unchanged"):
        manager_provisioner.ensure_attached_workspace_manager(
            tmp_path,
            python_executable=python,
            repositories=RecordingRepositoryService(),
        )

    assert marker.read_text(encoding="utf-8") == "preserve"


def _install_doubles(
    monkeypatch: pytest.MonkeyPatch,
    probe: _RecordingProbe,
    installer: _RecordingInstaller,
    requirements_probe: _RecordingRequirementsProbe | None = None,
) -> None:
    """Install provisioning collaborators at their construction boundary."""

    monkeypatch.setattr(manager_provisioner, "ComfyManagerRuntimeProbe", lambda: probe)
    monkeypatch.setattr(
        manager_provisioner,
        "ComfyManagerRequirementsInstaller",
        lambda: installer,
    )
    monkeypatch.setattr(
        manager_provisioner,
        "PythonRequirementsProbe",
        lambda: requirements_probe or _RecordingRequirementsProbe(),
    )
    monkeypatch.setattr(
        manager_provisioner,
        "LegacyComfyManagerInstaller",
        lambda *, repositories: LegacyComfyManagerInstaller(
            repositories=repositories,
            requirements_installer=installer,
            runtime_probe=probe,
        ),
    )


def _prepare_integrated_contract(
    workspace: Path,
    manager_requirement: str,
) -> Path:
    """Create one integrated Manager contract and Python fixture."""

    (workspace / "comfy").mkdir(parents=True)
    (workspace / "comfy" / "cli_args.py").write_text(
        'parser.add_argument("--enable-manager")',
        encoding="utf-8",
    )
    (workspace / "manager_requirements.txt").write_text(
        manager_requirement,
        encoding="utf-8",
    )
    python = workspace / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    return python


def _integrated_runtime(
    workspace: Path,
    python: Path,
    *,
    version: str,
    supports: bool = False,
    uses: bool = False,
) -> ComfyManagerProbeResult:
    """Build integrated Manager probe evidence."""

    return ComfyManagerProbeResult(
        ComfyManagerRuntime(
            kind=ComfyManagerKind.INTEGRATED,
            workspace=workspace,
            python_executable=python,
            version=version,
            supports_pygit2=supports,
            uses_pygit2=uses,
        )
    )


def _legacy_runtime(workspace: Path, python: Path) -> ComfyManagerProbeResult:
    """Build legacy Manager probe evidence."""

    return ComfyManagerProbeResult(
        ComfyManagerRuntime(
            kind=ComfyManagerKind.LEGACY_CUSTOM_NODE,
            workspace=workspace,
            python_executable=python,
            legacy_cli_path=ComfyManagerContract(workspace).legacy_cli_path,
        )
    )


def _manager_version_mismatch(
    installed: str,
    expected: str,
) -> PythonRequirementsAssessment:
    """Return stale but importable integrated Manager evidence."""

    return PythonRequirementsAssessment(
        (
            PythonRequirementIssue(
                f"comfyui_manager=={expected}",
                installed,
                "version_mismatch",
                1,
            ),
        )
    )
