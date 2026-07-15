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

"""Normalize generation progress payloads into presentation-friendly state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProgressViewState:
    """Capture progress values used by overlay bars and taskbar progress."""

    show_overlay: bool
    workflow_value: int
    sampler_value: int
    active: bool = True
    workflow_id: str | None = None
    generation_run_id: str | None = None
    prompt_id: str | None = None

    @classmethod
    def hidden(
        cls,
        *,
        workflow_id: str | None = None,
        generation_run_id: str | None = None,
        prompt_id: str | None = None,
    ) -> "ProgressViewState":
        """Return a hidden progress state that resets all visible values."""

        return cls(
            show_overlay=False,
            workflow_value=0,
            sampler_value=0,
            active=False,
            workflow_id=workflow_id,
            generation_run_id=generation_run_id,
            prompt_id=prompt_id,
        )


@dataclass(frozen=True)
class ModelLoadProgressViewState:
    """Capture presentation state for measured model-loading progress."""

    show_overlay: bool
    value: int
    display_percent: float | None


class ProgressService:
    """Build deterministic progress display state without UI dependencies."""

    def build_view_state(
        self,
        *,
        active: bool,
        workflow_percent: float | None,
        sampler_percent: float | None,
        workflow_id: str | None = None,
        generation_run_id: str | None = None,
        prompt_id: str | None = None,
    ) -> ProgressViewState:
        """Convert raw percentage updates into UI-ready overlay values."""

        if not active:
            return ProgressViewState.hidden(
                workflow_id=workflow_id,
                generation_run_id=generation_run_id,
                prompt_id=prompt_id,
            )
        workflow_value_raw = self._clamp_percent(workflow_percent)
        sampler_value_raw = self._clamp_percent(sampler_percent)
        show_overlay = (
            workflow_value_raw is not None and workflow_value_raw < 100
        ) or (sampler_value_raw is not None and sampler_value_raw < 100)
        workflow_value = (
            int(workflow_value_raw) if workflow_value_raw is not None else 0
        )
        sampler_value = int(sampler_value_raw) if sampler_value_raw is not None else 0
        return ProgressViewState(
            show_overlay=show_overlay,
            workflow_value=workflow_value,
            sampler_value=sampler_value,
            active=show_overlay,
            workflow_id=workflow_id,
            generation_run_id=generation_run_id,
            prompt_id=prompt_id,
        )

    def build_model_load_view_state(
        self,
        *,
        percent: float | None,
        state: str,
    ) -> ModelLoadProgressViewState:
        """Convert measured model-loading telemetry into overlay state."""
        percent_raw = self._clamp_percent(percent)
        display_percent = (
            min(percent_raw, 99.0)
            if percent_raw is not None and state == "running"
            else None
        )
        show_overlay = display_percent is not None
        return ModelLoadProgressViewState(
            show_overlay=show_overlay,
            value=int(display_percent) if display_percent is not None else 0,
            display_percent=display_percent,
        )

    @staticmethod
    def _clamp_percent(percent: float | None) -> float | None:
        """Return a percentage constrained to progress presentation bounds."""
        if percent is None:
            return None
        return min(100.0, max(0.0, percent))


__all__ = [
    "ModelLoadProgressViewState",
    "ProgressService",
    "ProgressViewState",
]
