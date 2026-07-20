#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Coordinate editor surface work caused by persisted field value changes."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol

from PySide6.QtCore import QTimer

from .field_state_controller import EditorFieldBinding
from .preset_context_refresh import PanelPresetContextRefreshCoordinator

_DYNAMIC_COMBO_TYPE = "COMFY_DYNAMICCOMBO_V3"


class DynamicFieldRefreshHost(Protocol):
    """Describe panel operations needed to rebuild one dynamic field surface."""

    _cube_states: Mapping[str, object] | None
    _stack_order: Sequence[str] | None

    def mark_cube_sections_stale(
        self,
        cube_aliases: Sequence[str],
        *,
        reason: str,
    ) -> bool:
        """Prevent affected cube sections from being reused."""

    def insert_cube_section(
        self,
        cube_alias: str,
        cube_state: object,
        cube_states: Mapping[str, object] | None = None,
        stack_order: Sequence[str] | None = None,
        on_complete: Callable[[], None] | None = None,
        completion_phase: str = "first_usable",
    ) -> None:
        """Reconcile one cube through the production projection path."""


class PanelFieldValueChangeCoordinator:
    """Refresh field consumers and reproject schema-changing native controls."""

    def __init__(
        self,
        *,
        host: DynamicFieldRefreshHost,
        preset_context: PanelPresetContextRefreshCoordinator,
        schedule: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        """Store collaborators and the deferred Qt-safe refresh scheduler."""

        self._host = host
        self._preset_context = preset_context
        self._schedule = schedule or self._schedule_on_qt_event_loop
        self._pending_cube_aliases: set[str] = set()

    def field_value_changed(
        self,
        binding: EditorFieldBinding,
        value: object,
    ) -> None:
        """Propagate one value and schedule schema-dependent card replacement."""

        self._preset_context.update_field_value(
            cube_alias=binding.cube_alias,
            node_name=binding.node_name,
            node_type=binding.node_type,
            field_key=binding.field_key,
            value=value,
        )
        cube_alias = binding.cube_alias
        if (
            binding.native_widget_type != _DYNAMIC_COMBO_TYPE
            or cube_alias is None
            or cube_alias in self._pending_cube_aliases
        ):
            return
        self._pending_cube_aliases.add(cube_alias)
        self._schedule(lambda: self._refresh_cube(cube_alias))

    def _refresh_cube(self, cube_alias: str) -> None:
        """Replace one stale cube so active dynamic descendants match its selector."""

        self._pending_cube_aliases.discard(cube_alias)
        cube_states = self._host._cube_states
        if cube_states is None:
            return
        cube_state = cube_states.get(cube_alias)
        if cube_state is None:
            return
        self._host.mark_cube_sections_stale(
            (cube_alias,),
            reason="native_dynamic_field_changed",
        )
        self._host.insert_cube_section(
            cube_alias,
            cube_state,
            cube_states=cube_states,
            stack_order=self._host._stack_order,
            completion_phase="complete",
        )

    @staticmethod
    def _schedule_on_qt_event_loop(callback: Callable[[], None]) -> None:
        """Defer destructive widget replacement until the current signal returns."""

        QTimer.singleShot(0, callback)


__all__ = ["DynamicFieldRefreshHost", "PanelFieldValueChangeCoordinator"]
