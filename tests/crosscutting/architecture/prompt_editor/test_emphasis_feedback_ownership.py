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

"""Enforce focused ownership of projection emphasis feedback."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_surface_delegates_emphasis_projection_to_focused_owner() -> None:
    """Keep emphasis state, feedback, and caret policy outside the mounted surface."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    lifecycle_runtime_source = (
        projection_root / "surface_lifecycle_runtime.py"
    ).read_text(encoding="utf-8")
    projection_owner_source = (
        projection_root / "emphasis_projection_owner.py"
    ).read_text(encoding="utf-8")
    feedback_owner_source = (projection_root / "emphasis_feedback_owner.py").read_text(
        encoding="utf-8"
    )
    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    facade_source = (PROMPT_PRESENTATION_ROOT / "emphasis_facade.py").read_text(
        encoding="utf-8"
    )

    obsolete_surface_state = (
        "self._overlay_emphasis_accent_range",
        "self._wheel_intent_emphasis_accent_range",
        "self._pulsed_emphasis_accent_range",
        "self._emphasis_feedback_timer",
        "def _clear_pulsed_emphasis_accent_range(",
    )
    assert all(item not in surface_source for item in obsolete_surface_state)
    assert "self._emphasis.accent_ranges()" in surface_source
    assert "self._emphasis = lifecycle_runtime.emphasis" in surface_source
    assert "PromptProjectionEmphasisOwner(" in lifecycle_runtime_source
    assert "PromptProjectionEmphasisOwner(" not in surface_source
    assert "class PromptProjectionEmphasisOwner" in projection_owner_source
    assert "class PromptProjectionEmphasisFeedbackOwner" in feedback_owner_source
    assert (
        "self._pulse_timer.timeout.connect(self.clear_pulse)" in feedback_owner_source
    )

    moved_methods = (
        "set_emphasis_adjustment_session",
        "clear_emphasis_adjustment_session",
        "emphasis_adjustment_session",
        "prompt_weight_wheel_identity",
        "pulse_emphasis_feedback",
        "show_transient_neutral_emphasis",
        "clear_transient_neutral_emphasis",
        "set_emphasis_caret_to_content_boundary",
    )
    for method_name in moved_methods:
        declaration = f"def {method_name}("
        assert declaration not in surface_source
        assert declaration not in widget_source
        assert declaration in facade_source
