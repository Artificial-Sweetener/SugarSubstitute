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

"""Contract tests for shared generation titlebar control registration."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.shell.generation_action_state import (
    GenerationActionPresentation,
)
from substitute.presentation.shell.generation_titlebar_control_registry import (
    GenerationTitleBarControlRegistry,
)
from substitute.presentation.shell.titlebar_buttons import GenerationTitleBarRunControl


class _Signal:
    """Minimal signal double with connect, disconnect, and emit."""

    def __init__(self) -> None:
        """Initialize an empty callback list."""

        self.callbacks: list[Any] = []

    def connect(self, callback: Any) -> None:
        """Register one callback."""

        self.callbacks.append(callback)

    def disconnect(self, callback: Any) -> None:
        """Remove one callback or raise like Qt when absent."""

        if callback not in self.callbacks:
            raise RuntimeError("callback is not connected")
        self.callbacks.remove(callback)

    def emit(self, *args: object) -> None:
        """Invoke all registered callbacks."""

        for callback in list(self.callbacks):
            callback(*args)


class _Control:
    """Small generation titlebar control double for registry tests."""

    def __init__(self, target: QWidget) -> None:
        """Create signals and observable state."""

        self.playClicked = _Signal()
        self.skipClicked = _Signal()
        self.queueClicked = _Signal()
        self.queueContextMenuRequested = _Signal()
        self.stopClicked = _Signal()
        self.generateModeSelected = _Signal()
        self.batchCountChanged = _Signal()
        self._target = target
        self.batch_count = 1
        self.batch_calls: list[int] = []
        self.presentations: list[GenerationActionPresentation] = []

    def queue_button_target(self) -> QWidget:
        """Return the queue anchor target for this control."""

        return self._target

    def set_batch_count(self, value: int) -> None:
        """Record and emit batch count changes like the real control."""

        self.batch_count = int(value)
        self.batch_calls.append(self.batch_count)
        self.batchCountChanged.emit(self.batch_count)

    def apply_generation_presentation(
        self,
        presentation: GenerationActionPresentation,
    ) -> None:
        """Record one presentation update."""

        self.presentations.append(presentation)


def test_registry_fans_out_generation_presentation_to_registered_controls() -> None:
    """Presentation snapshots should apply to every registered titlebar control."""

    _app()
    registry = _registry()
    main = _control()
    output = _control()
    presentation = _presentation()

    _register(registry, main)
    _register(registry, output)
    registry.apply_generation_presentation(presentation)

    assert main.presentations == [presentation]
    assert output.presentations == [presentation]


def test_registry_applies_latest_presentation_to_late_control() -> None:
    """Newly registered controls should receive the latest presentation immediately."""

    _app()
    registry = _registry()
    presentation = _presentation(skip_enabled=True)
    output = _control()

    registry.apply_generation_presentation(presentation)
    _register(registry, output)

    assert output.presentations == [presentation]


def test_registry_synchronizes_batch_count_between_controls() -> None:
    """Batch count changes from one control should mirror to other controls."""

    _app()
    registry = _registry()
    main = _control()
    output = _control()
    _register(registry, main)
    _register(registry, output)

    main.batchCountChanged.emit(4)

    assert registry.effective_batch_count() == 4
    assert output.batch_count == 4
    assert main.batch_count == 1


def test_registry_effective_batch_count_returns_one_when_accessory_hidden() -> None:
    """Continuous presentation should keep effective batch count at one."""

    _app()
    registry = _registry()
    registry.set_batch_count(7)
    registry.apply_generation_presentation(_presentation(batch_accessory_visible=False))

    assert registry.effective_batch_count() == 1


def test_registry_routes_queue_actions_to_emitting_control_target() -> None:
    """Queue commands should anchor to the control that emitted the signal."""

    _app()
    queue_targets: list[QWidget] = []
    context_targets: list[QWidget] = []
    registry = _registry(
        show_queue_for=queue_targets.append,
        show_queue_context_menu_for=context_targets.append,
    )
    main_target = QWidget()
    output_target = QWidget()
    main = _control(main_target)
    output = _control(output_target)
    _register(registry, main)
    _register(registry, output)

    output.queueClicked.emit()
    main.queueContextMenuRequested.emit()

    assert queue_targets == [output_target]
    assert context_targets == [main_target]


def test_registry_disconnects_unregistered_control() -> None:
    """Unregistered controls should stop invoking registry callbacks."""

    _app()
    calls: list[str] = []
    registry = _registry(
        on_generate=lambda: calls.append("generate"),
        on_skip=lambda: calls.append("skip"),
    )
    control = _control()
    _register(registry, control)
    registry.unregister(cast(GenerationTitleBarRunControl, control))

    control.playClicked.emit()
    control.skipClicked.emit()
    control.batchCountChanged.emit(9)

    assert calls == []
    assert registry.effective_batch_count() == 1


def test_registry_forwards_generation_mode_selection() -> None:
    """Generation mode menu selections should use the shared registry wiring."""

    _app()
    modes: list[str] = []
    registry = _registry(on_generate_mode_selected=modes.append)
    control = _control()
    _register(registry, control)

    control.generateModeSelected.emit("continuous")

    assert modes == ["continuous"]


def _control(target: QWidget | None = None) -> _Control:
    """Return a fake generation titlebar control."""

    return _Control(target or QWidget())


def _register(
    registry: GenerationTitleBarControlRegistry,
    control: _Control,
) -> None:
    """Register a fake control against the production registry type."""

    registry.register(cast(GenerationTitleBarRunControl, control))


def _app() -> QApplication:
    """Return the shared QApplication used by registry tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _registry(
    *,
    on_generate: Any = None,
    on_skip: Any = None,
    on_stop: Any = None,
    show_queue_for: Any = None,
    show_queue_context_menu_for: Any = None,
    on_generate_mode_selected: Any = None,
) -> GenerationTitleBarControlRegistry:
    """Build a registry with no-op callbacks unless overridden."""

    return GenerationTitleBarControlRegistry(
        on_generate=on_generate or (lambda: None),
        on_skip=on_skip or (lambda: None),
        on_stop=on_stop or (lambda: None),
        show_queue_for=show_queue_for or (lambda _target: None),
        show_queue_context_menu_for=show_queue_context_menu_for
        or (lambda _target: None),
        on_generate_mode_selected=on_generate_mode_selected,
    )


def _presentation(
    *,
    skip_enabled: bool = False,
    batch_accessory_visible: bool = True,
) -> GenerationActionPresentation:
    """Return one complete generation presentation snapshot."""

    return GenerationActionPresentation(
        play_mode="generate",
        play_enabled=True,
        play_tooltip="Generate",
        stop_enabled=False,
        skip_enabled=skip_enabled,
        queue_primary_enabled=True,
        queue_badge_count=0,
        queue_segment_visible=True,
        batch_accessory_visible=batch_accessory_visible,
        batch_accessory_enabled=True,
        mode_menu_enabled=True,
    )
