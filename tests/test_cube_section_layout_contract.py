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

"""Contract tests for cube-section layout behavior."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import LineEdit  # type: ignore[import-untyped]

from substitute.application.node_behavior import FieldBehavior
from substitute.application.workflows import (
    CubeRuntimeIssue,
    CubeRuntimeIssueKind,
    CubeRuntimeIssueSeverity,
    CubeRuntimeIssueSource,
)
from substitute.presentation.editor.panel.widgets.field_row import FieldRowBuilder


def _ensure_qapp() -> QApplication:
    """Return the QApplication required by cube-section widget tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _section() -> Any:
    """Build a minimal cube section suitable for layout-state checks."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.cube_section"
    )
    header = QWidget()
    prompt_area = QVBoxLayout()
    grid_layout = mod.MasonryGridLayout()
    content = QWidget()
    content.setMinimumSize(120, 40)
    grid_layout.addWidget(content)
    section = mod.CubeSectionView(
        header_bar=header,
        prompt_area=prompt_area,
        grid_layout=grid_layout,
    )
    section.resize(220, 120)
    section.show()
    return section


def _process_events(app: QApplication, *, cycles: int = 6) -> None:
    """Process enough event turns for deferred cube-section layout work."""

    for _ in range(cycles):
        app.processEvents()


class _FixedHintWidget(QWidget):
    """Provide a deterministic size hint for masonry geometry tests."""

    def sizeHint(self) -> QSize:
        """Return the fixed natural size consumed by MasonryGridLayout."""

        return QSize(200, 40)


def test_masonry_layout_ignores_provisional_tiny_parent_height() -> None:
    """Masonry placement should follow accumulated column height, not rect bottom."""

    _ensure_qapp()
    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.masonry_grid_layout"
    )
    host = QWidget()
    layout = mod.MasonryGridLayout(host, column_width=200, spacing=8)
    host.setLayout(layout)
    cards: list[QWidget] = []
    try:
        for _index in range(3):
            card = _FixedHintWidget(host)
            card.setFixedHeight(40)
            layout.addWidget(card)
            cards.append(card)
        host.resize(220, 1)
        host.show()
        layout.setGeometry(host.rect())

        card_tops = [card.geometry().top() for card in cards]

        assert card_tops == [0, 48, 96]
        assert len(set(card_tops)) == len(card_tops)
    finally:
        host.close()
        host.deleteLater()


def test_cube_section_finalization_removes_provisional_masonry_overlap() -> None:
    """Reveal finalization should leave visible cube cards at distinct vertical slots."""

    app = _ensure_qapp()
    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.cube_section"
    )
    header = QWidget()
    prompt_area = QVBoxLayout()
    grid_layout = mod.MasonryGridLayout(column_width=200, spacing=8)
    section = mod.CubeSectionView(
        header_bar=header,
        prompt_area=prompt_area,
        grid_layout=grid_layout,
    )
    cards: list[QWidget] = []
    try:
        for _index in range(3):
            card = _FixedHintWidget(section)
            card.setFixedHeight(40)
            grid_layout.addWidget(card)
            cards.append(card)
        section.resize(220, 1)
        section.show()
        _process_events(app)

        section.finalize_layout_for_reveal(reason="test")

        visible_tops = [card.geometry().top() for card in cards if card.isVisible()]
        assert len(visible_tops) == 3
        assert visible_tops == sorted(visible_tops)
        assert len(set(visible_tops)) == len(visible_tops)
    finally:
        section.close()
        section.deleteLater()
        _process_events(app)


def _string_input_row(
    *,
    label_width: int,
    key: str,
) -> tuple[QWidget, LineEdit]:
    """Return one label-plus-string row that mimics node-card width ownership."""

    row = QWidget()
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(0)
    label = QWidget(row)
    label.setFixedWidth(label_width)
    field = LineEdit(row)
    field.setProperty(
        "input_metadata",
        {"cube_alias": "cube", "node_name": "node", "key": key, "type": "STRING"},
    )
    field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    row_layout.addWidget(label, 0)
    row_layout.addWidget(field, 1)
    return row, field


class _FieldRowPanel(QWidget):
    """Minimal panel double for real field-row width-group tests."""

    def __init__(self) -> None:
        """Initialize field-row registries expected by FieldRowBuilder."""

        super().__init__()
        self.row_widgets: dict[object, object] = {}
        self.col_widgets: dict[object, object] = {}


def _field_row_builder(panel: QWidget) -> FieldRowBuilder:
    """Return a field-row builder with no custom icons."""

    return FieldRowBuilder(
        panel=panel,
        icon_builder=lambda _icon: QWidget(panel),
        icon_resolver=lambda _node_name, _row_label, _column_index=None: None,
    )


def _real_string_field_row(
    *,
    panel: QWidget,
    label: str,
    key: str,
) -> tuple[QWidget, LineEdit]:
    """Return a real editor scalar row containing one string line edit."""

    content = QWidget(panel)
    content_layout = QVBoxLayout(content)
    field = LineEdit(panel)
    field.setProperty(
        "input_metadata",
        {"cube_alias": "cube", "node_name": "node", "key": key, "type": "STRING"},
    )
    _field_row_builder(panel).add_input_row(
        label=label,
        widget=field,
        field_behavior=FieldBehavior(field_key=key),
        content_layout=content_layout,
    )
    row_item = content_layout.itemAt(0)
    assert row_item is not None
    row = row_item.widget()
    assert row is not None
    return row, field


def test_resolved_cube_height_overrides_stale_larger_size_hint() -> None:
    """Resolved masonry height should be the section's authoritative size hint."""

    app = _ensure_qapp()
    section = _section()
    app.processEvents()

    section.update_cube_height()
    resolved_height = section._resolved_height
    assert isinstance(resolved_height, int)

    section.resize(section.width(), resolved_height + 120)

    assert section.minimumHeight() == resolved_height
    assert section.sizeHint().height() == resolved_height
    assert section.minimumSizeHint().height() == resolved_height


def test_cube_section_header_gap_matches_editor_cube_gap() -> None:
    """Cube title-to-card spacing should match the editor's leading cube gap."""

    _ensure_qapp()
    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.cube_section"
    )
    panel = cast(Any, QWidget())
    panel._last_behavior_snapshot = SimpleNamespace(field_specs_by_alias={})
    panel.scroll = SimpleNamespace(schedule_metrics_refresh=lambda: None)
    panel.cube_headers = {}
    panel._cube_visibility_btns = {}
    panel._cube_visibility_menus = {}
    try:
        parts = mod.CubeSectionBuilder(panel).build_cube_section("SDXL/Text to Image")

        header_layout = parts.widget._header.layout()
        assert header_layout is not None
        margins = header_layout.contentsMargins()

        assert margins.bottom() == mod.EDITOR_SECTION_GAP
    finally:
        panel.deleteLater()


def test_direct_workflow_section_hides_cube_title_chrome() -> None:
    """A complete Comfy document should render without a cube heading separator."""

    _ensure_qapp()
    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.cube_section"
    )
    panel = cast(Any, QWidget())
    panel._last_behavior_snapshot = SimpleNamespace(field_specs_by_alias={})
    panel.scroll = SimpleNamespace(schedule_metrics_refresh=lambda: None)
    panel.cube_headers = {}
    panel._cube_visibility_btns = {}
    panel._cube_visibility_menus = {}
    panel._cube_states = {
        "__direct_comfy_workflow__": SimpleNamespace(
            shows_cube_section_title=False,
            buffer={"nodes": {}},
        )
    }
    try:
        parts = mod.CubeSectionBuilder(panel).build_cube_section(
            "__direct_comfy_workflow__"
        )

        header_layout = parts.widget._header.layout()
        assert header_layout is not None
        assert header_layout.contentsMargins().bottom() == 0
        assert parts.header_label.isHidden() is True
        assert parts.reveal_button.isHidden() is False
    finally:
        panel.deleteLater()


def test_cube_section_title_marks_bypassed_cube() -> None:
    """Initial cube section titles should reflect bypassed workflow state."""

    _ensure_qapp()
    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.cube_section"
    )
    panel = cast(Any, QWidget())
    panel._last_behavior_snapshot = SimpleNamespace(field_specs_by_alias={})
    panel.scroll = SimpleNamespace(schedule_metrics_refresh=lambda: None)
    panel.cube_headers = {}
    panel._cube_visibility_btns = {}
    panel._cube_visibility_menus = {}
    panel._cube_states = {
        "Anima/Text to Image": SimpleNamespace(bypassed=True, buffer={"nodes": {}})
    }
    try:
        mod.CubeSectionBuilder(panel).build_cube_section("Anima/Text to Image")

        assert panel.cube_headers["Anima/Text to Image"].text() == (
            "Anima/Text to Image (bypassed)"
        )
    finally:
        panel.deleteLater()


def test_cube_section_title_elision_preserves_bypassed_suffix() -> None:
    """Long editor cube titles should elide before dropping bypass context."""

    _ensure_qapp()
    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.cube_section"
    )
    panel = cast(Any, QWidget())
    panel._last_behavior_snapshot = SimpleNamespace(field_specs_by_alias={})
    panel.scroll = SimpleNamespace(schedule_metrics_refresh=lambda: None)
    panel.cube_headers = {}
    panel._cube_visibility_btns = {}
    panel._cube_visibility_menus = {}
    long_alias = "SDXL/Very Long Automask Detailer With Extra Context"
    panel._cube_states = {
        long_alias: SimpleNamespace(bypassed=True, buffer={"nodes": {}})
    }
    try:
        mod.CubeSectionBuilder(panel).build_cube_section(long_alias)
        title = panel.cube_headers[long_alias]

        elided = title._elided_text_for_width(260)

        assert elided.endswith(" (bypassed)")
        assert "..." in elided or "\u2026" in elided
        assert elided != title.text()
    finally:
        panel.deleteLater()


def test_content_container_fills_section_height_from_top() -> None:
    """Extra resolved section height should not center or clip cube content."""

    app = _ensure_qapp()
    section = _section()
    app.processEvents()

    section.update_cube_height()
    resolved_height = section._resolved_height
    assert isinstance(resolved_height, int)

    section.resize(section.width(), resolved_height + 120)
    app.processEvents()

    assert section._content_container.geometry().top() == 0
    assert section._content_container.height() == section.height()


def test_error_cube_section_height_includes_issue_details() -> None:
    """Error sections should not collapse to the empty masonry grid height."""

    app = _ensure_qapp()
    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.cube_section"
    )
    panel = cast(Any, QWidget())
    panel.scroll = SimpleNamespace(schedule_metrics_refresh=lambda: None)
    panel.cube_headers = {}
    issue = CubeRuntimeIssue(
        workflow_id="workflow",
        cube_alias="Anima/Diffusion Upscale",
        severity=CubeRuntimeIssueSeverity.ERROR,
        kind=CubeRuntimeIssueKind.MISSING_LIVE_NODE_DEFINITION,
        message="This cube cannot be rendered because live Comfy metadata is unavailable.",
        operation="resolve wrapper body node metadata",
        source=CubeRuntimeIssueSource.PROJECTION,
        missing_node_classes=("SimpleSyrup.KSamplerMixtureOfDiffusers",),
        node_names=("resize_by_factor",),
        recommended_action=(
            "Update this cube from the Cube Library, or start or restart ComfyUI "
            "and confirm required custom nodes loaded."
        ),
    )
    try:
        section = mod.CubeSectionBuilder(panel).build_error_cube_widget(
            "Anima/Diffusion Upscale",
            issue_lines=(
                issue.message,
                "Missing definition: SimpleSyrup.KSamplerMixtureOfDiffusers",
                issue.recommended_action,
            ),
        )
        section.resize(420, 40)
        section.show()
        _process_events(app)

        section.update_cube_height()

        assert section.minimumHeight() >= 120
        assert section.findChild(QWidget, "CubeRuntimeIssueNodeCard") is not None
        assert "Missing definition: SimpleSyrup.KSamplerMixtureOfDiffusers" in (
            section.issueMessages()
        )
    finally:
        panel.deleteLater()


def test_string_line_edits_share_cube_width_group_and_grow_with_section() -> None:
    """Cube string line edits should share the shortest available row width."""

    app = _ensure_qapp()
    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.cube_section"
    )
    header = QWidget()
    prompt_area = QVBoxLayout()
    first_row, first_field = _string_input_row(label_width=56, key="first")
    second_row, second_field = _string_input_row(label_width=176, key="second")
    prompt_area.addWidget(first_row)
    prompt_area.addWidget(second_row)
    section = mod.CubeSectionView(
        header_bar=header,
        prompt_area=prompt_area,
        grid_layout=mod.MasonryGridLayout(),
    )
    section.resize(420, 140)
    section.show()
    _process_events(app)

    narrow_width = first_field.width()
    assert narrow_width == second_field.width()
    assert first_field.geometry().right() == second_field.geometry().right()

    section.resize(620, 140)
    _process_events(app)

    assert first_field.width() == second_field.width()
    assert first_field.width() > narrow_width
    assert first_field.geometry().right() == second_field.geometry().right()


def test_real_string_line_edit_rows_align_shared_width_to_trailing_edge() -> None:
    """Real scalar string rows should right-align width-capped line edits."""

    app = _ensure_qapp()
    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.cube_section"
    )
    panel = _FieldRowPanel()
    header = QWidget()
    prompt_area = QVBoxLayout()
    first_row, first_field = _real_string_field_row(
        panel=panel,
        label="Short",
        key="first",
    )
    second_row, second_field = _real_string_field_row(
        panel=panel,
        label="Much Longer Label",
        key="second",
    )
    prompt_area.addWidget(first_row)
    prompt_area.addWidget(second_row)
    section = mod.CubeSectionView(
        header_bar=header,
        prompt_area=prompt_area,
        grid_layout=mod.MasonryGridLayout(),
    )
    section.resize(560, 180)
    section.show()
    _process_events(app)
    try:
        first_left = first_field.mapTo(section, first_field.rect().topLeft()).x()
        second_left = second_field.mapTo(section, second_field.rect().topLeft()).x()
        first_right = first_field.mapTo(section, first_field.rect().bottomRight()).x()
        second_right = second_field.mapTo(
            section,
            second_field.rect().bottomRight(),
        ).x()

        assert first_field.width() == second_field.width()
        assert first_right == second_right
        assert first_left == second_left
        assert first_field.width() > first_field.sizeHint().width()
    finally:
        section.close()
        section.deleteLater()
        panel.deleteLater()
        _process_events(app)
