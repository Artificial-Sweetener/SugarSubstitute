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

"""Build focused Output composition test collaborators."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from types import SimpleNamespace
from uuid import UUID, uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_compare_state import (
    OutputCompareSelection,
    OutputCompareState,
)
from substitute.presentation.canvas.output.output_compare_presenter import (
    OutputComparePresentation,
)
from substitute.presentation.canvas.output.output_compare_controller import (
    OutputCompareController,
)
from substitute.presentation.canvas.output.output_canvas_context_menu_controller import (
    OutputToggleAction,
    OutputToggleSignal,
)
from substitute.presentation.canvas.shared.canvas_nav_picker import CanvasNavPickerItem
from substitute.presentation.widgets.menu_model import (
    MenuItem,
    MenuModel,
    MenuSeparator,
)
from substitute.domain.workflow import ImageMeta


class _Catalog:
    """Provide the route presenter catalog protocol for composition tests."""

    def contains(self, image_id: object) -> bool:
        """Return no cached images."""

        _ = image_id
        return False


class _Registrar:
    """Provide the route presenter registrar protocol for composition tests."""

    def register_image(
        self,
        image_id: object,
        image: object,
        path: object,
    ) -> None:
        """Ignore registered images."""

        _ = image_id, image, path


@dataclass(slots=True)
class _PreviewPresenter:
    """Record preview images registered by composed preview controllers."""

    registered_image_ids: tuple[object, ...] = ()

    def register_image(
        self,
        image_id: object,
        image: object,
        path: object,
    ) -> None:
        """Record one preview image registration."""

        _ = image, path
        self.registered_image_ids = (*self.registered_image_ids, image_id)

    def remove_image(self, image_id: object) -> None:
        """Ignore preview image removals for composition tests."""

        _ = image_id


@dataclass(slots=True)
class _OverlayPane:
    """Record overlay registration from the composed material-gap overlay."""

    registered_names: tuple[str, ...] = ()

    def registerOverlay(self, name: str, callback: object) -> None:  # noqa: N802
        """Record the overlay registration name."""

        _ = callback
        self.registered_names = (*self.registered_names, name)


@dataclass(slots=True)
class _SetPicker:
    """Record set picker calls from a composed picker controller."""

    calls: list[tuple[object, int, int, bool, Callable[[int], None]]] = field(
        default_factory=list
    )

    def show_for(
        self,
        anchor: object,
        *,
        set_count: int,
        active_set_index: int,
        include_grid: bool,
        selected_callback: Callable[[int], None],
    ) -> None:
        """Record set picker arguments."""

        self.calls.append(
            (anchor, set_count, active_set_index, include_grid, selected_callback)
        )


@dataclass(slots=True)
class _NavPicker:
    """Record navigation picker calls from a composed picker controller."""

    calls: list[
        tuple[
            object,
            tuple[CanvasNavPickerItem, ...],
            str,
            int | None,
            Callable[[str], None],
        ]
    ] = field(default_factory=list)

    def show_for(
        self,
        anchor: object,
        *,
        items: tuple[CanvasNavPickerItem, ...],
        active_key: str,
        row_width: int | None,
        selected_callback: Callable[[str], None],
    ) -> None:
        """Record navigation picker arguments."""

        self.calls.append((anchor, items, active_key, row_width, selected_callback))


@dataclass(slots=True)
class _Signal:
    """Record emitted signal arguments."""

    calls: list[tuple[object, ...]] = field(default_factory=list)

    def emit(self, *args: object) -> None:
        """Record one signal emission."""

        self.calls.append(args)


@dataclass(slots=True)
class _ContextMenu:
    """Record context-menu entries and execution calls."""

    entries: list[object] = field(default_factory=list)
    exec_calls: list[tuple[object, dict[str, object]]] = field(default_factory=list)

    def addAction(self, action: object) -> None:  # noqa: N802
        """Record one action."""

        self.entries.append(action)

    def addSeparator(self) -> None:  # noqa: N802
        """Record one separator."""

        self.entries.append("separator")

    def exec(self, pos: object, **kwargs: object) -> None:
        """Record menu execution."""

        self.exec_calls.append((pos, kwargs))


def _render_context_menu(menus: list[_ContextMenu], model: MenuModel) -> _ContextMenu:
    """Create and record a context menu from shared menu entries."""

    menu = _ContextMenu()
    for entry in model.entries:
        if isinstance(entry, MenuItem):
            if entry.checkable:
                action = _ContextToggleAction(entry.icon, entry.label, "parent")
                action.setCheckable(entry.checkable)
                action.setChecked(entry.checked)
                action.setEnabled(entry.enabled)
                if entry.checked_callback is not None:
                    action.toggled.connect(entry.checked_callback)
                menu.entries.append(action)
            else:
                callback = entry.callback
                if callback is not None:
                    menu.entries.append(
                        _ContextAction(entry.icon, entry.label, callback)
                    )
        elif isinstance(entry, MenuSeparator):
            menu.entries.append("separator")
    menus.append(menu)
    return menu


@dataclass(slots=True)
class _ContextToggleSignal(OutputToggleSignal):
    """Record toggle callbacks."""

    callbacks: list[Callable[[bool], None]] = field(default_factory=list)

    def connect(self, callback: Callable[[bool], None]) -> None:
        """Record one toggle callback."""

        self.callbacks.append(callback)

    def emit(self, checked: bool) -> None:
        """Emit one checked state."""

        for callback in self.callbacks:
            callback(checked)


@dataclass(slots=True)
class _ContextToggleAction(OutputToggleAction):
    """Record compare-toggle action state."""

    icon: object
    text: str
    parent: object
    toggled: _ContextToggleSignal = field(default_factory=_ContextToggleSignal)
    checkable: bool = False
    checked: bool = False
    enabled: bool = True

    def setCheckable(self, checkable: bool) -> None:  # noqa: N802
        """Record checkable state."""

        self.checkable = checkable

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        """Record checked state."""

        self.checked = checked

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        """Record enabled state."""

        self.enabled = enabled

    def trigger(self) -> None:
        """Toggle the action and emit the checked state."""

        self.checked = not self.checked
        self.toggled.emit(self.checked)


@dataclass(frozen=True, slots=True)
class _ContextAction:
    """Record a regular context-menu action."""

    icon: object | None
    text: str
    triggered: Callable[[], None]


class _SourceTabSignal:
    """Record source-tab signal connections."""

    def __init__(self) -> None:
        """Initialize an empty slot list."""

        self.slots: list[object] = []

    def connect(self, slot: object) -> None:
        """Record one connected slot."""

        self.slots.append(slot)

    def disconnect(self, slot: object) -> None:
        """Disconnect one slot or mimic Qt's missing-slot RuntimeError."""

        if slot not in self.slots:
            raise RuntimeError("slot not connected")
        self.slots.remove(slot)


class _SourceTabItem:
    """Record source-tab tooltip state."""

    def __init__(self, label: str) -> None:
        """Store display label and tooltip text."""

        self.label = label
        self.tooltip = ""

    def setToolTip(self, text: str) -> None:  # noqa: N802
        """Record the assigned tooltip text."""

        self.tooltip = text


class _SourceTabbar:
    """Record source-tab mutations requested through composition."""

    def __init__(self, *, width: int) -> None:
        """Initialize tabbar state with deterministic preferred width."""

        self.items: dict[str, _SourceTabItem] = {}
        self.currentItemChanged = _SourceTabSignal()
        self.added: list[tuple[str, str]] = []
        self.current: str | None = None
        self._width = width

    def addItem(self, key: str, label: str) -> None:  # noqa: N802
        """Record and create one source-tab item."""

        self.added.append((key, label))
        self.items[key] = _SourceTabItem(label)

    def removeWidget(self, key: str) -> None:  # noqa: N802
        """Remove one source-tab item."""

        self.items.pop(key, None)

    def adjustSize(self) -> None:  # noqa: N802
        """No-op size settle hook."""

    def setCurrentItem(self, key: str) -> None:  # noqa: N802
        """Record selected source-tab key."""

        self.current = key

    def sizeHint(self) -> _SizeHint:  # noqa: N802
        """Return deterministic size hint."""

        return _SizeHint(self._width)


@dataclass(frozen=True, slots=True)
class _SizeHint:
    """Expose deterministic size-hint width."""

    value: int

    def width(self) -> int:
        """Return configured width."""

        return self.value


@dataclass(slots=True)
class _Projector:
    """Return a configured current image id."""

    current_image_id: UUID | None

    def current_image_id_for_event(self) -> UUID | None:
        """Return the configured current image id."""

        return self.current_image_id


def _record_context_menu(menus: list[_ContextMenu]) -> _ContextMenu:
    """Create and record one context menu."""

    menu = _ContextMenu()
    menus.append(menu)
    return menu


def _install_source_filter(
    installed: list[tuple[object, int]],
    tab_item: object,
    delay: int,
) -> object:
    """Record source-tab tooltip filter installation."""

    installed.append((tab_item, delay))
    return f"filter:{id(tab_item)}"


@dataclass(slots=True)
class _MeasuredSelector:
    """Expose a deterministic width surface for selector metric tests."""

    width_value: int = 0

    def width(self) -> int:
        """Return the configured selector width."""

        return self.width_value


@dataclass(slots=True)
class _Host:
    """Provide the picker host surface needed by the composition factory."""

    _set_picker: _SetPicker = field(default_factory=_SetPicker)
    _scene_picker: _NavPicker = field(default_factory=_NavPicker)
    _source_picker: _NavPicker = field(default_factory=_NavPicker)
    _output_projection: object = None
    active_source_key: str | None = "txt"
    active_scene_key: str | None = None
    active_scene_overview: bool = False
    active_set_index: int = 1
    last_real_set_index: int = 1
    scene_count: int = 1
    set_count: int = 2
    _suppress_tab_change: bool = False
    _preview_registry: object | None = None
    _revision_cache: object | None = None
    _source_tab_cache_signature: tuple[tuple[str, str], ...] | None = None
    _source_tabbar_preferred_width: int = 0
    _source_tab_tooltip_filters: dict[str, object] = field(default_factory=dict)
    width_value: int | None = None
    tabbar: object = field(
        default_factory=lambda: SimpleNamespace(
            items={},
            setCurrentItem=lambda _key: None,
        )
    )
    _source_tabs_controller: object = field(
        default_factory=lambda: SimpleNamespace(
            rebuild_source_tabs=lambda *, active_source_key: None,
            refresh_source_tab_tooltips=lambda: None,
        )
    )
    _interaction_controller: object = field(
        default_factory=lambda: SimpleNamespace(
            set_grid_interaction_locked=lambda _locked: None,
        )
    )
    set_selector_button: object = "set-button"
    scene_selector_button: object = "scene-button"
    source_selector_button: object = "source-button"
    comparison_set_selector_button: object = "comparison-set-button"
    comparison_scene_selector_button: object = "comparison-scene-button"
    comparison_source_selector_button: object = "comparison-source-button"
    _visible_compare_state: OutputCompareState = field(
        default_factory=OutputCompareState
    )
    activeOutputSceneChanged: _Signal = field(default_factory=lambda: _Signal())
    activeOutputGridChanged: _Signal = field(default_factory=lambda: _Signal())
    activeOutputChanged: _Signal = field(default_factory=lambda: _Signal())
    activeOutputCompareChanged: _Signal = field(default_factory=lambda: _Signal())

    def _sync_scene_selector_button(self) -> None:
        """No-op selector sync hook for navigation adapter tests."""

    def _sync_source_selector_button(self) -> None:
        """No-op selector sync hook for navigation adapter tests."""

    def width(self) -> int:
        """Return configured host width for navigation composition tests."""

        return self.width_value if self.width_value is not None else 0


def _compare_controller(
    *,
    compare_source_sets: list[tuple[str, str]] | None = None,
) -> OutputCompareController:
    """Return a compare controller sufficient for picker composition tests."""

    source_sets = compare_source_sets if compare_source_sets is not None else []
    source_groups = (
        OutputCanvasSourceGroup("txt", "Text", {1: _image_item()}),
        OutputCanvasSourceGroup("up", "Upscale", {1: _image_item()}),
    )
    state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection(None, 1, "txt"),
    )
    return OutputCompareController(
        output_projection=lambda: OutputCanvasProjection(
            sources=source_groups,
            active_source_key="txt",
            active_set_index=1,
            active_uuid=None,
            set_count=1,
        ),
        visible_compare_state=lambda: state,
        output_compare_presenter=lambda: _Presenter(),
        set_visible_compare_state=lambda _state: None,
        emit_compare_changed=lambda _state: None,
        sync_compare_projection=lambda _projection, _state: None,
        sync_compare_rendering=lambda: None,
        update_tabbar_container=lambda: None,
        active_source_key=lambda: "txt",
        active_set_index=lambda: 1,
        scene_count=lambda: 1,
        active_scene_key=lambda: None,
        set_active_source_key=lambda source_key: source_sets.append(
            ("base", source_key)
        ),
        set_active_set_index=lambda _set_index: None,
        set_active_scene_key=lambda _scene_key: None,
        sync_scene_selector_button=lambda: None,
        sync_set_selector_button=lambda: None,
        sync_source_selector_button=lambda: None,
        sync_comparison_nav_buttons=lambda: None,
        set_count_for_sources=lambda _sources: 2,
        base_scene_button=lambda: "base-scene",
        comparison_scene_button=lambda: "comparison-scene",
        base_set_button=lambda: "base-set",
        comparison_set_button=lambda: "comparison-set",
        base_source_button=lambda: "base-source",
        comparison_source_button=lambda: "comparison-source",
        source_selector_width_for_text=lambda _text: 88,
        source_selector_min_width=44,
    )


class _Presenter:
    """Placeholder compare presenter for unused controller methods."""

    def state_for_enabled(
        self,
        projection: OutputCanvasProjection,
        *,
        current_selection: OutputCompareSelection | None,
    ) -> OutputCompareState:
        """Return a stable enabled state."""

        _ = projection, current_selection
        return OutputCompareState(enabled=True)

    def state_for_disabled(self, state: OutputCompareState) -> OutputCompareState:
        """Return a stable disabled state."""

        _ = state
        return OutputCompareState(enabled=False)

    def state_from_qpane_change(
        self,
        state: OutputCompareState,
        qpane_state: object,
    ) -> OutputCompareState:
        """Return unchanged state for unused QPane changes."""

        _ = qpane_state
        return state


class _CompareRenderer:
    """Placeholder compare renderer for composition wiring tests."""

    def present(
        self,
        *,
        projection: OutputCanvasProjection,
        state: OutputCompareState,
        route_blocked: bool = False,
    ) -> OutputComparePresentation:
        """Return unchanged state for unused render calls."""

        _ = projection, route_blocked
        return OutputComparePresentation(state=state, applied=True)


def _image_item(*, set_index: int = 1) -> OutputCanvasImageItem:
    """Return a concrete output item for compare selection reconciliation."""

    return OutputCanvasImageItem(
        uuid4(),
        ImageMeta(
            workflow_name="Workflow",
            cube_name="Cube",
            image_number=1,
            suffix="",
            path="C:\\outputs\\image.png",
            width=512,
            height=512,
            list_index=0,
            cube_execution_duration_ms=1.0,
        ),
        set_index,
    )
