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

"""Verify readiness policy for one normal installed-application lifetime."""

from __future__ import annotations

import pytest

from launcher.sugarsubstitute_launcher import application_lifecycle_supervisor
from sugarsubstitute_shared.application_readiness import ApplicationReadinessSurface


def test_normal_lifecycle_accepts_every_painted_primary_application_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normal launch must supervise main, setup, and repair application routes."""

    captured_surfaces: list[frozenset[ApplicationReadinessSurface]] = []

    class _ReadinessSupervisor:
        """Capture normal-lifecycle readiness construction."""

        def __init__(
            self,
            *,
            accepted_surfaces: tuple[ApplicationReadinessSurface, ...],
        ) -> None:
            """Record the accepted painted surfaces."""

            captured_surfaces.append(frozenset(accepted_surfaces))

    class _CrashSupervisor:
        """Stand in for unrelated crash supervision construction."""

    monkeypatch.setattr(
        application_lifecycle_supervisor,
        "ApplicationReadinessSupervisor",
        _ReadinessSupervisor,
    )
    monkeypatch.setattr(
        application_lifecycle_supervisor,
        "ApplicationCrashSupervisor",
        _CrashSupervisor,
    )

    application_lifecycle_supervisor.ApplicationLifecycleSupervisor()

    assert captured_surfaces == [
        frozenset(
            {
                ApplicationReadinessSurface.MAIN_SHELL,
                ApplicationReadinessSurface.ONBOARDING,
            }
        )
    ]
