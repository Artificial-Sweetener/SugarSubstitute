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

"""Own rendered editor field identity, bindings, and widget lifecycle."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from typing import TypeAlias

from .field_state_controller import EditorFieldBinding

EditorFieldIdentity: TypeAlias = tuple[str, str, str]


@dataclass(frozen=True, slots=True)
class RegisteredEditorField:
    """Associate one rendered widget with its application field binding."""

    identity: EditorFieldIdentity
    binding: EditorFieldBinding
    widget: object


class EditorFieldRegistry:
    """Provide one authoritative index for rendered editor fields."""

    def __init__(self) -> None:
        """Initialize empty identity and node-class indexes."""

        self._entries: dict[EditorFieldIdentity, RegisteredEditorField] = {}
        self._identities_by_node_class: dict[str, set[EditorFieldIdentity]] = {}
        self._widget_map: dict[EditorFieldIdentity, object] = {}

    @property
    def widget_map(self) -> dict[EditorFieldIdentity, object]:
        """Return the compatibility widget mapping owned by this registry."""

        return self._widget_map

    def register(self, binding: EditorFieldBinding, widget: object) -> None:
        """Register one fully identified rendered field."""

        identity = self._identity_for_binding(binding)
        if identity is None:
            return
        self.unregister(identity)
        entry = RegisteredEditorField(identity=identity, binding=binding, widget=widget)
        self._entries[identity] = entry
        self._widget_map[identity] = widget
        if binding.node_type:
            self._identities_by_node_class.setdefault(binding.node_type, set()).add(
                identity
            )

    def update_binding(
        self,
        identity: EditorFieldIdentity,
        binding: EditorFieldBinding,
    ) -> None:
        """Replace one field binding while preserving its widget identity."""

        entry = self._entries.get(identity)
        if entry is None:
            return
        self.register(binding, entry.widget)

    def entry(self, identity: EditorFieldIdentity) -> RegisteredEditorField | None:
        """Return one registered field by exact identity."""

        return self._entries.get(identity)

    def entries(self) -> tuple[RegisteredEditorField, ...]:
        """Return all registered fields in deterministic identity order."""

        return tuple(self._entries[key] for key in sorted(self._entries))

    def entries_for_node_classes(
        self,
        node_classes: Iterable[str],
    ) -> tuple[RegisteredEditorField, ...]:
        """Return fields whose bindings belong to selected node classes."""

        identities: set[EditorFieldIdentity] = set()
        for node_class in node_classes:
            identities.update(self._identities_by_node_class.get(node_class, ()))
        return tuple(self._entries[key] for key in sorted(identities))

    def unregister(self, identity: EditorFieldIdentity) -> bool:
        """Remove one field from every registry index."""

        entry = self._entries.pop(identity, None)
        self._widget_map.pop(identity, None)
        if entry is None:
            return False
        node_type = entry.binding.node_type
        if node_type:
            identities = self._identities_by_node_class.get(node_type)
            if identities is not None:
                identities.discard(identity)
                if not identities:
                    self._identities_by_node_class.pop(node_type, None)
        return True

    def remove_node(self, cube_alias: str, node_name: str) -> int:
        """Remove every rendered field owned by one node card."""

        return self._remove_matching(
            lambda identity: identity[0] == cube_alias and identity[1] == node_name
        )

    def remove_cube(self, cube_alias: str) -> int:
        """Remove every rendered field owned by one cube section."""

        return self._remove_matching(lambda identity: identity[0] == cube_alias)

    def rename_cube(self, old_alias: str, new_alias: str) -> None:
        """Migrate field identities, bindings, and Qt metadata to a new alias."""

        migrating = tuple(
            entry for entry in self.entries() if entry.identity[0] == old_alias
        )
        for entry in migrating:
            self.unregister(entry.identity)
        for entry in migrating:
            self._rewrite_widget_alias_metadata(entry.widget, old_alias, new_alias)
            self.register(
                replace(entry.binding, cube_alias=new_alias),
                entry.widget,
            )

    def clear(self) -> None:
        """Clear every field and secondary index in place."""

        self._entries.clear()
        self._identities_by_node_class.clear()
        self._widget_map.clear()

    def synchronize_from_widget_map(
        self,
        widgets: Mapping[EditorFieldIdentity, object],
    ) -> None:
        """Adopt legacy mapping entries through typed widget metadata."""

        self.clear()
        for widget in widgets.values():
            binding = EditorFieldBinding.from_widget(widget)
            if binding is not None:
                self.register(binding, widget)

    def _remove_matching(
        self,
        predicate: Callable[[EditorFieldIdentity], bool],
    ) -> int:
        """Remove identities accepted by one internal predicate."""

        identities = [identity for identity in self._entries if predicate(identity)]
        for identity in identities:
            self.unregister(identity)
        return len(identities)

    @staticmethod
    def _identity_for_binding(
        binding: EditorFieldBinding,
    ) -> EditorFieldIdentity | None:
        """Return a complete registry identity for one binding."""

        if not binding.cube_alias or not binding.node_name:
            return None
        return (binding.cube_alias, binding.node_name, binding.field_key)

    @staticmethod
    def _rewrite_widget_alias_metadata(
        widget: object,
        old_alias: str,
        new_alias: str,
    ) -> None:
        """Keep Qt field metadata aligned with an alias migration."""

        property_getter = getattr(widget, "property", None)
        set_property = getattr(widget, "setProperty", None)
        if not callable(property_getter) or not callable(set_property):
            return
        metadata = property_getter("input_metadata")
        if not isinstance(metadata, dict) or metadata.get("cube_alias") != old_alias:
            return
        updated_metadata = dict(metadata)
        updated_metadata["cube_alias"] = new_alias
        set_property("input_metadata", updated_metadata)


__all__ = [
    "EditorFieldIdentity",
    "EditorFieldRegistry",
    "RegisteredEditorField",
]
