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

"""Restore interrupted installation state before choosing a startup route."""

from __future__ import annotations
from dataclasses import replace
from launcher.sugarsubstitute_launcher.startup_plan import LauncherStartupCandidate
from launcher.sugarsubstitute_launcher.installation_recovery import InstallationRecovery
from sugarsubstitute_shared.installation_mutation import installation_mutation


def recover_startup_candidate(
    candidate: LauncherStartupCandidate,
) -> LauncherStartupCandidate:
    """Recover under native ownership and reassess configuration after restoration.

    Call after the optional splash attempt and before dispatching generations or
    assessing application files. Journal existence identifies recovery work, not
    permission to race another repair or to trust its unvalidated destinations.
    """
    layout = candidate.layout
    recovery = InstallationRecovery(layout)
    if not recovery.pending:
        return candidate
    with installation_mutation(layout.root) as operation:
        recovery.recover(ownership=operation)
        return replace(candidate, installed_config_found=layout.config_path.is_file())
