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

"""Build localized activity copy for launcher-owned update operations."""

from __future__ import annotations

from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from sugarsubstitute_shared.launch_splash import SplashActivity


def application_install_activity(version: str) -> SplashActivity:
    """Return activity copy for installing one application payload version."""

    return SplashActivity(
        initial_text=launcher_text("Installing SugarSubstitute %1", version),
        long_wait_text=launcher_text(
            "Installing SugarSubstitute %1 is taking longer than usual",
            version,
        ),
        extended_wait_text=launcher_text(
            "Still installing SugarSubstitute %1—network, slow storage, or package "
            "installation may be causing the delay",
            version,
        ),
    )


def application_dependencies_activity() -> SplashActivity:
    """Return activity copy for reconciling application runtime dependencies."""

    return SplashActivity(
        initial_text=launcher_text("Installing SugarSubstitute dependencies"),
        long_wait_text=launcher_text(
            "Installing SugarSubstitute dependencies is taking longer than usual"
        ),
        extended_wait_text=launcher_text(
            "Still installing SugarSubstitute dependencies—network, slow storage, or "
            "package installation may be causing the delay"
        ),
    )


def launcher_update_activity(version: str) -> SplashActivity:
    """Return activity copy for staging one launcher update version."""

    return SplashActivity(
        initial_text=launcher_text(
            "Updating the SugarSubstitute launcher to %1", version
        ),
        long_wait_text=launcher_text(
            "Updating the SugarSubstitute launcher to %1 is taking longer than usual",
            version,
        ),
        extended_wait_text=launcher_text(
            "Still updating the SugarSubstitute launcher to %1—network or slow storage "
            "may be causing the delay",
            version,
        ),
    )


__all__ = [
    "application_dependencies_activity",
    "application_install_activity",
    "launcher_update_activity",
]
