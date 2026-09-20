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

"""Verify non-locking Cube dependency reconciliation orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.cube_library import (
    CubeDependencyReconciliationCoordinator,
)
from substitute.domain.cube_library import (
    CubeDependencySyncAndCheckRequest,
    CubeDependencySyncAndCheckResult,
    CubeLibraryReadiness,
)


@dataclass
class _Gateway:
    """Capture authoritative maintenance requests for assertions."""

    result: CubeDependencySyncAndCheckResult | None
    error: BaseException | None = None
    requests: list[CubeDependencySyncAndCheckRequest] | None = None

    def __post_init__(self) -> None:
        """Initialize request capture without a shared mutable default."""

        self.requests = []

    def sync_and_check(
        self,
        request: CubeDependencySyncAndCheckRequest,
    ) -> CubeDependencySyncAndCheckResult | None:
        """Return the configured result or raise the configured failure."""

        assert self.requests is not None
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.result


def test_reconciliation_approves_all_actionable_cube_requirements() -> None:
    """Catalog reconciliation should ask SugarCubes for one authoritative repair."""

    result = _result(restart_required=True)
    gateway = _Gateway(result)
    observed: list[CubeDependencySyncAndCheckResult] = []
    failures: list[BaseException | None] = []
    coordinator = CubeDependencyReconciliationCoordinator(
        gateway=gateway,
        result_observer=observed.append,
        failure_observer=failures.append,
        submitter=None,
    )

    coordinator.request(reason="catalog_changed")

    assert gateway.requests == [
        CubeDependencySyncAndCheckRequest(
            include_versions=True,
            approve_all=True,
            repair=True,
        )
    ]
    assert observed == [result]
    assert failures == []


def test_reconciliation_failure_is_reported_without_raising_or_locking() -> None:
    """Unavailable maintenance must remain retryable and must not block the app."""

    failure = RuntimeError("registry unavailable")
    gateway = _Gateway(None, error=failure)
    failures: list[BaseException | None] = []
    coordinator = CubeDependencyReconciliationCoordinator(
        gateway=gateway,
        result_observer=lambda _result: None,
        failure_observer=failures.append,
        submitter=None,
    )

    coordinator.request(reason="startup")
    coordinator.request(reason="retry")

    assert failures == [failure, failure]
    assert gateway.requests is not None
    assert len(gateway.requests) == 2


def _result(*, restart_required: bool) -> CubeDependencySyncAndCheckResult:
    """Build one compact authoritative reconciliation result."""

    readiness = CubeLibraryReadiness(
        schema_version=1,
        ready=True,
        required_custom_nodes=("simple-syrup",),
        missing_custom_nodes=(),
        installed_custom_nodes=("simple-syrup",),
        can_install=True,
        install_supported=True,
        catalog_revision="revision",
        errors=(),
    )
    return CubeDependencySyncAndCheckResult(
        schema_version=1,
        readiness=readiness,
        repair_result=None,
        restart_required=restart_required,
        errors=(),
    )
