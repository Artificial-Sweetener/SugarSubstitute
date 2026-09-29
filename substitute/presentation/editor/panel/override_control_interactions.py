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

"""Own committed toolbar override values and seed-mode interactions."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

from PySide6.QtCore import QSignalBlocker

from substitute.application.overrides import PinnedOverrideService
from substitute.domain.generation.seed_control import (
    SeedControlState,
    SeedMode,
    seed_mode_from_value,
)
from substitute.presentation.editor.panel.override_control_binding import (
    bind_override_control,
)
from substitute.presentation.editor.panel.override_workflow_state import (
    compact_override_log_value,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("presentation.editor.panel.override_control_interactions")


class OverrideControlInteractionController:
    """Bind toolbar controls to authoritative workflow value and mode state."""

    def __init__(
        self,
        mainwindow: Any,
        service: PinnedOverrideService,
        *,
        on_value_committed: Callable[[], None],
        request_autosave: Callable[[], None],
    ) -> None:
        """Capture workflow and post-commit integration boundaries."""

        self._mainwindow = mainwindow
        self._service = service
        self._on_value_committed = on_value_committed
        self._request_autosave = request_autosave

    def bind(self, override_key: str, widget: Any) -> None:
        """Bind one realized control to value and optional seed-mode commands."""

        self._restore_seed_mode(override_key, widget)
        self._connect_seed_mode_signal(override_key, widget)
        bind_override_control(
            widget,
            partial(self._commit_value, override_key),
        )

    def project_seed_value(self, widget: Any, value: int) -> None:
        """Project authoritative seed state without emitting user intent."""

        blocker = QSignalBlocker(widget)
        try:
            setter = getattr(widget, "setValue", None)
            if callable(setter):
                setter(int(value))
        finally:
            del blocker

    def _commit_value(self, override_key: str, value: object) -> None:
        """Persist one committed toolbar value and refresh its projections."""

        workflow = self._mainwindow.get_active_workflow()
        if workflow is None:
            return
        workflow_overrides = self._service.normalize_workflow_overrides(
            getattr(workflow, "global_overrides", None)
        )
        log_debug(
            _LOGGER,
            "sync override from toolbar buffer",
            override_key=override_key,
            value=compact_override_log_value(value),
            previous_value=compact_override_log_value(
                workflow_overrides.get(override_key, {}).get("value")
            ),
        )
        self._service.set_override_value(workflow_overrides, override_key, value)
        workflow.global_overrides = dict(workflow_overrides)
        self._on_value_committed()
        self._request_autosave()

    def _restore_seed_mode(self, override_key: str, widget: Any) -> None:
        """Restore workflow seed mode on one realized seed control."""

        if not self._is_seed_widget(override_key, widget):
            return
        set_mode = getattr(widget, "setMode", None)
        if callable(set_mode):
            set_mode(self._seed_mode(override_key).value)

    def _connect_seed_mode_signal(self, override_key: str, widget: Any) -> None:
        """Connect one seed control's mode signal to workflow persistence."""

        if not self._is_seed_widget(override_key, widget):
            return
        mode_changed = getattr(widget, "modeChanged", None)
        if mode_changed is None or not hasattr(mode_changed, "connect"):
            return
        mode_changed.connect(
            lambda mode, key=override_key: self._sync_seed_mode(key, mode)
        )

    def _seed_mode(self, override_key: str) -> SeedMode:
        """Return the workflow-owned seed mode for one override key."""

        workflow = self._mainwindow.get_active_workflow()
        canonical_key = self._service.canonicalize_override_key(override_key)
        states = getattr(workflow, "override_control_states", None)
        if not isinstance(states, dict):
            return SeedMode.RANDOM
        state = states.get(canonical_key)
        return state.mode if isinstance(state, SeedControlState) else SeedMode.RANDOM

    def _sync_seed_mode(self, override_key: str, mode: object) -> None:
        """Persist seed random/fixed mode without changing override participation."""

        workflow = self._mainwindow.get_active_workflow()
        if workflow is None:
            return
        canonical_key = self._service.canonicalize_override_key(override_key)
        next_state = SeedControlState(seed_mode_from_value(mode))
        states = getattr(workflow, "override_control_states", None)
        if not isinstance(states, dict):
            states = {}
            setattr(workflow, "override_control_states", states)
        previous = states.get(canonical_key)
        if isinstance(previous, SeedControlState) and previous.mode == next_state.mode:
            return
        states[canonical_key] = next_state
        self._request_autosave()
        log_debug(
            _LOGGER,
            "persisted override seed mode",
            override_key=canonical_key,
            seed_mode=next_state.mode.value,
        )

    def _is_seed_widget(self, override_key: str, widget: Any) -> bool:
        """Return whether one toolbar widget carries seed random/fixed mode."""

        canonical_key = self._service.canonicalize_override_key(override_key)
        return (
            canonical_key == "seed"
            and widget.__class__.__name__ == "SeedBox"
            and hasattr(widget, "modeChanged")
        )


__all__ = ["OverrideControlInteractionController"]
