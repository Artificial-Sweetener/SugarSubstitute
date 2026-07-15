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

"""Construct panel meta widgets and synchronize prompt/scheduler link controls."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping, Sequence

from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import SwitchButton  # type: ignore[import-untyped]
from shiboken6 import isValid

from substitute.application.node_behavior import NodeDisplayDecision
from substitute.application.overrides import ChoiceLinkFieldState
from substitute.application.ports import NodeDefinitionGateway
from substitute.application.overrides import link_policy as _link_policy
from substitute.application.workflows import (
    NodeLinkEndpoint,
    NodeLinkEndpointIndex,
    NodeLinkIdentity,
)
from substitute.presentation.widgets import LinkSelectorComboBox
from substitute.shared.logging.logger import get_logger, log_warning

apply_choice_selection = _link_policy.apply_choice_selection
build_sampler_choice_items = _link_policy.build_sampler_choice_items
build_scheduler_choice_items = _link_policy.build_scheduler_choice_items
resolve_linked_choice_label = _link_policy.resolve_linked_choice_label
sanitize_sampler_link_selection = _link_policy.sanitize_sampler_link_selection
sanitize_scheduler_link_selection = _link_policy.sanitize_scheduler_link_selection
update_prompt_link_references_on_rename = (
    _link_policy.update_prompt_link_references_on_rename
)
update_sampler_link_references_on_rename = (
    _link_policy.update_sampler_link_references_on_rename
)
update_scheduler_link_references_on_rename = (
    _link_policy.update_scheduler_link_references_on_rename
)

_LOGGER = get_logger("presentation.editor.panel.factories.meta_factories")


@dataclass(frozen=True, slots=True)
class NodeLinkComboContext:
    """Carry panel-owned node-link state needed by selector construction."""

    ordered_aliases: Sequence[str]
    apply_manual_node_link_selection: Callable[
        [str, NodeLinkIdentity, str | None, str | None],
        None,
    ]
    notify_node_link_changed: Callable[[], None] | None = None


def _shared_width_for_labels(
    combo: LinkSelectorComboBox,
    labels: Sequence[str],
) -> int | None:
    """Return the preferred control width for labels using combo font metrics."""

    if not labels:
        return None
    longest_text_width = max(
        combo.fontMetrics().horizontalAdvance(label) for label in labels
    )
    return combo._closed_display_control_width_for_text_width(longest_text_width)


def _apply_shared_width_labels(
    combo: LinkSelectorComboBox,
    labels: Sequence[str] | None,
) -> None:
    """Apply shared width labels as a preferred widget width when supplied."""

    if labels is None:
        return
    combo.setSharedPreferredWidth(_shared_width_for_labels(combo, labels))


def setup_node_link_combobox(
    parent: Any,
    node_link_widgets: MutableMapping[tuple[str, object], Any],
    endpoint: NodeLinkEndpoint,
    endpoint_index: NodeLinkEndpointIndex,
    all_buffers: Mapping[str, Mapping[str, Any]],
    title_layout: Any,
    beautify_label_func: Any,
    *,
    shared_width_labels: Sequence[str] | None = None,
    node_definition_gateway: NodeDefinitionGateway | None = None,
    link_context: NodeLinkComboContext | None = None,
) -> tuple[Any, str | None]:
    """Create or refresh a generic whole-node link ComboBox for one endpoint."""

    _ = (beautify_label_func, node_definition_gateway)
    ordered_aliases = (
        list(link_context.ordered_aliases)
        if link_context is not None
        else list(all_buffers)
    )
    first_endpoint = None
    for alias in ordered_aliases:
        candidate = endpoint_index.endpoint_for(alias, endpoint.identity)
        if candidate is not None:
            first_endpoint = candidate
            break
    first_cube = first_endpoint.cube_alias if first_endpoint is not None else None
    combo_key = (endpoint.cube_alias, endpoint.identity)
    label_map: dict[str, NodeLinkEndpoint] = {}

    def on_combo_change(text: str, ca: str = endpoint.cube_alias) -> None:
        if not all_buffers[ca]:
            return
        current_endpoint = endpoint_index.endpoint_for(ca, endpoint.identity)
        if current_endpoint is None:
            return
        if text == "Independent":
            if link_context is None:
                return
            link_context.apply_manual_node_link_selection(
                ca,
                endpoint.identity,
                None,
                None,
            )
        elif text in label_map:
            target = label_map[text]
            if link_context is None:
                return
            link_context.apply_manual_node_link_selection(
                ca,
                endpoint.identity,
                target.cube_alias,
                target.node_name,
            )
        if link_context.notify_node_link_changed is not None:
            link_context.notify_node_link_changed()

    combo_created = False
    reuse_existing = (
        combo_key in node_link_widgets
        and node_link_widgets[combo_key] is not None
        and isValid(node_link_widgets[combo_key])
    )
    if reuse_existing:
        combo = node_link_widgets[combo_key]
        try:
            combo.currentTextChanged.disconnect()
        except (RuntimeError, TypeError) as error:
            log_warning(
                _LOGGER,
                "Failed to disconnect existing node-link change handler",
                cube_alias=endpoint.cube_alias,
                node_name=endpoint.node_name,
                error_type=type(error).__name__,
            )
    else:
        combo = LinkSelectorComboBox(parent)
        node_link_widgets[combo_key] = combo
        combo_created = True

    _apply_shared_width_labels(combo, shared_width_labels)

    if combo is not None and isValid(combo):
        combo.currentTextChanged.connect(on_combo_change)
    else:
        return None, first_cube

    combo.blockSignals(True)
    combo.clear()
    combo.addItem("Independent")
    valid_options = endpoint_index.valid_link_targets(
        ordered_aliases,
        endpoint.cube_alias,
        endpoint.identity,
    )
    for target_endpoint in valid_options:
        label = f"🔗 {target_endpoint.cube_alias}"
        label_map[label] = target_endpoint
        combo.addItem(label)

    node_buf = (
        all_buffers.get(endpoint.cube_alias, {})
        .get("nodes", {})
        .get(endpoint.node_name)
    )
    link_cfg = node_buf.get("node_link", {}) if isinstance(node_buf, Mapping) else {}
    target_cube = link_cfg.get("from_cube") if isinstance(link_cfg, Mapping) else None
    valid_aliases = {target_endpoint.cube_alias for target_endpoint in valid_options}
    if target_cube and target_cube in valid_aliases:
        combo.setCurrentText(f"🔗 {target_cube}")
    else:
        combo.setCurrentIndex(0)

    combo.blockSignals(False)

    if combo_created:
        title_layout.addWidget(combo)
    hidden_reason = None
    if endpoint.cube_alias == first_cube:
        hidden_reason = "first_endpoint"
    elif not valid_options:
        hidden_reason = "no_valid_options"
    if hidden_reason is not None:
        combo.hide()
    else:
        combo.show()
    return combo, first_cube


def _setup_choice_link_combobox(
    *,
    link_widgets: Mapping[tuple[str, str], Any],
    cube_alias: str,
    node_name: str,
    all_buffers: Mapping[str, Mapping[str, Any]],
    literal_key: str,
    link_key: str,
    choice_builder: Any,
    field_state: ChoiceLinkFieldState | None,
) -> None:
    """Refresh one linked choice combobox using shared domain choice helpers."""

    combo_key = (cube_alias, node_name)
    node_buf = all_buffers.get(cube_alias, {}).get("nodes", {}).get(node_name, None)
    if not isinstance(node_buf, dict):
        return

    combo = link_widgets.get(combo_key)
    if combo is None or not isValid(combo):
        return

    if field_state is None:
        log_warning(
            _LOGGER,
            "Skipped value-link combobox refresh without resolved field state",
            cube_alias=cube_alias,
            node_name=node_name,
            field_key=literal_key,
        )
        _set_combo_enabled(combo, False)
        return

    if not field_state.options_resolved:
        log_warning(
            _LOGGER,
            "Skipped value-link combobox refresh without authoritative options",
            cube_alias=cube_alias,
            node_name=node_name,
            field_key=literal_key,
            link_key=link_key,
            class_type=repr(node_buf.get("class_type")),
            active_link=repr(node_buf.get(link_key)),
        )
        _set_combo_enabled(combo, False)
        return

    _set_combo_enabled(combo, True)
    if literal_key == "sampler_name":
        choice_node_data = {"sampler_links": field_state.link_target_mappings()}
    else:
        choice_node_data = {"scheduler_links": field_state.link_target_mappings()}
    choice_items = choice_builder(choice_node_data, field_state.literal_options)
    combo.blockSignals(True)
    combo.clear()
    combo.addItems([label for label, _ in choice_items])

    link_value = node_buf.get(link_key)
    selected_label = resolve_linked_choice_label(choice_items, link_value)
    if selected_label is None:
        current_value = node_buf.get("inputs", {}).get(literal_key)
        for label, value in choice_items:
            if value == current_value:
                selected_label = label
                break

    if selected_label is None and field_state.literal_options:
        selected_label = field_state.literal_options[0]
        apply_choice_selection(
            node_buf,
            literal_key=literal_key,
            link_key=link_key,
            selected_value=selected_label,
        )
    elif selected_label is None and choice_items:
        selected_label = choice_items[0][0]

    if selected_label is not None:
        combo.setCurrentText(selected_label)
    else:
        combo.setCurrentIndex(0)
    combo.blockSignals(False)


def _set_combo_enabled(combo: Any, enabled: bool) -> None:
    """Set combo enabled state when the test or Qt object exposes that API."""

    try:
        combo.setEnabled(enabled)
    except AttributeError:
        return


def setup_sampler_link_combobox(
    parent: Any,
    sampler_link_widgets: Mapping[tuple[str, str], Any],
    cube_alias: str,
    node_name: str,
    all_buffers: Mapping[str, Mapping[str, Any]],
    title_layout: Any | None = None,
    *,
    node_definition_gateway: NodeDefinitionGateway | None = None,
    field_state: ChoiceLinkFieldState | None = None,
) -> None:
    """Refresh the sampler combobox contents and selection for one node."""

    _ = (parent, title_layout, node_definition_gateway)
    _setup_choice_link_combobox(
        link_widgets=sampler_link_widgets,
        cube_alias=cube_alias,
        node_name=node_name,
        all_buffers=all_buffers,
        literal_key="sampler_name",
        link_key="sampler_link",
        choice_builder=build_sampler_choice_items,
        field_state=field_state,
    )


def setup_scheduler_link_combobox(
    parent: Any,
    scheduler_link_widgets: Mapping[tuple[str, str], Any],
    cube_alias: str,
    node_name: str,
    all_buffers: Mapping[str, Mapping[str, Any]],
    title_layout: Any | None = None,
    *,
    node_definition_gateway: NodeDefinitionGateway | None = None,
    field_state: ChoiceLinkFieldState | None = None,
) -> None:
    """Refresh the scheduler combobox contents and selection for one node."""

    _ = (parent, title_layout, node_definition_gateway)
    _setup_choice_link_combobox(
        link_widgets=scheduler_link_widgets,
        cube_alias=cube_alias,
        node_name=node_name,
        all_buffers=all_buffers,
        literal_key="scheduler",
        link_key="scheduler_link",
        choice_builder=build_scheduler_choice_items,
        field_state=field_state,
    )


def build_enabled_switch(
    parent: Any,
    cube_alias: str | None,
    node_name: str,
    cube_state: Any,
    display_decision: NodeDisplayDecision,
    *,
    checked_changed_callback: Callable[[bool], None] | None = None,
) -> QWidget:
    """Construct an activation switch from prepared node display state."""

    _ = cube_state
    switch = SwitchButton(parent, indicatorPos=1)
    switch.setChecked(bool(display_decision.enabled))
    switch.setProperty(
        "input_metadata",
        {"cube_alias": cube_alias, "node_name": node_name, "key": "enabled"},
    )

    def on_checked_changed(checked: bool) -> None:
        """Forward one user-issued activation toggle to the owner callback."""

        if checked_changed_callback is None:
            return
        checked_changed_callback(checked)

    switch.checkedChanged.connect(on_checked_changed)

    # Optionally, wrap in a container for padding
    switch_wrapper = QWidget(parent)
    wrapper_layout = QHBoxLayout(switch_wrapper)
    wrapper_layout.setContentsMargins(0, 0, 8, 0)  # right padding
    wrapper_layout.setSpacing(0)
    wrapper_layout.addWidget(switch)
    setattr(switch_wrapper, "_enabled_switch_widget", switch)

    return switch_wrapper


__all__ = [
    "build_enabled_switch",
    "NodeLinkComboContext",
    "sanitize_sampler_link_selection",
    "sanitize_scheduler_link_selection",
    "setup_node_link_combobox",
    "setup_sampler_link_combobox",
    "setup_scheduler_link_combobox",
    "update_prompt_link_references_on_rename",
    "update_sampler_link_references_on_rename",
    "update_scheduler_link_references_on_rename",
]
