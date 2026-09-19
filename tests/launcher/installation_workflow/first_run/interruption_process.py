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

"""Interrupt only the fixture process at a first-install publication boundary."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from unittest.mock import patch

from launcher.sugarsubstitute_launcher.first_run import FirstRunInstaller
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.release_sources import LocalFolderReleaseSource
from launcher.sugarsubstitute_launcher.update_activation import PendingUpdateActivation
from launcher.sugarsubstitute_launcher.payload_models import (
    AppPayloadInstallResult,
    StagedAppPayload,
)
from launcher.sugarsubstitute_launcher.update_activation_journal import (
    write_update_journal_data,
)


def main() -> int:
    """Run the real installer with abrupt exit after one selected filesystem write."""
    layout = InstallLayout.from_root(Path(sys.argv[1]))
    boundary = sys.argv[3]
    write_text = Path.write_text
    atomic_replace = os.replace
    promote_app = PendingUpdateActivation.promote_app

    def interrupt_journal(path: Path, payload: dict[str, object]) -> None:
        """Exit after durable preparation intent exists."""

        write_update_journal_data(path, payload)
        if boundary == "app_retired" and payload.get("phase") == "preparing":
            os._exit(73)

    def interrupt_promotion(
        self: PendingUpdateActivation, staged: StagedAppPayload
    ) -> AppPayloadInstallResult:
        """Exit after the candidate app payload has been fully promoted."""

        result = promote_app(self, staged)
        if boundary == "app_promoted":
            os._exit(73)
        return result

    def interrupt_atomic_replace(
        source: str | os.PathLike[str], target: str | os.PathLike[str]
    ) -> None:
        """Interrupt configuration publication before or after its atomic replace."""
        if boundary == "config_partial" and Path(target) == layout.config_path:
            write_text(Path(source), "{", encoding="utf-8")
            os._exit(73)
        atomic_replace(source, target)
        if boundary == "config_written" and Path(target) == layout.config_path:
            os._exit(73)
        if boundary == "state_written" and Path(target) == layout.state_path:
            os._exit(73)

    with (
        patch.object(os, "replace", interrupt_atomic_replace),
        patch(
            "launcher.sugarsubstitute_launcher.update_activation."
            "write_update_journal_data",
            interrupt_journal,
        ),
        patch.object(PendingUpdateActivation, "promote_app", interrupt_promotion),
    ):
        FirstRunInstaller().continue_install(
            layout=layout, release_source=LocalFolderReleaseSource(Path(sys.argv[2]))
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
