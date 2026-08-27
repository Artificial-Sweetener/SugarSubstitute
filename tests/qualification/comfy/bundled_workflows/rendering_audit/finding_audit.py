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

"""Turn observed production states into actionable audit findings."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QWidget
from shiboken6 import isValid

from substitute.presentation.editor.panel.factories.field_build_outcome import (
    EditorFieldBuildKind,
)
from tests.qualification.comfy.bundled_workflows.catalog import (
    BundledWorkflowCatalogEntry,
)
from tests.qualification.comfy.bundled_workflows.rendering_audit.models import (
    AuditFinding,
    NodeObservation,
)


class FindingAuditor:
    """Classify one workflow's observed production contradictions."""

    def production_findings(
        self,
        *,
        entry: BundledWorkflowCatalogEntry,
        nodes: tuple[NodeObservation, ...],
        masonry_order: tuple[str, ...],
        cards: Mapping[str, QWidget],
    ) -> tuple[AuditFinding, ...]:
        """Report exceptions and contradictions in observed production operations."""

        findings: list[AuditFinding] = []
        converted_ids = {node.node_id for node in nodes}
        for node in nodes:
            if not node.behavior_present:
                findings.append(
                    self.finding(
                        entry,
                        code="missing_production_behavior",
                        stage="behavior",
                        message="Converted node has no production behavior.",
                        node_id=node.node_id,
                        class_type=node.class_type,
                    )
                )
            if len(node.build_outcomes) != 1:
                findings.append(
                    self.finding(
                        entry,
                        code="build_outcome_cardinality",
                        stage="card_build",
                        message=(
                            "Converted node received "
                            f"{len(node.build_outcomes)} production build outcomes."
                        ),
                        node_id=node.node_id,
                        class_type=node.class_type,
                    )
                )
            factory_exception = False
            for observation in node.factory_observations:
                if observation.result == EditorFieldBuildKind.UNSUPPORTED.value:
                    findings.append(
                        self.finding(
                            entry,
                            code="field_factory_unhandled",
                            stage="field_factory",
                            message=(
                                "The production field-factory pipeline has no "
                                "registered editor for this field."
                            ),
                            node_id=node.node_id,
                            class_type=node.class_type,
                            field_key=observation.field_key,
                        )
                    )
                elif observation.result == "exception":
                    factory_exception = True
                    findings.append(
                        self.finding(
                            entry,
                            code="field_factory_exception",
                            stage="field_factory",
                            message=observation.exception_message,
                            node_id=node.node_id,
                            class_type=node.class_type,
                            field_key=observation.field_key,
                            exception_type=observation.exception_type,
                            traceback_text=observation.traceback,
                        )
                    )
            if len(node.build_outcomes) != 1:
                continue
            outcome = node.build_outcomes[0]
            if outcome.kind == "build_error" and not factory_exception:
                findings.append(
                    self.finding(
                        entry,
                        code="node_card_build_exception",
                        stage="card_build",
                        message=outcome.message
                        or "Production card construction failed.",
                        node_id=node.node_id,
                        class_type=node.class_type,
                    )
                )
            if outcome.kind == "built":
                if not node.card.registered:
                    findings.append(
                        self.finding(
                            entry,
                            code="built_card_missing_registry",
                            stage="card_registry",
                            message="Production reported built but registered no card.",
                            node_id=node.node_id,
                            class_type=node.class_type,
                        )
                    )
                elif not node.card.valid:
                    findings.append(
                        self.finding(
                            entry,
                            code="built_card_invalid_qt_object",
                            stage="card_lifecycle",
                            message="Registered production card is no longer a valid Qt object.",
                            node_id=node.node_id,
                            class_type=node.class_type,
                        )
                    )
                if not node.card.in_masonry:
                    findings.append(
                        self.finding(
                            entry,
                            code="built_card_missing_masonry",
                            stage="masonry",
                            message="Built card is absent from production masonry order.",
                            node_id=node.node_id,
                            class_type=node.class_type,
                        )
                    )
            else:
                if node.card.registered:
                    findings.append(
                        self.finding(
                            entry,
                            code="unbuilt_node_registered_card",
                            stage="card_registry",
                            message=(
                                f"Production outcome {outcome.kind!r} retained a card."
                            ),
                            node_id=node.node_id,
                            class_type=node.class_type,
                        )
                    )
                if node.card.registered_field_keys:
                    findings.append(
                        self.finding(
                            entry,
                            code="unbuilt_node_retained_field_widgets",
                            stage="card_cleanup",
                            message=(
                                f"Production outcome {outcome.kind!r} retained fields: "
                                f"{', '.join(node.card.registered_field_keys)}."
                            ),
                            node_id=node.node_id,
                            class_type=node.class_type,
                        )
                    )
        unexpected_masonry = set(masonry_order) - converted_ids
        unexpected_registry = set(cards) - converted_ids
        for node_id in sorted(unexpected_masonry | unexpected_registry):
            findings.append(
                self.finding(
                    entry,
                    code="stale_or_unexpected_card",
                    stage="card_lifecycle",
                    message="Card state contains a node absent from this converted workflow.",
                    node_id=node_id,
                )
            )
        return tuple(findings)

    def masonry_findings(
        self,
        entry: BundledWorkflowCatalogEntry,
        cards: Mapping[str, QWidget],
    ) -> tuple[AuditFinding, ...]:
        """Report invalid final geometry for cards production left visible."""

        findings: list[AuditFinding] = []
        visible_cards = [
            (node_id, card)
            for node_id, card in cards.items()
            if isValid(card) and card.isVisible()
        ]
        for node_id, card in visible_cards:
            geometry = card.geometry()
            parent = card.parentWidget()
            if geometry.width() <= 0 or geometry.height() <= 0:
                findings.append(
                    self._geometry_finding(
                        entry,
                        node_id,
                        card,
                        code="visible_card_empty_geometry",
                        message="Visible production card has empty geometry.",
                    )
                )
            if geometry.x() < 0 or geometry.y() < 0:
                findings.append(
                    self._geometry_finding(
                        entry,
                        node_id,
                        card,
                        code="visible_card_negative_position",
                        message="Visible production card starts outside masonry bounds.",
                    )
                )
            if parent is None or not parent.rect().contains(geometry):
                findings.append(
                    self._geometry_finding(
                        entry,
                        node_id,
                        card,
                        code="visible_card_out_of_bounds",
                        message="Visible production card extends beyond its parent.",
                    )
                )
        for index, (left_id, left_card) in enumerate(visible_cards):
            for right_id, right_card in visible_cards[index + 1 :]:
                if _positive_intersection(left_card.geometry(), right_card.geometry()):
                    findings.append(
                        self.finding(
                            entry,
                            code="visible_cards_overlap",
                            stage="masonry",
                            message=f"Visible cards {left_id!r} and {right_id!r} overlap.",
                            node_id=f"{left_id},{right_id}",
                        )
                    )
        return tuple(findings)

    def _geometry_finding(
        self,
        entry: BundledWorkflowCatalogEntry,
        node_id: str,
        card: QWidget,
        *,
        code: str,
        message: str,
    ) -> AuditFinding:
        """Build one card-geometry finding with observed node context."""

        return self.finding(
            entry,
            code=code,
            stage="masonry",
            message=f"{message} Geometry={card.geometry().getRect()!r}",
            node_id=node_id,
            class_type=str(card.property("node_class_type") or ""),
        )

    @staticmethod
    def finding(
        entry: BundledWorkflowCatalogEntry,
        *,
        code: str,
        stage: str,
        message: str,
        node_id: str = "",
        class_type: str = "",
        field_key: str = "",
        exception_type: str = "",
        traceback_text: str = "",
    ) -> AuditFinding:
        """Build one workflow-scoped observed failure record."""

        return AuditFinding(
            workflow=entry.name,
            category=entry.category,
            code=code,
            stage=stage,
            message=message,
            node_id=node_id,
            class_type=class_type,
            field_key=field_key,
            exception_type=exception_type,
            traceback=traceback_text,
        )


def _positive_intersection(left: QRect, right: QRect) -> bool:
    """Return whether two final card geometries overlap with positive area."""

    intersection = left.intersected(right)
    return intersection.width() > 0 and intersection.height() > 0
