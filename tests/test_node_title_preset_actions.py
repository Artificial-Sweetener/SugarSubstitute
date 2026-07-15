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

"""Qt contract tests for node-card title preset actions."""

from __future__ import annotations

import os
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.node_behavior import ResolvedFieldSpec
from substitute.domain.node_behavior import FieldBehavior
from substitute.domain.user_presets import GLOBAL_PRESET_ASSOCIATION
from substitute.domain.workflow import CubeState
import substitute.presentation.editor.panel.menus.node_title_preset_actions as node_title_preset_actions
from substitute.presentation.editor.panel.menus.node_input_preset_menu_source import (
    NodeInputPresetMenuItem,
    NodeInputPresetMenuModel,
    NodeInputPresetMenuSection,
)
from substitute.presentation.editor.panel.menus.node_title_preset_actions import (
    NodeInputPresetContext,
    bind_node_title_preset_actions,
)
from substitute.presentation.widgets.save_preset_dialog import PresetSaveScope

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "node title context-menu tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


class _FakeRoundMenu:
    """Record menu actions, submenus, and execution positions without a popup."""

    instances: list["_FakeRoundMenu"] = []

    def __init__(self, *args: Any, parent: QWidget | None = None) -> None:
        """Record the created menu, title, and parent widget."""

        self.title = args[0] if args and isinstance(args[0], str) else ""
        if parent is None and args and isinstance(args[-1], QWidget):
            parent = args[-1]
        self.parent = parent
        self.actions: list[Any] = []
        self.submenus: list["_FakeRoundMenu"] = []
        self.entries: list[tuple[str, str]] = []
        self.exec_position: QPoint | None = None
        self.instances.append(self)

    def addAction(self, action: Any) -> None:
        """Record one menu action."""

        self.actions.append(action)
        self.entries.append(("action", action.text()))

    def addMenu(self, menu: "_FakeRoundMenu") -> None:
        """Record one nested menu."""

        self.submenus.append(menu)
        self.entries.append(("menu", menu.title))

    def addSeparator(self) -> None:
        """Record one menu separator."""

        self.entries.append(("separator", ""))

    def menuActions(self) -> list[Any]:
        """Return recorded actions and submenu sentinels."""

        return [*self.actions, *self.submenus]

    def exec(self, position: QPoint) -> None:
        """Record the requested global popup position."""

        self.exec_position = position


def _capture_rendered_menus(
    monkeypatch: pytest.MonkeyPatch,
) -> list[Any]:
    """Capture real menus produced by the shared renderer without popups."""

    rendered: list[Any] = []
    renderer_type = cast(Any, node_title_preset_actions).QFluentMenuRenderer
    original_render = renderer_type.render

    def capture_render(self: Any, model: Any) -> Any:
        """Record each rendered menu and return the real renderer result."""

        menu = original_render(self, model)
        rendered.append(menu)
        return menu

    monkeypatch.setattr(
        renderer_type,
        "render",
        capture_render,
    )
    monkeypatch.setattr(
        "qfluentwidgets.components.widgets.menu.RoundMenu.exec",
        lambda *_args, **_kwargs: None,
    )
    return rendered


def _round_menu_entries(menu: Any) -> list[tuple[str, str]]:
    """Return visual rows from a QFluent menu in displayed order."""

    entries: list[tuple[str, str]] = []
    view = menu.view
    for row in range(view.count()):
        item = view.item(row)
        value = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(value, QAction):
            entries.append(("action", value.text()))
            continue
        title = getattr(value, "title", None)
        if callable(title):
            entries.append(("menu", str(title())))
            continue
        if item.data(Qt.ItemDataRole.DecorationRole) == "seperator":
            entries.append(("separator", ""))
    return entries


class _FakeNodePresetSource:
    """Return deterministic saved node preset data and record saves."""

    def __init__(self, model: NodeInputPresetMenuModel) -> None:
        """Store the menu model returned by this source."""

        self.model = model
        self.prepare_calls: list[tuple[str, str]] = []
        self.scope = PresetSaveScope(
            title="Global",
            full_label="Global",
            association=GLOBAL_PRESET_ASSOCIATION,
        )
        self.saved: list[tuple[str, str, dict[str, object], PresetSaveScope]] = []

    def prepare_node_input_preset_menu_model(
        self,
        *,
        node_type: str,
        reason: str,
    ) -> None:
        """Record explicit preparation calls."""

        self.prepare_calls.append((node_type, reason))

    def prepare_known_node_input_preset_menu_models(self, *, reason: str) -> None:
        """Record known-node refresh requests."""

        self.prepare_calls.append(("*", reason))

    def current_node_input_preset_menu_model(
        self,
        *,
        node_type: str,
    ) -> NodeInputPresetMenuModel | None:
        """Return saved node input preset menu sections."""

        assert node_type == "KSampler"
        return self.model

    def list_node_input_presets(self, *, node_type: str) -> NodeInputPresetMenuModel:
        """Fail if menu opening tries to load preset sections."""

        raise AssertionError(f"unexpected menu-open preset listing for {node_type}")

    def node_input_save_scopes(self) -> tuple[PresetSaveScope, ...]:
        """Fail if menu opening tries to load save scopes."""

        raise AssertionError("unexpected menu-open save-scope lookup")

    def save_node_input_preset(
        self,
        *,
        label: str,
        node_type: str,
        inputs: dict[str, object],
        scope: PresetSaveScope,
    ) -> None:
        """Record one save request."""

        self.saved.append((label, node_type, inputs, scope))


def test_node_title_menu_shows_apply_before_save_and_applies_preset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Right-clicking a title row should expose and apply matching node presets."""

    app = _ensure_app()
    rendered_menus = _capture_rendered_menus(monkeypatch)
    title = QWidget()
    cube_state = _cube_state({"steps": 20})
    source = _FakeNodePresetSource(
        NodeInputPresetMenuModel(
            sections=(
                NodeInputPresetMenuSection(
                    title="Global",
                    presets=(
                        NodeInputPresetMenuItem(
                            id="node_inputs:test",
                            label="Fast Draft",
                            inputs={"steps": 12},
                            tooltip="KSampler - 1 input",
                        ),
                    ),
                ),
            ),
            save_scopes=(
                PresetSaveScope(
                    title="Global",
                    full_label="Global",
                    association=GLOBAL_PRESET_ASSOCIATION,
                ),
            ),
        )
    )
    try:
        bind_node_title_preset_actions(
            title_row=title,
            context=_context(cube_state),
            preset_source=source,
            dialog_parent=lambda: title,
            is_connection=_is_connection,
            position_mapper=lambda point: point,
        )

        title.customContextMenuRequested.emit(QPoint(4, 4))

        root_menu = rendered_menus[0]
        assert _round_menu_entries(root_menu) == [
            ("menu", "Apply preset"),
            ("separator", ""),
            ("action", "Save current Sampler as preset..."),
        ]
        apply_menu = cast(Any, root_menu)._subMenus[0]
        apply_menu.populate_if_needed()
        assert _round_menu_entries(apply_menu) == [("action", "Fast Draft")]
        apply_menu.menuActions()[0].trigger()
        assert _sampler_inputs(cube_state)["steps"] == 12
    finally:
        title.close()
        app.processEvents()


def test_node_title_menu_omits_apply_when_no_presets_and_saves_named_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Save action should open the preset dialog and pass captured current inputs."""

    app = _ensure_app()
    rendered_menus = _capture_rendered_menus(monkeypatch)
    title = QWidget()
    cube_state = _cube_state({"steps": 20})
    source = _FakeNodePresetSource(
        NodeInputPresetMenuModel(
            save_scopes=(
                PresetSaveScope(
                    title="Global",
                    full_label="Global",
                    association=GLOBAL_PRESET_ASSOCIATION,
                ),
            ),
        )
    )

    class _FakeSavePresetDialog:
        """Record construction for the save-node-preset dialog."""

        instances: list["_FakeSavePresetDialog"] = []

        def __init__(
            self,
            *,
            parent: QWidget,
            title: str,
            scopes: tuple[PresetSaveScope, ...],
        ) -> None:
            """Accept the same construction contract as the real dialog."""

            self.parent = parent
            self.title = title
            self.scopes = scopes
            self.instances.append(self)

    monkeypatch.setattr(
        node_title_preset_actions,
        "SavePresetDialog",
        _FakeSavePresetDialog,
    )
    monkeypatch.setattr(
        node_title_preset_actions,
        "preset_dialog_result",
        lambda _dialog: ("Fast Draft", source.scope),
    )
    try:
        bind_node_title_preset_actions(
            title_row=title,
            context=_context(cube_state),
            preset_source=source,
            dialog_parent=lambda: title,
            is_connection=_is_connection,
            position_mapper=lambda point: point,
        )

        title.customContextMenuRequested.emit(QPoint(4, 4))

        root_menu = rendered_menus[0]
        assert _round_menu_entries(root_menu) == [
            ("action", "Save current Sampler as preset...")
        ]
        root_menu.menuActions()[0].trigger()
        assert _FakeSavePresetDialog.instances[0].title == "Save Sampler preset"
        assert source.saved == [("Fast Draft", "KSampler", {"steps": 20}, source.scope)]
    finally:
        title.close()
        app.processEvents()


def test_node_title_menu_omits_save_when_no_savable_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Save action should be absent when capture finds no preset-safe values."""

    app = _ensure_app()
    rendered_menus = _capture_rendered_menus(monkeypatch)
    title = QWidget()
    cube_state = _cube_state({"steps": ["other", 0]})
    source = _FakeNodePresetSource(NodeInputPresetMenuModel())
    try:
        bind_node_title_preset_actions(
            title_row=title,
            context=_context(cube_state),
            preset_source=source,
            dialog_parent=lambda: title,
            is_connection=_is_connection,
            position_mapper=lambda point: point,
        )

        title.customContextMenuRequested.emit(QPoint(4, 4))

        assert rendered_menus == []
    finally:
        title.close()
        app.processEvents()


def _ensure_app() -> QApplication:
    """Return an existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def _context(cube_state: CubeState) -> NodeInputPresetContext:
    """Return a standard KSampler preset context."""

    return NodeInputPresetContext(
        cube_alias="A",
        node_name="sampler",
        node_type="KSampler",
        inputs=_sampler_inputs(cube_state),
        field_specs={"steps": _field("steps", "INT")},
        cube_state=cube_state,
        input_widgets_by_field_key={},
    )


def _cube_state(inputs: dict[str, object]) -> CubeState:
    """Return a cube state containing one sampler node."""

    return CubeState(
        cube_id="cube",
        version="1",
        alias="A",
        original_cube={},
        buffer={
            "nodes": {
                "sampler": {
                    "class_type": "KSampler",
                    "inputs": inputs,
                }
            }
        },
    )


def _sampler_inputs(cube_state: CubeState) -> dict[str, object]:
    """Return typed sampler inputs from a test cube state."""

    nodes = cast(dict[str, object], cube_state.buffer["nodes"])
    sampler = cast(dict[str, object], nodes["sampler"])
    return cast(dict[str, object], sampler["inputs"])


def _field(field_key: str, field_type: str | None) -> ResolvedFieldSpec:
    """Return a minimal resolved field spec for node title tests."""

    return ResolvedFieldSpec(
        cube_alias="A",
        node_name="sampler",
        class_type="KSampler",
        field_key=field_key,
        field_type=field_type,
        constraints={},
        meta_info={},
        field_info=None,
        value=None,
        field_behavior=FieldBehavior(field_key=field_key),
    )


def _is_connection(value: object) -> bool:
    """Return whether a value has the common Comfy connection shape."""

    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    )
