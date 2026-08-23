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

"""Contract tests for prompt-card behavior resolution and rendering."""

from __future__ import annotations

from collections.abc import Iterator

from PySide6.QtWidgets import QVBoxLayout, QWidget
import pytest

from substitute.application.node_behavior import CardMode, CollapseMode
import substitute.presentation.editor.panel.node_card_builder as node_card_view
from substitute.presentation.editor.panel.widgets.field_row import (
    BuiltFieldRow,
    EDITOR_FULL_WIDTH_ROW_MARGINS,
    EDITOR_ROW_BODY_SPACING,
)
from substitute.presentation.editor.panel.node_card_builder import NodeCardBuilder
from tests.presentation.editor.node_card.builder_support import build_node_card_builder
from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.support.node_behavior import build_behavior_snapshot, cube_state
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
)
from tests.support.qt.lifecycle import destroy_widget_roots, ensure_qt_application
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _Gateway:
    """Return deterministic prompt node definitions for widget building."""

    @staticmethod
    def get_node_definition(_node_class: str) -> dict[str, object]:
        """Return no optional live definition payload."""

        return _Gateway.get_required_node_definition(_node_class)

    @staticmethod
    def get_required_node_definition(_node_class: str) -> dict[str, object]:
        """Return no required live definition payload."""

        return {}


def _add_test_field_row(
    content_layout: QVBoxLayout,
    panel: QWidget,
) -> BuiltFieldRow:
    """Append one field-row stand-in with the current composition result shape."""

    row = QWidget(panel)
    content_layout.addWidget(row)
    return BuiltFieldRow("prompt_template", row)


class _Panel(QWidget):
    """Provide the minimal panel surface used by NodeCardBuilder."""

    def __init__(self) -> None:
        super().__init__()
        self._stack_order = ["A"]
        self._cube_states: dict[str, object] = {}
        self._hidden_field_keys: set[object] = set()
        self.row_widgets: dict[object, tuple[QWidget, QWidget | None]] = {}
        self.col_widgets: dict[object, tuple[QWidget, QWidget, QWidget]] = {}
        self.prompt_link_widgets: dict[object, object] = {}

    @staticmethod
    def is_connection(_value: object) -> bool:
        """Return whether a focused prompt-card value is a connection."""

        return False


@pytest.fixture
def widget_roots() -> Iterator[list[QWidget]]:
    """Track top-level prompt-card roots and destroy them after each contract."""

    ensure_qt_application()
    roots: list[QWidget] = []
    yield roots
    destroy_widget_roots(roots)


def mount_prompt_card(
    host: QWidget,
    wrapper: QWidget,
    *,
    width: int,
    height: int,
) -> None:
    """Mount one built prompt-card wrapper at its real host dimensions."""

    layout = QVBoxLayout(host)
    layout.addWidget(wrapper)
    host.resize(width, height)
    host.show()


def height_padding(box: PromptEditor) -> int:
    """Return the prompt-editor shell padding applied outside one text line."""

    return box.minimumEditorHeight() - box.lineHeight()


def set_manual_scroll_height(box: PromptEditor, height: int) -> None:
    """Set the prompt editor's manual scroll height for contract tests."""

    box.setManualScrollHeight(height)


def assert_prompt_row_uses_shared_flexible_margins(
    padded_row: QWidget,
    prompt_editor: PromptEditor,
) -> None:
    """Assert prompt rows use shared spacing while remaining content-height driven."""

    layout = padded_row.layout()
    assert isinstance(layout, QVBoxLayout)
    margins = layout.contentsMargins()
    assert (
        margins.left(),
        margins.top(),
        margins.right(),
        margins.bottom(),
    ) == EDITOR_FULL_WIDTH_ROW_MARGINS
    assert margins.top() == EDITOR_ROW_BODY_SPACING
    assert margins.bottom() == EDITOR_ROW_BODY_SPACING
    assert padded_row.height() >= (
        prompt_editor.height() + margins.top() + margins.bottom()
    )


def test_prompt_cards_resolve_to_prompt_mode_and_skip_collapse_animation(
    monkeypatch: pytest.MonkeyPatch,
    widget_roots: list[QWidget],
) -> None:
    """Prompt cards should resolve to prompt mode and never attach accordion behavior."""

    panel = _Panel()
    widget_roots.append(panel)
    definitions = {
        "PromptNode": {
            "input": {"required": {"prompt_template": ["STRING", {}]}},
        }
    }
    cube = cube_state(
        nodes={
            "positive_prompt": {
                "class_type": "PromptNode",
                "inputs": {"prompt_template": "hello world"},
            }
        },
        definitions=definitions,
    )
    panel._cube_states = {"A": cube}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=definitions,
    )
    resolved = snapshot.resolved_nodes_by_alias["A"]["positive_prompt"]
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )
    collapsible_calls: list[bool] = []
    monkeypatch.setattr(
        NodeCardBuilder,
        "_setup_collapsible_animation",
        lambda *args, **kwargs: collapsible_calls.append(True),
    )
    monkeypatch.setattr(
        NodeCardBuilder,
        "_create_title_row",
        lambda self, **_kwargs: (QWidget(panel), None),
    )
    monkeypatch.setattr(
        node_card_view,
        "build_widget_for_field_spec",
        lambda **_kwargs: QWidget(),
    )
    monkeypatch.setattr(
        NodeCardBuilder,
        "_add_input_row",
        lambda self, *, content_layout, **_kwargs: _add_test_field_row(
            content_layout,
            panel,
        ),
    )

    wrapper = builder.build_node_card(
        node_name="positive_prompt",
        inputs={"prompt_template": "hello world"},
        node_type="PromptNode",
        field_specs=snapshot.field_specs_by_alias["A"]["positive_prompt"],
        cube_state=cube,
        resolved_behavior=resolved,
        alias="A",
    )

    assert wrapper is not None
    assert resolved.card.card_mode == CardMode.PROMPT
    assert resolved.card.collapse_mode == CollapseMode.EXEMPT
    assert collapsible_calls == []


def test_prompt_card_full_width_row_grows_with_prompt_editor_on_narrow_resize(
    monkeypatch: pytest.MonkeyPatch,
    widget_roots: list[QWidget],
) -> None:
    """Prompt-card full-width rows should expand when wrapped prompt height increases."""

    panel = _Panel()
    widget_roots.append(panel)
    definitions = {
        "PromptNode": {
            "input": {"required": {"prompt_template": ["STRING", {}]}},
        }
    }
    prompt_text = (
        "landscape photography, cinematic lighting, hyper detailed, dramatic "
        "sky, volumetric fog, sharp focus, 35mm film, subtle grain"
    )
    cube = cube_state(
        nodes={
            "positive_prompt": {
                "class_type": "PromptNode",
                "inputs": {"prompt_template": prompt_text},
            }
        },
        definitions=definitions,
    )
    panel._cube_states = {"A": cube}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=definitions,
    )
    resolved = snapshot.resolved_nodes_by_alias["A"]["positive_prompt"]
    autocomplete_gateway = EmptyPromptAutocompleteGateway()
    builder = build_node_card_builder(
        panel,
        _Gateway(),
        prompt_autocomplete_gateway=autocomplete_gateway,
    )
    monkeypatch.setattr(
        NodeCardBuilder,
        "_create_title_row",
        lambda self, **_kwargs: (QWidget(panel), None),
    )

    wrapper = builder.build_node_card(
        node_name="positive_prompt",
        inputs={"prompt_template": prompt_text},
        node_type="PromptNode",
        field_specs=snapshot.field_specs_by_alias["A"]["positive_prompt"],
        cube_state=cube,
        resolved_behavior=resolved,
        alias="A",
    )

    assert wrapper is not None

    host = QWidget()
    widget_roots.append(host)
    mount_prompt_card(host, wrapper, width=600, height=420)

    prompt_editor = wrapper.findChild(PromptEditor)
    assert prompt_editor is not None
    wait_for_qt_condition(lambda: prompt_editor.viewport().width() >= 500)
    assert (
        prompt_editor._autocomplete_refresh_controller._lifecycle_requester._result_controller._prompt_autocomplete_gateway
        is autocomplete_gateway
    )

    row_widgets = panel.row_widgets[("A", "positive_prompt", "prompt_template")]
    _divider, padded_row = row_widgets
    assert padded_row is not None

    host.resize(260, 420)
    wait_for_qt_condition(lambda: padded_row.height() != 33)

    assert_prompt_row_uses_shared_flexible_margins(padded_row, prompt_editor)


def test_prompt_card_body_grows_after_manual_prompt_editor_resize(
    monkeypatch: pytest.MonkeyPatch,
    widget_roots: list[QWidget],
) -> None:
    """Prompt-card layout should follow manual prompt editor viewport growth."""

    panel = _Panel()
    widget_roots.append(panel)
    definitions = {
        "PromptNode": {
            "input": {"required": {"prompt_template": ["STRING", {}]}},
        }
    }
    prompt_text = "\n".join(f"line {index}" for index in range(40))
    cube = cube_state(
        nodes={
            "positive_prompt": {
                "class_type": "PromptNode",
                "inputs": {"prompt_template": prompt_text},
            }
        },
        definitions=definitions,
    )
    panel._cube_states = {"A": cube}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=definitions,
    )
    resolved = snapshot.resolved_nodes_by_alias["A"]["positive_prompt"]
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )
    monkeypatch.setattr(
        NodeCardBuilder,
        "_create_title_row",
        lambda self, **_kwargs: (QWidget(panel), None),
    )

    wrapper = builder.build_node_card(
        node_name="positive_prompt",
        inputs={"prompt_template": prompt_text},
        node_type="PromptNode",
        field_specs=snapshot.field_specs_by_alias["A"]["positive_prompt"],
        cube_state=cube,
        resolved_behavior=resolved,
        alias="A",
    )

    assert wrapper is not None
    host = QWidget()
    widget_roots.append(host)
    mount_prompt_card(host, wrapper, width=600, height=640)

    prompt_editor = wrapper.findChild(PromptEditor)
    assert prompt_editor is not None
    row_widgets = panel.row_widgets[("A", "positive_prompt", "prompt_template")]
    _divider, padded_row = row_widgets
    assert padded_row is not None
    wait_for_qt_condition(lambda: prompt_editor.viewport().width() >= 500)
    initial_row_height = padded_row.height()
    target_height = prompt_editor.height() + prompt_editor.lineHeight() * 4

    set_manual_scroll_height(prompt_editor, target_height)
    wait_for_qt_condition(
        lambda: (
            prompt_editor.height() == target_height
            and padded_row.height() > initial_row_height
        )
    )

    assert_prompt_row_uses_shared_flexible_margins(padded_row, prompt_editor)


def test_prompt_card_initial_prompt_height_tracks_laid_out_card_width(
    monkeypatch: pytest.MonkeyPatch,
    widget_roots: list[QWidget],
) -> None:
    """Prompt cards should settle prompt height from the real laid-out card width."""

    panel = _Panel()
    widget_roots.append(panel)
    definitions = {
        "PromptNode": {
            "input": {"required": {"prompt_template": ["STRING", {}]}},
        }
    }
    prompt_text = (
        "landscape photography, cinematic lighting, hyper detailed, dramatic "
        "sky, volumetric fog, sharp focus, 35mm film, subtle grain"
    )
    cube = cube_state(
        nodes={
            "positive_prompt": {
                "class_type": "PromptNode",
                "inputs": {"prompt_template": prompt_text},
            }
        },
        definitions=definitions,
    )
    panel._cube_states = {"A": cube}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=definitions,
    )
    resolved = snapshot.resolved_nodes_by_alias["A"]["positive_prompt"]
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )
    monkeypatch.setattr(
        NodeCardBuilder,
        "_create_title_row",
        lambda self, **_kwargs: (QWidget(panel), None),
    )

    wrapper = builder.build_node_card(
        node_name="positive_prompt",
        inputs={"prompt_template": prompt_text},
        node_type="PromptNode",
        field_specs=snapshot.field_specs_by_alias["A"]["positive_prompt"],
        cube_state=cube,
        resolved_behavior=resolved,
        alias="A",
    )

    assert wrapper is not None

    host = QWidget()
    widget_roots.append(host)
    mount_prompt_card(host, wrapper, width=600, height=420)

    prompt_editor = wrapper.findChild(PromptEditor)
    assert prompt_editor is not None
    wait_for_qt_condition(lambda: prompt_editor.viewport().width() >= 500)
    assert prompt_editor.height() < prompt_editor.lineHeight() * 10 + height_padding(
        prompt_editor
    )
    wait_for_qt_condition(
        lambda: prompt_editor.scrollDelegate.vScrollBar.isVisible() is False
    )

    row_widgets = panel.row_widgets[("A", "positive_prompt", "prompt_template")]
    _divider, padded_row = row_widgets
    assert padded_row is not None
    assert_prompt_row_uses_shared_flexible_margins(padded_row, prompt_editor)
    assert padded_row.height() != 33
