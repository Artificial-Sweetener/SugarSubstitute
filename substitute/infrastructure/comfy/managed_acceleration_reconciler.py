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

"""Reconcile SeedVR2 acceleration packages without owning nodepack setup."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from substitute.infrastructure.comfy.hardware_models import HardwareDetectionResult
from substitute.infrastructure.comfy.managed_acceleration_environment import (
    ManagedAccelerationEnvironment,
    ManagedAccelerationWorkspace,
)
from substitute.infrastructure.comfy.managed_acceleration_policy import (
    ManagedAccelerationPolicy,
    resolve_managed_acceleration_policy,
)
from substitute.infrastructure.comfy.workspace_python_resolver import (
    resolve_workspace_python,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning

StatusCallback = Callable[[str], None]
LogCallback = Callable[[str], None]

_LOGGER = get_logger("infrastructure.comfy.managed_acceleration_reconciler")
_SEEDVR2_SENTINEL = Path("custom_nodes") / "seedvr2_videoupscaler" / "__init__.py"


@dataclass(frozen=True)
class ManagedAccelerationReconciliationResult:
    """Describe mutations and remaining optional acceleration fallbacks."""

    changed: bool
    ready_packages: tuple[str, ...]
    unavailable_packages: tuple[str, ...]
    diagnostics: tuple[str, ...]


class ManagedAccelerationReconciler:
    """Reconcile one resolved package policy through an environment port."""

    def __init__(
        self,
        environment: ManagedAccelerationEnvironment,
        *,
        on_log: LogCallback | None = None,
    ) -> None:
        """Initialize reconciliation with one authoritative environment adapter."""

        self._environment = environment
        self._on_log = on_log

    def reconcile(
        self,
        policy: ManagedAccelerationPolicy,
    ) -> ManagedAccelerationReconciliationResult:
        """Repair package drift and preserve optional SDPA fallbacks on failure."""

        inspected_distributions = tuple(
            dict.fromkeys(
                distribution_name
                for package in policy.packages
                for distribution_name in (
                    package.distribution_name,
                    *package.conflicting_distributions,
                )
            )
        )
        versions = self._environment.installed_versions(inspected_distributions)
        changed = False
        ready: list[str] = []
        unavailable: list[str] = []
        diagnostics: list[str] = []
        for package in policy.packages:
            installed_conflicts = tuple(
                name
                for name in package.conflicting_distributions
                if versions.get(name) is not None
            )
            if installed_conflicts:
                changed = True
                self._emit(
                    "[ManagedAcceleration] Removing packages that conflict with "
                    f"{package.display_name}: {', '.join(installed_conflicts)}."
                )
                try:
                    self._environment.uninstall(installed_conflicts)
                except Exception as error:
                    diagnostic = (
                        f"{package.display_name} conflicts could not be removed: "
                        f"{str(error).strip() or type(error).__name__}"
                    )
                    if package.required:
                        raise RuntimeError(diagnostic) from error
                    unavailable.append(package.distribution_name)
                    diagnostics.append(diagnostic)
                    self._warn(diagnostic + " PyTorch SDPA remains available.")
                    continue
                for conflict in installed_conflicts:
                    versions[conflict] = None
            installed_version = versions.get(package.distribution_name)
            version_ready = package.accepts_version(installed_version)
            verification_ready = False
            verification_detail = "version does not satisfy managed policy"
            if version_ready:
                verification_ready, verification_detail = self._environment.verify(
                    package
                )
            if version_ready and verification_ready:
                ready.append(package.distribution_name)
                continue
            changed = True
            reason = (
                verification_detail
                if version_ready
                else f"installed version is {installed_version or 'missing'}"
            )
            self._emit(
                f"[ManagedAcceleration] Repairing {package.display_name}: {reason}."
            )
            try:
                self._environment.install(package)
                repaired_version = self._environment.installed_versions(
                    (package.distribution_name,)
                ).get(package.distribution_name)
                if not package.accepts_version(repaired_version):
                    raise RuntimeError(
                        "installer reported an incompatible version "
                        f"({repaired_version or 'missing'})"
                    )
                verified, detail = self._environment.verify(package)
                if not verified:
                    raise RuntimeError(detail)
            except Exception as error:
                diagnostic = (
                    f"{package.display_name} could not be prepared: "
                    f"{str(error).strip() or type(error).__name__}"
                )
                if package.required:
                    raise RuntimeError(diagnostic) from error
                unavailable.append(package.distribution_name)
                diagnostics.append(diagnostic)
                self._warn(diagnostic + " PyTorch SDPA remains available.")
                continue
            ready.append(package.distribution_name)
            self._emit(f"[ManagedAcceleration] {package.display_name} is ready.")
        for note in policy.fallback_notes:
            self._emit(f"[ManagedAcceleration] {note}")
        return ManagedAccelerationReconciliationResult(
            changed=changed,
            ready_packages=tuple(ready),
            unavailable_packages=tuple(unavailable),
            diagnostics=tuple(diagnostics),
        )

    def _emit(self, message: str) -> None:
        """Record and optionally forward one reconciliation status line."""

        log_info(_LOGGER, message)
        if self._on_log is not None:
            self._on_log(message)

    def _warn(self, message: str) -> None:
        """Record and optionally forward one optional acceleration failure."""

        log_warning(_LOGGER, message)
        if self._on_log is not None:
            self._on_log(message)


def reconcile_managed_acceleration_stack(
    *,
    workspace: Path,
    detection: HardwareDetectionResult,
    on_status: StatusCallback | None = None,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
    python_executable: Path | None = None,
) -> ManagedAccelerationReconciliationResult:
    """Reconcile supported acceleration only when managed SeedVR2 is installed."""

    if not (workspace / _SEEDVR2_SENTINEL).exists():
        return ManagedAccelerationReconciliationResult(
            changed=False,
            ready_packages=(),
            unavailable_packages=(),
            diagnostics=(),
        )
    if on_status is not None:
        on_status("Preparing managed acceleration support.")
    if python_executable is None:
        python_executable = resolve_workspace_python(workspace)
    environment = ManagedAccelerationWorkspace(
        workspace=workspace,
        python_executable=python_executable,
        on_log=on_log,
        env=env,
    )
    policy = resolve_managed_acceleration_policy(
        detection=detection,
        runtime=environment.runtime(),
    )
    return ManagedAccelerationReconciler(environment, on_log=on_log).reconcile(policy)


__all__ = [
    "ManagedAccelerationReconciler",
    "ManagedAccelerationReconciliationResult",
    "reconcile_managed_acceleration_stack",
]
