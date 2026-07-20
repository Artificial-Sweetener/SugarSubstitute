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

"""Render the Comfy environment planned-changes queue."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import (
    ApplicationMessage,
    app_text,
)

from sugarsubstitute_shared.presentation.localization import (
    set_localized_text,
    set_localized_tooltip,
)
from substitute.presentation.localization import (
    LocalizedPrimaryPushButton,
    LocalizedPushButton,
    LocalizedStrongBodyLabel,
)

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QBoxLayout,
    QFrame,
    QHBoxLayout,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    CaptionLabel,
    FluentIcon,
    InfoBadge,
    ListWidget,
    StrongBodyLabel,
    TransparentToolButton,
)

from substitute.application.comfy_environment import (
    ComfyMaintenancePlan,
    ComfyMaintenancePlanItem,
)
from sugarsubstitute_shared.presentation.localization import (
    translate_application_message,
    translate_application_text,
)

_PLAN_ITEM_ID_ROLE = Qt.ItemDataRole.UserRole
_PLAN_GROUP_ID_ROLE = Qt.ItemDataRole.UserRole + 1
_PLAN_GROUP_IDS_ROLE = Qt.ItemDataRole.UserRole + 2
_PLAN_LINKED_ROLE = Qt.ItemDataRole.UserRole + 3
_PLAN_ROW_HEIGHT = 44
_PLAN_LINKED_ROW_HEIGHT = 40
_LINKED_ACTION_INDENT = 30


class PlanQueueItemWidget(QWidget):
    """Render one compact planned maintenance item row."""

    remove_requested = Signal(str)
    move_up_requested = Signal(str)
    move_down_requested = Signal(str)

    def __init__(
        self,
        item: ComfyMaintenancePlanItem,
        *,
        linked: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        """Build one queue row for a backend-owned plan item."""

        super().__init__(parent)
        self._item = item
        self._linked = linked
        self._build_ui()

    def _build_ui(self) -> None:
        """Build row labels and mouse controls."""

        layout = QHBoxLayout(self)
        left_margin = _LINKED_ACTION_INDENT if self._linked else 6
        layout.setContentsMargins(left_margin, 2, 6, 2)
        layout.setSpacing(6)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(4)
        self.title_label = StrongBodyLabel(self._item.title, self)
        title_row.addWidget(self.title_label)
        self.badges = _badges_for_item(self._item, self, linked=self._linked)
        for badge in self.badges:
            title_row.addWidget(badge)
        title_row.addStretch(1)
        self.target_label = CaptionLabel(_target_summary(self._item), self)
        self.target_label.setWordWrap(True)
        text_layout.addLayout(title_row)
        if self.target_label.text():
            text_layout.addWidget(self.target_label)
        else:
            self.target_label.hide()
        layout.addLayout(text_layout)

        self.move_up_button = TransparentToolButton(FluentIcon.UP, self)
        set_localized_tooltip(self.move_up_button, "Move up")
        self.move_up_button.setEnabled(self._item.can_reorder and not self._linked)
        self.move_up_button.setFixedSize(24, 24)
        self.move_up_button.clicked.connect(
            lambda: self.move_up_requested.emit(self._item.item_id)
        )
        self.move_down_button = TransparentToolButton(FluentIcon.DOWN, self)
        set_localized_tooltip(self.move_down_button, "Move down")
        self.move_down_button.setEnabled(self._item.can_reorder and not self._linked)
        self.move_down_button.setFixedSize(24, 24)
        self.move_down_button.clicked.connect(
            lambda: self.move_down_requested.emit(self._item.item_id)
        )
        self.remove_button = TransparentToolButton(FluentIcon.DELETE, self)
        remove_tooltip = _remove_tooltip(self._item)
        set_localized_tooltip(
            self.remove_button,
            remove_tooltip.source_text,
            *remove_tooltip.arguments,
        )
        self.remove_button.setEnabled(self._item.can_remove and not self._linked)
        self.remove_button.setFixedSize(24, 24)
        self.remove_button.clicked.connect(
            lambda: self.remove_requested.emit(self._item.item_id)
        )
        if self._linked:
            self.move_up_button.hide()
            self.move_down_button.hide()
            self.remove_button.hide()
        else:
            layout.addWidget(self.move_up_button)
            layout.addWidget(self.move_down_button)
            layout.addWidget(self.remove_button)
        self.setFixedHeight(
            _PLAN_LINKED_ROW_HEIGHT if self._linked else _PLAN_ROW_HEIGHT
        )
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Retranslate derived app copy while retaining backend-authored row text."""

        super().changeEvent(event)
        if event.type() != QEvent.Type.LanguageChange:
            return
        self.target_label.setText(_target_summary(self._item))
        self.target_label.setVisible(bool(self.target_label.text()))


class PlannedChangesPanel(QFrame):
    """Display and edit the backend-owned maintenance plan."""

    remove_item_requested = Signal(str)
    reorder_requested = Signal(object)
    clear_requested = Signal()
    apply_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the planned changes panel."""

        super().__init__(parent)
        self._plan: ComfyMaintenancePlan | None = None
        self._items_by_id: dict[str, ComfyMaintenancePlanItem] = {}
        self._rendering = False
        self._build_ui()

    def render_plan(self, plan: ComfyMaintenancePlan | None) -> None:
        """Render the current backend-owned maintenance plan."""

        self._plan = plan
        self._items_by_id = (
            {item.item_id: item for item in plan.items} if plan is not None else {}
        )
        self._rendering = True
        self.plan_list.clear()
        if plan is None:
            self.summary_label.setText("")
            self.validation_label.setText("")
            self.empty_label.setText("")
            self.empty_label.hide()
            self.selected_detail_label.hide()
            self.plan_list.hide()
            self.apply_button.setEnabled(False)
            self.clear_button.setEnabled(False)
            self._rendering = False
            return
        self.summary_label.setText(_plan_summary_text(plan))
        self.summary_label.setVisible(bool(self.summary_label.text()))
        self.validation_label.setText("")
        self.apply_button.setEnabled(plan.summary.applyable)
        self.clear_button.setEnabled(bool(plan.items))
        if plan.items:
            self.empty_label.hide()
            self.plan_list.show()
            for group in _group_plan_items(plan.items):
                self._add_group_items(group)
            self.plan_list.setCurrentRow(0)
            self.selected_detail_label.hide()
        else:
            self.plan_list.hide()
            set_localized_text(self.empty_label, "No changes planned.")
            self.empty_label.show()
            self.selected_detail_label.hide()
        self._rendering = False

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Retranslate derived plan summary without rebuilding backend-owned rows."""

        super().changeEvent(event)
        if event.type() == QEvent.Type.LanguageChange and self._plan is not None:
            self.summary_label.setText(_plan_summary_text(self._plan))

    def item_ids(self) -> tuple[str, ...]:
        """Return the queue item IDs in rendered order."""

        ids: list[str] = []
        for row in range(self.plan_list.count()):
            item = self.plan_list.item(row)
            item_id = item.data(_PLAN_ITEM_ID_ROLE)
            if isinstance(item_id, str):
                ids.append(item_id)
        return tuple(ids)

    def set_compact_width_mode(self, compact: bool) -> None:
        """Apply width-contended layout for the owning Settings page."""

        self.setMinimumWidth(0 if compact else 280)
        self._action_row.setDirection(
            QBoxLayout.Direction.TopToBottom
            if compact
            else QBoxLayout.Direction.LeftToRight
        )

    def group_ids(self) -> tuple[str, ...]:
        """Return the root plan item IDs in rendered group order."""

        ids: list[str] = []
        for row in range(self.plan_list.count()):
            item = self.plan_list.item(row)
            if item.data(_PLAN_LINKED_ROLE) is True:
                continue
            group_id = item.data(_PLAN_GROUP_ID_ROLE)
            if isinstance(group_id, str):
                ids.append(group_id)
        return tuple(ids)

    def _build_ui(self) -> None:
        """Build panel widgets and wire local controls."""

        self.setObjectName("comfyEnvironmentPlannedChangesPanel")
        self.setMinimumWidth(280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        self.title_label = LocalizedStrongBodyLabel(app_text("Planned changes"), self)
        header.addWidget(self.title_label)
        header.addStretch(1)
        layout.addLayout(header)

        self.summary_label = CaptionLabel("", self)
        self.summary_label.setWordWrap(True)
        self.validation_label = CaptionLabel("", self)
        self.validation_label.setWordWrap(True)
        self.summary_label.hide()
        self.validation_label.hide()

        self.empty_label = CaptionLabel("", self)
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.empty_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.empty_label.hide()
        layout.addWidget(self.summary_label)
        layout.addWidget(self.validation_label)
        layout.addWidget(self.empty_label)

        self.plan_list = ListWidget(self)
        self.plan_list.setObjectName("comfyEnvironmentPlanList")
        self.plan_list.setSpacing(0)
        self.plan_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.plan_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.plan_list.setDragDropOverwriteMode(False)
        self.plan_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.plan_list.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.plan_list.model().rowsMoved.connect(
            lambda *_args: self._emit_rendered_reorder()
        )
        layout.addWidget(self.plan_list, 1)

        self.selected_detail_label = CaptionLabel("", self)
        self.selected_detail_label.setWordWrap(True)
        self.selected_detail_label.hide()

        self._action_row = QHBoxLayout()
        self._action_row.setContentsMargins(0, 0, 0, 0)
        self._action_row.setSpacing(8)
        self.apply_button = LocalizedPrimaryPushButton(
            app_text("Apply planned changes"), self
        )
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self._emit_apply)
        self.clear_button = LocalizedPushButton(app_text("Clear"), self)
        self.clear_button.setEnabled(False)
        self.clear_button.clicked.connect(self.clear_requested.emit)
        self._action_row.addWidget(self.apply_button)
        self._action_row.addWidget(self.clear_button)
        layout.addLayout(self._action_row)

    def _add_group_items(
        self,
        group: tuple[ComfyMaintenancePlanItem, tuple[ComfyMaintenancePlanItem, ...]],
    ) -> None:
        """Add one parent action and its linked action rows to the queue list."""

        parent_item, linked_items = group
        group_item_ids = (
            parent_item.item_id,
            *(item.item_id for item in linked_items),
        )
        self._add_item(parent_item, parent_item.item_id, group_item_ids, linked=False)
        for linked_item in linked_items:
            self._add_item(
                linked_item, parent_item.item_id, group_item_ids, linked=True
            )

    def _add_item(
        self,
        item: ComfyMaintenancePlanItem,
        group_id: str,
        group_item_ids: tuple[str, ...],
        *,
        linked: bool,
    ) -> None:
        """Add one visible row to the queue list."""

        row_widget = PlanQueueItemWidget(item, linked=linked, parent=self.plan_list)
        row_widget.remove_requested.connect(self.remove_item_requested)
        row_widget.move_up_requested.connect(self._move_item_up)
        row_widget.move_down_requested.connect(self._move_item_down)
        list_item = QListWidgetItem()
        list_item.setData(_PLAN_ITEM_ID_ROLE, item.item_id)
        list_item.setData(_PLAN_GROUP_ID_ROLE, group_id)
        list_item.setData(_PLAN_GROUP_IDS_ROLE, group_item_ids)
        list_item.setData(_PLAN_LINKED_ROLE, linked)
        list_item.setSizeHint(
            QSize(0, _PLAN_LINKED_ROW_HEIGHT if linked else _PLAN_ROW_HEIGHT)
        )
        if linked:
            list_item.setFlags(
                list_item.flags()
                & ~Qt.ItemFlag.ItemIsDragEnabled
                & ~Qt.ItemFlag.ItemIsDropEnabled
            )
        self.plan_list.addItem(list_item)
        self.plan_list.setItemWidget(list_item, row_widget)

    def _emit_rendered_reorder(self) -> None:
        """Emit a reorder request after user-driven drag movement."""

        if self._rendering or self._plan is None:
            return
        item_ids = _flatten_group_order(self.group_ids(), self._plan.items)
        if item_ids:
            self.reorder_requested.emit(item_ids)

    def _move_item_up(self, item_id: str) -> None:
        """Request moving one action group up."""

        self._emit_requested_group_order(_move_id(self.group_ids(), item_id, -1))

    def _move_item_down(self, item_id: str) -> None:
        """Request moving one action group down."""

        self._emit_requested_group_order(_move_id(self.group_ids(), item_id, 1))

    def _emit_requested_group_order(self, group_ids: tuple[str, ...]) -> None:
        """Emit a proposed flattened order from root group IDs."""

        if self._plan is None or group_ids == self.group_ids():
            return
        self.reorder_requested.emit(_flatten_group_order(group_ids, self._plan.items))

    def _emit_apply(self) -> None:
        """Request applying the current backend plan revision."""

        if self._plan is not None:
            self.apply_requested.emit(self._plan.revision)


def _target_summary(item: ComfyMaintenancePlanItem) -> str:
    """Return compact affected-package text for one row."""

    if (
        item.install_requirements
        and item.install_requirements != item.affected_packages
    ):
        return translate_application_message(
            "%1 from %2",
            ", ".join(item.affected_packages),
            ", ".join(item.install_requirements),
        )
    if len(item.affected_packages) == 1:
        package_name = item.affected_packages[0]
        if package_name.casefold() in item.title.casefold():
            return ""
    return ", ".join(item.affected_packages) or item.target.display_name


def _plan_summary_text(plan: ComfyMaintenancePlan) -> str:
    """Return compact queue status text for the plan header."""

    if not plan.items:
        return ""
    change_text = (
        translate_application_text("1 change planned")
        if len(plan.items) == 1
        else translate_application_message("%1 changes planned", len(plan.items))
    )
    if plan.summary.applyable:
        return change_text
    if plan.blockers:
        return translate_application_message(
            "%1; blocked until issues are resolved.",
            change_text,
        )
    return change_text


def _group_plan_items(
    items: tuple[ComfyMaintenancePlanItem, ...],
) -> tuple[tuple[ComfyMaintenancePlanItem, tuple[ComfyMaintenancePlanItem, ...]], ...]:
    """Return root items grouped with backend-generated linked actions."""

    items_by_id = {item.item_id: item for item in items}
    children_by_parent: dict[str, list[ComfyMaintenancePlanItem]] = {}
    for item in items:
        if item.generated_by_item_id is not None:
            children_by_parent.setdefault(item.generated_by_item_id, []).append(item)

    groups: list[
        tuple[ComfyMaintenancePlanItem, tuple[ComfyMaintenancePlanItem, ...]]
    ] = []
    grouped_ids: set[str] = set()
    for item in items:
        if (
            item.generated_by_item_id is not None
            and item.generated_by_item_id in items_by_id
        ):
            continue
        linked_items = tuple(children_by_parent.get(item.item_id, ()))
        groups.append((item, linked_items))
        grouped_ids.add(item.item_id)
        grouped_ids.update(linked.item_id for linked in linked_items)

    for item in items:
        if item.item_id not in grouped_ids:
            groups.append((item, ()))
    return tuple(groups)


def _flatten_group_order(
    group_ids: tuple[str, ...],
    items: tuple[ComfyMaintenancePlanItem, ...],
) -> tuple[str, ...]:
    """Return backend item order from a proposed root group order."""

    groups_by_id = {
        parent.item_id: (parent, linked) for parent, linked in _group_plan_items(items)
    }
    ordered: list[str] = []
    for group_id in group_ids:
        group = groups_by_id.get(group_id)
        if group is None:
            continue
        parent, linked_items = group
        ordered.append(parent.item_id)
        ordered.extend(item.item_id for item in linked_items)
    return tuple(ordered)


def _coerce_item_ids(value: object) -> tuple[str, ...]:
    """Return item IDs from Qt item data."""

    if isinstance(value, str):
        return (value,)
    if isinstance(value, tuple) and all(isinstance(item_id, str) for item_id in value):
        return value
    if isinstance(value, list) and all(isinstance(item_id, str) for item_id in value):
        return tuple(value)
    return ()


def _badges_for_item(
    item: ComfyMaintenancePlanItem,
    parent: QWidget,
    *,
    linked: bool = False,
) -> tuple[InfoBadge, ...]:
    """Return compact state badges for one queue row."""

    badges: list[InfoBadge] = []
    if item.generated and not linked:
        badges.append(
            _configured_badge(
                app_text("Req"), parent, tooltip=app_text("Required action")
            )
        )
    if item.blockers:
        badge = InfoBadge.error("", parent)
        _bind_badge_text(badge, app_text("Blocked"))
        badges.append(badge)
    return tuple(badges)


def _configured_badge(
    text: ApplicationMessage,
    parent: QWidget,
    *,
    tooltip: ApplicationMessage | None = None,
) -> InfoBadge:
    """Return one compact informational badge."""

    badge = InfoBadge.info("", parent)
    _bind_badge_text(badge, text)
    if tooltip is not None:
        set_localized_tooltip(badge, tooltip.source_text, *tooltip.arguments)
    return badge


def _bind_badge_text(badge: InfoBadge, text: ApplicationMessage) -> None:
    """Bind badge copy and recompute its compact width after translation."""

    def apply_text(translated: str) -> None:
        """Apply one translated badge value without clipping it."""

        badge.setText(translated)
        _configure_badge(badge)

    set_localized_text(
        badge,
        text.source_text,
        *text.arguments,
        property_setter=apply_text,
    )


def _configure_badge(badge: InfoBadge) -> None:
    """Prevent QFluent badges from expanding into wide bars."""

    text_width = badge.fontMetrics().horizontalAdvance(badge.text())
    badge.setFixedWidth(max(22, text_width + 18))
    badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


def _remove_tooltip(item: ComfyMaintenancePlanItem) -> ApplicationMessage:
    """Return remove tooltip text for one item."""

    if item.can_remove:
        return app_text("Remove from plan")
    return app_text("Required by another planned change")


def _move_id(
    item_ids: tuple[str, ...],
    item_id: str,
    offset: int,
) -> tuple[str, ...]:
    """Return item ids with one id moved by offset."""

    ids = list(item_ids)
    if item_id not in ids:
        return item_ids
    index = ids.index(item_id)
    target_index = index + offset
    if target_index < 0 or target_index >= len(ids):
        return item_ids
    ids[index], ids[target_index] = ids[target_index], ids[index]
    return tuple(ids)
