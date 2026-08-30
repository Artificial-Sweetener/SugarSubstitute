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

"""Cover owned-nodepack recovery eligibility and message policy."""

from __future__ import annotations


from pathlib import Path


from substitute.app.bootstrap.managed_compatibility_recovery import (
    core_nodepacks_for_compatibility_recovery,
    owned_nodepack_recovery_message,
    should_attempt_owned_nodepack_recovery,
)


from substitute.application.backend_compatibility import (
    RuntimeCompatibilityStatus,
)


from substitute.domain.onboarding import (
    ComfyTargetMode,
)


from substitute.domain.comfy_nodepacks import CoreNodepackId


from .support import (
    _compatibility,
    _target,
)


def test_managed_core_refresh_allowed_for_updateable_core_mismatch(
    tmp_path: Path,
) -> None:
    """Managed startup should auto-refresh old core nodepacks once."""

    target = _target(tmp_path, launch_owned=True)
    compatibility = _compatibility(RuntimeCompatibilityStatus.BACKEND_TOO_OLD)

    assert (
        should_attempt_owned_nodepack_recovery(
            target=target,
            compatibility=compatibility,
            recovery_attempted=False,
            recovery_running=False,
        )
        is True
    )


def test_managed_core_refresh_blocks_too_new_core_mismatch(tmp_path: Path) -> None:
    """Startup recovery should not try to fix too-new nodepacks by updating."""

    target = _target(tmp_path, launch_owned=True)
    compatibility = _compatibility(RuntimeCompatibilityStatus.BACKEND_TOO_NEW)

    assert (
        should_attempt_owned_nodepack_recovery(
            target=target,
            compatibility=compatibility,
            recovery_attempted=False,
            recovery_running=False,
        )
        is False
    )


def test_managed_core_refresh_requires_owned_launch(tmp_path: Path) -> None:
    """Targets not launched by Substitute must not be mutated by startup recovery."""

    target = _target(tmp_path, launch_owned=False)
    compatibility = _compatibility(RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD)

    assert (
        should_attempt_owned_nodepack_recovery(
            target=target,
            compatibility=compatibility,
            recovery_attempted=False,
            recovery_running=False,
        )
        is False
    )


def test_owned_nodepack_recovery_allows_attached_local_owned_launch(
    tmp_path: Path,
) -> None:
    """Attached local launch-owned workspaces should use owned-nodepack recovery."""

    target = _target(
        tmp_path,
        launch_owned=True,
        mode=ComfyTargetMode.ATTACHED_LOCAL,
    )
    compatibility = _compatibility(RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD)

    assert (
        should_attempt_owned_nodepack_recovery(
            target=target,
            compatibility=compatibility,
            recovery_attempted=False,
            recovery_running=False,
        )
        is True
    )


def test_owned_nodepack_recovery_rejects_remote_targets(tmp_path: Path) -> None:
    """Remote targets should stay read-only because there is no local workspace."""

    target = _target(
        tmp_path,
        launch_owned=False,
        mode=ComfyTargetMode.REMOTE,
    )
    compatibility = _compatibility(RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD)

    assert (
        should_attempt_owned_nodepack_recovery(
            target=target,
            compatibility=compatibility,
            recovery_attempted=False,
            recovery_running=False,
        )
        is False
    )


def test_backend_mismatch_recovery_targets_only_backend() -> None:
    """BackEnd compatibility failures should not refresh SugarCubes."""

    for status in (
        RuntimeCompatibilityStatus.BACKEND_UNREACHABLE,
        RuntimeCompatibilityStatus.BACKEND_VERSION_UNKNOWN,
        RuntimeCompatibilityStatus.BACKEND_TOO_OLD,
        RuntimeCompatibilityStatus.BACKEND_API_MISMATCH,
        RuntimeCompatibilityStatus.BACKEND_FEATURE_MISSING,
    ):
        assert core_nodepacks_for_compatibility_recovery(status) == frozenset(
            {CoreNodepackId.SUBSTITUTE_BACKEND}
        )


def test_sugarcubes_mismatch_recovery_targets_only_sugarcubes() -> None:
    """SugarCubes compatibility failures should not refresh BackEnd."""

    for status in (
        RuntimeCompatibilityStatus.SUGARCUBES_MISSING,
        RuntimeCompatibilityStatus.SUGARCUBES_VERSION_UNKNOWN,
        RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD,
        RuntimeCompatibilityStatus.SUGARCUBES_DEV_VERSION_RELEASE_BLOCKED,
    ):
        assert core_nodepacks_for_compatibility_recovery(status) == frozenset(
            {CoreNodepackId.SUGARCUBES}
        )


def test_compatible_runtime_recovery_targets_no_nodepacks() -> None:
    """Compatible runtimes should not request a managed nodepack refresh."""

    assert (
        core_nodepacks_for_compatibility_recovery(RuntimeCompatibilityStatus.COMPATIBLE)
        == frozenset()
    )


def test_managed_recovery_message_describes_targeted_nodepack() -> None:
    """Startup splash text should describe the exact targeted recovery."""

    assert (
        owned_nodepack_recovery_message(frozenset({CoreNodepackId.SUBSTITUTE_BACKEND}))
        == "Updating Substitute BackEnd before opening."
    )
    assert (
        owned_nodepack_recovery_message(frozenset({CoreNodepackId.SUGARCUBES}))
        == "Updating SugarCubes before opening."
    )
