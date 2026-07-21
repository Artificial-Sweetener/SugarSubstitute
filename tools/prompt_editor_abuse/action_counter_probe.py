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

"""Attribute production reorder-owner work to individual abuse actions."""

from __future__ import annotations

from typing import Any, cast

from .models import PromptAbuseActionOwnerDelta
from .structural_instrumentation import active_structural_counter_counts


class PromptAbuseActionCounterProbe:
    """Read owner counters around individual measured dispatch units."""

    def __init__(self, editor: object) -> None:
        """Bind the probe to one mounted production editor."""

        self._editor = editor
        self._overlay_before: Any | None = None
        self._counters_before: dict[str, float] = {}
        self._structural_counters_before: dict[str, float] = {}

    def begin_unit(self) -> None:
        """Capture the current overlay identity and numeric counter baseline."""

        self._overlay_before = _active_reorder_overlay(self._editor)
        self._counters_before = _numeric_reorder_counters(self._overlay_before)
        self._structural_counters_before = active_structural_counter_counts()

    def finish_unit(
        self,
        *,
        action_index: int,
        unit_index: int,
        label: str,
    ) -> PromptAbuseActionOwnerDelta:
        """Return non-zero counter changes for one measured dispatch unit."""

        overlay_after = _active_reorder_overlay(self._editor)
        observed_overlay = overlay_after or self._overlay_before
        counters_after = _numeric_reorder_counters(observed_overlay)
        counters_before = (
            self._counters_before if observed_overlay is self._overlay_before else {}
        )
        reorder_deltas = {
            name: value - counters_before.get(name, 0.0)
            for name, value in counters_after.items()
            if value > counters_before.get(name, 0.0)
        }
        structural_counters_after = active_structural_counter_counts()
        structural_deltas = {
            name: value - self._structural_counters_before.get(name, 0.0)
            for name, value in structural_counters_after.items()
            if value > self._structural_counters_before.get(name, 0.0)
        }
        deltas = tuple(
            (name, value)
            for name, value in sorted(
                {
                    **reorder_deltas,
                    **structural_deltas,
                }.items()
            )
        )
        reset_counter_names = tuple(
            name
            for name, value in sorted(counters_after.items())
            if value < counters_before.get(name, 0.0)
        )
        return PromptAbuseActionOwnerDelta(
            action_index=action_index,
            unit_index=unit_index,
            label=label,
            counter_deltas=deltas,
            reset_counter_names=reset_counter_names,
        )


def _active_reorder_overlay(editor: object) -> Any | None:
    """Return the production reorder overlay without creating one."""

    return getattr(editor, "_segment_overlay", None)


def _numeric_reorder_counters(overlay: Any | None) -> dict[str, float]:
    """Return numeric counters from one live or detached production overlay."""

    if overlay is None:
        return {}
    counters = cast(dict[str, object], overlay.reorder_performance_counters())
    return {
        name: float(value)
        for name, value in counters.items()
        if isinstance(value, int | float) and not isinstance(value, bool)
    }


__all__ = ["PromptAbuseActionCounterProbe"]
