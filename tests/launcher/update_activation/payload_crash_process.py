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

"""Crash an isolated activation owner after preparation or durable commitment."""

from __future__ import annotations
import os
from pathlib import Path
import sys
from unittest.mock import patch
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.payload_models import StagedAppPayload
from launcher.sugarsubstitute_launcher.update_activation import PendingUpdateActivation
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState


def main() -> None:
    """Leave a real interrupted journal without releasing ownership through cleanup."""
    layout = InstallLayout.from_root(Path(sys.argv[1]))
    activation = PendingUpdateActivation.begin(
        layout=layout,
        successful_state=LauncherUpdateState(installed_app_version="0.4.0"),
    )
    activation.staging_directory.mkdir(parents=True)
    (activation.staging_directory / "version.txt").write_text(
        "candidate-app", encoding="utf-8"
    )
    activation.promote_app(
        StagedAppPayload(version="0.4.0", staging_dir=activation.staging_directory)
    )
    activation.prepare_runtime()
    (layout.runtime_dir / "version.txt").write_text(
        "candidate-runtime", encoding="utf-8"
    )
    if sys.argv[2] == "committed":
        with patch.object(LauncherUpdateState, "save", _crash_at_publication):
            activation.commit()
    os._exit(73)


def _crash_at_publication(_state: LauncherUpdateState, _path: Path) -> None:
    """Interrupt after the durable commitment marker and before state publication."""
    os._exit(73)


if __name__ == "__main__":
    main()
