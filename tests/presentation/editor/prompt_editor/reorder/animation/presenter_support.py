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

"""Build and deterministically drive mounted reorder animation presenters."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor.overlays.reorder_animation_presenter import (
    PromptReorderAnimationPresenter,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_animation import (
    PromptReorderAnimationPlan,
    PromptReorderAnimationTarget,
)
from tests.presentation.editor.prompt_editor.reorder.animation.planner_support import (
    _layout,
)
from tests.support.qt.semantic_wait import wait_for_queued_qt_turn


def _ensure_qapp() -> QApplication:
    """Return the running Qt application used by presenter tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _process_events(app: QApplication, cycles: int = 5) -> None:
    """Deliver callbacks queued by an explicitly controlled test action."""

    _ = (app, cycles)
    wait_for_queued_qt_turn()


def _host_with_chips() -> tuple[QApplication, QWidget, dict[int, QWidget]]:
    """Return a small visible widget tree for presenter-owned chip animation."""

    app = _ensure_qapp()
    host = QWidget()
    host.setGeometry(0, 0, 220, 80)
    chips = {
        0: QWidget(host),
        1: QWidget(host),
    }
    chips[0].setGeometry(0, 0, 20, 10)
    chips[1].setGeometry(24, 0, 20, 10)
    for segment_index, chip in chips.items():
        chip.setObjectName(f"chip{segment_index}")
        chip.show()
    host.show()
    _process_events(app)
    return app, host, chips


def _presenter_plan(
    *,
    generation: int,
    dragged_segment_index: int | None = None,
    changed_targets: tuple[PromptReorderAnimationTarget, ...] = (),
    immediate_targets: tuple[PromptReorderAnimationTarget, ...] = (),
    stale: bool = False,
) -> PromptReorderAnimationPlan:
    """Return one presenter-facing animation plan without invoking planning logic."""

    return PromptReorderAnimationPlan(
        generation=generation,
        dragged_segment_index=dragged_segment_index,
        ordered_segment_indices=(0, 1),
        layout_view=_layout((0, 1)),
        changed_targets=changed_targets,
        immediate_segment_indices=frozenset(
            target.segment_index for target in immediate_targets
        ),
        reason="presenter_test",
        immediate_targets=immediate_targets,
        stale=stale,
    )


def _set_presenter_animation_time(
    presenter: PromptReorderAnimationPresenter,
    elapsed_ms: int,
) -> None:
    """Drive the active Qt animation clock to an exact elapsed time."""

    animation = cast(Any, presenter)._active_animation
    assert animation is not None
    animation.setCurrentTime(elapsed_ms)
