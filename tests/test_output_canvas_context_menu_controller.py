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

"""Verify Output canvas context-menu behavior outside the widget host."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_compare_state import OutputCompareState
from substitute.domain.workflow import ImageMeta
from substitute.presentation.canvas.output.output_canvas_context_menu_controller import (
    OutputCanvasContextMenuController,
    OutputToggleAction,
    OutputToggleSignal,
)
from substitute.presentation.canvas.shared.types import OutputImageMeta
from substitute.presentation.widgets.menu_model import (
    MenuItem,
    MenuModel,
    MenuSeparator,
)


def test_context_menu_suppresses_grid_mode_without_compare() -> None:
    """Grid mode should not show single-image actions unless compare is active."""

    menus: list[_Menu] = []
    controller = _controller(active_set_index=0, menus=menus)

    controller.show_context_menu("local")

    assert menus == []


def test_context_menu_adds_compare_toggle_when_projection_is_active() -> None:
    """Menus with multiple projected outputs should expose a compare toggle."""

    menus: list[_Menu] = []
    compare_calls: list[bool] = []
    controller = _controller(
        projection=_projection(uuid4(), uuid4()),
        menus=menus,
        compare_calls=compare_calls,
    )

    controller.show_context_menu("local")

    compare_action = menus[0].entries[0]
    assert isinstance(compare_action, _ToggleAction)
    assert compare_action.text == "Compare outputs"
    assert compare_action.checkable is True
    assert compare_action.checked is False
    assert compare_action.enabled is True

    compare_action.trigger()

    assert compare_calls == [True]


def test_context_menu_omits_compare_toggle_for_one_projected_image() -> None:
    """A single projected image should not offer an unusable compare action."""

    menus: list[_Menu] = []
    controller = _controller(
        projection=_projection(uuid4()),
        menus=menus,
    )

    controller.show_context_menu("local")

    assert [
        entry.text if isinstance(entry, (_Action, _ToggleAction)) else entry
        for entry in menus[0].entries
    ] == [
        "Copy",
        "Open in Photoshop",
        "Open All in Photoshop",
        "Reveal in File Manager",
        "separator",
        "Undock canvas",
    ]


def test_context_menu_omits_compare_toggle_for_duplicate_image_routes() -> None:
    """Multiple routes to one image should not create a false compare capability."""

    image_id = uuid4()
    menus: list[_Menu] = []
    controller = _controller(
        projection=_projection(image_id, image_id),
        menus=menus,
    )

    controller.show_context_menu("local")

    assert all(not isinstance(entry, _ToggleAction) for entry in menus[0].entries)


def test_context_menu_adds_dock_action_after_image_actions() -> None:
    """Dock management should stay separated from image actions."""

    menus: list[_Menu] = []
    dock_calls: list[None] = []
    controller = _controller(
        menus=menus,
        dock_action_text="Redock canvas",
        dock_calls=dock_calls,
    )

    controller.show_context_menu("local")

    menu = menus[0]
    assert [
        entry.text if isinstance(entry, (_Action, _ToggleAction)) else entry
        for entry in menu.entries
    ] == [
        "Copy",
        "Open in Photoshop",
        "Open All in Photoshop",
        "Reveal in File Manager",
        "separator",
        "Redock canvas",
    ]
    assert menu.exec_calls == [(("global", "local"), {"aniType": "drop-down"})]
    action_icons = [entry.icon for entry in menu.entries if isinstance(entry, _Action)]
    assert action_icons == ["copy", "photo", "image-multiple", "folder-open", "dock"]

    dock_action = menu.entries[-1]
    assert isinstance(dock_action, _Action)
    dock_action.triggered()

    assert dock_calls == [None]


def test_context_menu_copy_action_uses_authorized_current_image() -> None:
    """Copy should use the route projector before touching the clipboard."""

    image_id = uuid4()
    copied: list[object] = []
    image = object()
    controller = _controller(
        current_image_id=image_id,
        current_image=image,
        copied=copied,
    )

    controller.copy_current_image()

    assert copied == [image]


def test_context_menu_open_current_requires_payload_and_metadata() -> None:
    """Open-current should pass only resolved final output data to the editor."""

    image_id = uuid4()
    image = object()
    meta = _meta(image_id)
    opened: list[tuple[object, OutputImageMeta]] = []
    controller = _controller(
        current_image_id=image_id,
        payloads={image_id: image},
        metas={image_id: meta},
        open_single=lambda payload, image_meta: _record_single_open(
            opened,
            payload,
            image_meta,
        ),
    )

    controller.open_current_external()

    assert opened == [(image, meta)]


def test_context_menu_open_all_uses_authorized_projection_outputs() -> None:
    """Open-all should prepare only allowed projection images with full data."""

    allowed_id = uuid4()
    blocked_id = uuid4()
    missing_meta_id = uuid4()
    allowed_image = object()
    blocked_image = object()
    missing_meta_image = object()
    allowed_meta = _meta(allowed_id)
    opened: list[list[tuple[object, OutputImageMeta]]] = []
    controller = _controller(
        projection=_projection(allowed_id, blocked_id, missing_meta_id),
        allowed_image_ids=frozenset({allowed_id, missing_meta_id}),
        payloads={
            allowed_id: allowed_image,
            blocked_id: blocked_image,
            missing_meta_id: missing_meta_image,
        },
        metas={allowed_id: allowed_meta},
        open_all=lambda prepared: _record_open_all(opened, prepared),
    )

    controller.open_all_external()

    assert opened == [[(allowed_image, allowed_meta)]]


def test_context_menu_reveal_current_forwards_authorized_metadata() -> None:
    """Reveal should forward only the route-authorized output metadata."""

    image_id = uuid4()
    meta = _meta(image_id)
    revealed: list[OutputImageMeta] = []
    controller = _controller(
        current_image_id=image_id,
        metas={image_id: meta},
        reveal_asset=lambda image_meta: _record_reveal(revealed, image_meta),
    )

    controller.reveal_current_asset()

    assert revealed == [meta]


def test_context_menu_reveal_current_ignores_missing_asset_path() -> None:
    """Reveal should reject output metadata without a local asset path."""

    image_id = uuid4()
    revealed: list[OutputImageMeta] = []
    controller = _controller(
        current_image_id=image_id,
        metas={
            image_id: ImageMeta(
                workflow_name="workflow",
                cube_name="cube",
                image_number=1,
                suffix="",
                path="",
            )
        },
        reveal_asset=lambda image_meta: _record_reveal(revealed, image_meta),
    )

    controller.reveal_current_asset()

    assert revealed == []


@dataclass(slots=True)
class _Menu:
    """Record menu entries and execution calls."""

    entries: list[object] = field(default_factory=list)
    exec_calls: list[tuple[object, dict[str, object]]] = field(default_factory=list)

    def addAction(self, action: object) -> None:  # noqa: N802
        """Record one menu action."""

        self.entries.append(action)

    def addSeparator(self) -> None:  # noqa: N802
        """Record one menu separator."""

        self.entries.append("separator")

    def exec(self, pos: object, **kwargs: object) -> None:
        """Record menu execution."""

        self.exec_calls.append((pos, kwargs))


@dataclass(slots=True)
class _Signal(OutputToggleSignal):
    """Record connected callbacks and emit checked state."""

    callbacks: list[Callable[[bool], None]] = field(default_factory=list)

    def connect(self, callback: Callable[[bool], None]) -> None:
        """Record one callback."""

        self.callbacks.append(callback)

    def emit(self, checked: bool) -> None:
        """Invoke recorded callbacks with checked state."""

        for callback in self.callbacks:
            callback(checked)


@dataclass(slots=True)
class _ToggleAction(OutputToggleAction):
    """Record compare toggle action state."""

    icon: object
    text: str
    parent: object
    toggled: _Signal = field(default_factory=_Signal)
    checkable: bool = False
    checked: bool = False
    enabled: bool = True

    def setCheckable(self, checkable: bool) -> None:  # noqa: N802
        """Set checkable state."""

        self.checkable = checkable

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        """Set checked state."""

        self.checked = checked

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        """Set enabled state."""

        self.enabled = enabled

    def trigger(self) -> None:
        """Toggle and emit checked state."""

        self.checked = not self.checked
        self.toggled.emit(self.checked)


@dataclass(frozen=True, slots=True)
class _Action:
    """Represent a regular menu action."""

    icon: object | None
    text: str
    triggered: Callable[[], None]


@dataclass(slots=True)
class _Projector:
    """Return a configured current image id."""

    current_image_id: UUID | None

    def current_image_id_for_event(self) -> UUID | None:
        """Return configured current image id."""

        return self.current_image_id


def _controller(
    *,
    menus: list[_Menu] | None = None,
    compare_calls: list[bool] | None = None,
    compare_state: OutputCompareState | None = None,
    active_scene_overview: bool = False,
    active_set_index: int = 1,
    projection: OutputCanvasProjection | None = None,
    current_image_id: UUID | None = None,
    current_image: object | None = None,
    copied: list[object] | None = None,
    payloads: dict[UUID, object] | None = None,
    metas: dict[UUID, OutputImageMeta] | None = None,
    open_single: Callable[[object, OutputImageMeta], bool] | None = None,
    open_all: Callable[[list[tuple[object, OutputImageMeta]]], bool] | None = None,
    reveal_asset: Callable[[OutputImageMeta], bool] | None = None,
    allowed_image_ids: frozenset[UUID] = frozenset(),
    dock_action_text: str = "Undock canvas",
    dock_calls: list[None] | None = None,
) -> OutputCanvasContextMenuController:
    """Return a context-menu controller with deterministic collaborators."""

    active_menus = menus if menus is not None else []
    active_compare_calls = compare_calls if compare_calls is not None else []
    active_copied = copied if copied is not None else []
    active_payloads = payloads or {}
    active_metas = metas or {}
    active_dock_calls = dock_calls if dock_calls is not None else []
    return OutputCanvasContextMenuController(
        pane=lambda: "pane",
        action_parent=lambda: "parent",
        visible_compare_state=lambda: compare_state or OutputCompareState(),
        active_scene_overview=lambda: active_scene_overview,
        active_set_index=lambda: active_set_index,
        output_projection=lambda: projection,
        set_compare_mode_enabled=active_compare_calls.append,
        menu_renderer=lambda _parent, model: _render_menu(active_menus, model),
        compare_enabled_icon=lambda: "compare-enabled",
        compare_disabled_icon=lambda: "compare-disabled",
        copy_icon=lambda: "copy",
        open_external_icon=lambda: "photo",
        open_all_external_icon=lambda: "image-multiple",
        reveal_asset_icon=lambda: "folder-open",
        dock_action_icon=lambda: "dock",
        menu_animation_type=lambda: "drop-down",
        map_to_global=lambda pos: ("global", pos),
        current_image=lambda: current_image,
        clipboard_set_image=active_copied.append,
        output_route_projector=lambda: _Projector(current_image_id),
        final_output_payload=lambda image_id: active_payloads.get(image_id),
        final_output_metadata=lambda image_id: active_metas.get(image_id),
        open_single_external_editor=lambda: open_single,
        open_all_external_editor=lambda: open_all,
        reveal_asset=lambda: reveal_asset,
        allowed_image_ids=lambda: allowed_image_ids,
        dock_action_text=lambda: dock_action_text,
        request_dock_action=lambda: active_dock_calls.append(None),
    )


def _render_menu(menus: list[_Menu], model: MenuModel) -> _Menu:
    """Create and record a menu instance from shared menu entries."""

    menu = _Menu()
    for entry in model.entries:
        if isinstance(entry, MenuItem):
            if entry.checkable:
                action = _ToggleAction(
                    entry.icon,
                    entry.label,
                    "parent",
                )
                action.setCheckable(entry.checkable)
                action.setChecked(entry.checked)
                action.setEnabled(entry.enabled)
                if entry.checked_callback is not None:
                    action.toggled.connect(entry.checked_callback)
                menu.entries.append(action)
            else:
                callback = entry.callback
                if callback is not None:
                    menu.entries.append(_Action(entry.icon, entry.label, callback))
        elif isinstance(entry, MenuSeparator):
            menu.entries.append("separator")
    menus.append(menu)
    return menu


def _record_single_open(
    opened: list[tuple[object, OutputImageMeta]],
    payload: object,
    image_meta: OutputImageMeta,
) -> bool:
    """Record one single-image external editor call."""

    opened.append((payload, image_meta))
    return True


def _record_open_all(
    opened: list[list[tuple[object, OutputImageMeta]]],
    prepared: list[tuple[object, OutputImageMeta]],
) -> bool:
    """Record one multi-image external editor call."""

    opened.append(prepared)
    return True


def _record_reveal(
    revealed: list[OutputImageMeta],
    image_meta: OutputImageMeta,
) -> bool:
    """Record one output metadata reveal request."""

    revealed.append(image_meta)
    return True


def _projection(*image_ids: UUID) -> OutputCanvasProjection:
    """Return a projection containing one source with image ids by set index."""

    return OutputCanvasProjection(
        sources=(
            OutputCanvasSourceGroup(
                source_key="source-a",
                label="Source A",
                images_by_set={
                    index: OutputCanvasImageItem(image_id, _meta(image_id), index)
                    for index, image_id in enumerate(image_ids, start=1)
                },
            ),
        ),
        active_source_key="source-a",
        active_set_index=1,
        active_uuid=image_ids[0] if image_ids else None,
        set_count=len(image_ids),
    )


def _meta(image_id: UUID) -> ImageMeta:
    """Return output metadata for context-menu tests."""

    return ImageMeta(
        workflow_name="workflow",
        cube_name="cube",
        image_number=1,
        suffix="",
        path=f"E:/{image_id}.png",
        source_key="source-a",
        source_label="Source A",
    )
