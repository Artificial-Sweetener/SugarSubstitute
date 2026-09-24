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

"""Verify explicit binding of cross-graph projection effects."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF

from substitute.presentation.editor.prompt_editor.projection.surface_graph_effects import (
    PromptProjectionSurfaceGraphEffectBindings,
    PromptProjectionSurfaceGraphEffects,
)


def test_surface_graph_effects_reject_dispatch_before_binding() -> None:
    """Expose construction-order violations instead of reaching future owners."""

    effects = PromptProjectionSurfaceGraphEffects()

    with pytest.raises(RuntimeError, match="graph effects are unwired"):
        effects.ensure_caret_visible()


def test_surface_graph_effects_forward_complete_bound_contract() -> None:
    """Forward every cross-graph effect through one authoritative binding."""

    calls: list[tuple[object, ...]] = []
    effects = PromptProjectionSurfaceGraphEffects()
    effects.bind(
        PromptProjectionSurfaceGraphEffectBindings(
            projection_is_stale=lambda: True,
            rebuild_projection=lambda: calls.append(("rebuild",)),
            reconcile_autocomplete=(
                lambda cursor, empty: calls.append(("autocomplete", cursor, empty))
            ),
            refresh_active_projection=lambda: calls.append(("active",)),
            ensure_caret_visible=lambda: calls.append(("visible",)),
            refresh_caret_layers=lambda: calls.append(("caret_layers",)),
            refresh_deferred_caret_layers=lambda: calls.append(("deferred_layers",)),
            restart_caret_blink=lambda: calls.append(("restart_blink",)),
            update_caret_paint=lambda rect: calls.append(("caret_paint", rect)),
            diagnostic_layer_changed=lambda: calls.append(("diagnostics",)),
            rebuild_active_projection=lambda: calls.append(("rebuild_active",)),
            prepare_focus_chrome=lambda: calls.append(("focus_chrome",)),
            schedule_caret_blink=lambda reset: calls.append(("schedule_blink", reset)),
            is_projected=lambda: True,
            apply_session_paint_state=lambda: False,
        )
    )
    previous_rect = QRectF(1.0, 2.0, 3.0, 4.0)

    assert effects.projection_is_stale() is True
    effects.rebuild_projection()
    effects.reconcile_autocomplete(7, False)
    effects.refresh_active_projection()
    effects.ensure_caret_visible()
    effects.refresh_caret_layers()
    effects.refresh_deferred_caret_layers()
    effects.restart_caret_blink()
    effects.update_caret_paint(previous_rect)
    effects.diagnostic_layer_changed()
    effects.rebuild_active_projection()
    effects.prepare_focus_chrome()
    effects.schedule_caret_blink(True)
    assert effects.is_projected() is True
    assert effects.apply_session_paint_state() is False

    assert calls == [
        ("rebuild",),
        ("autocomplete", 7, False),
        ("active",),
        ("visible",),
        ("caret_layers",),
        ("deferred_layers",),
        ("restart_blink",),
        ("caret_paint", previous_rect),
        ("diagnostics",),
        ("rebuild_active",),
        ("focus_chrome",),
        ("schedule_blink", True),
    ]


def test_surface_graph_effects_reject_rebinding() -> None:
    """Preserve one graph binding for the mounted surface lifetime."""

    effects = PromptProjectionSurfaceGraphEffects()
    bindings = PromptProjectionSurfaceGraphEffectBindings(
        projection_is_stale=lambda: False,
        rebuild_projection=lambda: None,
        reconcile_autocomplete=lambda _cursor, _empty: None,
        refresh_active_projection=lambda: None,
        ensure_caret_visible=lambda: None,
        refresh_caret_layers=lambda: None,
        refresh_deferred_caret_layers=lambda: None,
        restart_caret_blink=lambda: None,
        update_caret_paint=lambda _rect: None,
        diagnostic_layer_changed=lambda: None,
        rebuild_active_projection=lambda: None,
        prepare_focus_chrome=lambda: None,
        schedule_caret_blink=lambda _reset: None,
        is_projected=lambda: False,
        apply_session_paint_state=lambda: False,
    )
    effects.bind(bindings)

    with pytest.raises(RuntimeError, match="graph effects are wired"):
        effects.bind(bindings)
