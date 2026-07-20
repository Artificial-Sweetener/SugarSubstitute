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

"""Own transactional field registration for one editor node-card build."""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass
from typing import cast

from PySide6.QtWidgets import QWidget
from shiboken6 import delete

from .field_registry import EditorFieldRegistry
from .field_state_controller import EditorFieldBinding


@dataclass(frozen=True, slots=True)
class NodeCardRegistrationCleanup:
    """Report stale or partial registrations removed for one node card."""

    row_count: int = 0
    column_count: int = 0
    input_count: int = 0

    @property
    def removed_any(self) -> bool:
        """Return whether cleanup removed any published surface."""

        return bool(self.row_count or self.column_count or self.input_count)


@dataclass(frozen=True, slots=True)
class _PendingFieldRegistration:
    """Hold one field registration until the complete card is viable."""

    field_key: str
    binding: EditorFieldBinding | None
    widget: object


class NodeCardBuildTransaction:
    """Stage field registrations and roll back abandoned card surfaces."""

    def __init__(
        self,
        *,
        panel: object,
        cube_alias: str | None,
        node_name: str,
    ) -> None:
        """Bind one transaction to the card identity and its panel registries."""

        self._panel = panel
        self._cube_alias = cube_alias
        self._node_name = node_name
        self._pending: list[_PendingFieldRegistration] = []
        self._committed = False

    def replace_existing(self) -> NodeCardRegistrationCleanup:
        """Clear registrations from a preceding render of this node card."""

        self._pending.clear()
        self._committed = False
        return self._remove_published_registrations()

    def stage(self, *, field_key: str, widget: object) -> None:
        """Delay publishing one built field until its card fully succeeds."""

        if self._cube_alias is None:
            return
        if self._committed:
            raise RuntimeError("Cannot stage a field after committing its node card")
        self._pending.append(
            _PendingFieldRegistration(
                field_key=field_key,
                binding=EditorFieldBinding.from_widget(widget),
                widget=widget,
            )
        )

    def commit(self) -> None:
        """Publish every staged field atomically from the card's perspective."""

        if self._committed:
            raise RuntimeError("Cannot commit a node card more than once")
        try:
            self._publish_pending_registrations()
        except Exception:
            self._remove_published_registrations()
            self._pending.clear()
            raise
        self._pending.clear()
        self._committed = True

    def rollback(self) -> NodeCardRegistrationCleanup:
        """Remove partial surfaces and forget fields staged by a failed build."""

        self._pending.clear()
        self._committed = False
        return self._remove_published_registrations()

    def discard(self, root: QWidget | None) -> NodeCardRegistrationCleanup:
        """Roll back registrations and synchronously destroy an abandoned card."""

        cleanup = self.rollback()
        if root is None:
            return cleanup
        try:
            root.hide()
            delete(root)
        except RuntimeError:
            pass
        return cleanup

    def _publish_pending_registrations(self) -> None:
        """Publish staged fields through the authoritative registry when present."""

        if self._cube_alias is None:
            return
        field_registry = getattr(self._panel, "_field_registry", None)
        legacy_map = self._mutable_mapping(
            getattr(self._panel, "input_widgets_by_field_key", None)
        )
        for pending in self._pending:
            if (
                isinstance(field_registry, EditorFieldRegistry)
                and pending.binding is not None
            ):
                field_registry.register(pending.binding, pending.widget)
                continue
            if legacy_map is not None:
                identity = (self._cube_alias, self._node_name, pending.field_key)
                legacy_map[identity] = pending.widget

    def _remove_published_registrations(self) -> NodeCardRegistrationCleanup:
        """Remove every panel registration owned by this card identity."""

        if self._cube_alias is None:
            return NodeCardRegistrationCleanup()
        row_count = self._remove_node_field_keys(
            getattr(self._panel, "row_widgets", None)
        )
        column_count = self._remove_node_field_keys(
            getattr(self._panel, "col_widgets", None)
        )
        field_registry = getattr(self._panel, "_field_registry", None)
        if isinstance(field_registry, EditorFieldRegistry):
            input_count = field_registry.remove_node(
                self._cube_alias,
                self._node_name,
            )
        else:
            input_count = self._remove_node_field_keys(
                getattr(self._panel, "input_widgets_by_field_key", None)
            )
        return NodeCardRegistrationCleanup(
            row_count=row_count,
            column_count=column_count,
            input_count=input_count,
        )

    def _remove_node_field_keys(self, registry: object) -> int:
        """Remove mapping keys identifying fields from this node card."""

        mutable_registry = self._mutable_mapping(registry)
        if mutable_registry is None or self._cube_alias is None:
            return 0
        identities = [
            identity
            for identity in mutable_registry
            if self._is_owned_field_identity(identity)
        ]
        for identity in identities:
            mutable_registry.pop(identity, None)
        return len(identities)

    def _is_owned_field_identity(self, identity: object) -> bool:
        """Return whether a mapping identity belongs to this card."""

        return bool(
            isinstance(identity, tuple)
            and len(identity) >= 3
            and identity[0] == self._cube_alias
            and identity[1] == self._node_name
        )

    @staticmethod
    def _mutable_mapping(value: object) -> MutableMapping[object, object] | None:
        """Narrow a runtime registry surface to a mutable mapping."""

        if not isinstance(value, MutableMapping):
            return None
        return cast(MutableMapping[object, object], value)


__all__ = ["NodeCardBuildTransaction", "NodeCardRegistrationCleanup"]
