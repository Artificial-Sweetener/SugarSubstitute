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

"""Render and abuse the compact canvas tool-strip projection."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QContextMenuEvent, QEnterEvent, QIcon
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    MenuAnimationType,
    TransparentToolButton,
)

from sugarsubstitute_shared.localization import app_text
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel
from substitute.presentation.canvas.tools.layout import (
    CanvasToolGroupSlot,
    CanvasToolLayout,
    CanvasToolLayoutSnapshot,
)
from substitute.presentation.canvas.tools.model import (
    CanvasToolContext,
    CanvasToolContribution,
    CanvasToolKind,
)
from substitute.presentation.canvas.tools.palette import CanvasToolPalette
from substitute.presentation.canvas.tools.registry import CanvasToolRegistry
from substitute.presentation.canvas.tools.tool_strip import (
    CANVAS_TOOL_BUTTON_SIZE,
    CanvasToolStrip,
)


def _app() -> QApplication:
    """Return a QApplication for offscreen widget verification."""

    instance = QCoreApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def _tool(
    tool_id: str,
    order: int,
    *,
    section: str = "main",
    kind: CanvasToolKind = CanvasToolKind.MODE,
) -> CanvasToolContribution:
    """Return one visible enabled contribution."""

    return CanvasToolContribution(
        tool_id=tool_id,
        label=app_text(tool_id),
        icon=QIcon(),
        kind=kind,
        section=section,
        order=order,
        required_context_tags=frozenset({"canvas"}),
    )


def _palette(
    *tools: CanvasToolContribution,
) -> tuple[CanvasToolRegistry, CanvasToolPalette]:
    """Return a registry and enabled canvas palette."""

    registry = CanvasToolRegistry()
    registry.register_many(tools)
    palette = CanvasToolPalette(registry)
    palette.set_context(CanvasToolContext(tags=frozenset({"canvas"})))
    return registry, palette


def test_tool_strip_occupies_only_its_content_over_a_full_canvas() -> None:
    """Pixels below the compact strip should retain the canvas's full width."""

    app = _app()
    host = QWidget()
    host.setGeometry(QRect(0, 0, 640, 480))
    canvas = QWidget(host)
    canvas.setGeometry(host.rect())
    _registry, palette = _palette(
        _tool("move", 10),
        _tool("brush", 20),
        _tool("pan", 30, section="navigation"),
    )
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(palette)
    strip.move(6, 6)
    app.processEvents()

    assert canvas.geometry() == host.rect()
    assert strip.width() < canvas.width()
    assert strip.height() < canvas.height()
    assert strip.geometry().bottom() < canvas.geometry().bottom()
    assert canvas.childAt(2, strip.geometry().bottom() + 10) is not strip
    assert all(
        button.width() == button.height() == CANVAS_TOOL_BUTTON_SIZE
        for button in strip.tool_buttons()
    )


def test_disabled_tool_uses_contextual_denial_as_its_tooltip() -> None:
    """Unavailable controls must explain the owning missing capability."""
    app = _app()
    canvas = QWidget()
    tool = CanvasToolContribution(
        tool_id="transform",
        label=app_text("Transform"),
        icon=QIcon(),
        kind=CanvasToolKind.MODE,
        section="main",
        order=10,
        required_context_tags=frozenset({"canvas"}),
        required_capabilities=frozenset({"content"}),
    )
    registry = CanvasToolRegistry()
    registry.register(tool)
    palette = CanvasToolPalette(registry)
    palette.set_context(
        CanvasToolContext(
            tags=frozenset({"canvas"}),
            capability_denials=(("content", app_text("Nothing to transform!")),),
        )
    )
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(palette)
    app.processEvents()

    button = strip.tool_buttons()[0]
    assert not button.isEnabled()
    assert button.toolTip() == "Nothing to transform!"


def test_tool_strip_centers_buttons_without_reserving_indicator_width() -> None:
    """The overlay marker must not shift button or icon geometry to the right."""

    app = _app()
    canvas = QWidget()
    _registry, palette = _palette(_tool("move", 10), _tool("brush", 20))
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(palette)
    canvas.show()
    app.processEvents()

    strip_center_x = strip.rect().center().x()
    for button in strip.tool_buttons():
        assert button.geometry().center().x() == strip_center_x
        assert button.iconSize().width() == button.iconSize().height() == 20
        assert (button.width() - button.iconSize().width()) // 2 == 7

    assert strip.indicator.geometry() == strip.rect()


def test_tool_strip_uses_one_even_gap_across_contribution_sections() -> None:
    """Semantic tool sections must not create uneven visual spacing."""

    app = _app()
    canvas = QWidget()
    _registry, palette = _palette(
        _tool("move", 10),
        _tool("brush", 20, section="paint"),
        _tool("pan", 30, section="navigation"),
    )
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(palette)
    canvas.show()
    app.processEvents()
    buttons = strip.tool_buttons()

    gaps = tuple(
        following.y() - preceding.geometry().bottom() - 1
        for preceding, following in zip(buttons[:-1], buttons[1:], strict=True)
    )

    assert gaps == (2, 2)


def test_tool_strip_projects_active_mode_with_one_sliding_indicator() -> None:
    """The selected mode should use cube-stack indicator language without checks."""

    app = _app()
    canvas = QWidget()
    _registry, palette = _palette(_tool("move", 10), _tool("brush", 20))
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(palette)
    canvas.show()
    app.processEvents()

    assert palette.set_active_tool("move") is True
    move_target = strip.indicator.target_y
    animation_spy = QSignalSpy(strip.indicator.animation.finished)
    assert palette.set_active_tool("brush") is True
    move = strip.button_for("move")
    brush = strip.button_for("brush")

    assert move is not None and brush is not None
    assert move.text() == brush.text() == ""
    assert move.isCheckable() is False
    assert brush.isCheckable() is False
    assert strip.indicator.isVisible()
    assert strip.indicator.target_y != move_target
    assert strip.indicator.target_y == brush.y() + brush.height() // 2 - 8
    assert strip.indicator.animation.state().name == "Running"
    strip.indicator.animation.setCurrentTime(strip.indicator.motion.extend_duration_ms)
    assert strip.indicator.indicator_height > 16
    assert strip.indicator.indicator_y == move_target
    assert animation_spy.wait(1_000)
    assert strip.indicator.indicator_y == strip.indicator.target_y
    assert strip.indicator.indicator_height == 16


def test_tool_strip_redirects_mid_animation_from_the_visible_marker() -> None:
    """Rapid tool changes must redirect the stretched marker without a jump."""

    app = _app()
    canvas = QWidget()
    _registry, palette = _palette(
        _tool("move", 10),
        _tool("brush", 20),
        _tool("pan", 30),
    )
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(palette)
    canvas.show()
    app.processEvents()
    assert palette.set_active_tool("move")
    assert palette.set_active_tool("pan")
    strip.indicator.animation.setCurrentTime(
        strip.indicator.motion.extend_duration_ms // 2
    )
    visible_frame = (
        strip.indicator.indicator_y,
        strip.indicator.indicator_height,
    )

    assert palette.set_active_tool("brush")

    assert strip.indicator.animation.state().name == "Running"
    assert (
        strip.indicator.indicator_y,
        strip.indicator.indicator_height,
    ) == visible_frame
    animation_spy = QSignalSpy(strip.indicator.animation.finished)
    assert animation_spy.wait(1_000)
    assert strip.indicator.indicator_y == strip.indicator.target_y
    assert strip.indicator.indicator_height == 16


def test_tool_strip_respects_reduced_motion_policy() -> None:
    """Reduced motion should project the selected marker without a transition."""

    app = _app()
    app.setProperty("substitute.reduce_motion", True)
    try:
        canvas = QWidget()
        _registry, palette = _palette(_tool("move", 10), _tool("brush", 20))
        strip = CanvasToolStrip(canvas)
        strip.bind_palette(palette)
        canvas.show()
        app.processEvents()
        assert palette.set_active_tool("move")

        assert palette.set_active_tool("brush")

        assert strip.indicator.animation.state().name == "Stopped"
        assert strip.indicator.indicator_y == strip.indicator.target_y
        assert strip.indicator.indicator_height == 16
    finally:
        app.setProperty("substitute.reduce_motion", None)


def test_tool_click_does_not_cancel_its_own_selection_animation() -> None:
    """Authoritative click projection must leave the zippy transition running."""

    app = _app()
    canvas = QWidget()
    _registry, palette = _palette(_tool("move", 10), _tool("brush", 20))
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(palette)
    strip.toolRequested.connect(palette.set_active_tool)
    canvas.show()
    app.processEvents()
    assert palette.set_active_tool("move")
    brush = strip.button_for("brush")
    assert brush is not None

    QTest.mouseClick(brush, Qt.MouseButton.LeftButton)

    assert palette.active_tool_id == "brush"
    assert strip.indicator.animation.state().name == "Running"
    assert strip.indicator.indicator_y != strip.indicator.target_y


def test_tool_strip_realigns_preselected_indicator_after_first_show() -> None:
    """A mode selected while hidden should align after Qt lays out the strip."""

    app = _app()
    canvas = QWidget()
    _registry, palette = _palette(_tool("move", 10), _tool("brush", 20))
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(palette)
    assert palette.set_active_tool("brush")
    brush = strip.button_for("brush")
    assert brush is not None

    canvas.show()
    app.processEvents()

    assert strip.indicator.target_y == brush.y() + brush.height() // 2 - 8
    assert strip.indicator.indicator_y == strip.indicator.target_y


def test_tool_strip_buttons_use_qfluent_transparent_hover_feedback() -> None:
    """Each icon button should retain qfluent's transparent hover interaction."""

    app = _app()
    canvas = QWidget()
    canvas.resize(200, 200)
    _registry, palette = _palette(_tool("move", 10))
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(palette)
    canvas.show()
    app.processEvents()
    button = strip.button_for("move")
    assert button is not None
    assert isinstance(button, TransparentToolButton)

    app.sendEvent(button, QEvent(QEvent.Type.Leave))
    app.processEvents()
    resting_surface = button.grab().toImage().pixelColor(QPoint(2, 2))
    app.sendEvent(
        button,
        QEnterEvent(QPointF(2, 2), QPointF(2, 2), QPointF(2, 2)),
    )
    app.processEvents()
    hover_surface = button.grab().toImage().pixelColor(QPoint(2, 2))

    assert button.isHover is True
    assert hover_surface != resting_surface


def test_tool_strip_forces_the_standard_pointer_over_canvas_tool_cursors() -> None:
    """Canvas editing cursors must not leak over strip margins or buttons."""

    _app()
    canvas = QWidget()
    canvas.setCursor(Qt.CursorShape.CrossCursor)
    _registry, palette = _palette(_tool("move", 10), _tool("brush", 20))
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(palette)

    assert strip.cursor().shape() is Qt.CursorShape.ArrowCursor
    assert all(
        button.cursor().shape() is Qt.CursorShape.ArrowCursor
        for button in strip.tool_buttons()
    )


def test_tool_strip_buttons_do_not_steal_modifier_focus_from_the_canvas() -> None:
    """Selecting a tool must preserve the canvas's active modifier key lifetime."""

    app = _app()
    canvas = QWidget()
    canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    _registry, palette = _palette(_tool("move", 10), _tool("brush", 20))
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(palette)
    canvas.show()
    canvas.setFocus()
    app.processEvents()
    brush = strip.button_for("brush")
    assert brush is not None

    QTest.mouseClick(brush, Qt.MouseButton.LeftButton)
    app.processEvents()

    assert brush.focusPolicy() is Qt.FocusPolicy.NoFocus
    assert app.focusWidget() is canvas


def test_tool_strip_emits_mode_and_action_intents_without_owning_state() -> None:
    """Clicks should emit stable IDs while the palette remains authoritative."""

    _app()
    canvas = QWidget()
    _registry, palette = _palette(
        _tool("move", 10),
        _tool("workflow", 20, kind=CanvasToolKind.ACTION),
    )
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(palette)
    requested: list[str] = []
    strip.toolRequested.connect(requested.append)

    move = strip.button_for("move")
    workflow = strip.button_for("workflow")
    assert move is not None and workflow is not None
    move.click()
    workflow.click()

    assert requested == ["move", "workflow"]
    assert palette.active_tool_id is None
    assert workflow.isCheckable() is False


def test_tool_strip_tracks_runtime_add_remove_and_rapid_replacement() -> None:
    """Runtime palette churn must not leave stale or duplicate buttons."""

    app = _app()
    canvas = QWidget()
    registry, palette = _palette(_tool("stable", 10))
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(palette)

    for index in range(75):
        tool_id = f"runtime-{index}"
        registry.register(_tool(tool_id, 100 + index))
        assert strip.button_for(tool_id) is not None
        assert registry.unregister(tool_id) is True
        app.processEvents()
        assert strip.button_for(tool_id) is None

    assert tuple(button.tool_id for button in strip.tool_buttons()) == ("stable",)


def test_tool_strip_defers_self_removing_action_until_click_returns() -> None:
    """A runtime action may remove itself without deleting its emitting button."""

    app = _app()
    canvas = QWidget()
    registry, palette = _palette(
        _tool("stable", 10),
        _tool("self-remove", 20, kind=CanvasToolKind.ACTION),
    )
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(palette)
    action = strip.button_for("self-remove")
    assert action is not None
    observed_during_dispatch: list[bool] = []

    def remove_requested_tool(tool_id: str) -> None:
        """Remove the action and record whether its button survived dispatch."""

        assert tool_id == "self-remove"
        assert registry.unregister(tool_id)
        observed_during_dispatch.append(strip.button_for(tool_id) is action)

    strip.toolRequested.connect(remove_requested_tool)

    action.click()

    assert observed_during_dispatch == [True]
    assert strip.button_for("self-remove") is action
    app.processEvents()
    assert strip.button_for("self-remove") is None
    assert tuple(button.tool_id for button in strip.tool_buttons()) == ("stable",)


def test_tool_strip_reasserts_z_order_when_active_tool_changes() -> None:
    """A canvas sibling raised later must not cover refreshed tool chrome."""

    app = _app()
    canvas = QWidget()
    canvas.resize(200, 200)
    _registry, palette = _palette(_tool("move", 10), _tool("brush", 20))
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(palette)
    canvas.show()
    app.processEvents()
    cover = QWidget(canvas)
    cover.setGeometry(strip.geometry())
    cover.show()
    cover.raise_()
    assert canvas.childAt(strip.geometry().center()) is cover

    assert palette.set_active_tool("brush")
    app.processEvents()
    top_child = canvas.childAt(strip.geometry().center())

    assert top_child is not None
    assert top_child is strip or strip.isAncestorOf(top_child)


def test_tool_strip_rebind_releases_the_previous_palette_subscription() -> None:
    """A moved strip should ignore mutations from its former palette."""

    _app()
    canvas = QWidget()
    first_registry, first_palette = _palette(_tool("first", 10))
    second_registry, second_palette = _palette(_tool("second", 10))
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(first_palette)
    strip.bind_palette(second_palette)

    first_registry.register(_tool("stale", 20))
    second_registry.register(_tool("current", 20))

    assert strip.button_for("stale") is None
    assert tuple(button.tool_id for button in strip.tool_buttons()) == (
        "second",
        "current",
    )


def test_tool_strip_destruction_releases_runtime_palette_observation() -> None:
    """Registry mutations after host teardown must not target a deleted widget."""

    app = _app()
    canvas = QWidget()
    registry, palette = _palette(_tool("stable", 10))
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(palette)

    strip.deleteLater()
    app.sendPostedEvents()
    app.processEvents()

    registry.register(_tool("after-teardown", 20))
    assert tuple(item.tool_id for item in palette.snapshot()) == (
        "stable",
        "after-teardown",
    )


def test_tool_strip_teardown_cancels_deferred_self_removal_projection() -> None:
    """Deleting the host during a queued rebuild must not call a dead widget."""

    app = _app()
    canvas = QWidget()
    registry, palette = _palette(
        _tool("stable", 10),
        _tool("self-remove", 20, kind=CanvasToolKind.ACTION),
    )
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(palette)
    action = strip.button_for("self-remove")
    assert action is not None
    strip.toolRequested.connect(registry.unregister)

    action.click()
    strip.deleteLater()
    app.sendPostedEvents()
    app.processEvents()

    assert tuple(item.tool_id for item in palette.snapshot()) == ("stable",)


def test_grouped_layout_projects_one_stable_button_for_multiple_tools() -> None:
    """Like tools should share one slot while palette state remains authoritative."""

    app = _app()
    canvas = QWidget()
    _registry, palette = _palette(_tool("rectangle", 10), _tool("ellipse", 20))
    layout = CanvasToolLayout(
        CanvasToolLayoutSnapshot(
            (
                CanvasToolGroupSlot(
                    "shape",
                    ("rectangle", "ellipse"),
                    "rectangle",
                ),
            )
        )
    )
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(palette, layout)
    canvas.show()
    app.processEvents()

    rectangle = strip.button_for("rectangle")
    ellipse = strip.button_for("ellipse")
    assert rectangle is not None and rectangle is ellipse
    assert len(strip.tool_buttons()) == 1
    assert rectangle.tool_id == "rectangle"

    assert palette.set_active_tool("ellipse")
    app.processEvents()

    assert rectangle.tool_id == "ellipse"
    assert strip.indicator.isVisible()


def test_grouped_button_right_click_opens_member_picker_and_activates_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The grouped-slot marker should expose a right-click member switcher."""

    app = _app()
    canvas = QWidget()
    _registry, palette = _palette(_tool("rectangle", 10), _tool("ellipse", 20))
    layout = CanvasToolLayout(
        CanvasToolLayoutSnapshot(
            (
                CanvasToolGroupSlot(
                    "shape",
                    ("rectangle", "ellipse"),
                    "rectangle",
                ),
            )
        )
    )
    rendered_models: list[MenuModel] = []
    executions: list[tuple[QPoint, MenuAnimationType]] = []

    class _Menu:
        """Record menu execution without starting a nested event loop."""

        def exec(
            self,
            position: QPoint,
            *,
            aniType: MenuAnimationType,
        ) -> None:
            """Capture the global placement and animation policy."""

            executions.append((position, aniType))

    class _Renderer:
        """Capture the generic menu model passed by the tool strip."""

        def __init__(self, *, parent: QWidget) -> None:
            """Accept the production renderer construction contract."""

            del parent

        def render(self, model: MenuModel) -> _Menu:
            """Return a non-blocking menu double for the supplied model."""

            rendered_models.append(model)
            return _Menu()

    monkeypatch.setattr(
        "substitute.presentation.canvas.tools.tool_strip.QFluentMenuRenderer",
        _Renderer,
    )
    strip = CanvasToolStrip(canvas)
    strip.bind_palette(palette, layout)
    requested: list[str] = []
    strip.toolRequested.connect(requested.append)
    canvas.show()
    app.processEvents()
    button = strip.button_for("rectangle")
    assert button is not None

    button.contextMenuEvent(
        QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse,
            QPoint(3, 3),
            QPoint(100, 100),
        )
    )

    assert executions
    model = rendered_models[0]
    assert len(model.entries) == 2
    ellipse_entry = model.entries[1]
    assert isinstance(ellipse_entry, MenuItem)
    assert ellipse_entry.callback is not None
    ellipse_entry.callback()
    assert layout.snapshot().slots[0].selected_tool_id == "ellipse"
    assert requested == ["ellipse"]
