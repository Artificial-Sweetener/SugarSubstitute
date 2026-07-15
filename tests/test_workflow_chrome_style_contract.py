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

"""Contract tests for workflow chrome material and style ownership."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtGui import QColor
from pytest import MonkeyPatch

from substitute.presentation.shell import chrome_style

REPO_ROOT = Path(__file__).resolve().parents[1]


class _ThemeSignal:
    """Minimal signal stand-in that supports connection lifecycle assertions."""

    def __init__(self) -> None:
        """Initialize an empty callback list."""

        self.callbacks: list[Callable[[], None]] = []

    def connect(self, callback: Callable[[], None]) -> None:
        """Register one callback."""

        self.callbacks.append(callback)

    def disconnect(self, callback: Callable[[], None]) -> None:
        """Remove one registered callback."""

        if callback not in self.callbacks:
            raise TypeError("callback is not connected")
        self.callbacks.remove(callback)

    def emit(self) -> None:
        """Invoke a snapshot of the registered callbacks."""

        for callback in list(self.callbacks):
            callback()


class _ThemeConfig:
    """Minimal QFluent config stand-in with the two theme refresh signals."""

    def __init__(self) -> None:
        """Create isolated theme signals."""

        self.themeChangedFinished = _ThemeSignal()
        self.themeColorChanged = _ThemeSignal()


class _ThemeWidget:
    """Object stub with a Qt-like destroyed signal."""

    def __init__(self) -> None:
        """Create a destroyed signal for lifecycle tests."""

        self.destroyed = _ThemeSignal()


class _TitleBarButton:
    """Record qframelesswindow titlebar color assignments."""

    def __init__(self) -> None:
        """Initialize empty color slots."""

        self.normal_color: QColor | None = None
        self.hover_color: QColor | None = None
        self.pressed_color: QColor | None = None
        self.hover_background_color: QColor | None = None
        self.pressed_background_color: QColor | None = None

    def setNormalColor(self, color: QColor) -> None:
        """Record one normal icon color assignment."""

        self.normal_color = QColor(color)

    def setHoverColor(self, color: QColor) -> None:
        """Record one hover icon color assignment."""

        self.hover_color = QColor(color)

    def setPressedColor(self, color: QColor) -> None:
        """Record one pressed icon color assignment."""

        self.pressed_color = QColor(color)

    def setHoverBackgroundColor(self, color: QColor) -> None:
        """Record one hover background color assignment."""

        self.hover_background_color = QColor(color)

    def setPressedBackgroundColor(self, color: QColor) -> None:
        """Record one pressed background color assignment."""

        self.pressed_background_color = QColor(color)


class _TitleBar:
    """Provide the titlebar buttons consumed by shell button theming."""

    def __init__(self) -> None:
        """Create min, max, and close button doubles."""

        self.minBtn = _TitleBarButton()
        self.maxBtn = _TitleBarButton()
        self.closeBtn = _TitleBarButton()


def _source(relative_path: str) -> str:
    """Read one repository source file for lightweight style contracts."""
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _rgba(color: tuple[int, int, int, int]) -> str:
    """Return one CSS rgba string for token comparison."""

    red, green, blue, alpha = color
    return f"rgba({red}, {green}, {blue}, {alpha})"


def test_shell_titlebar_button_theme_leaves_dark_titlebar_buttons_at_defaults(
    monkeypatch: MonkeyPatch,
) -> None:
    """Shared titlebar helper should use qfluent's theme-aware stylesheet."""

    from substitute.presentation.shell import window_frame

    monkeypatch.setattr(window_frame, "isDarkTheme", lambda: True)
    applied: list[object] = []
    monkeypatch.setattr(
        window_frame,
        "FluentStyleSheet",
        SimpleNamespace(FLUENT_WINDOW=SimpleNamespace(apply=applied.append)),
    )
    titlebar = _TitleBar()

    window_frame.apply_shell_titlebar_button_theme(titlebar)

    assert applied == [titlebar.minBtn, titlebar.maxBtn, titlebar.closeBtn]
    assert titlebar.minBtn.normal_color is None
    assert titlebar.minBtn.hover_color is None
    assert titlebar.minBtn.pressed_color is None
    assert titlebar.minBtn.hover_background_color is None
    assert titlebar.minBtn.pressed_background_color is None
    assert titlebar.maxBtn.normal_color is None
    assert titlebar.closeBtn.normal_color is None
    assert titlebar.closeBtn.hover_color is None
    assert titlebar.closeBtn.hover_background_color is None


def test_shell_titlebar_button_theme_leaves_light_titlebar_buttons_at_defaults(
    monkeypatch: MonkeyPatch,
) -> None:
    """Shared titlebar helper should use qfluent's theme-aware stylesheet."""

    from substitute.presentation.shell import window_frame

    monkeypatch.setattr(window_frame, "isDarkTheme", lambda: False)
    applied: list[object] = []
    monkeypatch.setattr(
        window_frame,
        "FluentStyleSheet",
        SimpleNamespace(FLUENT_WINDOW=SimpleNamespace(apply=applied.append)),
    )
    titlebar = _TitleBar()

    window_frame.apply_shell_titlebar_button_theme(titlebar)

    assert applied == [titlebar.minBtn, titlebar.maxBtn, titlebar.closeBtn]
    assert titlebar.minBtn.normal_color is None
    assert titlebar.minBtn.hover_color is None
    assert titlebar.minBtn.pressed_color is None
    assert titlebar.minBtn.hover_background_color is None
    assert titlebar.minBtn.pressed_background_color is None
    assert titlebar.maxBtn.normal_color is None
    assert titlebar.closeBtn.normal_color is None
    assert titlebar.closeBtn.hover_color is None
    assert titlebar.closeBtn.hover_background_color is None


def test_workflow_chrome_material_constants_match_mica_alt_plan() -> None:
    """Workflow chrome should expose theme-aware washes and fixed shell geometry."""

    assert chrome_style.BODY_MATERIAL_SURFACE_OBJECT_NAME == (
        "SubstituteBodyMaterialSurface"
    )
    assert (
        chrome_style.body_material_wash_rgba()
        in chrome_style.body_material_wash_style()
    )
    assert len(chrome_style.body_material_wash_color()) == 4
    assert len(chrome_style.winui_card_fill_color()) == 4
    assert len(chrome_style.winui_card_border_color()) == 4
    assert chrome_style.CUBE_STACK_TOP_INSET == 6
    assert len(chrome_style.workflow_chrome_wash_color()) == 4
    assert chrome_style.WORKFLOW_TITLEBAR_MICA_SLIVER_HEIGHT == 4
    assert chrome_style.WORKFLOW_TITLEBAR_HEIGHT == 34
    assert chrome_style.WORKFLOW_TAB_CORNER_OVERLAY_WIDTH == 8.0
    assert chrome_style.WORKFLOW_TAB_BODY_TOP_RADIUS == 8.0
    assert chrome_style.WORKFLOW_TAB_BOTTOM_CORNER_RADIUS == 4.0
    assert chrome_style.WORKFLOW_TAB_BOTTOM_CORNER_WIDTH == 8.0
    assert chrome_style.WORKFLOW_TAB_INACTIVE_INSET == 1.0
    assert chrome_style.WORKFLOW_TAB_INACTIVE_RADIUS == 7.0
    assert len(chrome_style.workflow_tab_separator_rgba()) == 4
    assert chrome_style.WORKFLOW_TOOLBAR_VERTICAL_PADDING == 4
    assert chrome_style.WORKFLOW_TOOLBAR_CONTROL_HEIGHT == 36
    assert chrome_style.WORKFLOW_TOOLBAR_HEIGHT == 44
    assert chrome_style.APP_ORB_DIAMETER == 46
    assert chrome_style.APP_ORB_LEFT_MARGIN == 8
    assert chrome_style.APP_ORB_TOP == 6
    assert chrome_style.APP_ORB_RESERVED_WIDTH == (
        chrome_style.APP_ORB_LEFT_MARGIN + chrome_style.APP_ORB_DIAMETER + 8
    )
    assert chrome_style.APP_ORB_ICON_SIZE == 28
    assert chrome_style.APP_ORB_TAB_RESERVED_WIDTH == (
        chrome_style.APP_ORB_RESERVED_WIDTH - 14
    )
    assert chrome_style.APP_ORB_TAB_CUTOUT_RADIUS == 25.0
    assert chrome_style.APP_ORB_TAB_CUTOUT_OVERLAP == (
        chrome_style.APP_ORB_RESERVED_WIDTH - chrome_style.APP_ORB_TAB_RESERVED_WIDTH
    )
    assert chrome_style.APP_ORB_TAB_CUTOUT_CENTER_X == (
        chrome_style.APP_ORB_LEFT_MARGIN
        + chrome_style.APP_ORB_DIAMETER / 2
        - chrome_style.APP_ORB_TAB_RESERVED_WIDTH
    )
    assert chrome_style.APP_ORB_TAB_CUTOUT_CENTER_Y == (
        chrome_style.APP_ORB_TOP
        + chrome_style.APP_ORB_DIAMETER / 2
        - chrome_style.WORKFLOW_TITLEBAR_MICA_SLIVER_HEIGHT
    )
    assert chrome_style.APP_ORB_TAB_CUTOUT_ANIMATION_MS == 160
    assert chrome_style.WORKFLOW_TAB_HEIGHT == (
        chrome_style.WORKFLOW_TITLEBAR_HEIGHT
        - chrome_style.WORKFLOW_TITLEBAR_MICA_SLIVER_HEIGHT
    )


def test_acrylic_shell_washes_gain_opacity_without_becoming_opaque(
    monkeypatch: MonkeyPatch,
) -> None:
    """Acrylic-only shell washes should become stronger than the mica defaults."""

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: True)
    assert chrome_style.body_material_wash_color() == (32, 32, 32, 150)
    assert chrome_style.body_material_wash_color("acrylic") == (32, 32, 32, 169)
    assert chrome_style.workflow_chrome_wash_color() == (44, 44, 44, 150)
    assert chrome_style.workflow_chrome_wash_color("acrylic") == (44, 44, 44, 169)

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: False)
    assert chrome_style.body_material_wash_color("acrylic") == (251, 251, 251, 177)
    assert chrome_style.workflow_chrome_wash_color("acrylic") == (
        252,
        252,
        252,
        177,
    )


def test_winui_card_tokens_match_windows_card_resource_values(
    monkeypatch: MonkeyPatch,
) -> None:
    """WinUI card helpers should expose the exact default card fill and stroke tokens."""

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: False)
    assert chrome_style.winui_card_fill_color() == (255, 255, 255, 179)
    assert chrome_style.winui_card_fill_color("acrylic") == (255, 255, 255, 224)
    assert chrome_style.winui_card_border_color() == (0, 0, 0, 15)

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: True)
    assert chrome_style.winui_card_fill_color() == (255, 255, 255, 13)
    assert chrome_style.winui_card_fill_color("acrylic") == (255, 255, 255, 16)
    assert chrome_style.winui_card_border_color() == (0, 0, 0, 25)


def test_field_row_divider_token_matches_card_stroke_tints(
    monkeypatch: MonkeyPatch,
) -> None:
    """Field-row dividers should match the node-card title/body stroke token."""

    assert chrome_style.field_row_divider_rgba().startswith("rgba(")

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: False)
    assert chrome_style.field_row_divider_rgba() == "rgba(0, 0, 0, 15)"
    assert chrome_style.field_row_divider_rgba() == _rgba(
        chrome_style.winui_card_border_color()
    )

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: True)
    assert chrome_style.field_row_divider_rgba() == "rgba(0, 0, 0, 25)"
    assert chrome_style.field_row_divider_rgba() == _rgba(
        chrome_style.winui_card_border_color()
    )


def test_floating_surface_uses_opaque_winui_findbar_colors(
    monkeypatch: MonkeyPatch,
) -> None:
    """Floating shell surfaces should use opaque WinUI find-bar colors."""

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: False)
    assert chrome_style.floating_surface_rgba() == "rgba(252, 252, 252, 255)"
    assert chrome_style.floating_surface_color() == QColor(252, 252, 252, 255)

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: True)
    assert chrome_style.floating_surface_rgba() == "rgba(44, 44, 44, 255)"
    assert chrome_style.floating_surface_color() == QColor(44, 44, 44, 255)
    assert chrome_style.floating_surface_border_color() == QColor(255, 255, 255, 25)
    assert chrome_style.floating_surface_text_color() == QColor(255, 255, 255)


def test_winui_accent_button_disabled_tokens_match_fluent_primary_button(
    monkeypatch: MonkeyPatch,
) -> None:
    """Disabled accent-button helpers should mirror Fluent primary button tokens."""

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: False)
    assert chrome_style.winui_accent_button_disabled_fill_color() == (
        QColor(205, 205, 205)
    )
    assert chrome_style.winui_accent_button_disabled_foreground_color() == (
        QColor(255, 255, 255, 230)
    )

    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: True)
    assert chrome_style.winui_accent_button_disabled_fill_color() == (
        QColor(52, 52, 52)
    )
    assert chrome_style.winui_accent_button_disabled_foreground_color() == (
        QColor(255, 255, 255, 110)
    )


def test_theme_refresh_disconnects_when_widget_is_destroyed(
    monkeypatch: MonkeyPatch,
) -> None:
    """Theme refresh callbacks should leave global QFluent signals with the widget."""

    qconfig = _ThemeConfig()
    widget = _ThemeWidget()
    calls: list[str] = []
    monkeypatch.setattr(chrome_style, "qconfig", qconfig)
    monkeypatch.setattr(chrome_style, "_shiboken_is_valid", lambda _obj: True)

    chrome_style.connect_theme_refresh(widget, lambda: calls.append("refresh"))

    qconfig.themeChangedFinished.emit()
    widget.destroyed.emit()
    qconfig.themeColorChanged.emit()

    assert calls == ["refresh"]
    assert qconfig.themeChangedFinished.callbacks == []
    assert qconfig.themeColorChanged.callbacks == []


def test_theme_refresh_detaches_deleted_qt_wrappers(
    monkeypatch: MonkeyPatch,
) -> None:
    """A deleted Qt wrapper should not keep failing on future theme changes."""

    qconfig = _ThemeConfig()
    widget = _ThemeWidget()
    monkeypatch.setattr(chrome_style, "qconfig", qconfig)
    monkeypatch.setattr(chrome_style, "_shiboken_is_valid", lambda _obj: True)

    def _raise_deleted() -> None:
        """Mimic PySide's deleted C++ object RuntimeError."""

        raise RuntimeError("Internal C++ object (PromptEditor) already deleted.")

    chrome_style.connect_theme_refresh(widget, _raise_deleted)

    qconfig.themeChangedFinished.emit()
    qconfig.themeChangedFinished.emit()

    assert qconfig.themeChangedFinished.callbacks == []
    assert qconfig.themeColorChanged.callbacks == []


def test_theme_refresh_reraises_unexpected_runtime_errors(
    monkeypatch: MonkeyPatch,
) -> None:
    """Non-lifecycle failures should remain visible to callers."""

    qconfig = _ThemeConfig()
    widget = _ThemeWidget()
    monkeypatch.setattr(chrome_style, "qconfig", qconfig)
    monkeypatch.setattr(chrome_style, "_shiboken_is_valid", lambda _obj: True)

    def _raise_unexpected() -> None:
        """Raise a runtime error unrelated to Qt object destruction."""

        raise RuntimeError("boom")

    chrome_style.connect_theme_refresh(widget, _raise_unexpected)

    try:
        qconfig.themeChangedFinished.emit()
    except RuntimeError as error:
        assert str(error) == "boom"
    else:
        raise AssertionError("unexpected theme errors must be propagated")


def test_workflow_tab_style_opts_into_connected_top_accent_chrome() -> None:
    """Workflow tabs should declare the connected wash and top accent policy."""

    source = _source("substitute/presentation/workflows/workflow_tabs_view.py")

    assert 'selected_accent_position = "top"' in source
    assert "selected_border_reacts_to_hover = False" in source
    assert "paint_overlap_gutter" not in source
    assert "content_uses_body_rect" not in source
    assert "selected_uses_additive_bottom_corners" not in source
    assert "selected_bottom_corner_radius = WORKFLOW_TAB_BOTTOM_CORNER_RADIUS" in source
    assert "selected_bottom_corner_width = WORKFLOW_TAB_BOTTOM_CORNER_WIDTH" in source
    assert 'selected_bottom_border_mode = "none"' in source
    assert "selected_connects_to_bottom_surface = True" in source
    assert "selected_fill_color = workflow_chrome_wash_color()" in source
    assert "unselected_separator_color = WORKFLOW_TAB_SEPARATOR_RGBA" not in source
    assert "unselected_top_rounded_only = True" in source
    assert "inactive_text_alpha = WORKFLOW_TAB_INACTIVE_TEXT_ALPHA" in source
    assert "self.setShadowEnabled(False)" in source
    assert "def setShadowEnabled(self, isEnabled: bool) -> None:" in source
    assert "self.shadowEffect.setEnabled(False)" in source


def test_workflow_tabbar_owns_corner_overlay_model() -> None:
    """Workflow tabs should paint cross-tab corners from a parent overlay."""

    source = _source("substitute/presentation/workflows/workflow_tabs_view.py")

    assert "class WorkflowTabCornerOverlay(QWidget):" in source
    assert "self.cornerOverlay = WorkflowTabCornerOverlay(self)" in source
    assert "Qt.WidgetAttribute.WA_TransparentForMouseEvents" in source
    assert "def _syncCornerOverlay" in source
    assert "self.mapFromGlobal(selected_item.mapToGlobal(QPoint(0, 0)))" in source
    assert "WORKFLOW_TAB_CORNER_OVERLAY_WIDTH" in source
    assert "_bottom_join_extension = 1.0" in source
    assert "painter.drawPath(left_corner_path)" in source
    assert "painter.drawPath(right_corner_path)" in source
    assert "self.cornerOverlay.sync()" in source
    assert "for i, item in enumerate(self.items[:-1]):" in source


def test_workflow_tabbar_paint_avoids_corner_overlay_sync() -> None:
    """Workflow tab painting should not resync selected-corner overlay geometry."""

    source = _source("substitute/presentation/workflows/workflow_tabs_view.py")
    tabbar_source = source.split("class TabBar(ReorderableTabBarBase):", maxsplit=1)[1]
    paint_source = tabbar_source.split(
        "def paintEvent(self, event: QMouseEvent) -> None:",
        maxsplit=1,
    )[1].split("def resizeEvent", maxsplit=1)[0]

    assert "super().paintEvent(event)" in paint_source
    assert "_syncCornerOverlay()" not in paint_source


def test_workflow_tab_corner_overlay_caches_paths_by_signature() -> None:
    """Workflow tab corner overlay should reuse paths until geometry/theme changes."""

    source = _source("substitute/presentation/workflows/workflow_tabs_view.py")

    assert "_corner_path_cache_signature" in source
    assert "_corner_path_cache" in source
    assert "def _selectedCornerPaths" in source
    assert "selected_rect.getRect()" in source
    assert "self.rect().getRect()" in source
    assert "self._tab_bar.backdrop_mode" in source
    assert "selected_item.orb_cutout_progress()" in source
    assert "cutout_progress" in source
    assert "isDarkTheme()" in source


def test_workflow_tab_orb_cutout_stays_owned_by_workflow_tab_item() -> None:
    """Orb-adjacent tab shape logic should stay out of the generic tab base."""

    workflow_source = _source("substitute/presentation/workflows/workflow_tabs_view.py")
    base_source = _source("substitute/presentation/workflows/reorderable_tabs_base.py")

    assert "orbCutoutProgress" in workflow_source
    assert "def _drawConnectedSelectedBackground" in workflow_source
    assert "def _drawNotSelectedBackground" in workflow_source
    assert "APP_ORB_TAB_CUTOUT_RADIUS" in workflow_source
    assert "orbCutout" not in base_source
    assert "APP_ORB" not in base_source


def test_workflow_tabbar_only_exposes_inline_rename_paths() -> None:
    """Workflow tab rename should be inline-only through context menu or double-click."""

    workflow_source = _source("substitute/presentation/workflows/workflow_tabs_view.py")
    base_source = _source("substitute/presentation/workflows/reorderable_tabs_base.py")
    main_window_source = _source("substitute/presentation/shell/main_window.py")
    coordinator_source = _source(
        "substitute/presentation/shell/workflow_workspace_coordinator.py"
    )
    service_source = _source("substitute/application/workflows/workflow_tab_service.py")

    assert "tabRenameRequested" not in workflow_source
    assert "Rename Tab" not in workflow_source
    assert "Rename Inline" not in workflow_source
    assert '"workflow_tab.rename"' in workflow_source
    assert "callback=tab_item._startRename" in workflow_source
    assert "def mouseDoubleClickEvent" in base_source
    assert "self._startRename()" in base_source
    assert "tabRenameRequested" not in main_window_source
    assert "on_workflow_tab_rename_requested" not in coordinator_source
    assert "validate_dialog_rename" not in service_source


def test_shared_tab_painter_keeps_connected_style_explicit() -> None:
    """The shared painter should not own workflow cross-tab corner painting."""

    source = _source("substitute/presentation/workflows/reorderable_tabs_base.py")

    assert 'selected_accent_position: str = "bottom"' in source
    assert "selected_bottom_corner_radius: float = 0.0" in source
    assert "selected_bottom_corner_width: float = 0.0" in source
    assert "selected_connects_to_bottom_surface: bool = False" in source
    assert "selected_border_reacts_to_hover: bool = True" in source
    assert (
        "unselected_separator_color: tuple[int, int, int, int] | None = None" in source
    )
    assert "unselected_top_rounded_only: bool = False" in source
    assert "def _topRoundedPath" in source
    assert "def _topRoundedBorderPath" in source
    assert "def _drawConnectedSelectedBackground" in source
    assert "def _drawSelectedAccent" in source
    assert "painter.setClipPath(clip_path)" in source
    assert "painter.drawRect(accent_rect)" in source
    assert "WORKFLOW_TAB_TOP_ACCENT_INSET" not in source
    assert "font.setWeight(QFont.Weight(self.selected_font_weight))" in source
    assert "_drawAdditiveConnectedSelectedBackground" not in source
    assert "_tabBodyRect" not in source
    assert "visualBodyRight" not in source
    assert "paint_overlap_gutter" not in source


def test_toolbar_and_tabbar_sources_use_workflow_chrome_without_height_hack() -> None:
    """Toolbar/tabbar setup should use the shared wash and avoid 10px tab hacks."""

    menu_source = _source("substitute/presentation/shell/main_window_menu.py")
    workspace_source = _source("substitute/presentation/shell/main_window_workspace.py")
    material_source = _source(
        "substitute/presentation/shell/workspace_body_material_surface.py"
    )
    composition_source = _source("substitute/app/bootstrap/composition.py")

    assert "WorkflowChromeToolbar" in menu_source
    assert "workflow_chrome_wash_rgba" in menu_source
    assert "WORKFLOW_TOOLBAR_HEIGHT" in menu_source
    assert "menu_bar.setFixedHeight(WORKFLOW_TOOLBAR_HEIGHT)" in menu_source
    assert "WORKFLOW_TOOLBAR_VERTICAL_PADDING" in menu_source
    assert "WorkspaceBodyMaterialSurface" in workspace_source
    assert "body_material_wash_style" not in workspace_source
    assert "body_material_wash_color" in material_source
    assert "BODY_MATERIAL_SURFACE_OBJECT_NAME" in material_source
    assert "create_body_material_surface=False" in composition_source
    assert "min-height: 10px" not in workspace_source
    assert "max-height: 10px" not in workspace_source
