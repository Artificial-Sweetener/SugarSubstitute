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

"""Build shared preferred-width label groups for node-link selectors."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from substitute.application.workflows import NodeLinkEndpointIndex, NodeLinkIdentity

INDEPENDENT_LINK_LABEL = "Independent"
LINK_TARGET_PREFIX = "🔗 "


@dataclass(frozen=True, slots=True)
class NodeLinkWidthLabels:
    """Hold candidate labels keyed by whole-node link compatibility identity."""

    labels_by_identity: Mapping[NodeLinkIdentity, tuple[str, ...]]


def link_target_label(cube_alias: str) -> str:
    """Return the user-facing selector label for a linked cube target."""

    return f"{LINK_TARGET_PREFIX}{cube_alias}"


def node_link_width_labels_by_identity(
    endpoint_index: NodeLinkEndpointIndex,
    ordered_aliases: Sequence[str],
) -> dict[NodeLinkIdentity, tuple[str, ...]]:
    """Return node-link width labels grouped by endpoint compatibility identity."""

    labels_by_identity: dict[NodeLinkIdentity, tuple[str, ...]] = {}
    for identity in endpoint_index.identities():
        labels: list[str] = [INDEPENDENT_LINK_LABEL]
        seen = {INDEPENDENT_LINK_LABEL}
        for cube_alias in ordered_aliases:
            if endpoint_index.endpoint_for(cube_alias, identity) is None:
                continue
            for target in endpoint_index.valid_link_targets(
                list(ordered_aliases),
                cube_alias,
                identity,
            ):
                _append_unique_label(labels, seen, link_target_label(target.cube_alias))
        labels_by_identity[identity] = tuple(labels)
    return labels_by_identity


def _append_unique_label(
    labels: list[str],
    seen: set[str],
    label: str,
) -> None:
    """Append a label once while preserving first-seen stack order."""

    if label in seen:
        return
    labels.append(label)
    seen.add(label)


__all__ = [
    "INDEPENDENT_LINK_LABEL",
    "LINK_TARGET_PREFIX",
    "NodeLinkWidthLabels",
    "link_target_label",
    "node_link_width_labels_by_identity",
]
