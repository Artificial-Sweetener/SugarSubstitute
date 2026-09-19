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

"""Run launcher replacement from the independently managed app runtime."""

from __future__ import annotations

import logging
from pathlib import Path
import sys

from sugarsubstitute_shared.launcher_update.attempt_status import (
    LauncherUpdateAttemptPhase,
    LauncherUpdateAttemptStatus,
    LauncherUpdateAttemptStore,
)
from sugarsubstitute_shared.launcher_update.baseline_transaction import (
    LauncherBaselineTransaction,
)
from sugarsubstitute_shared.launcher_update.delegation_contract import (
    supports_launcher_delegation,
)
from sugarsubstitute_shared.launcher_update.legacy_request_bridge import (
    renew_legacy_launcher_handoff,
)
from sugarsubstitute_shared.launcher_update.request import LauncherUpdateRequest
from sugarsubstitute_shared.launcher_update.targets import (
    launcher_bundle_target_for_key,
)
from sugarsubstitute_shared.launcher_update.transaction import (
    LauncherUpdateTransaction,
)


def main(argv: list[str] | None = None) -> int:
    """Apply the single pending update request named on the command line."""

    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        raise SystemExit("usage: launcher-update-helper REQUEST_PATH")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    request_path = Path(arguments[0]).expanduser().resolve()
    apply_launcher_update_request(request_path)
    logging.getLogger(__name__).info(
        "Launcher update completed | request_path=%s",
        request_path,
    )
    return 0


def apply_launcher_update_request(request_path: Path) -> None:
    """Route one request through legacy baseline migration or generation selection."""

    request = renew_legacy_launcher_handoff(request_path)
    target = launcher_bundle_target_for_key(request.target_key)
    install_root = request.install_root.resolve()
    route = (
        "generation_activation"
        if supports_launcher_delegation(install_root, target)
        else "legacy_baseline_bridge"
    )
    status_store = LauncherUpdateAttemptStore(install_root)
    status_store.save(
        LauncherUpdateAttemptStatus.create(
            version=request.version,
            phase=LauncherUpdateAttemptPhase.RUNNING,
            route=route,
        )
    )
    try:
        if route == "generation_activation":
            LauncherUpdateTransaction().apply(request_path=request_path)
        else:
            _require_delegating_candidate(request)
            LauncherBaselineTransaction().apply(request_path=request_path)
    except BaseException as error:
        status_store.save(
            LauncherUpdateAttemptStatus.create(
                version=request.version,
                phase=LauncherUpdateAttemptPhase.FAILED,
                route=route,
                error=error,
            )
        )
        raise
    status_store.save(
        LauncherUpdateAttemptStatus.create(
            version=request.version,
            phase=LauncherUpdateAttemptPhase.COMPLETED,
            route=route,
        )
    )


def _require_delegating_candidate(request: LauncherUpdateRequest) -> None:
    """Allow the one-time baseline replacement only with the permanent contract."""

    target = launcher_bundle_target_for_key(request.target_key)
    if not supports_launcher_delegation(request.staged_bundle_dir, target):
        raise ValueError(
            "Legacy launcher bridge candidate does not provide permanent delegation."
        )


if __name__ == "__main__":
    raise SystemExit(main())
