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

"""Contract tests for Fluent accordion motion behavior."""

from __future__ import annotations

from collections.abc import Callable, Iterator
import time
from typing import cast

import pytest
from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from substitute.presentation.editor.panel.node_card.accordion_motion import (
    AccordionChevronWidget,
    AccordionContentClip,
    AccordionMotionController,
    _paint_rotated_icon,
)
from substitute.presentation.editor.panel.node_card.body_layout import (
    ensure_card_body_layout_state,
)
from substitute.presentation.motion import (
    ACCORDION_COLLAPSE_DURATION_MS,
    ACCORDION_EXPAND_DURATION_MS,
)
from substitute.presentation.motion import fluent_motion

_REDUCED_MOTION_PROPERTY = "substitute.reduce_motion"


@pytest.fixture(autouse=True)
def normal_motion_for_accordion_tests() -> Iterator[None]:
    """Run accordion motion contracts with animations enabled by default."""

    app = ensure_qapp()
    previous_override = app.property(_REDUCED_MOTION_PROPERTY)
    app.setProperty(_REDUCED_MOTION_PROPERTY, False)
    try:
        yield
    finally:
        app.setProperty(_REDUCED_MOTION_PROPERTY, previous_override)


def test_accordion_motion_uses_winui_settings_durations() -> None:
    """Accordion motion tokens should match WinUI SettingsExpander timings."""

    assert ACCORDION_EXPAND_DURATION_MS == 333
    assert ACCORDION_COLLAPSE_DURATION_MS == 167


def test_offscreen_motion_ignores_host_animation_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Offscreen geometry tests should not inherit host reduced-motion state."""

    app = ensure_qapp()
    app.setProperty(_REDUCED_MOTION_PROPERTY, None)
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(
        fluent_motion,
        "_read_windows_client_area_animation_enabled",
        lambda: False,
    )

    assert fluent_motion.is_reduced_motion_enabled() is False


def test_node_card_chevron_paints_inside_logical_rect_at_fractional_dpr() -> None:
    """Node-card chevrons should not center physical pixmap sizes as logical pixels."""

    ensure_qapp()
    logical_size = 14
    device_pixel_ratio = 1.5
    image_size = int(logical_size * device_pixel_ratio)
    image = QImage(
        image_size,
        image_size,
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.setDevicePixelRatio(device_pixel_ratio)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    try:
        _paint_rotated_icon(
            painter,
            FIF.ARROW_DOWN,
            QRectF(0.0, 0.0, float(logical_size), float(logical_size)),
            180.0,
        )
    finally:
        painter.end()

    painted_pixels = [
        (x, y)
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).alpha() > 0
    ]

    assert painted_pixels
    assert min(x for x, _ in painted_pixels) > 0
    assert min(y for _, y in painted_pixels) > 0
    assert max(x for x, _ in painted_pixels) < image.width() - 1
    assert max(y for _, y in painted_pixels) < image.height() - 1


class _CubeHost(QWidget):
    """Provide a small host that records height refresh requests."""

    def __init__(self) -> None:
        """Initialize the refresh counter used by motion callbacks."""

        super().__init__()
        self.update_calls = 0

    def update_cube_height(self) -> None:
        """Record one cube-height refresh request."""

        self.update_calls += 1


def ensure_qapp() -> QApplication:
    """Return a running Qt application for motion tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def process_events(app: QApplication, cycles: int = 5) -> None:
    """Flush a few event-loop cycles so deferred Qt work settles."""

    for _ in range(cycles):
        app.processEvents()


def wait_for_motion_state(
    app: QApplication,
    predicate: Callable[[], bool],
    *,
    timeout_seconds: float = 5.0,
) -> None:
    """Process Qt events until motion reaches a deterministic final state."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        QTest.qWait(10)
    raise AssertionError("Timed out waiting for accordion motion to settle.")


def expected_visible_item_height(layout: QVBoxLayout, *widgets: QWidget) -> int:
    """Return layout height from visible widgets, margins, and inter-item spacing."""

    margins = layout.contentsMargins()
    visible_widgets = [widget for widget in widgets if not widget.isHidden()]
    spacing = layout.spacing() * max(0, len(visible_widgets) - 1)
    return (
        margins.top()
        + sum(expected_widget_height(widget) for widget in visible_widgets)
        + spacing
        + margins.bottom()
    )


def expected_widget_height(widget: QWidget) -> int:
    """Return the height Qt layout constraints contribute for one visible widget."""

    return max(widget.sizeHint().height(), widget.minimumHeight(), widget.height())


def title_geometry_for(content_body: QWidget) -> QRect:
    """Return the title-row geometry adjacent to one fixture body."""

    parent = content_body.parentWidget()
    assert parent is not None
    layout = parent.layout()
    assert isinstance(layout, QVBoxLayout)
    title_item = layout.itemAt(0)
    assert title_item is not None
    title = title_item.widget()
    assert title is not None
    return QRect(title.geometry())


def build_motion_fixture() -> tuple[
    QApplication,
    _CubeHost,
    QWidget,
    AccordionContentClip,
    AccordionChevronWidget,
]:
    """Build a minimal accordion surface for focused controller tests."""

    app = ensure_qapp()
    host = _CubeHost()
    layout = QVBoxLayout(host)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    title = QWidget(host)
    title.setFixedHeight(20)
    divider = QWidget(host)
    content_body = AccordionContentClip(host)
    content_layout = QVBoxLayout(content_body.content_widget())
    content_layout.setContentsMargins(0, 0, 0, 0)
    filler = QWidget(content_body.content_widget())
    filler.setFixedHeight(140)
    content_layout.addWidget(filler)
    chevron = AccordionChevronWidget(title)
    title_layout = QVBoxLayout(title)
    title_layout.setContentsMargins(0, 0, 0, 0)
    title_layout.addWidget(chevron)

    layout.addWidget(title)
    layout.addWidget(divider)
    layout.addWidget(content_body)

    controller = AccordionMotionController(
        owner=host,
        card_title=title,
        content_body=content_body,
        content_layout=content_layout,
        divider_below_title=divider,
        chevron=chevron,
        cube_height_updater=host.update_cube_height,
    )
    setattr(content_body, "_accordion_motion_controller", controller)
    host.show()
    process_events(app)
    return app, host, divider, content_body, chevron


def test_accordion_motion_reaches_expected_final_states() -> None:
    """Accordion motion should settle to the expected collapse and expand states."""

    app, host, divider, content_body, chevron = build_motion_fixture()
    try:
        controller = getattr(content_body, "_accordion_motion_controller")
        state = ensure_card_body_layout_state(
            content_body=content_body,
            expanded_height=content_body.maximumHeight(),
        )

        controller.toggle()
        wait_for_motion_state(app, lambda: not state.animating)

        assert state.collapsed is True
        assert state.animating is False
        assert content_body.maximumHeight() == 0
        assert content_body.isHidden() is True
        assert controller.content_offset_y() == -state.expanded_height
        assert divider.isVisible() is False
        assert chevron.rotation_value() == 0.0

        controller.toggle()
        wait_for_motion_state(app, lambda: not state.animating)

        assert state.collapsed is False
        assert state.animating is False
        assert content_body.isHidden() is False
        assert content_body.maximumHeight() == state.expanded_height
        assert controller.content_offset_y() == 0
        assert divider.isVisible() is True
        assert chevron.rotation_value() == 180.0
        assert host.update_calls > 0
    finally:
        host.close()
        host.deleteLater()
        process_events(app)


def test_accordion_motion_replaces_in_flight_transition_safely() -> None:
    """Rapid retoggles should settle to the last requested accordion state."""

    app, host, _divider, content_body, _chevron = build_motion_fixture()
    try:
        controller = getattr(content_body, "_accordion_motion_controller")
        state = ensure_card_body_layout_state(
            content_body=content_body,
            expanded_height=content_body.maximumHeight(),
        )

        controller.toggle()
        QTest.qWait(40)
        controller.toggle()
        wait_for_motion_state(app, lambda: not state.animating)

        assert state.collapsed is False
        assert state.animating is False
        assert content_body.maximumHeight() == state.expanded_height
        assert controller.content_offset_y() == 0
    finally:
        host.close()
        host.deleteLater()
        process_events(app)


def test_accordion_motion_does_not_reflow_owner_on_each_animation_frame() -> None:
    """Accordion motion should not ask masonry parents to repack every frame."""

    app, host, _divider, content_body, _chevron = build_motion_fixture()
    try:
        controller = getattr(content_body, "_accordion_motion_controller")
        expanded_height = content_body.maximumHeight()
        state = ensure_card_body_layout_state(
            content_body=content_body,
            expanded_height=expanded_height,
        )
        title_geometry = title_geometry_for(content_body)
        host.update_calls = 0

        controller.toggle()
        QTest.qWait(40)
        process_events(app)

        assert host.update_calls == 1
        assert content_body.maximumHeight() == expanded_height
        assert controller.is_body_clip_visible() is True
        assert -expanded_height < controller.content_offset_y() < 0
        assert title_geometry_for(content_body) == title_geometry

        wait_for_motion_state(app, lambda: not state.animating)

        assert host.update_calls == 2
        assert content_body.maximumHeight() == 0
        assert controller.is_body_clip_visible() is False
    finally:
        host.close()
        host.deleteLater()
        process_events(app)


def test_accordion_motion_does_not_install_body_opacity_fade() -> None:
    """Accordion body motion should use clipped translation instead of fading."""

    app, host, _divider, content_body, _chevron = build_motion_fixture()
    try:
        controller = getattr(content_body, "_accordion_motion_controller")

        controller.toggle()
        QTest.qWait(40)
        process_events(app)

        effect = content_body.graphicsEffect()
        assert not isinstance(effect, QGraphicsOpacityEffect)
    finally:
        host.close()
        host.deleteLater()
        process_events(app)


def test_accordion_motion_respects_reduced_motion_override() -> None:
    """Reduced-motion mode should skip the animated wait while preserving final state."""

    app = ensure_qapp()
    previous_override = app.property(_REDUCED_MOTION_PROPERTY)
    app.setProperty(_REDUCED_MOTION_PROPERTY, True)
    fixture = build_motion_fixture()
    _, host, divider, content_body, chevron = fixture
    try:
        controller = getattr(content_body, "_accordion_motion_controller")
        state = ensure_card_body_layout_state(
            content_body=content_body,
            expanded_height=content_body.maximumHeight(),
        )

        controller.toggle()
        process_events(app)

        assert state.collapsed is True
        assert state.animating is False
        assert content_body.maximumHeight() == 0
        assert content_body.isHidden() is True
        assert controller.content_offset_y() == -state.expanded_height
        assert divider.isVisible() is False
        assert chevron.rotation_value() == 0.0
    finally:
        host.close()
        host.deleteLater()
        app.setProperty(_REDUCED_MOTION_PROPERTY, previous_override)
        process_events(app)


def test_accordion_collapsed_body_does_not_reserve_parent_layout_spacing() -> None:
    """Collapsed card bodies should be absent from parent-layout sizing at rest."""

    app = ensure_qapp()
    host = _CubeHost()
    host_layout = QVBoxLayout(host)
    card = QWidget(host)
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(0, 10, 0, 10)
    card_layout.setSpacing(12)
    title = QWidget(card)
    title.setFixedHeight(20)
    content_body = AccordionContentClip(card)
    content_layout = QVBoxLayout(content_body.content_widget())
    content_layout.setContentsMargins(0, 0, 0, 0)
    filler = QWidget(content_body.content_widget())
    filler.setFixedHeight(140)
    content_layout.addWidget(filler)
    chevron = AccordionChevronWidget(title)
    card_layout.addWidget(title)
    card_layout.addWidget(content_body)
    host_layout.addWidget(card)
    controller = AccordionMotionController(
        owner=host,
        card_title=title,
        content_body=content_body,
        content_layout=content_layout,
        divider_below_title=None,
        chevron=chevron,
        cube_height_updater=host.update_cube_height,
    )
    state = ensure_card_body_layout_state(
        content_body=content_body,
        expanded_height=content_body.maximumHeight(),
    )
    host.show()
    process_events(app)
    try:
        controller.toggle()
        wait_for_motion_state(app, lambda: not state.animating)

        body_item = card_layout.itemAt(1)
        assert content_body.maximumHeight() == 0
        assert content_body.isHidden() is True
        assert body_item is not None
        assert body_item.isEmpty() is True
        assert card.sizeHint().height() == expected_visible_item_height(
            card_layout,
            title,
            content_body,
        )

        controller.toggle()
        wait_for_motion_state(app, lambda: not state.animating)

        assert content_body.isHidden() is False
        assert body_item.isEmpty() is False
        assert card.sizeHint().height() == expected_visible_item_height(
            card_layout,
            title,
            content_body,
        )
    finally:
        host.close()
        host.deleteLater()
        process_events(app)
