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

"""Reconcile realized override controls with semantic toolbar snapshots."""

from __future__ import annotations

from typing import Any

from substitute.application.overrides import (
    OverrideToolbarSnapshot,
    PinnedOverrideControl,
)
from substitute.presentation.editor.panel.override_control_interactions import (
    OverrideControlInteractionController,
)
from substitute.presentation.editor.panel.override_control_realizer import (
    OverrideControlRealizer,
)
from substitute.presentation.editor.panel.override_toolbar_registry import (
    OverrideToolbarRegistry,
)
from substitute.presentation.editor.panel.override_workflow_state import (
    compact_override_log_value,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("presentation.editor.panel.override_toolbar_controller")


class OverrideToolbarController:
    """Apply semantic override snapshots to mounted toolbar controls."""

    def __init__(
        self,
        mainwindow: Any,
        *,
        registry: OverrideToolbarRegistry,
        realizer: OverrideControlRealizer,
        interactions: OverrideControlInteractionController,
    ) -> None:
        """Capture the focused realization, interaction, and layout owners."""

        self._mainwindow = mainwindow
        self.registry = registry
        self._realizer = realizer
        self._interactions = interactions

    def rebuild(self, snapshot: OverrideToolbarSnapshot) -> None:
        """Reconcile mounted controls with one authoritative toolbar snapshot."""

        log_debug(
            _LOGGER,
            "rebuilding active override controls started",
            active_override_keys=snapshot.active_override_keys,
            existing_control_keys=tuple(sorted(self.registry.controls)),
            active_controls=tuple(
                {
                    "override_key": control.override_key,
                    "value": compact_override_log_value(control.value),
                    "representative_cube": control.spec.cube_alias,
                    "representative_node": control.spec.node_name,
                    "representative_class": control.spec.class_type,
                    "representative_field": control.spec.field_key,
                    "spec_value": compact_override_log_value(control.spec.value),
                    "spec_raw_value": compact_override_log_value(
                        control.spec.raw_value
                    ),
                    "spec_value_source": control.spec.value_source.value,
                }
                for control in snapshot.active_controls
            ),
        )
        active_by_key = {
            control.override_key: control for control in snapshot.active_controls
        }
        active_signature = tuple(
            self._realizer.signature(control) for control in snapshot.active_controls
        )
        active_keys_unchanged = tuple(sorted(self.registry.controls)) == tuple(
            sorted(active_by_key)
        )
        if (
            self.registry.active_signature == active_signature
            and active_keys_unchanged
            and self.registry.all_attached(active_by_key)
        ):
            self._normalize_existing(active_by_key)
            self._refresh_restart_spacing()
            return
        reused_count = 0
        created_count = 0
        removed_count = 0
        replaced_count = 0

        for override_key in list(self.registry.controls):
            if override_key not in active_by_key and self.registry.remove(override_key):
                removed_count += 1

        for control in snapshot.active_controls:
            signature = self._realizer.signature(control)
            existing_control = self.registry.control(control.override_key)
            existing_signature = self.registry.control_signature(control.override_key)
            if existing_control is not None and existing_signature == signature:
                label_widget, widget = existing_control
                self._realizer.normalize(control, label_widget, widget)
                self.registry.insert(
                    override_key=control.override_key,
                    label_widget=label_widget,
                    widget=widget,
                    active_keys=snapshot.active_override_keys,
                )
                reused_count += 1
                continue
            if existing_control is not None:
                self.registry.remove(control.override_key)
                replaced_count += 1
            if self._create(control, snapshot.active_override_keys):
                created_count += 1
        log_debug(
            _LOGGER,
            "Rebuilt active override controls",
            reused_count=reused_count,
            created_count=created_count,
            removed_count=removed_count,
            replaced_count=replaced_count,
            active_control_count=len(snapshot.active_controls),
        )
        self.registry.active_signature = active_signature
        self._refresh_restart_spacing()

    def project_seed_value(self, value: int) -> None:
        """Project the authoritative seed into a mounted seed control."""

        control = self.registry.control("seed")
        if control is None:
            return
        _label, widget = control
        self._interactions.project_seed_value(widget, value)

    def detach(self) -> None:
        """Detach cached controls without disposing reusable widgets."""

        self.registry.detach()

    def clear(self) -> None:
        """Dispose all mounted controls and reset reconciliation identity."""

        self.registry.clear()

    def mounted_control_count(self) -> int:
        """Return the number of realized toolbar override controls."""

        return len(self.registry.controls)

    def _normalize_existing(
        self,
        active_by_key: dict[str, PinnedOverrideControl],
    ) -> None:
        """Restore sizing and live options on every reused control."""

        for override_key, control in active_by_key.items():
            existing_control = self.registry.control(override_key)
            if existing_control is None:
                continue
            label_widget, widget = existing_control
            self._realizer.normalize(control, label_widget, widget)

    def _create(
        self,
        control: PinnedOverrideControl,
        active_keys: tuple[str, ...],
    ) -> bool:
        """Realize, mount, register, and bind one active override control."""

        realization = self._realizer.realize(control)
        if realization is None:
            return False
        self.registry.insert(
            override_key=control.override_key,
            label_widget=realization.label_widget,
            widget=realization.widget,
            active_keys=active_keys,
        )
        self.registry.register(
            control.override_key,
            realization.label_widget,
            realization.widget,
            realization.signature,
        )
        self._interactions.bind(control.override_key, realization.widget)
        return True

    def _refresh_restart_spacing(self) -> None:
        """Ask the restart toolbar control to absorb slack after reconciliation."""

        refresh = getattr(
            getattr(self._mainwindow, "pendingRestartButton", None),
            "refresh_toolbar_spacing",
            None,
        )
        if callable(refresh):
            refresh()


__all__ = ["OverrideToolbarController"]
