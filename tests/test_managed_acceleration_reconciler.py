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

"""Tests for managed acceleration package reconciliation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from substitute.infrastructure.comfy.managed_acceleration_policy import (
    ManagedAccelerationPackage,
    ManagedAccelerationPolicy,
    ManagedAccelerationRuntime,
    ManagedPackageVersion,
)
from substitute.infrastructure.comfy.managed_acceleration_reconciler import (
    ManagedAccelerationReconciler,
    reconcile_managed_acceleration_stack,
)


@dataclass
class _RecordingEnvironment:
    """Record package inspection, installation, and verification calls."""

    versions: dict[str, str | None]
    verification: dict[str, tuple[bool, str]] = field(default_factory=dict)
    installed: list[str] = field(default_factory=list)
    uninstalled: list[tuple[str, ...]] = field(default_factory=list)

    def installed_versions(
        self,
        distribution_names: tuple[str, ...],
    ) -> dict[str, str | None]:
        """Return configured installed distribution versions."""

        return {name: self.versions.get(name) for name in distribution_names}

    def install(self, package: ManagedAccelerationPackage) -> None:
        """Record installation and expose the expected version."""

        self.installed.append(package.distribution_name)
        self.versions[package.distribution_name] = package.version.exact_version
        if package.version.exact_version is None:
            self.versions[package.distribution_name] = "5.10.1"

    def verify(self, package: ManagedAccelerationPackage) -> tuple[bool, str]:
        """Return configured package verification state."""

        return self.verification.get(package.distribution_name, (True, "ready"))

    def uninstall(self, distribution_names: tuple[str, ...]) -> None:
        """Record removal and clear the configured package versions."""

        self.uninstalled.append(distribution_names)
        for distribution_name in distribution_names:
            self.versions[distribution_name] = None


def test_reconciler_repairs_missing_and_stale_packages_then_verifies() -> None:
    """Existing managed installs should repair drift without reinstalling good packages."""

    environment = _RecordingEnvironment(
        versions={
            "transformers": "5.8.0",
            "triton-windows": "3.6.0.post26",
            "sageattention": None,
        }
    )
    reconciler = ManagedAccelerationReconciler(environment)

    result = reconciler.reconcile(_policy())

    assert environment.installed == ["transformers", "sageattention"]
    assert result.changed is True
    assert result.ready_packages == (
        "transformers",
        "triton-windows",
        "sageattention",
    )
    assert result.unavailable_packages == ()


def test_reconciler_reinstalls_a_broken_matching_native_package() -> None:
    """A matching version with a broken DLL should be repaired."""

    environment = _RecordingEnvironment(
        versions={
            "transformers": "5.14.0",
            "triton-windows": "3.6.0.post26",
            "sageattention": "2.2.0+cu130torch2.10.0andhigher.post5",
        },
        verification={"sageattention": (False, "DLL load failed")},
    )
    verification_calls = 0

    def verify(package: ManagedAccelerationPackage) -> tuple[bool, str]:
        """Fail Sage once, then accept the repaired package."""

        nonlocal verification_calls
        if package.distribution_name != "sageattention":
            return True, "ready"
        verification_calls += 1
        return (
            (False, "DLL load failed") if verification_calls == 1 else (True, "ready")
        )

    environment.verify = verify  # type: ignore[method-assign]

    result = ManagedAccelerationReconciler(environment).reconcile(_policy())

    assert environment.installed == ["sageattention"]
    assert result.unavailable_packages == ()


def test_optional_install_failure_preserves_sdpa_and_reports_unavailable() -> None:
    """Native optimization failure should not make managed Comfy unusable."""

    environment = _RecordingEnvironment(
        versions={"transformers": "5.14.0", "triton-windows": None}
    )

    def install(package: ManagedAccelerationPackage) -> None:
        """Fail the optional Triton installation."""

        if package.distribution_name == "triton-windows":
            raise RuntimeError("wheel unavailable")
        environment.installed.append(package.distribution_name)

    environment.install = install  # type: ignore[method-assign]

    result = ManagedAccelerationReconciler(environment).reconcile(
        ManagedAccelerationPolicy(
            packages=_policy().packages[:2],
            fallback_notes=("PyTorch SDPA remains available.",),
        )
    )

    assert result.ready_packages == ("transformers",)
    assert result.unavailable_packages == ("triton-windows",)
    assert "wheel unavailable" in result.diagnostics[0]


def test_required_compatibility_failure_blocks_broken_seedvr2_startup() -> None:
    """The Transformers fallback fix is required for SeedVR2 to import safely."""

    environment = _RecordingEnvironment(versions={"transformers": "5.8.0"})

    def install(_package: ManagedAccelerationPackage) -> None:
        """Reject required package repair."""

        raise RuntimeError("index unavailable")

    environment.install = install  # type: ignore[assignment]

    with pytest.raises(RuntimeError, match="Transformers compatibility"):
        ManagedAccelerationReconciler(environment).reconcile(
            ManagedAccelerationPolicy(
                packages=(_policy().packages[0],),
                fallback_notes=(),
            )
        )


def test_reconciler_is_a_no_op_when_versions_and_imports_are_ready() -> None:
    """A current environment should avoid every package mutation."""

    environment = _RecordingEnvironment(
        versions={
            "transformers": "5.14.0",
            "triton-windows": "3.6.0.post26",
            "sageattention": "2.2.0+cu130torch2.10.0andhigher.post5",
        }
    )

    result = ManagedAccelerationReconciler(environment).reconcile(_policy())

    assert environment.installed == []
    assert result.changed is False


def test_reconciler_removes_conflicting_distribution_ownership() -> None:
    """The selected platform package should own the shared Triton import path."""

    policy = _policy()
    triton = policy.packages[1]
    triton = ManagedAccelerationPackage(
        distribution_name=triton.distribution_name,
        display_name=triton.display_name,
        version=triton.version,
        install_arguments=triton.install_arguments,
        verification_code=triton.verification_code,
        required=triton.required,
        conflicting_distributions=("triton",),
    )
    environment = _RecordingEnvironment(
        versions={
            "transformers": "5.14.0",
            "triton-windows": "3.6.0.post26",
            "triton": "3.6.0",
        }
    )

    result = ManagedAccelerationReconciler(environment).reconcile(
        ManagedAccelerationPolicy(
            packages=(policy.packages[0], triton),
            fallback_notes=(),
        )
    )

    assert environment.uninstalled == [("triton",)]
    assert result.changed is True


def test_workspace_coordination_skips_when_seedvr2_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed acceleration policy must not install packages without its nodepack."""

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.managed_acceleration_reconciler.resolve_workspace_python",
        lambda _workspace: pytest.fail("workspace Python should not be resolved"),
    )

    result = reconcile_managed_acceleration_stack(
        workspace=tmp_path,
        detection=object(),  # type: ignore[arg-type]
    )

    assert result.changed is False
    assert result.ready_packages == ()


def _policy() -> ManagedAccelerationPolicy:
    """Return a compact deterministic policy for reconciler tests."""

    runtime = ManagedAccelerationRuntime(
        python_version="3.13.12",
        machine="amd64",
        torch_version="2.10.0+cu130",
        cuda_version="13.0",
        hip_version=None,
        compute_capability=(12, 0),
    )
    _ = runtime
    return ManagedAccelerationPolicy(
        packages=(
            ManagedAccelerationPackage(
                distribution_name="transformers",
                display_name="Transformers compatibility",
                version=ManagedPackageVersion(
                    minimum_release=(5, 10, 1),
                    maximum_exclusive=(6, 0, 0),
                ),
                install_arguments=("--upgrade", "transformers>=5.10.1,<6"),
                verification_code="import transformers",
                required=True,
            ),
            ManagedAccelerationPackage(
                distribution_name="triton-windows",
                display_name="Triton",
                version=ManagedPackageVersion(exact_version="3.6.0.post26"),
                install_arguments=("--upgrade", "triton-windows==3.6.0.post26"),
                verification_code="import triton",
                required=False,
            ),
            ManagedAccelerationPackage(
                distribution_name="sageattention",
                display_name="SageAttention",
                version=ManagedPackageVersion(
                    exact_version="2.2.0+cu130torch2.10.0andhigher.post5"
                ),
                install_arguments=("--upgrade", "https://example.test/sage.whl"),
                verification_code="import sageattention",
                required=False,
            ),
        ),
        fallback_notes=(),
    )
