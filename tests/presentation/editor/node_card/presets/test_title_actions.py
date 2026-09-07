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

from typing import Any, cast


import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget

from substitute.application.node_behavior import ResolvedFieldSpec
from substitute.domain.node_behavior import FieldBehavior
from substitute.domain.user_presets import GLOBAL_PRESET_ASSOCIATION
from substitute.domain.workflow import CubeState
from substitute.presentation.editor.field_actions import (
    FieldActionContribution,
    FieldActionContext,
)
import substitute.presentation.editor.panel.menus.node_title_preset_actions as node_title_preset_actions
import substitute.presentation.editor.panel.node_card.action_menu as node_card_action_menu
from substitute.presentation.editor.panel.menus.node_input_preset_menu_source import (
    NodeInputPresetMenuItem,
    NodeInputPresetMenuModel,
    NodeInputPresetMenuSection,
)
from substitute.presentation.editor.panel.menus.node_title_preset_actions import (
    NodeInputPresetContext,
)
from substitute.presentation.editor.panel.node_card.action_menu import (
    NodeCardActionMenuBinding,
    NodeCardActionMenuButton,
)
from substitute.presentation.editor.panel.node_card.advanced_input_binding import (
    AdvancedInputCardBinding,
)
from substitute.presentation.widgets.save_preset_dialog import PresetSaveScope
from substitute.presentation.widgets.menu_model import (
    MenuEntry,
    MenuItem,
    MenuSeparator,
    MenuSubmenu,
)


def _capture_rendered_menus(
    monkeypatch: pytest.MonkeyPatch,
) -> list[Any]:
    """Capture real menus produced by the shared renderer without popups."""

    rendered: list[Any] = []
    renderer_type = cast(Any, node_card_action_menu).QFluentMenuRenderer
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
    """The title gear should expose and apply matching node presets."""

    _ensure_app()
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
        binding = _create_binding(title, cube_state, source)
        assert binding is not None
        assert title.contextMenuPolicy() == Qt.ContextMenuPolicy.DefaultContextMenu
        binding.button.click()

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


def test_node_title_menu_omits_apply_when_no_presets_and_saves_named_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Save action should open the preset dialog and pass captured current inputs."""

    _ensure_app()
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
        binding = _create_binding(title, cube_state, source)
        assert binding is not None
        binding.button.click()

        root_menu = rendered_menus[0]
        assert _round_menu_entries(root_menu) == [
            ("action", "Save current Sampler as preset...")
        ]
        root_menu.menuActions()[0].trigger()
        assert _FakeSavePresetDialog.instances[0].title == "Save Sampler preset"
        assert source.saved == [("Fast Draft", "KSampler", {"steps": 20}, source.scope)]
    finally:
        title.close()


def test_node_title_menu_omits_save_when_no_savable_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Save action should be absent when capture finds no preset-safe values."""

    _ensure_app()
    rendered_menus = _capture_rendered_menus(monkeypatch)
    title = QWidget()
    cube_state = _cube_state({"steps": ["other", 0]})
    source = _FakeNodePresetSource(
        NodeInputPresetMenuModel(
            sections=(NodeInputPresetMenuSection(title="Global", presets=()),),
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
        binding = _create_binding(title, cube_state, source)

        assert binding is None
        assert rendered_menus == []
        assert title.findChildren(NodeCardActionMenuButton) == []
        assert title.contextMenuPolicy() == Qt.ContextMenuPolicy.DefaultContextMenu
    finally:
        title.close()


def test_node_title_menu_appends_advanced_visibility_after_preset_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Place advanced visibility at the separated bottom of the gear menu."""

    _ensure_app()
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

    class _AdvancedInputs:
        """Provide the action-menu surface of an advanced binding."""

        shown = False

        def set_shown(self, shown: bool) -> None:
            """Set the represented disclosure state."""

            self.shown = shown

    advanced = _AdvancedInputs()
    try:
        binding = _create_binding(
            title,
            cube_state,
            source,
            advanced=cast(AdvancedInputCardBinding, advanced),
        )
        assert binding is not None
        binding.button.click()

        root_menu = rendered_menus[-1]
        assert _round_menu_entries(root_menu) == [
            ("menu", "Apply preset"),
            ("separator", ""),
            ("action", "Save current Sampler as preset..."),
            ("separator", ""),
            ("action", "Show advanced inputs"),
        ]
        root_menu.menuActions()[-1].trigger()
        assert advanced.shown is True

        binding.button.click()

        advanced_action = rendered_menus[-1].menuActions()[-1]
        assert _round_menu_entries(rendered_menus[-1])[-1] == (
            "action",
            "Show advanced inputs",
        )
        assert advanced_action.isCheckable() is True
        assert advanced_action.isChecked() is True
    finally:
        title.close()


def test_node_action_menu_flattens_live_semantic_field_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cog should expose field actions directly without wrapper submenus."""

    _ensure_app()
    rendered_menus = _capture_rendered_menus(monkeypatch)
    title = QWidget()
    cube_state = _cube_state({"steps": 20})
    source = _FakeNodePresetSource(NodeInputPresetMenuModel())
    contexts: list[FieldActionContext] = []

    def dimension_entries(context: FieldActionContext) -> tuple[MenuItem, ...]:
        """Return one live dimension action and record the popup anchor."""

        contexts.append(context)
        return (MenuItem("dimension.swap", "Swap width & height"),)

    def prompt_entries(context: FieldActionContext) -> tuple[MenuEntry, ...]:
        """Return prompt actions and record the same popup anchor."""

        contexts.append(context)
        return (
            MenuSubmenu(
                "Insert trigger words",
                entries=(MenuItem("prompt.trigger", "Friendly Midna"),),
            ),
            MenuItem("prompt.schedule", "Schedule LoRA"),
            MenuSeparator(),
            MenuItem("prompt.rendering", "Rich prompt rendering"),
        )

    try:
        binding = _create_binding(
            title,
            cube_state,
            source,
            field_action_contributions=(
                FieldActionContribution(
                    contribution_id="field.width.height",
                    availability_factory=lambda: True,
                    entries_factory=dimension_entries,
                ),
                FieldActionContribution(
                    contribution_id="field.unavailable",
                    availability_factory=lambda: False,
                    entries_factory=lambda _context: (),
                ),
                FieldActionContribution(
                    contribution_id="field.prompt",
                    availability_factory=lambda: True,
                    entries_factory=prompt_entries,
                ),
            ),
        )
        assert binding is not None

        binding.button.click()

        assert len(contexts) == 2
        assert contexts[0].anchor_global_position == contexts[1].anchor_global_position
        root_menu = rendered_menus[-1]
        assert _round_menu_entries(root_menu) == [
            ("action", "Swap width & height"),
            ("separator", ""),
            ("menu", "Insert trigger words"),
            ("action", "Schedule LoRA"),
            ("separator", ""),
            ("action", "Rich prompt rendering"),
        ]
        assert [submenu.title() for submenu in cast(Any, root_menu)._subMenus] == [
            "Insert trigger words"
        ]
    finally:
        title.close()


def _ensure_app() -> QApplication:
    """Return an existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def _create_binding(
    title: QWidget,
    cube_state: CubeState,
    source: _FakeNodePresetSource,
    *,
    advanced: AdvancedInputCardBinding | None = None,
    field_action_contributions: tuple[FieldActionContribution, ...] = (),
) -> NodeCardActionMenuBinding | None:
    """Create the production gear binding for one preset test node."""

    layout = QHBoxLayout(title)
    return NodeCardActionMenuBinding.create(
        title_row=title,
        title_layout=layout,
        preset_context=_context(cube_state),
        preset_source=source,
        dialog_parent=lambda: title,
        is_connection=_is_connection,
        advanced_inputs=advanced,
        field_action_contributions=field_action_contributions,
    )


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
