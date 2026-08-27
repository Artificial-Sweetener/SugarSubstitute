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

"""Own onboarding controller shutdown and native Qt lifetime."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from substitute.presentation.onboarding.onboarding_controller import (
    OnboardingController,
)
from tests.support.qt.lifecycle import destroy_qt_object


@pytest.fixture
def owned_controllers() -> Iterator[list[OnboardingController]]:
    """Shut down and destroy every controller created by the current test."""

    controllers: list[OnboardingController] = []
    yield controllers
    for controller in reversed(controllers):
        controller.shutdown()
        destroy_qt_object(controller)
