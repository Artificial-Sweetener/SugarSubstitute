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

"""Verify explicit binding of projection source lifecycle effects."""

from __future__ import annotations

import pytest

from substitute.presentation.editor.prompt_editor.projection.source_lifecycle_effects import (
    PromptProjectionSourceLifecycleEffectBindings,
    PromptProjectionSourceLifecycleEffects,
)


def test_source_lifecycle_effects_reject_dispatch_before_binding() -> None:
    """Expose construction-order violations instead of calling future owners."""

    effects = PromptProjectionSourceLifecycleEffects()

    with pytest.raises(RuntimeError, match="effects are unwired"):
        effects.rebuild_projection()


def test_source_lifecycle_effects_forward_every_bound_operation() -> None:
    """Forward source effects through one complete, authoritative binding."""

    calls: list[tuple[object, ...]] = []
    effects = PromptProjectionSourceLifecycleEffects()
    effects.bind(
        PromptProjectionSourceLifecycleEffectBindings(
            ensure_caret_visible=lambda: calls.append(("ensure_caret_visible",)),
            rebuild_projection=lambda: calls.append(("rebuild_projection",)),
            publish_active_span_range=(
                lambda value: calls.append(("publish_active_span_range", value))
            ),
            reconcile_committed_active_projection=(
                lambda: calls.append(("reconcile_committed_active_projection",))
            ),
            rebuild_active_projection=(
                lambda commit: calls.append(("rebuild_active_projection", commit))
            ),
            clear_reorder_for_source_change=(
                lambda: calls.append(("clear_reorder_for_source_change",))
            ),
            invalidate_render_for_source_change=(
                lambda clear_cache: calls.append(
                    ("invalidate_render_for_source_change", clear_cache)
                )
            ),
        )
    )

    effects.ensure_caret_visible()
    effects.rebuild_projection()
    effects.publish_active_span_range((2, 5))
    effects.reconcile_committed_active_projection()
    effects.rebuild_active_projection(True)
    effects.clear_reorder_for_source_change()
    effects.invalidate_render_for_source_change(False)

    assert calls == [
        ("ensure_caret_visible",),
        ("rebuild_projection",),
        ("publish_active_span_range", (2, 5)),
        ("reconcile_committed_active_projection",),
        ("rebuild_active_projection", True),
        ("clear_reorder_for_source_change",),
        ("invalidate_render_for_source_change", False),
    ]


def test_source_lifecycle_effects_reject_rebinding() -> None:
    """Preserve one authoritative lifecycle binding for the surface lifetime."""

    effects = PromptProjectionSourceLifecycleEffects()
    bindings = PromptProjectionSourceLifecycleEffectBindings(
        ensure_caret_visible=lambda: None,
        rebuild_projection=lambda: None,
        publish_active_span_range=lambda _value: None,
        reconcile_committed_active_projection=lambda: None,
        rebuild_active_projection=lambda _commit: None,
        clear_reorder_for_source_change=lambda: None,
        invalidate_render_for_source_change=lambda _clear_cache: None,
    )
    effects.bind(bindings)

    with pytest.raises(RuntimeError, match="effects are wired"):
        effects.bind(bindings)
