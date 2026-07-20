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

"""Validate passive production observation without creating product policy."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from substitute.application.node_behavior import FieldValueSource, ResolvedFieldSpec
from substitute.domain.node_behavior import FieldBehavior
from substitute.presentation.editor.panel import node_card_builder
from substitute.presentation.editor.panel.cube_section_build_plan import (
    node_card_build_outcome,
)
from tests.bundled_comfy_workflow_catalog import BundledWorkflowCatalogEntry
from tests.bundled_comfy_workflow_rendering_harness import (
    BundledComfyWorkflowRenderingHarness,
    CardLifecycleObservation,
    FieldFactoryObservation,
    NodeObservation,
    ProductionFieldFactoryObserver,
)


def _field_spec() -> ResolvedFieldSpec:
    """Return one production field contract for observer tests."""

    return ResolvedFieldSpec(
        cube_alias="A",
        node_name="node",
        class_type="ExampleNode",
        field_key="value",
        field_type="UNSUPPORTED",
        constraints={},
        meta_info={},
        field_info=None,
        value="example",
        field_behavior=FieldBehavior(field_key="value"),
        raw_value="example",
        value_source=FieldValueSource.EXPLICIT,
    )


def _absent_card() -> CardLifecycleObservation:
    """Return final state for a production node that did not build a card."""

    return CardLifecycleObservation(
        registered=False,
        widget_type="",
        valid=False,
        parent_type="",
        in_masonry=False,
        masonry_index=None,
        visible=False,
        hidden=True,
        base_card_visible=None,
        has_title_controls=None,
        geometry=None,
        registered_field_keys=(),
        visibility_events=(),
    )


def _node(
    outcome_kind: str,
    *,
    factory_observations: tuple[FieldFactoryObservation, ...] = (),
) -> NodeObservation:
    """Return one observed node with a caller-selected production outcome."""

    return NodeObservation(
        node_id="node",
        class_type="ExampleNode",
        title="Example",
        behavior_present=True,
        decision_present=True,
        decision_visible=False,
        decision_enabled=False,
        decision_reason="production:test",
        decision_show_enabled_switch=False,
        field_specs=(),
        factory_observations=factory_observations,
        build_outcomes=(
            node_card_build_outcome(
                node_name="node",
                node_class_type="ExampleNode",
                kind=outcome_kind,  # type: ignore[arg-type]
                field_spec_count=1,
            ),
        ),
        card=_absent_card(),
    )


def test_factory_observer_records_a_real_pipeline_decline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A production None result must be preserved without support inference."""

    def production_decline(*_args: object, **_kwargs: object) -> None:
        """Represent the existing production pipeline declining a field."""

        return None

    monkeypatch.setattr(
        node_card_builder,
        "build_widget_for_field_spec",
        production_decline,
    )
    observer = ProductionFieldFactoryObserver()

    with observer:
        observed_factory = cast(
            Callable[..., object],
            getattr(node_card_builder, "build_widget_for_field_spec"),
        )
        result = observed_factory(field_spec=_field_spec())

    assert result is None
    assert (
        getattr(node_card_builder, "build_widget_for_field_spec") is production_decline
    )
    observation = observer.observations()[0]
    assert observation.result == "unsupported"
    assert observation.field_type == "UNSUPPORTED"
    assert observation.field_key == "value"


def test_factory_observer_preserves_exception_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A production factory exception must retain its original traceback."""

    def production_failure(*_args: object, **_kwargs: object) -> object:
        """Represent an existing production factory throwing during construction."""

        raise ValueError("broken options")

    monkeypatch.setattr(
        node_card_builder,
        "build_widget_for_field_spec",
        production_failure,
    )
    observer = ProductionFieldFactoryObserver()

    with observer, pytest.raises(ValueError, match="broken options"):
        observed_factory = cast(
            Callable[..., object],
            getattr(node_card_builder, "build_widget_for_field_spec"),
        )
        observed_factory(field_spec=_field_spec())

    observation = observer.observations()[0]
    assert observation.result == "exception"
    assert observation.exception_type == "ValueError"
    assert "production_failure" in observation.traceback


@pytest.mark.parametrize(
    "outcome_kind",
    ["hidden_by_policy", "connection_only", "missing_field_specs"],
)
def test_intentional_production_outcomes_are_not_findings(
    outcome_kind: str,
) -> None:
    """The audit must record production omissions without judging their policy."""

    harness = object.__new__(BundledComfyWorkflowRenderingHarness)
    entry = BundledWorkflowCatalogEntry(
        name="workflow",
        title="Workflow",
        category="Tests",
        path=Path("workflow.json"),
    )

    findings = harness._production_findings(  # noqa: SLF001
        entry=entry,
        nodes=(_node(outcome_kind),),
        masonry_order=(),
        cards={},
    )

    assert findings == ()


def test_production_factory_decline_is_a_finding() -> None:
    """A real attempted field that every production factory declines is actionable."""

    observation = FieldFactoryObservation(
        node_id="node",
        class_type="ExampleNode",
        field_key="value",
        field_type="UNSUPPORTED",
        presentation="standard",
        control_name="",
        value_source="explicit",
        result="unsupported",
        widget_type="",
        exception_type="",
        exception_message="",
        traceback="",
        elapsed_ms=1.0,
    )
    harness = object.__new__(BundledComfyWorkflowRenderingHarness)
    entry = BundledWorkflowCatalogEntry(
        name="workflow",
        title="Workflow",
        category="Tests",
        path=Path("workflow.json"),
    )

    findings = harness._production_findings(  # noqa: SLF001
        entry=entry,
        nodes=(
            _node(
                "factory_returned_none",
                factory_observations=(observation,),
            ),
        ),
        masonry_order=(),
        cards={},
    )

    assert [finding.code for finding in findings] == ["field_factory_unhandled"]
