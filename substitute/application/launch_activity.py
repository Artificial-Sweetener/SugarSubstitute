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

"""Define localized activity copy for long-running startup operations."""

from __future__ import annotations

from dataclasses import dataclass

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.domain.comfy_nodepacks import CoreNodepackId


@dataclass(frozen=True, slots=True)
class LocalizedSplashActivity:
    """Carry untranslated application copy for every splash wait stage."""

    initial_text: ApplicationText
    long_wait_text: ApplicationText
    extended_wait_text: ApplicationText


def owned_nodepack_update_activity(
    nodepacks: frozenset[CoreNodepackId],
) -> LocalizedSplashActivity:
    """Return operation-specific activity copy for targeted nodepack updates."""

    if nodepacks == frozenset({CoreNodepackId.SUBSTITUTE_BACKEND}):
        return LocalizedSplashActivity(
            initial_text=app_text("Updating Substitute BackEnd"),
            long_wait_text=app_text(
                "Updating Substitute BackEnd is taking longer than usual"
            ),
            extended_wait_text=app_text(
                "Still updating Substitute BackEnd—network, slow storage, or package "
                "installation may be causing the delay"
            ),
        )
    if nodepacks == frozenset({CoreNodepackId.SUGARCUBES}):
        return LocalizedSplashActivity(
            initial_text=app_text("Updating SugarCubes"),
            long_wait_text=app_text("Updating SugarCubes is taking longer than usual"),
            extended_wait_text=app_text(
                "Still updating SugarCubes—network, slow storage, or package "
                "installation may be causing the delay"
            ),
        )
    return LocalizedSplashActivity(
        initial_text=app_text("Updating Substitute Comfy nodepacks"),
        long_wait_text=app_text(
            "Updating Substitute Comfy nodepacks is taking longer than usual"
        ),
        extended_wait_text=app_text(
            "Still updating Substitute Comfy nodepacks—network, slow storage, or "
            "package installation may be causing the delay"
        ),
    )


__all__ = ["LocalizedSplashActivity", "owned_nodepack_update_activity"]
