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

"""Verify semantic synthetic-resolution node-card contributions."""

from __future__ import annotations

import gc
from typing import Any, cast


from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget

from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
)

from substitute.application.workflows.synthetic_canvas_resolution_role_service import (
    SyntheticCanvasResolutionRole,
)
from substitute.domain.node_behavior import FieldBehavior
from substitute.domain.workflow import CanvasDimensionAuthority, CanvasDimensions
from substitute.presentation.editor.field_actions import FieldActionContext
from substitute.presentation.editor.panel.node_card.body_contribution import (
    NodeCardBodyContributionContext,
)
from substitute.presentation.editor.panel.node_card.body_composer import (
    NodeCardBodyComposer,
)
from substitute.presentation.editor.panel.node_card.synthetic_resolution_contributor import (
    SyntheticCanvasResolutionContributor,
    SyntheticCanvasResolutionRowDecorator,
)
from substitute.presentation.editor.panel.menus.dimension_row_actions import (
    DimensionRowActions,
)
from substitute.presentation.editor.panel.widgets.field_row import (
    GROUPED_FIELD_DIVIDER_WIDTH,
    EDITOR_ROW_HEIGHT,
    FieldRowBuilder,
)
from substitute.presentation.widgets.spin_box import SpinBox


class _RoleResolver:
    """Return one configured semantic role for contributor tests."""

    def __init__(self, role: SyntheticCanvasResolutionRole | None) -> None:
        """Store the result returned for every node query."""

        self.role = role

    def resolve_for_node(
        self, **_kwargs: object
    ) -> SyntheticCanvasResolutionRole | None:
        """Return the configured role."""

        return self.role


class _Panel(QWidget):
    """Provide the row registry expected by node-card composition."""

    def __init__(self) -> None:
        """Initialize an empty row registry."""

        super().__init__()
        self.row_widgets: dict[object, tuple[QWidget | None, QWidget]] = {}


def _app() -> QApplication:
    """Return the process QApplication."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_contributor_locks_original_dimension_fields_and_opens_intent() -> None:
    """The semantic row should retain genuine fields and preserve action identity."""

    _app()
    role = _role()
    requests: list[SyntheticCanvasResolutionRole] = []
    contributor = SyntheticCanvasResolutionContributor(
        roles=_RoleResolver(role),
        change_requested=requests.append,
    )
    panel = _Panel()
    width = _dimension_spin(panel, value=960, key="width")
    height = _dimension_spin(panel, value=1344, key="height")
    field_rows = FieldRowBuilder(
        panel=panel,
        icon_builder=lambda _icon: QWidget(panel),
        icon_resolver=lambda _node, _field, column_index=None: None,
    )
    content = QWidget(panel)
    content_layout = QVBoxLayout(content)

    contribution = contributor.build(_context())

    assert contribution is not None
    assert contribution.claimed_field_keys == frozenset({"width", "height"})
    assert contribution.field_keys == ("width", "height")
    decorator = cast(
        SyntheticCanvasResolutionRowDecorator,
        contribution.row_decorator,
    )
    row = NodeCardBodyComposer(panel=panel, field_rows=field_rows).add_n_column_row(
        fields=[("width", width), ("height", height)],
        field_behaviors={
            "width": FieldBehavior(field_key="width"),
            "height": FieldBehavior(field_key="height"),
        },
        content_layout=content_layout,
        contribution=contribution,
    )

    content_item = content_layout.itemAt(0)
    assert content_item is not None
    assert content_item.widget() is row.row
    assert row.text_targets[0].field_widget is width
    assert row.text_targets[1].field_widget is height
    assert width.value() == 960
    assert height.value() == 1344
    assert not width.isEnabled()
    assert not height.isEnabled()
    assert width.height() == EDITOR_ROW_HEIGHT
    assert height.height() == EDITOR_ROW_HEIGHT
    assert decorator.change_button is not None
    assert decorator.change_button.parent() is row.row
    assert decorator.change_button.height() == EDITOR_ROW_HEIGHT
    assert decorator.change_button.text() == render_application_text(
        app_text("Resize canvas")
    )
    row_layout = row.row.layout()
    assert isinstance(row_layout, QHBoxLayout)
    assert row_layout.indexOf(decorator.change_button) == row_layout.count() - 2
    action_item = row_layout.itemAt(row_layout.count() - 3)
    assert action_item is not None
    action_divider = action_item.widget()
    assert action_divider is not None
    assert action_divider.width() == GROUPED_FIELD_DIVIDER_WIDTH
    assert action_divider.height() == EDITOR_ROW_HEIGHT
    change_button = decorator.change_button
    del decorator
    del contribution
    gc.collect()

    change_button.click()
    assert requests == [role]


def test_contributor_leaves_non_authority_nodes_untouched() -> None:
    """A missing semantic role should preserve normal field rendering."""

    _app()
    contributor = SyntheticCanvasResolutionContributor(
        roles=_RoleResolver(None),
        change_requested=lambda _role: None,
    )

    assert contributor.build(_context()) is None


def test_synthetic_resolution_decorator_restricts_dimension_menu_to_saving(
    monkeypatch: Any,
) -> None:
    """Synthetic authority rows should suppress resolution-changing menu actions."""

    _app()
    calls: list[DimensionRowActions] = []
    original = DimensionRowActions.show_save_only

    def record_save_only(actions: DimensionRowActions) -> None:
        """Record the restriction while preserving production behavior."""

        calls.append(actions)
        original(actions)

    monkeypatch.setattr(DimensionRowActions, "show_save_only", record_save_only)
    role = _role()
    contributor = SyntheticCanvasResolutionContributor(
        roles=_RoleResolver(role),
        change_requested=lambda _role: None,
    )
    panel = _Panel()
    width = _dimension_spin(panel, value=960, key="width")
    height = _dimension_spin(panel, value=1344, key="height")
    field_rows = FieldRowBuilder(
        panel=panel,
        icon_builder=lambda _icon: QWidget(panel),
        icon_resolver=lambda _node, _field, column_index=None: None,
    )
    content = QWidget(panel)
    content_layout = QVBoxLayout(content)
    contribution = contributor.build(_context())

    assert contribution is not None
    built_row = NodeCardBodyComposer(
        panel=panel,
        field_rows=field_rows,
    ).add_n_column_row(
        fields=[("width", width), ("height", height)],
        field_behaviors={
            "width": FieldBehavior(field_key="width"),
            "height": FieldBehavior(field_key="height"),
        },
        content_layout=content_layout,
        contribution=contribution,
    )

    assert built_row.dimension_actions is not None
    assert calls == [built_row.dimension_actions]
    assert len(built_row.action_contributions) == 1
    assert built_row.action_contributions[0].is_available() is False
    assert built_row.action_contributions[0].entries(FieldActionContext(QPoint())) == ()


def _dimension_spin(parent: QWidget, *, value: int, key: str) -> SpinBox:
    """Build one pre-existing field widget with normal builder metadata."""

    spin = SpinBox(parent)
    spin.setRange(1, 16_384)
    spin.setValue(value)
    spin.setProperty("input_metadata", {"key": key})
    return spin


def _context() -> NodeCardBodyContributionContext:
    """Build a representative latent-root card context."""

    return NodeCardBodyContributionContext(
        section_key="Prompt by Region",
        node_name="spatial root",
        node_type="ArbitraryNode",
        inputs={"width": 960, "height": 1344, "batch_size": 1},
        graph={"nodes": {}},
    )


def _role() -> SyntheticCanvasResolutionRole:
    """Build one role whose class/name carry no detection meaning."""

    return SyntheticCanvasResolutionRole(
        section_key="Prompt by Region",
        surface_key="@synthetic/example",
        authority=CanvasDimensionAuthority(
            dimensions=CanvasDimensions(width=960, height=1344),
            node_names=("spatial root",),
            field_pairs=(("width", "height"),),
            convergence_node_names=("sampler",),
            structural_fingerprint="structure",
            dimension_fingerprint="dimensions",
        ),
    )
