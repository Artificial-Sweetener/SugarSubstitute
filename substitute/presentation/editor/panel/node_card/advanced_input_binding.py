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

"""Bind advanced-input visibility state to one production node card."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.application.node_behavior import (
    AdvancedInputStateService,
    ResolvedFieldSpec,
)
from substitute.presentation.editor.panel.node_card.body_layout import (
    apply_card_body_layout_state,
    ensure_card_body_layout_state,
    resolve_card_body_expanded_height,
)
from substitute.presentation.editor.panel.node_card.accordion_motion import (
    set_accordion_surface_attachment,
)


class AdvancedInputCardBinding(QObject):
    """Own one card's advanced registry state and geometry refresh."""

    @classmethod
    def create(
        cls,
        *,
        panel: object,
        wrapper: QWidget,
        card_surface: QWidget,
        content_body: QWidget,
        content_layout: QVBoxLayout,
        editor_state: object,
        alias: str | None,
        node_name: str,
        field_specs: Mapping[str, ResolvedFieldSpec],
        allow_unbounded_height: bool,
    ) -> AdvancedInputCardBinding | None:
        """Create a binding only when at least one advanced field rendered."""

        if alias is None:
            return None
        advanced_identities = {
            (alias, node_name, field_key)
            for field_key, field_spec in field_specs.items()
            if field_spec.is_advanced
            and cls._field_rendered(panel, (alias, node_name, field_key))
        }
        if not advanced_identities:
            return None
        return cls(
            panel=panel,
            wrapper=wrapper,
            card_surface=card_surface,
            content_body=content_body,
            content_layout=content_layout,
            editor_state=editor_state,
            node_identity=(alias, node_name),
            advanced_field_identities=advanced_identities,
            allow_unbounded_height=allow_unbounded_height,
        )

    def __init__(
        self,
        *,
        panel: object,
        wrapper: QWidget,
        card_surface: QWidget,
        content_body: QWidget,
        content_layout: QVBoxLayout,
        editor_state: object,
        node_identity: tuple[str, str],
        advanced_field_identities: set[tuple[str, str, str]],
        allow_unbounded_height: bool,
    ) -> None:
        """Publish field identities and apply the persisted visibility state."""

        super().__init__(wrapper)
        self._panel = panel
        self._wrapper = wrapper
        self._card_surface = card_surface
        self._content_body = content_body
        self._content_layout = content_layout
        self._editor_state = editor_state
        self._node_identity = node_identity
        self._advanced_field_identities = advanced_field_identities
        self._allow_unbounded_height = allow_unbounded_height
        self._title_row: QWidget | None = None
        self._state_service = AdvancedInputStateService()
        shown = self._state_service.is_shown(editor_state, node_identity[1])

        advanced_registry = getattr(panel, "advanced_field_keys", None)
        if not isinstance(advanced_registry, set):
            advanced_registry = set()
            setattr(panel, "advanced_field_keys", advanced_registry)
        advanced_registry.update(advanced_field_identities)
        shown_registry = getattr(panel, "shown_advanced_input_nodes", None)
        if not isinstance(shown_registry, set):
            shown_registry = set()
            setattr(panel, "shown_advanced_input_nodes", shown_registry)
        if shown:
            shown_registry.add(node_identity)

        wrapper.setProperty("has_advanced_input_action", True)
        wrapper.setProperty("show_advanced_inputs", shown)
        setattr(wrapper, "_advanced_input_binding", self)
        self._apply_visibility()

    @property
    def shown(self) -> bool:
        """Return the effective persisted disclosure state for this node."""

        return self._state_service.is_shown(
            self._editor_state,
            self._node_identity[1],
        )

    def attach_title_row(self, title_row: QWidget) -> None:
        """Attach the later-built title surface for corner-state reconciliation."""

        self._title_row = title_row
        self.reconcile_visibility()

    def reconcile_visibility(self) -> None:
        """Reconcile card and owning-cube geometry after visibility changes."""

        self._content_layout.invalidate()
        self._content_layout.activate()
        expanded_height = (
            resolve_card_body_expanded_height(
                content_layout=self._content_layout,
                allow_unbounded_height=self._allow_unbounded_height,
            )
            if self._has_visible_card_field()
            else 0
        )
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
        if self._title_row is not None:
            set_accordion_surface_attachment(
                card_title=self._title_row,
                content_body=self._content_body,
                attached=bool(
                    expanded_height > 0
                    and not state.collapsed
                    and not state.forced_collapsed
                ),
            )
        defer_width_sync = getattr(
            self._card_surface,
            "defer_model_picker_width_group_sync",
            None,
        )
        if callable(defer_width_sync):
            defer_width_sync()
        self._refresh_owner_cube_height()

    def toggle(self) -> None:
        """Persist and apply the inverse per-node disclosure state."""

        node_name = self._node_identity[1]
        shown = not self._state_service.is_shown(self._editor_state, node_name)
        self._state_service.set_shown(self._editor_state, node_name, shown)
        shown_registry = getattr(self._panel, "shown_advanced_input_nodes", None)
        if isinstance(shown_registry, set):
            if shown:
                shown_registry.add(self._node_identity)
            else:
                shown_registry.discard(self._node_identity)
        self._wrapper.setProperty("show_advanced_inputs", shown)
        self._apply_visibility()

    def _apply_visibility(self) -> None:
        """Delegate composed row visibility to the panel owner, then relayout."""

        controller = getattr(self._panel, "_field_sync_controller", None)
        apply_hidden = getattr(controller, "apply_hidden_field_keys", None)
        if callable(apply_hidden):
            hidden_keys = set(getattr(self._panel, "_hidden_field_keys", set()))
            apply_hidden(hidden_keys)
        self.reconcile_visibility()

    @staticmethod
    def _field_rendered(panel: object, identity: tuple[str, str, str]) -> bool:
        """Return whether a field created a row or grouped column surface."""

        rows = getattr(panel, "row_widgets", {})
        columns = getattr(panel, "col_widgets", {})
        return identity in rows or identity in columns

    def _has_visible_card_field(self) -> bool:
        """Return whether any registered field surface remains visible."""

        for registry_name in ("row_widgets", "col_widgets"):
            registry = getattr(self._panel, registry_name, {})
            if not isinstance(registry, Mapping):
                continue
            for identity, registration in registry.items():
                if (
                    not isinstance(identity, tuple)
                    or len(identity) < 3
                    or identity[:2] != self._node_identity
                    or not isinstance(registration, tuple)
                    or len(registration) < 2
                ):
                    continue
                surface = registration[1]
                is_hidden = getattr(surface, "isHidden", None)
                if surface is not None and callable(is_hidden) and not is_hidden():
                    return True
        return False

    def _refresh_owner_cube_height(self) -> None:
        """Ask the nearest cube section to settle after disclosure geometry changes."""

        current = self._wrapper.parentWidget()
        while current is not None:
            defer_update = getattr(current, "defer_update_cube_height", None)
            if callable(defer_update):
                defer_update()
                return
            current = current.parentWidget()


__all__ = ["AdvancedInputCardBinding"]
