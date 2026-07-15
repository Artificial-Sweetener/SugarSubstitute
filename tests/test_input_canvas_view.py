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

"""Verify InputCanvas view adapters and context-menu wiring."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from substitute.presentation.canvas.input.input_mask_tool_controller import (
    InputMaskToolMenuState,
    InputMaskToolMode,
)
import substitute.presentation.canvas.input.input_canvas_view as input_mod
from substitute.presentation.widgets.menu_model import (
    MenuItem,
    MenuModel,
    MenuSeparator,
)

_input_canvas_qpane_features = cast(
    Callable[[], tuple[str, ...]],
    getattr(input_mod, "_input_canvas_qpane_features"),
)


def test_input_canvas_qpane_features_keep_sam_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Input canvas should keep SAM enabled outside diagnostic harness runs."""

    monkeypatch.delenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", raising=False)
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")

    assert _input_canvas_qpane_features() == ("mask", "sam")


def test_input_canvas_qpane_features_can_defer_sam_for_harness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup harness diagnostics may measure Input canvas without eager SAM."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")

    assert _input_canvas_qpane_features() == ("mask",)


def test_set_available_false_disables_pane_and_shows_overlay() -> None:
    """Unavailable input canvas should disable QPane without clearing mask state."""

    enabled_calls: list[bool] = []
    overlay_calls: list[tuple[str, object]] = []
    fake = SimpleNamespace(
        pane=SimpleNamespace(setEnabled=lambda value: enabled_calls.append(value)),
        _availability_overlay=SimpleNamespace(
            setText=lambda text: overlay_calls.append(("text", text)),
            setGeometry=lambda rect: overlay_calls.append(("geometry", rect)),
            raise_=lambda: overlay_calls.append(("raise", None)),
            show=lambda: overlay_calls.append(("show", None)),
            hide=lambda: overlay_calls.append(("hide", None)),
        ),
        rect=lambda: "canvas-rect",
    )

    cast(Any, input_mod.InputCanvas).set_available(fake, False, "No input canvas nodes")

    assert enabled_calls == [False]
    assert overlay_calls == [
        ("text", "No input canvas nodes"),
        ("geometry", "canvas-rect"),
        ("raise", None),
        ("show", None),
    ]


def test_set_available_true_enables_pane_and_hides_overlay() -> None:
    """Available input canvas should re-enable QPane and hide the empty state."""

    enabled_calls: list[bool] = []
    overlay_calls: list[str] = []
    fake = SimpleNamespace(
        pane=SimpleNamespace(setEnabled=lambda value: enabled_calls.append(value)),
        _availability_overlay=SimpleNamespace(
            hide=lambda: overlay_calls.append("hide")
        ),
    )

    cast(Any, input_mod.InputCanvas).set_available(fake, True)

    assert enabled_calls == [True]
    assert overlay_calls == ["hide"]


def test_on_pane_mask_saved_relays_save_completion() -> None:
    """Pane maskSaved should relay as the app-facing save-completed signal."""

    signal = _Signal()
    fake = SimpleNamespace(inputMaskSaved=signal)

    cast(Any, input_mod.InputCanvas)._on_pane_mask_saved(
        fake, "mask-1", "E:/masks/mask.png"
    )

    assert signal.calls == [("mask-1", "E:/masks/mask.png")]


def test_on_pane_image_loaded_relays_active_image_id() -> None:
    """Pane imageLoaded should include the current image UUID for graph lookup."""

    image_id = uuid4()
    signal = _Signal()
    fake = SimpleNamespace(
        pane=SimpleNamespace(currentImageID=lambda: image_id),
        _route_projector=SimpleNamespace(loaded_image_id_for_event=lambda: image_id),
        inputImageLoaded=signal,
    )

    cast(Any, input_mod.InputCanvas)._on_pane_image_loaded(fake, "E:/images/input.png")

    assert signal.calls == [(image_id, "E:/images/input.png")]


def test_context_menu_adds_separator_and_dock_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Input context menu should separate tool actions from dock management."""

    _install_fake_canvas_menu(monkeypatch)

    dock_signal = _Signal()
    pane = SimpleNamespace(
        mapToGlobal=lambda pos: ("global", pos),
    )
    state_requested = _Signal()
    mode_requested = _Signal()
    fake = SimpleNamespace(
        pane=pane,
        maskToolMenuStateRequested=state_requested,
        maskToolModeRequested=mode_requested,
        _mask_tool_menu_state=InputMaskToolMenuState(
            brush_enabled=True,
            smart_select_enabled=False,
        ),
        _dock_action_text="Redock canvas",
        dockActionRequested=dock_signal,
    )

    cast(Any, input_mod.InputCanvas)._show_context_menu(fake, "local-pos")

    menu = _FakeRoundMenu.instances[0]
    assert [
        entry.text if isinstance(entry, _FakeMenuAction) else entry
        for entry in menu.entries
    ] == ["Pan & Zoom", "Brush", "Smart Select", "separator", "Redock canvas"]
    assert isinstance(menu.entries[1], _FakeMenuAction)
    assert menu.entries[1].enabled is True
    assert isinstance(menu.entries[2], _FakeMenuAction)
    assert menu.entries[2].enabled is False
    assert isinstance(menu.entries[0], _FakeMenuAction)
    menu.entries[0].trigger()
    menu.entries[1].trigger()

    dock_action = menu.entries[-1]
    assert isinstance(dock_action, _FakeMenuAction)
    dock_action.trigger()

    assert state_requested.calls == [()]
    assert mode_requested.calls == [
        (InputMaskToolMode.PAN_ZOOM,),
        (InputMaskToolMode.BRUSH,),
    ]
    assert dock_signal.calls == [()]
    assert menu.exec_calls == [
        (
            ("global", "local-pos"),
            {"aniType": cast(Any, input_mod).MenuAnimationType.DROP_DOWN},
        )
    ]


def test_set_mask_tool_menu_state_updates_visual_state() -> None:
    """Input view should store presenter-owned menu state without tool policy."""

    fake = SimpleNamespace(_mask_tool_menu_state=InputMaskToolMenuState())
    state = InputMaskToolMenuState(
        brush_enabled=True,
        smart_select_enabled=True,
    )

    cast(Any, input_mod.InputCanvas).set_mask_tool_menu_state(fake, state)

    assert fake._mask_tool_menu_state == state


def test_set_dock_action_text_updates_menu_label() -> None:
    """Input dock action label should be stored for the next context menu."""

    fake = SimpleNamespace(_dock_action_text="Undock canvas")

    cast(Any, input_mod.InputCanvas).set_dock_action_text(fake, "Redock canvas")

    assert fake._dock_action_text == "Redock canvas"


class _Signal:
    """Small signal double used by InputCanvas view tests."""

    def __init__(self) -> None:
        self._slots: list[Callable[..., None]] = []
        self.calls: list[tuple[object, ...]] = []

    def connect(self, slot: Callable[..., None]) -> None:
        """Connect one callback."""

        self._slots.append(slot)

    def disconnect(self, slot: Callable[..., None]) -> None:
        """Disconnect one callback."""

        if slot not in self._slots:
            raise RuntimeError("slot not connected")
        self._slots.remove(slot)

    def emit(self, *args: object) -> None:
        """Record and dispatch one signal emission."""

        self.calls.append(args)
        for slot in list(self._slots):
            slot(*args)


class _FakeMenuIcon:
    """Small non-null menu icon double for context-menu tests."""

    def __init__(self, name: str) -> None:
        self.name = name

    def isNull(self) -> bool:  # noqa: N802
        """Return that the fake icon is non-null."""

        return False


class _FakeMenuAction:
    """Record qfluentwidgets Action construction for context-menu tests."""

    def __init__(
        self,
        *args: object,
        triggered: Callable[..., object] | None = None,
        **_kwargs: object,
    ) -> None:
        self.icon_value = args[0] if len(args) > 1 else None
        self.text = str(args[1] if len(args) > 1 else args[0])
        self.triggered = triggered
        self.toggled = _Signal()
        self.enabled = True
        self.checkable = False
        self.checked = False

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        """Set whether the action is enabled."""

        self.enabled = enabled

    def setCheckable(self, checkable: bool) -> None:  # noqa: N802
        """Set whether the action can be checked."""

        self.checkable = checkable

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        """Set whether the action is checked."""

        self.checked = checked

    def isCheckable(self) -> bool:  # noqa: N802
        """Return whether the action can be checked."""

        return self.checkable

    def isChecked(self) -> bool:  # noqa: N802
        """Return whether the action is checked."""

        return self.checked

    def isEnabled(self) -> bool:  # noqa: N802
        """Return whether the action is enabled."""

        return self.enabled

    def icon(self) -> object:
        """Return the current icon."""

        return self.icon_value

    def setIcon(self, icon: object) -> None:  # noqa: N802
        """Set the current icon."""

        self.icon_value = icon

    def trigger(self) -> None:
        """Trigger the action callback."""

        if self.checkable:
            self.checked = not self.checked
            self.toggled.emit(self.checked)
        if self.triggered is None:
            return
        try:
            self.triggered(self.checked)
        except TypeError:
            self.triggered()


class _FakeRoundMenu:
    """Record menu entries so tests can assert context-menu layout."""

    instances: list["_FakeRoundMenu"] = []

    def __init__(self, parent: object | None = None) -> None:
        self.parent = parent
        self.entries: list[object] = []
        self.exec_calls: list[tuple[object, dict[str, object]]] = []
        _FakeRoundMenu.instances.append(self)

    def addAction(self, action: _FakeMenuAction) -> None:  # noqa: N802
        """Record one added action."""

        self.entries.append(action)

    def addSeparator(self) -> None:  # noqa: N802
        """Record one added separator."""

        self.entries.append("separator")

    def exec(self, pos: object, **kwargs: object) -> None:
        """Record one menu execution."""

        self.exec_calls.append((pos, kwargs))


class _FakeQFluentMenuRenderer:
    """Render shared menu models into fake menus for Input canvas tests."""

    def __init__(self, *, parent: object) -> None:
        """Store the parent used for fake menu construction."""

        self._parent = parent

    def render(self, model: MenuModel) -> _FakeRoundMenu:
        """Return a fake menu populated from shared menu entries."""

        menu = _FakeRoundMenu(parent=self._parent)
        for entry in model.entries:
            if isinstance(entry, MenuItem):
                action = _FakeMenuAction(
                    entry.label,
                    triggered=lambda _checked=False, callback=entry.callback: (
                        None if callback is None else callback()
                    ),
                )
                action.setEnabled(entry.enabled)
                menu.addAction(action)
            elif isinstance(entry, MenuSeparator):
                menu.addSeparator()
        return menu


def _install_fake_canvas_menu(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch InputCanvas to use recordable context-menu doubles."""

    _FakeRoundMenu.instances.clear()
    monkeypatch.setattr(input_mod, "QFluentMenuRenderer", _FakeQFluentMenuRenderer)
    monkeypatch.setattr(
        input_mod,
        "transparent_menu_icon",
        lambda: _FakeMenuIcon("transparent"),
        raising=False,
    )
