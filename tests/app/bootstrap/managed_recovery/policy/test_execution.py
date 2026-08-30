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

"""Cover background managed-recovery cleanup and dependency execution."""

from __future__ import annotations


from collections.abc import Callable


from pathlib import Path


from substitute.app.bootstrap.managed_compatibility_recovery import (
    ManagedCompatibilityRecoveryOutcome,
    run_managed_compatibility_recovery,
)


from substitute.application.backend_compatibility import (
    RuntimeCompatibilityStatus,
)


from substitute.domain.onboarding import (
    ComfyTargetConfiguration,
)


from substitute.domain.comfy_nodepacks import CoreNodepackId


from .support import (
    _CleanupResult,
    _ManagedStartupState,
    _compatibility,
    _target,
)


def test_managed_recovery_task_stops_state_and_refreshes_nodepack(
    tmp_path: Path,
) -> None:
    """Managed recovery task should clean the old state before refreshing setup."""

    compatibility = _compatibility(RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD)
    confirmed_status = object()
    cleanup_calls: list[object | None] = []
    setup_calls: list[tuple[ComfyTargetConfiguration, frozenset[CoreNodepackId]]] = []
    logs: list[str] = []
    state = _ManagedStartupState()

    def cleanup_state(cleanup_state: object | None) -> _CleanupResult:
        """Record cleanup and return a confirmed result."""

        cleanup_calls.append(cleanup_state)
        return _CleanupResult(
            managed_resource_present=True,
            termination_status=confirmed_status,
            user_safe_detail="Shutdown finished cleanly.",
        )

    def reconcile_owned_comfy_dependencies(
        target: ComfyTargetConfiguration,
        nodepacks: frozenset[CoreNodepackId],
        emit_log: Callable[[str], None],
    ) -> None:
        """Record setup and emit one fake setup log line."""

        setup_calls.append((target, nodepacks))
        emit_log("setup complete")

    target = _target(tmp_path, launch_owned=True)
    outcome = run_managed_compatibility_recovery(
        compatibility=compatibility,
        target=target,
        state_to_recover=state,
        confirmed_termination_status=confirmed_status,
        cleanup_state=cleanup_state,
        reconcile_owned_comfy_dependencies=reconcile_owned_comfy_dependencies,
        emit_recovery_log=logs.append,
    )

    assert outcome == ManagedCompatibilityRecoveryOutcome(compatibility)
    assert cleanup_calls == [state]
    assert state.wait_calls == [5.0]
    assert setup_calls == [(target, frozenset({CoreNodepackId.SUGARCUBES}))]
    assert logs == ["Shutdown finished cleanly.", "setup complete"]


def test_managed_recovery_task_fails_unconfirmed_cleanup(tmp_path: Path) -> None:
    """Managed recovery task should fail when a managed process remains uncertain."""

    compatibility = _compatibility(RuntimeCompatibilityStatus.BACKEND_TOO_OLD)

    def cleanup_state(_state: object | None) -> _CleanupResult:
        """Return an unconfirmed cleanup result."""

        return _CleanupResult(
            managed_resource_present=True,
            termination_status=object(),
            user_safe_detail="Shutdown uncertain.",
        )

    outcome = run_managed_compatibility_recovery(
        compatibility=compatibility,
        target=_target(tmp_path, launch_owned=True),
        state_to_recover=object(),
        confirmed_termination_status=object(),
        cleanup_state=cleanup_state,
        reconcile_owned_comfy_dependencies=(
            lambda _target, _nodepacks, _emit_log: None
        ),
        emit_recovery_log=lambda _line: None,
    )

    assert outcome.compatibility is compatibility
    assert isinstance(outcome.error, RuntimeError)
    assert str(outcome.error) == "Shutdown uncertain."
