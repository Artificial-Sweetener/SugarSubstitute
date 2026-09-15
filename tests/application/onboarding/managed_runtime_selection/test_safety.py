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

"""Regression tests for interruption-safe setup transaction state."""

from __future__ import annotations


from substitute.application.onboarding import ManagedRuntimeService
from substitute.domain.onboarding import (
    ManagedRuntimeConfiguration,
)


from tests.support.onboarding.setup_transaction_state import (
    _RecordingManagedRuntimeRepository,
    _StaticSelectionPolicy,
    _UnavailableSelectionPolicy,
)


def test_managed_runtime_selection_does_not_persist_active_state() -> None:
    """Selecting a runtime should be side-effect free until explicitly saved."""

    selected = ManagedRuntimeConfiguration(install_target="windows_nvidia")
    repository = _RecordingManagedRuntimeRepository()
    service = ManagedRuntimeService(
        repository,
        selection_policy=_StaticSelectionPolicy(selected),
    )

    result = service.select_configuration()

    assert result == selected
    assert repository.saved is None


def test_managed_runtime_draft_falls_back_when_managed_install_is_unavailable() -> None:
    """Opening onboarding remains possible without a managed Comfy install target."""

    repository = _RecordingManagedRuntimeRepository()
    service = ManagedRuntimeService(
        repository,
        selection_policy=_UnavailableSelectionPolicy(),
    )

    result = service.load_draft_configuration()

    assert result == ManagedRuntimeConfiguration()
    assert repository.saved is None
