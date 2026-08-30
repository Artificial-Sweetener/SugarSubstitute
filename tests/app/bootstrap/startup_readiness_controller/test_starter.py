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

"""Test the late-bound startup readiness starter port."""

from __future__ import annotations

import pytest

from substitute.app.bootstrap.startup_readiness_resources import (
    StartupReadinessStarter,
)


class _Startable:
    """Record readiness start calls."""

    def __init__(self) -> None:
        """Initialize empty start records."""

        self.start_calls = 0

    def start(self) -> None:
        """Record one start request."""

        self.start_calls += 1


def test_startup_readiness_starter_requires_bound_controller() -> None:
    """Readiness starter should fail loudly before the controller is bound."""

    starter = StartupReadinessStarter()

    with pytest.raises(RuntimeError, match="controller is not bound"):
        starter.start()


def test_startup_readiness_starter_forwards_to_bound_controller() -> None:
    """Readiness starter should forward start requests after binding."""

    starter = StartupReadinessStarter()
    controller = _Startable()

    starter.bind(controller)
    starter.start()
    starter.start()

    assert controller.start_calls == 2
