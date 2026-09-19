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

"""Contract tests for generic card-body relayout around self-sizing field widgets."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from tests.presentation.editor.node_card.builder_support import build_node_card_builder
from tests.support.qt.semantic_wait import (
    wait_for_qt_condition,
    wait_for_qt_signal,
    wait_for_queued_qt_turn,
)
from substitute.presentation.editor.panel.widgets.field_relayout import (
    bind_field_widget_card_relayout,
)
from substitute.presentation.editor.panel.node_card.body_layout import (
    apply_card_body_layout_state,
    ensure_card_body_layout_state,
)
from tests.support.node_behavior import build_behavior_snapshot, cube_state


class _DynamicHeightWidget(QWidget):
    """Provide a small QWidget whose height can change during a test."""

    def __init__(self) -> None:
        """Initialize the widget with a deterministic starting height."""

        super().__init__()
        self.setFixedHeight(40)

    def set_test_height(self, height: int) -> None:
        """Change the widget height and request relayout from parent layouts."""

        self.setFixedHeight(height)
        self.updateGeometry()


class _SignalHeightWidget(_DynamicHeightWidget):
    """Expose the resize-like signal used by self-sizing editor widgets."""

    resized = Signal()


class _Gateway:
    """Return deterministic node definitions for focused node-card tests."""

    @staticmethod
    def get_node_definition(node_class: str) -> dict[str, object]:
        """Return one minimal string-field definition for the requested class."""

        return _Gateway.get_required_node_definition(node_class)

    @staticmethod
    def get_required_node_definition(node_class: str) -> dict[str, object]:
        """Return one required minimal string-field definition for the class."""

        return {
            node_class: {
                "input": {
                    "required": {
                        "value": ["STRING", {}],
                    }
                }
            }
        }


class _Panel(QWidget):
    """Provide the minimal panel surface consumed by NodeCardBuilder."""

    def __init__(self) -> None:
        """Initialize panel maps used by row registration and card wiring."""

        super().__init__()
        self._stack_order = ["A"]
        self._cube_states: dict[str, object] = {}
        self._hidden_field_keys: set[object] = set()
        self.row_widgets: dict[object, tuple[QWidget, QWidget | None]] = {}
        self.col_widgets: dict[object, tuple[QWidget, QWidget, QWidget]] = {}
        self.prompt_link_widgets: dict[object, object] = {}
        self.input_widgets_by_field_key: dict[tuple[str, str, str], QWidget] = {}

    @staticmethod
    def is_connection(_value: object) -> bool:
        """Report that the focused test values are always literals."""

        return False


class _SectionOwner(QWidget):
    """Capture section-owner relayout notifications from field widgets."""

    def __init__(self) -> None:
        """Initialize the owner with no relayout notifications."""

        super().__init__()
        self.finalize_reasons: list[str] = []

    def finalize_layout_after_child_relayout(self, *, reason: str) -> None:
        """Record one child-relayout finalization request."""

        self.finalize_reasons.append(reason)


def ensure_qapp() -> QApplication:
    """Return a running Qt application for relayout tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _close_and_delete(widget: QWidget) -> None:
    """Close one test root and wait until Qt confirms its deletion."""

    destroyed = QSignalSpy(widget.destroyed)
    widget.close()
    widget.deleteLater()
    wait_for_qt_signal(destroyed)


def build_card_body(
    *, allow_unbounded_height: bool
) -> tuple[QWidget, QWidget, _DynamicHeightWidget]:
    """Create one minimal card body with a single self-sizing field widget."""

    content_body = QWidget()
    content_layout = QVBoxLayout(content_body)
    content_layout.setContentsMargins(0, 0, 0, 0)
    row = QWidget(content_body)
    row_layout = QVBoxLayout(row)
    row_layout.setContentsMargins(10, 0, 10, 8)
    field_widget = _DynamicHeightWidget()
    row_layout.addWidget(field_widget)
    content_layout.addWidget(row)
    if allow_unbounded_height:
        content_body.setMaximumHeight(16777215)
    else:
        content_body.setMaximumHeight(content_layout.sizeHint().height())
    bind_field_widget_card_relayout(
        field_widget=field_widget,
        content_body=content_body,
        content_layout=content_layout,
        allow_unbounded_height=allow_unbounded_height,
    )
    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(content_body)
    host.show()
    return host, row, field_widget


def test_field_widget_relayout_updates_collapsible_card_body_height() -> None:
    """Collapsible card bodies should grow when one field widget grows later."""

    ensure_qapp()
    host, row, field_widget = build_card_body(allow_unbounded_height=False)
    try:
        wait_for_queued_qt_turn()
        initial_row_hint = row.sizeHint().height()
        content_body = row.parentWidget()
        assert content_body is not None

        field_widget.set_test_height(180)
        wait_for_qt_condition(
            lambda: content_body.maximumHeight() >= row.sizeHint().height()
        )

        assert row.sizeHint().height() > initial_row_hint
        assert content_body.maximumHeight() >= row.sizeHint().height()
    finally:
        _close_and_delete(host)


def test_field_widget_relayout_keeps_exempt_card_body_unbounded() -> None:
    """Exempt card bodies should stay unbounded after one field widget grows."""

    ensure_qapp()
    host, row, field_widget = build_card_body(allow_unbounded_height=True)
    try:
        wait_for_queued_qt_turn()
        content_body = row.parentWidget()
        assert content_body is not None

        field_widget.set_test_height(220)
        wait_for_queued_qt_turn()

        assert content_body.maximumHeight() == 16777215
    finally:
        _close_and_delete(host)


def test_field_widget_relayout_preserves_collapsed_card_body_height() -> None:
    """Collapsed card bodies should stay closed while relayout caches new expanded height."""

    ensure_qapp()
    host, row, field_widget = build_card_body(allow_unbounded_height=False)
    try:
        wait_for_queued_qt_turn()
        content_body = row.parentWidget()
        assert content_body is not None
        state = ensure_card_body_layout_state(
            content_body=content_body,
            expanded_height=content_body.maximumHeight(),
        )
        state.collapsed = True
        apply_card_body_layout_state(
            content_body=content_body,
            state=state,
            allow_unbounded_height=False,
        )

        field_widget.set_test_height(180)
        relayout_filter = getattr(field_widget, "_card_field_relayout_filter")
        relayout_filter.schedule_relayout()
        wait_for_qt_condition(lambda: state.expanded_height >= row.sizeHint().height())

        assert content_body.maximumHeight() == 0
        assert content_body.isHidden()
        assert state.expanded_height >= row.sizeHint().height()
    finally:
        _close_and_delete(host)


def test_field_widget_relayout_notifies_nearest_section_owner() -> None:
    """Dynamic field relayout should report through the owning cube section."""

    ensure_qapp()
    section = _SectionOwner()
    content_body = QWidget(section)
    content_layout = QVBoxLayout(content_body)
    content_layout.setContentsMargins(0, 0, 0, 0)
    row = QWidget(content_body)
    row_layout = QVBoxLayout(row)
    row_layout.setContentsMargins(10, 0, 10, 8)
    field_widget = _DynamicHeightWidget()
    row_layout.addWidget(field_widget)
    content_layout.addWidget(row)
    section_layout = QVBoxLayout(section)
    section_layout.addWidget(content_body)
    bind_field_widget_card_relayout(
        field_widget=field_widget,
        content_body=content_body,
        content_layout=content_layout,
        allow_unbounded_height=False,
    )
    try:
        section.show()
        wait_for_queued_qt_turn()
        section.finalize_reasons.clear()

        field_widget.set_test_height(180)
        wait_for_qt_condition(
            lambda: (
                section.finalize_reasons == ["field_relayout"]
                and content_body.maximumHeight() >= row.sizeHint().height()
            )
        )

        assert section.finalize_reasons == ["field_relayout"]
        assert content_body.maximumHeight() >= row.sizeHint().height()
    finally:
        _close_and_delete(section)


def test_field_widget_layout_request_with_unchanged_geometry_is_no_op() -> None:
    """Settled LayoutRequest events should not feed the field relayout loop."""

    ensure_qapp()
    section = _SectionOwner()
    content_body = QWidget(section)
    content_layout = QVBoxLayout(content_body)
    content_layout.setContentsMargins(0, 0, 0, 0)
    row = QWidget(content_body)
    row_layout = QVBoxLayout(row)
    row_layout.setContentsMargins(10, 0, 10, 8)
    field_widget = _DynamicHeightWidget()
    row_layout.addWidget(field_widget)
    content_layout.addWidget(row)
    section_layout = QVBoxLayout(section)
    section_layout.addWidget(content_body)
    bind_field_widget_card_relayout(
        field_widget=field_widget,
        content_body=content_body,
        content_layout=content_layout,
        allow_unbounded_height=False,
    )
    try:
        section.show()
        wait_for_queued_qt_turn()
        section.finalize_reasons.clear()
        relayout_filter = getattr(field_widget, "_card_field_relayout_filter")

        QApplication.sendEvent(field_widget, QEvent(QEvent.Type.LayoutRequest))
        assert getattr(relayout_filter, "_update_pending") is False
        wait_for_queued_qt_turn()

        assert section.finalize_reasons == []
    finally:
        _close_and_delete(section)


def test_field_widget_resize_signal_with_unchanged_geometry_is_no_op() -> None:
    """Explicit widget resize signals should skip when geometry is already synced."""

    ensure_qapp()
    section = _SectionOwner()
    content_body = QWidget(section)
    content_layout = QVBoxLayout(content_body)
    content_layout.setContentsMargins(0, 0, 0, 0)
    row = QWidget(content_body)
    row_layout = QVBoxLayout(row)
    row_layout.setContentsMargins(10, 0, 10, 8)
    field_widget = _SignalHeightWidget()
    row_layout.addWidget(field_widget)
    content_layout.addWidget(row)
    section_layout = QVBoxLayout(section)
    section_layout.addWidget(content_body)
    bind_field_widget_card_relayout(
        field_widget=field_widget,
        content_body=content_body,
        content_layout=content_layout,
        allow_unbounded_height=False,
    )
    try:
        section.show()
        wait_for_queued_qt_turn()
        section.finalize_reasons.clear()

        field_widget.resized.emit()
        wait_for_queued_qt_turn()

        assert section.finalize_reasons == []
        assert content_body.maximumHeight() >= row.sizeHint().height()
    finally:
        _close_and_delete(section)


def test_field_widget_resize_signal_notifies_when_widget_geometry_changed() -> None:
    """Explicit widget resize signals should resync after a real height change."""

    ensure_qapp()
    section = _SectionOwner()
    content_body = QWidget(section)
    content_layout = QVBoxLayout(content_body)
    content_layout.setContentsMargins(0, 0, 0, 0)
    row = QWidget(content_body)
    row_layout = QVBoxLayout(row)
    row_layout.setContentsMargins(10, 0, 10, 8)
    field_widget = _SignalHeightWidget()
    row_layout.addWidget(field_widget)
    content_layout.addWidget(row)
    section_layout = QVBoxLayout(section)
    section_layout.addWidget(content_body)
    bind_field_widget_card_relayout(
        field_widget=field_widget,
        content_body=content_body,
        content_layout=content_layout,
        allow_unbounded_height=False,
    )
    try:
        section.show()
        wait_for_queued_qt_turn()
        section.finalize_reasons.clear()

        field_widget.set_test_height(180)
        field_widget.resized.emit()
        wait_for_qt_condition(
            lambda: (
                section.finalize_reasons == ["field_relayout"]
                and content_body.maximumHeight() >= row.sizeHint().height()
            )
        )

        assert section.finalize_reasons == ["field_relayout"]
        assert content_body.maximumHeight() >= row.sizeHint().height()
    finally:
        _close_and_delete(section)


def test_unbounded_field_resize_signal_notifies_when_widget_geometry_changed() -> None:
    """Unbounded prompt-style cards should still notify on real field resize."""

    ensure_qapp()
    section = _SectionOwner()
    content_body = QWidget(section)
    content_layout = QVBoxLayout(content_body)
    content_layout.setContentsMargins(0, 0, 0, 0)
    row = QWidget(content_body)
    row_layout = QVBoxLayout(row)
    row_layout.setContentsMargins(10, 0, 10, 8)
    field_widget = _SignalHeightWidget()
    row_layout.addWidget(field_widget)
    content_layout.addWidget(row)
    section_layout = QVBoxLayout(section)
    section_layout.addWidget(content_body)
    bind_field_widget_card_relayout(
        field_widget=field_widget,
        content_body=content_body,
        content_layout=content_layout,
        allow_unbounded_height=True,
    )
    try:
        section.show()
        wait_for_queued_qt_turn()
        section.finalize_reasons.clear()

        field_widget.set_test_height(180)
        field_widget.resized.emit()
        wait_for_qt_condition(
            lambda: (
                section.finalize_reasons == ["field_relayout"]
                and content_body.maximumHeight() == 16777215
            )
        )

        assert section.finalize_reasons == ["field_relayout"]
        assert content_body.maximumHeight() == 16777215
    finally:
        _close_and_delete(section)


def test_prompt_field_relayout_noops_unchanged_geometry() -> None:
    """Explicit relayout requests should not notify owners when geometry is stable."""

    ensure_qapp()
    section = _SectionOwner()
    content_body = QWidget(section)
    content_layout = QVBoxLayout(content_body)
    content_layout.setContentsMargins(0, 0, 0, 0)
    row = QWidget(content_body)
    row_layout = QVBoxLayout(row)
    row_layout.setContentsMargins(10, 0, 10, 8)
    field_widget = _DynamicHeightWidget()
    row_layout.addWidget(field_widget)
    content_layout.addWidget(row)
    section_layout = QVBoxLayout(section)
    section_layout.addWidget(content_body)
    bind_field_widget_card_relayout(
        field_widget=field_widget,
        content_body=content_body,
        content_layout=content_layout,
        allow_unbounded_height=False,
    )
    try:
        section.show()
        wait_for_queued_qt_turn()
        section.finalize_reasons.clear()
        initial_maximum_height = content_body.maximumHeight()
        relayout_filter = getattr(field_widget, "_card_field_relayout_filter")

        relayout_filter.schedule_relayout()
        wait_for_queued_qt_turn()

        assert section.finalize_reasons == []
        assert content_body.maximumHeight() == initial_maximum_height
    finally:
        _close_and_delete(section)


def test_standard_node_card_stays_collapsed_after_deferred_relayout() -> None:
    """Standard node cards should remain collapsed after deferred field relayout settles."""

    ensure_qapp()
    panel = _Panel()
    definitions = {
        "String": {
            "input": {
                "required": {
                    "value": ["STRING", {}],
                }
            }
        }
    }
    cube = cube_state(
        nodes={
            "encode_style": {
                "class_type": "String",
                "inputs": {"value": "STYLE(comfy++) "},
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
    resolved = snapshot.resolved_nodes_by_alias["A"]["encode_style"]
    builder = build_node_card_builder(
        panel,
        _Gateway(),
    )

    wrapper = builder.build_node_card(
        node_name="encode_style",
        inputs={"value": "STYLE(comfy++) "},
        node_type="String",
        field_specs=snapshot.field_specs_by_alias["A"]["encode_style"],
        cube_state=cube,
        resolved_behavior=resolved,
        alias="A",
    )

    assert wrapper is not None
    host = QWidget()
    try:
        layout = QVBoxLayout(host)
        layout.addWidget(wrapper)
        host.show()
        wait_for_queued_qt_turn()

        node_card = wrapper.layout().itemAt(0).widget()
        assert node_card is not None
        title_row = node_card.layout().itemAt(0).widget()
        content_body = node_card.layout().itemAt(1).widget()
        assert title_row is not None
        assert content_body is not None
        assert content_body.maximumHeight() > 0

        QTest.mouseClick(title_row, Qt.MouseButton.LeftButton)
        wait_for_qt_condition(lambda: content_body.maximumHeight() == 0)

        assert content_body.maximumHeight() == 0

        QTest.mouseClick(title_row, Qt.MouseButton.LeftButton)
        wait_for_qt_condition(lambda: content_body.maximumHeight() > 0)

        assert content_body.maximumHeight() > 0
    finally:
        _close_and_delete(host)
        _close_and_delete(panel)
