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

"""Own atomic Contextual Toolbar page, geometry, and opacity morphs."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from PySide6.QtCore import QObject, QSize
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from substitute.presentation.motion.fluent_motion import (
    CONTEXTUAL_TOOLBAR_DURATION_MS,
    resolve_motion_duration,
)

from .content_stage import ContextualToolbarContentStage
from .page import ContextualToolbarPage


class ContextualToolbarContentMotion(QObject):
    """Morph one mounted page without exposing content outside its host."""

    def __init__(
        self,
        *,
        host: QWidget,
        current_size: Callable[[], QSize],
        apply_size: Callable[[QSize], None],
        mount_page: Callable[[ContextualToolbarPage], None],
        release_page: Callable[[ContextualToolbarPage], None],
    ) -> None:
        """Bind the sole page-lifetime and animated-geometry collaborators."""

        super().__init__(host)
        self._host = host
        self._current_size = current_size
        self._apply_size = apply_size
        self._mount_page = mount_page
        self._release_page = release_page
        self._displayed: ContextualToolbarPage | None = None
        self._pending: ContextualToolbarPage | None = None
        self._effect: QGraphicsOpacityEffect | None = None
        self._stage = ContextualToolbarContentStage(self)
        self._generation = 0

    def present(self, page: ContextualToolbarPage) -> None:
        """Mount initial content at its complete intrinsic geometry."""

        self.clear()
        self._displayed = page
        self._apply_size(QSize(page.sizeHint()))
        self._mount_page(page)
        page.setEnabled(True)

    def replace(self, page: ContextualToolbarPage) -> None:
        """Fade through one contained midpoint while morphing to a new page."""

        displayed = self._displayed
        if displayed is None:
            self.present(page)
            return
        self._generation += 1
        generation = self._generation
        self._interrupt_replacement()
        self._pending = page
        page.setEnabled(False)
        page.hide()
        target_size = QSize(page.sizeHint())
        envelope = _size_envelope(
            self._current_size(),
            displayed.sizeHint(),
            target_size,
        )
        duration = resolve_motion_duration(CONTEXTUAL_TOOLBAR_DURATION_MS)
        if duration == 0:
            self._apply_size(envelope)
            self._swap_pending(generation, target_size, duration=0)
            return
        displayed.setEnabled(False)
        self._animate_stage(
            generation=generation,
            target_size=envelope,
            target_opacity=0.0,
            duration=max(1, duration // 2),
            finished=partial(
                self._swap_pending,
                generation,
                target_size,
                duration=max(1, duration - duration // 2),
            ),
        )

    def retarget_current_size(self, page: ContextualToolbarPage) -> None:
        """Keep a live page contained after its intrinsic geometry changes."""

        if page is not self._displayed or self._pending is not None:
            return
        target = QSize(page.sizeHint())
        current = self._current_size()
        if target.width() > current.width() or target.height() > current.height():
            self._apply_size(_size_envelope(current, target))
            return
        duration = resolve_motion_duration(CONTEXTUAL_TOOLBAR_DURATION_MS)
        if duration == 0:
            self._apply_size(target)
            return
        self._generation += 1
        self._stop_stage()
        self._animate_stage(
            generation=self._generation,
            target_size=target,
            target_opacity=self._current_opacity(),
            duration=duration,
        )

    def settle(self, current: ContextualToolbarPage | None) -> None:
        """Remove transient effects before an ancestor shell starts painting."""

        self._generation += 1
        self._stop_stage()
        pending = self._pending
        self._pending = None
        displayed = self._displayed
        if pending is not None and pending is current:
            self._apply_size(_size_envelope(self._current_size(), pending.sizeHint()))
            if displayed is not None and displayed is not pending:
                self._release_page(displayed)
            self._displayed = pending
            self._mount_page(pending)
        elif pending is not None:
            self._release_page(pending)
        if current is not None:
            self._apply_size(QSize(current.sizeHint()))
            self._displayed = current
            self._mount_page(current)
            current.setEnabled(True)
        self._detach_effect()

    def clear(self) -> None:
        """Release every page and remove all transient paint effects."""

        self._generation += 1
        self._stop_stage()
        pages = tuple(
            page for page in (self._displayed, self._pending) if page is not None
        )
        self._displayed = None
        self._pending = None
        for index, page in enumerate(pages):
            if page not in pages[:index]:
                self._release_page(page)
        self._detach_effect()
        self._apply_size(QSize())

    def _swap_pending(
        self,
        generation: int,
        target_size: QSize,
        *,
        duration: int,
    ) -> None:
        """Swap pages only after the host can contain both intrinsic sizes."""

        if generation != self._generation:
            return
        self._stop_stage()
        incoming = self._pending
        if incoming is None:
            return
        outgoing = self._displayed
        self._pending = None
        self._displayed = incoming
        if outgoing is not None and outgoing is not incoming:
            self._release_page(outgoing)
        incoming.setEnabled(True)
        self._mount_page(incoming)
        if duration == 0:
            self._apply_size(QSize(target_size))
            incoming.setEnabled(True)
            self._detach_effect()
            return
        self._animate_stage(
            generation=generation,
            target_size=target_size,
            target_opacity=1.0,
            duration=duration,
            finished=partial(self._finish_replacement, generation, incoming),
        )

    def _finish_replacement(
        self,
        generation: int,
        incoming: ContextualToolbarPage,
    ) -> None:
        """Publish a fully interactive terminal page for the latest generation."""

        if generation != self._generation:
            return
        self._stop_stage()
        self._apply_size(QSize(incoming.sizeHint()))
        incoming.setEnabled(True)
        self._detach_effect()

    def _animate_stage(
        self,
        *,
        generation: int,
        target_size: QSize,
        target_opacity: float,
        duration: int,
        finished: Callable[[], None] | None = None,
    ) -> None:
        """Animate one coordinated size-and-opacity stage from rendered state."""

        self._stage.start(
            current_size=self._current_size(),
            apply_size=self._apply_size,
            effect=self._install_effect(),
            target_size=target_size,
            target_opacity=target_opacity,
            duration=duration,
            finished=(
                finished
                if finished is not None
                else partial(self._finish_size_only, generation)
            ),
        )

    def _finish_size_only(self, generation: int) -> None:
        """Release a size-only animation without disturbing current content."""

        if generation != self._generation:
            return
        self._stop_stage()
        self._detach_effect()

    def _interrupt_replacement(self) -> None:
        """Retain rendered opacity while discarding only the superseded target."""

        self._stop_stage()
        pending = self._pending
        self._pending = None
        if pending is not None and pending is not self._displayed:
            self._release_page(pending)

    def _install_effect(self) -> QGraphicsOpacityEffect:
        """Install the single temporary effect owned by content motion."""

        effect = self._effect
        if effect is None:
            effect = QGraphicsOpacityEffect(self._host)
            effect.setOpacity(1.0)
            self._host.setGraphicsEffect(effect)
            self._effect = effect
        return effect

    def _detach_effect(self) -> None:
        """Remove terminal content effects to prevent nested Qt paint devices."""

        if self._effect is None:
            return
        self._host.setGraphicsEffect(None)  # type: ignore[arg-type]
        self._effect = None

    def _current_opacity(self) -> float:
        """Return the opacity currently rendered by the content host."""

        return 1.0 if self._effect is None else float(self._effect.opacity())

    def _stop_stage(self) -> None:
        """Stop and release the current coordinated interpolation stage."""

        self._stage.stop()


def _size_envelope(*sizes: QSize) -> QSize:
    """Return the smallest size that contains every supplied geometry."""

    return QSize(
        max((size.width() for size in sizes), default=0),
        max((size.height() for size in sizes), default=0),
    )


__all__ = ["ContextualToolbarContentMotion"]
