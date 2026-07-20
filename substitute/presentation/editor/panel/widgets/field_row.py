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

"""Render single-field and grouped field rows for behavior-driven node cards."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Final, Mapping

from PySide6.QtCore import QEvent, QObject, QSize, QTimer, Qt
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    StyleSheetBase,
    getStyleSheet,
    setCustomStyleSheet,
    setStyleSheet,
    styleSheetManager,
)

from substitute.application.node_behavior import (
    FieldBehavior,
    FieldPresentation,
    LabelMode,
    RowMode,
)
from substitute.presentation.editor.panel.menus.dimension_preset_models import (
    DimensionPresetMenuSource,
)
from substitute.presentation.editor.panel.menus.dimension_row_actions import (
    bind_dimension_row_actions,
)
from substitute.presentation.editor.panel.node_card.body_layout import (
    CardBodyLayoutState,
    apply_card_body_layout_state,
    ensure_card_body_layout_state,
    resolve_card_body_expanded_height,
)
from substitute.presentation.widgets.tooltips import (
    bind_fluent_tooltip,
    tooltip_from_input_metadata,
)
from substitute.presentation.shell.chrome_style import field_row_divider_rgba_for_theme
from substitute.application.display_labels import beautify_label
from substitute.presentation.qt_label_text import literal_label_text

_WIDE_ROW_FIELD_WIDGET_CLASSES = frozenset({"ModelPickerField"})
_MAX_WIDGET_HEIGHT: Final[int] = 16_777_215

EDITOR_ROW_HEIGHT = 33
EDITOR_ROW_HORIZONTAL_MARGINS = (10, 0, 10, 0)
EDITOR_ROW_ICON_SIZE = 20
EDITOR_ROW_SPACING = 6
EDITOR_ROW_BODY_SPACING = 8
EDITOR_FIELD_ROW_HEIGHT = EDITOR_ROW_HEIGHT + (EDITOR_ROW_BODY_SPACING * 2)
EDITOR_FULL_WIDTH_ROW_MARGINS = (
    EDITOR_ROW_HORIZONTAL_MARGINS[0],
    EDITOR_ROW_BODY_SPACING,
    EDITOR_ROW_HORIZONTAL_MARGINS[2],
    EDITOR_ROW_BODY_SPACING,
)
GROUPED_FIELD_DIVIDER_WIDTH = 1
_RELAYOUT_EVENT_TYPES: Final[tuple[QEvent.Type, ...]] = (
    QEvent.Type.LayoutRequest,
    QEvent.Type.Resize,
    QEvent.Type.Show,
)
_OPTIONAL_LAYOUT_SIGNAL_NAMES: Final[tuple[str, ...]] = (
    "resized",
    "layoutInvalidated",
    "contentSizeChanged",
)

try:
    from shiboken6 import isValid as _runtime_is_valid
except ImportError:  # pragma: no cover - test-stub fallback only

    def is_valid_widget(widget: object) -> bool:
        """Treat test doubles as valid when shiboken is unavailable."""

        _ = widget
        return True

else:

    def is_valid_widget(widget: object) -> bool:
        """Return whether one QWidget/QObject reference is still alive."""

        return bool(_runtime_is_valid(widget))


class ScalarFieldRowWidget(QWidget):
    """Render one editor scalar row with a stable visual height contribution."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize a row container constrained to the scalar row height."""

        super().__init__(parent)
        apply_editor_row_height(self)

    def sizeHint(self) -> QSize:
        """Return the natural row width with the standard field-row height."""

        hint = super().sizeHint()
        return QSize(hint.width(), EDITOR_FIELD_ROW_HEIGHT)

    def minimumSizeHint(self) -> QSize:
        """Return the natural minimum width with the standard field-row height."""

        hint = super().minimumSizeHint()
        return QSize(hint.width(), EDITOR_FIELD_ROW_HEIGHT)


def apply_editor_row_height(widget: QWidget) -> None:
    """Constrain one editor row container to the standard visual row height."""

    widget.setFixedHeight(EDITOR_FIELD_ROW_HEIGHT)


def apply_editor_control_height(widget: QWidget) -> None:
    """Constrain one scalar editor control to the standard fixed row height."""

    widget.setFixedHeight(EDITOR_ROW_HEIGHT)


class _FieldRowDividerStyleSheet(StyleSheetBase):  # type: ignore[misc]
    """Provide an empty QFluent-managed base source for custom divider QSS."""

    def path(self, theme: object | None = None) -> str:
        """Return no file path because divider QSS is stored as custom QSS."""

        _ = theme
        return ""

    def content(self, theme: object | None = None) -> str:
        """Return no base content so only the custom theme QSS paints dividers."""

        _ = theme
        return ""


_FIELD_ROW_DIVIDER_STYLE_SHEET = _FieldRowDividerStyleSheet()


def _field_row_divider_qss(rgba: str) -> str:
    """Return divider QSS that changes only paint color, not layout metrics."""

    return f"background-color: {rgba}; margin: 0px; padding: 0px;"


def _apply_field_row_divider_style(widget: QWidget) -> None:
    """Register one field-row divider with QFluent theme refresh."""

    light_qss = _field_row_divider_qss(field_row_divider_rgba_for_theme(False))
    dark_qss = _field_row_divider_qss(field_row_divider_rgba_for_theme(True))
    setStyleSheet(widget, _FIELD_ROW_DIVIDER_STYLE_SHEET)
    setCustomStyleSheet(widget, light_qss, dark_qss)
    widget.setStyleSheet(getStyleSheet(styleSheetManager.source(widget)))


@dataclass(frozen=True)
class FieldRowTextTarget:
    """Expose stable label and tooltip targets for locale-only rebinding."""

    field_key: str
    label: CaptionLabel | None
    field_widget: QWidget
    tooltip_owner: QWidget
    tooltip_targets: tuple[QWidget, ...]


@dataclass(frozen=True)
class BuiltFieldRow:
    """Carry one row widget and the field key used for visibility tracking."""

    field_key: Any
    row: QWidget
    text_targets: tuple[FieldRowTextTarget, ...] = ()


class FieldRowBuilder:
    """Build tagged field rows/dividers so panel-level visibility toggles remain stable."""

    def __init__(
        self,
        panel: Any,
        icon_builder: Callable[[Any], QWidget],
        icon_resolver: Callable[[str, str, int | None], Any],
        dimension_preset_source: DimensionPresetMenuSource | None = None,
    ) -> None:
        """Store panel collaborators used to build stable field-row widgets."""

        self._panel = panel
        self._icon_builder = icon_builder
        self._icon_resolver = icon_resolver
        self._dimension_preset_source = dimension_preset_source

    @staticmethod
    def _field_key_from_metadata(input_metadata: dict[str, Any] | None) -> Any:
        """Return canonical field key tuple when available, otherwise the leaf key string."""

        if not isinstance(input_metadata, dict):
            return None
        cube_alias = input_metadata.get("cube_alias")
        node_name = input_metadata.get("node_name")
        key = input_metadata.get("key")
        if cube_alias is not None and node_name is not None and key is not None:
            return (cube_alias, node_name, key)
        return key

    def make_horizontal_divider(self, parent: QWidget) -> QWidget:
        """Create one horizontal divider row."""

        line = QWidget(parent)
        line.setFixedHeight(1)
        line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        _apply_field_row_divider_style(line)
        return line

    def add_input_row(
        self,
        *,
        label: str,
        widget: QWidget,
        field_behavior: FieldBehavior,
        content_layout: QVBoxLayout,
    ) -> None:
        """Render one input row and register row widgets for hidden-field toggles."""

        built_row = self.build_input_row(
            label=label,
            widget=widget,
            field_behavior=field_behavior,
        )
        content_layout.addWidget(built_row.row)
        if built_row.field_key is not None:
            self._panel.row_widgets[built_row.field_key] = (None, built_row.row)

    def build_input_row(
        self,
        *,
        label: str,
        widget: QWidget,
        field_behavior: FieldBehavior,
    ) -> BuiltFieldRow:
        """Build one input row without assigning body-level separators."""

        panel = self._panel
        input_metadata = widget.property("input_metadata")
        field_tooltip = tooltip_from_input_metadata(input_metadata)
        field_key = self._field_key_from_metadata(input_metadata)
        leaf_field_key = self._leaf_field_key_from_metadata(input_metadata)
        if field_behavior.row_mode == RowMode.FULL_WIDTH:
            padded = QWidget(panel)
            padded_layout = QVBoxLayout(padded)
            padded_layout.setContentsMargins(*EDITOR_FULL_WIDTH_ROW_MARGINS)
            padded_layout.setSpacing(6)
            padded_layout.addWidget(widget)
            if input_metadata is not None:
                padded.setProperty("input_metadata", input_metadata)

            is_hidden = self._is_hidden(field_key)
            padded.setVisible(not is_hidden)
            bind_fluent_tooltip(
                padded,
                field_tooltip,
                padded,
                widget,
                show_delay_ms=600,
            )
            return BuiltFieldRow(
                field_key=field_key,
                row=padded,
                text_targets=(
                    FieldRowTextTarget(
                        field_key=leaf_field_key,
                        label=None,
                        field_widget=widget,
                        tooltip_owner=padded,
                        tooltip_targets=(padded, widget),
                    ),
                )
                if leaf_field_key is not None
                else (),
            )

        row = ScalarFieldRowWidget(panel)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(*EDITOR_ROW_HORIZONTAL_MARGINS)
        row_layout.setSpacing(EDITOR_ROW_SPACING)

        row_layout.addSpacing(EDITOR_ROW_ICON_SIZE)

        label_widget: CaptionLabel | None = None
        if field_behavior.label_mode != LabelMode.HIDDEN:
            label_text = field_behavior.label_override or label
            label_widget = CaptionLabel(literal_label_text(beautify_label(label_text)))
            if field_behavior.label_mode == LabelMode.PROMPT:
                label_widget.setStyleSheet("font-weight: bold;")
            label_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            row_layout.addWidget(
                label_widget,
                _label_stretch_for_field(widget),
                Qt.AlignmentFlag.AlignVCenter,
            )

        if _surface_may_size_field(field_behavior):
            if _should_apply_editor_control_height(field_behavior):
                apply_editor_control_height(widget)
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row_layout.addWidget(
            widget,
            _field_stretch_for_field(widget),
            _field_alignment_for_field(widget),
        )

        row_layout.addSpacing(EDITOR_ROW_ICON_SIZE)

        if input_metadata is not None:
            row.setProperty("input_metadata", input_metadata)

        is_hidden = self._is_hidden(field_key)
        row.setVisible(not is_hidden)
        tooltip_targets = (
            (row, widget) if label_widget is None else (row, label_widget, widget)
        )
        bind_fluent_tooltip(
            row,
            field_tooltip,
            *tooltip_targets,
            show_delay_ms=600,
        )
        return BuiltFieldRow(
            field_key=field_key,
            row=row,
            text_targets=(
                FieldRowTextTarget(
                    field_key=leaf_field_key,
                    label=label_widget,
                    field_widget=widget,
                    tooltip_owner=row,
                    tooltip_targets=tooltip_targets,
                ),
            )
            if leaf_field_key is not None
            else (),
        )

    def add_n_column_row(
        self,
        *,
        fields: list[tuple[str, QWidget]],
        field_behaviors: Mapping[str, FieldBehavior],
        content_layout: QVBoxLayout,
        node_name: str = "",
        field_labels: Mapping[str, str] | None = None,
    ) -> None:
        """Render a grouped n-column row with divider and visibility tracking."""

        built_row = self.build_n_column_row(
            fields=fields,
            field_behaviors=field_behaviors,
            node_name=node_name,
            field_labels=field_labels,
        )
        content_layout.addWidget(built_row.row)
        if built_row.field_key is not None:
            self._panel.row_widgets[built_row.field_key] = (None, built_row.row)

    def build_n_column_row(
        self,
        *,
        fields: list[tuple[str, QWidget]],
        field_behaviors: Mapping[str, FieldBehavior],
        node_name: str = "",
        field_labels: Mapping[str, str] | None = None,
    ) -> BuiltFieldRow:
        """Build one grouped n-column row without body-level separators."""

        panel = self._panel
        if not hasattr(panel, "col_widgets"):
            panel.col_widgets = {}

        row_container = ScalarFieldRowWidget(panel)
        row_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row_container.setStyleSheet("background-color: transparent;")

        row_layout = QHBoxLayout(row_container)
        row_layout.setContentsMargins(*EDITOR_ROW_HORIZONTAL_MARGINS)
        row_layout.setSpacing(EDITOR_ROW_SPACING)
        column_widgets: dict[str, QWidget] = {}
        column_tooltips: list[str] = []
        first_field_key = None
        text_targets: list[FieldRowTextTarget] = []

        for index, (label, widget) in enumerate(fields):
            behavior = field_behaviors.get(label)
            input_metadata = widget.property("input_metadata")
            field_tooltip = tooltip_from_input_metadata(input_metadata)
            if field_tooltip is not None:
                column_tooltips.append(field_tooltip)
            field_key = self._field_key_from_metadata(input_metadata)
            if first_field_key is None and field_key is not None:
                first_field_key = field_key

            col = ScalarFieldRowWidget(panel)
            column_widgets[label] = col
            col_layout = QHBoxLayout(col)
            col_layout.setContentsMargins(0, 0, 0, 0)
            col_layout.setSpacing(EDITOR_ROW_SPACING)

            icon_enum = self._icon_resolver(node_name, label, column_index=index)
            if icon_enum is None:
                col_layout.addSpacing(EDITOR_ROW_ICON_SIZE)
            else:
                icon_widget = self._icon_builder(icon_enum)
                col_layout.addWidget(icon_widget, 0, Qt.AlignmentFlag.AlignVCenter)

            label_text = (
                behavior.label_override
                if behavior is not None and behavior.label_override
                else (field_labels or {}).get(label, label)
            )
            label_widget: CaptionLabel | None = None
            if behavior is None or behavior.label_mode != LabelMode.HIDDEN:
                label_widget = CaptionLabel(
                    literal_label_text(beautify_label(label_text))
                )
                label_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                col_layout.addWidget(
                    label_widget,
                    _label_stretch_for_field(widget),
                    Qt.AlignmentFlag.AlignVCenter,
                )
            if _surface_may_size_field(behavior):
                if _should_apply_editor_control_height(behavior):
                    apply_editor_control_height(widget)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            col_layout.addWidget(
                widget,
                _field_stretch_for_field(widget),
                _field_alignment_for_field(widget),
            )
            tooltip_targets = (
                (col, widget) if label_widget is None else (col, label_widget, widget)
            )
            bind_fluent_tooltip(
                col,
                field_tooltip,
                *tooltip_targets,
                show_delay_ms=600,
            )
            text_targets.append(
                FieldRowTextTarget(
                    field_key=label,
                    label=label_widget,
                    field_widget=widget,
                    tooltip_owner=col,
                    tooltip_targets=tooltip_targets,
                )
            )

            if field_key is not None:
                col.setProperty("field_key", field_key)
                widget.setProperty("field_key", field_key)
                panel.col_widgets[field_key] = (row_container, col, widget)

            row_layout.addWidget(col, 1)

            if index < len(fields) - 1:
                divider = QWidget(panel)
                divider.setFixedSize(GROUPED_FIELD_DIVIDER_WIDTH, EDITOR_ROW_HEIGHT)
                divider.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                _apply_field_row_divider_style(divider)
                if field_key is not None:
                    divider.setProperty("vertical_divider_for_field", field_key)
                row_layout.addWidget(divider, 0, Qt.AlignmentFlag.AlignVCenter)

        row_layout.addSpacing(EDITOR_ROW_ICON_SIZE)
        bind_dimension_row_actions(
            row_container=row_container,
            fields=fields,
            column_widgets=column_widgets,
            dimension_preset_source=self._dimension_preset_source,
        )
        unique_tooltips = set(column_tooltips)
        bind_fluent_tooltip(
            row_container,
            column_tooltips[0] if len(unique_tooltips) == 1 else None,
            row_container,
            show_delay_ms=600,
        )
        return BuiltFieldRow(
            field_key=first_field_key,
            row=row_container,
            text_targets=tuple(text_targets),
        )

    @staticmethod
    def _leaf_field_key_from_metadata(
        input_metadata: dict[str, Any] | None,
    ) -> str | None:
        """Return the locale-neutral field key from sanitized widget metadata."""

        if not isinstance(input_metadata, dict):
            return None
        key = input_metadata.get("key")
        return key if isinstance(key, str) and key else None

    def gather_visible_keys(
        self,
        *,
        input_keys: list[str],
        field_groups: tuple[tuple[str, ...], ...],
        skip_keys: set[str],
    ) -> list[list[str]]:
        """Group visible field keys using resolved behavior-provided grouping rules."""

        keys = [key for key in input_keys if key not in skip_keys]
        if field_groups:
            used: set[str] = set()
            ordered_groups: list[list[str]] = []
            for key in keys:
                if key in used:
                    continue
                matching_group = None
                for group in field_groups:
                    if key in group:
                        matching_group = group
                        break
                if matching_group is None:
                    ordered_groups.append([key])
                    used.add(key)
                    continue
                visible_group = [
                    group_key
                    for group_key in matching_group
                    if group_key in keys and group_key not in used
                ]
                if visible_group:
                    ordered_groups.append(visible_group)
                    used.update(visible_group)
            return ordered_groups
        return [[key] for key in keys]

    def _is_hidden(self, field_key: Any) -> bool:
        """Return whether the panel currently hides the given field key."""

        hidden_keys = getattr(self._panel, "_hidden_field_keys", set())
        return bool(
            field_key in hidden_keys
            or (isinstance(field_key, tuple) and field_key[-1] in hidden_keys)
            or (isinstance(field_key, str) and field_key in hidden_keys)
        )


def _is_wide_row_field(widget: QWidget) -> bool:
    """Return whether a field widget should own surplus row width."""

    return any(
        candidate.__name__ in _WIDE_ROW_FIELD_WIDGET_CLASSES
        for candidate in widget.__class__.mro()
    )


def _is_fill_width_string_input(widget: QWidget) -> bool:
    """Return whether one scalar field is a node-card single-line string input."""

    input_metadata = widget.property("input_metadata")
    return (
        widget.__class__.__name__ == "LineEdit"
        and isinstance(input_metadata, Mapping)
        and input_metadata.get("type") == "STRING"
    )


def _field_should_own_surplus_width(widget: QWidget) -> bool:
    """Return whether a value widget should receive flexible row width."""

    return _is_wide_row_field(widget) or _is_fill_width_string_input(widget)


def _should_apply_editor_control_height(field_behavior: FieldBehavior | None) -> bool:
    """Return whether one field widget should fill the scalar row height."""

    if field_behavior is not None and (
        field_behavior.presentation == FieldPresentation.PROMPT_BOX
        or field_behavior.row_mode == RowMode.FULL_WIDTH
    ):
        return False
    return True


def _surface_may_size_field(field_behavior: FieldBehavior | None) -> bool:
    """Return whether generic row policy may override a control's owned geometry."""

    return not (
        field_behavior is not None
        and field_behavior.presentation is FieldPresentation.SEED_BOX
    )


def _label_stretch_for_field(widget: QWidget) -> int:
    """Return the label stretch factor for the row containing this field."""

    return 0 if _field_should_own_surplus_width(widget) else 1


def _field_stretch_for_field(widget: QWidget) -> int:
    """Return the field stretch factor for the row containing this field."""

    return 1 if _field_should_own_surplus_width(widget) else 0


def _field_alignment_for_field(widget: QWidget) -> Qt.AlignmentFlag:
    """Return row alignment for one field widget."""

    _ = widget
    return Qt.AlignmentFlag.AlignVCenter


class _FieldWidgetRelayoutFilter(QObject):
    """Defer row/card relayout after one field widget changes its layout needs."""

    def __init__(
        self,
        *,
        field_widget: QWidget,
        content_body: QWidget,
        content_layout: QVBoxLayout,
        allow_unbounded_height: bool,
    ) -> None:
        """Store field-widget and card-body references for deferred relayout."""

        super().__init__(field_widget)
        self._field_widget = field_widget
        self._content_body = content_body
        self._content_layout = content_layout
        self._allow_unbounded_height = allow_unbounded_height
        self._update_pending = False
        self._applying_relayout = False
        self._force_geometry_refresh_pending = False
        self._last_field_geometry_signature: tuple[int, int, int, int] | None = None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Schedule one deferred relayout when the watched field widget changes."""

        event_type = event.type()
        if (
            not self._applying_relayout
            and watched is self._field_widget
            and event_type in _RELAYOUT_EVENT_TYPES
        ):
            if (
                event_type == QEvent.Type.LayoutRequest
                and self._layout_request_is_settled()
            ):
                return super().eventFilter(watched, event)
            self.schedule_relayout(
                force_geometry_refresh=event_type != QEvent.Type.LayoutRequest,
                reason=f"event:{event_type.name}",
            )
        return super().eventFilter(watched, event)

    def schedule_relayout(
        self, *, force_geometry_refresh: bool = False, reason: str = "explicit"
    ) -> None:
        """Coalesce repeated geometry changes into one deferred relayout pass."""

        if force_geometry_refresh:
            self._force_geometry_refresh_pending = True
        if self._update_pending:
            return
        self._update_pending = True
        _ = reason
        QTimer.singleShot(0, self._apply_relayout)

    def _apply_relayout(self) -> None:
        """Invalidate the row and card body after one field-widget size change."""

        self._update_pending = False
        force_geometry_refresh = self._force_geometry_refresh_pending
        self._force_geometry_refresh_pending = False
        if not is_valid_widget(self._field_widget) or not is_valid_widget(
            self._content_body
        ):
            return

        self._applying_relayout = True
        try:
            field_geometry_signature = self._field_geometry_signature()
            field_geometry_changed = (
                field_geometry_signature != self._last_field_geometry_signature
            )
            if force_geometry_refresh or field_geometry_changed:
                self._invalidate_parent_chain(self._field_widget.parentWidget())
            else:
                self._invalidate_parent_layouts(self._field_widget.parentWidget())
            self._content_layout.invalidate()
            expanded_height = resolve_card_body_expanded_height(
                content_layout=self._content_layout,
                allow_unbounded_height=self._allow_unbounded_height,
            )
            existing_state = _card_body_layout_state(self._content_body)
            if (
                existing_state is not None
                and not field_geometry_changed
                and existing_state.expanded_height == expanded_height
                and self._card_body_layout_is_applied(existing_state)
            ):
                self._last_field_geometry_signature = field_geometry_signature
                return
            self._invalidate_parent_chain(self._field_widget.parentWidget())
            state = ensure_card_body_layout_state(
                content_body=self._content_body,
                expanded_height=expanded_height,
            )
            apply_card_body_layout_state(
                content_body=self._content_body,
                state=state,
                allow_unbounded_height=self._allow_unbounded_height,
                preserve_animation_height=True,
            )
            self._content_body.updateGeometry()
            self._invalidate_parent_chain(self._content_body.parentWidget())
            self._notify_owner_section()
            self._last_field_geometry_signature = field_geometry_signature
        finally:
            self._applying_relayout = False

    def _field_geometry_signature(self) -> tuple[int, int, int, int]:
        """Return field geometry values that affect parent layout sizing."""

        return (
            self._field_widget.minimumHeight(),
            self._field_widget.maximumHeight(),
            self._field_widget.sizeHint().height(),
            self._field_widget.height(),
        )

    def _layout_request_is_settled(self) -> bool:
        """Return whether a LayoutRequest cannot change card-body geometry."""

        existing_state = _card_body_layout_state(self._content_body)
        return (
            existing_state is not None
            and self._last_field_geometry_signature == self._field_geometry_signature()
            and self._card_body_layout_is_applied(existing_state)
        )

    def _card_body_layout_is_applied(self, state: CardBodyLayoutState) -> bool:
        """Return whether the current body geometry already reflects the state."""

        if state.collapsed or state.forced_collapsed:
            return self._content_body.maximumHeight() == 0
        if self._allow_unbounded_height:
            return self._content_body.maximumHeight() == _MAX_WIDGET_HEIGHT
        return self._content_body.maximumHeight() == state.expanded_height

    def _invalidate_parent_chain(self, widget: QWidget | None) -> None:
        """Invalidate layouts from the supplied widget upward through parent widgets."""

        current = widget
        while current is not None and is_valid_widget(current):
            layout = current.layout()
            if layout is not None:
                layout.invalidate()
            current.updateGeometry()
            current = current.parentWidget()

    def _invalidate_parent_layouts(self, widget: QWidget | None) -> None:
        """Invalidate parent layouts without requesting new widget geometry."""

        current = widget
        while current is not None and is_valid_widget(current):
            layout = current.layout()
            if layout is not None:
                layout.invalidate()
            current = current.parentWidget()

    def _notify_owner_section(self) -> None:
        """Ask the nearest cube-section owner to settle geometry after relayout."""

        current = self._content_body.parentWidget()
        while current is not None and is_valid_widget(current):
            finalize = getattr(current, "finalize_layout_after_child_relayout", None)
            if callable(finalize):
                finalize(reason="field_relayout")
                return
            update_height = getattr(current, "update_cube_height", None)
            if callable(update_height):
                update_height()
                return
            current = current.parentWidget()


def _card_body_layout_state(content_body: QWidget) -> CardBodyLayoutState | None:
    """Return existing card-body layout state without mutating it."""

    state = getattr(content_body, "_card_body_layout_state", None)
    return state if isinstance(state, CardBodyLayoutState) else None


def bind_field_widget_card_relayout(
    *,
    field_widget: QWidget,
    content_body: QWidget,
    content_layout: QVBoxLayout,
    allow_unbounded_height: bool,
) -> None:
    """Attach generic row/card relayout behavior to one field widget."""

    relayout_filter = _FieldWidgetRelayoutFilter(
        field_widget=field_widget,
        content_body=content_body,
        content_layout=content_layout,
        allow_unbounded_height=allow_unbounded_height,
    )
    field_widget.installEventFilter(relayout_filter)
    for signal_name in _OPTIONAL_LAYOUT_SIGNAL_NAMES:
        signal = getattr(field_widget, signal_name, None)
        if signal is None:
            continue
        try:
            signal.connect(
                lambda *_args, signal_name=signal_name: (
                    relayout_filter.schedule_relayout(
                        force_geometry_refresh=True,
                        reason=f"signal:{signal_name}",
                    )
                )
            )
        except TypeError:
            continue
    setattr(field_widget, "_card_field_relayout_filter", relayout_filter)
    relayout_filter.schedule_relayout(
        force_geometry_refresh=True,
        reason="initial_bind",
    )


__all__ = [
    "BuiltFieldRow",
    "EDITOR_FIELD_ROW_HEIGHT",
    "EDITOR_FULL_WIDTH_ROW_MARGINS",
    "EDITOR_ROW_BODY_SPACING",
    "EDITOR_ROW_HEIGHT",
    "EDITOR_ROW_HORIZONTAL_MARGINS",
    "EDITOR_ROW_ICON_SIZE",
    "EDITOR_ROW_SPACING",
    "FieldRowBuilder",
    "FieldRowTextTarget",
    "GROUPED_FIELD_DIVIDER_WIDTH",
    "ScalarFieldRowWidget",
    "apply_editor_control_height",
    "apply_editor_row_height",
    "bind_field_widget_card_relayout",
]
