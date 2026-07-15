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

"""Tests for prompt-safe panel projection observability helpers."""

from __future__ import annotations

import logging
import time

import pytest

from substitute.presentation.editor.panel.projection_observability import (
    log_panel_projection_event,
    log_panel_projection_timing,
    panel_projection_observability_started_at,
)

_LOGGER_NAME = "sugarsubstitute.presentation.editor.panel.projection_observability"


def test_panel_projection_timing_logs_prompt_safe_lifecycle_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Panel projection timing should expose lifecycle metrics without content."""

    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)

    elapsed_ms = log_panel_projection_timing(
        "preparation.hydrate_node_definitions",
        started_at=time.perf_counter() - 0.001,
        workflow_id="workflow",
        cube_section_count=2,
        errored_cube_count=1,
        reason="full_workflow_projection",
    )

    assert elapsed_ms >= 0.0
    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert "preparation.hydrate_node_definitions" in messages[0]
    assert "workflow_id=workflow" in messages[0]
    assert "cube_section_count=2" in messages[0]
    assert "errored_cube_count=1" in messages[0]
    assert "elapsed_ms=" in messages[0]
    assert "prompt_text" not in messages[0].lower()


def test_panel_projection_event_logs_visible_commit_retry_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Visible commit retry diagnostics should log scheduler state only."""

    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)

    log_panel_projection_event(
        "visible_commit.retry_scheduled",
        workflow_id="workflow",
        active_workflow_id="workflow",
        retry_attempts=2,
        retry_limit=5,
        panel_visible=False,
        pending_build_count=3,
    )

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert "visible_commit.retry_scheduled" in messages[0]
    assert "retry_attempts=2" in messages[0]
    assert "retry_limit=5" in messages[0]
    assert "panel_visible=False" in messages[0]
    assert "pending_build_count=3" in messages[0]


def test_panel_projection_event_logs_prompt_context_cache_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Prompt-context diagnostics should log neutral field identities only."""

    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)

    log_panel_projection_event(
        "prompt_context.profile_cache_miss",
        cube_alias="Cube",
        node_name="positive_prompt",
        field_key="value",
        context_source="projection",
        cache_entry_count=1,
    )

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert "prompt_context.profile_cache_miss" in messages[0]
    assert "cube_alias=Cube" in messages[0]
    assert "node_name=positive_prompt" in messages[0]
    assert "field_key=value" in messages[0]
    assert "context_source=projection" in messages[0]
    assert "prompt_node_name" not in messages[0]


def test_panel_projection_timing_logs_factory_metrics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Factory diagnostics should expose counts and readiness, not values."""

    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)

    log_panel_projection_timing(
        "choice_factory.model_picker_construct",
        started_at=time.perf_counter() - 0.001,
        field_key="ckpt_name",
        model_kind="checkpoints",
        option_count=2,
        readiness="warm",
    )

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert "choice_factory.model_picker_construct" in messages[0]
    assert "field_key=ckpt_name" in messages[0]
    assert "model_kind=checkpoints" in messages[0]
    assert "option_count=2" in messages[0]
    assert "readiness=warm" in messages[0]
    assert "elapsed_ms=" in messages[0]


def test_panel_projection_timing_logs_node_card_build_metrics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Node-card diagnostics should expose build shape without field values."""

    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)

    log_panel_projection_timing(
        "node_card.built",
        started_at=time.perf_counter() - 0.001,
        cube_alias="Cube",
        node_name="checkpoint_loader",
        node_class="CheckpointLoaderSimple",
        field_spec_count=3,
        visible_group_count=2,
        has_rows=True,
        has_title_controls=False,
        projection_mode="live",
    )

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert "node_card.built" in messages[0]
    assert "cube_alias=Cube" in messages[0]
    assert "node_name=checkpoint_loader" in messages[0]
    assert "node_class=CheckpointLoaderSimple" in messages[0]
    assert "field_spec_count=3" in messages[0]
    assert "visible_group_count=2" in messages[0]
    assert "has_rows=True" in messages[0]
    assert "elapsed_ms=" in messages[0]
    assert "prompt_text" not in messages[0].lower()


def test_panel_projection_timing_logs_node_card_field_metrics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Node-card field diagnostics should identify field shape, not content."""

    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)

    log_panel_projection_timing(
        "node_card.field_factory",
        started_at=time.perf_counter() - 0.001,
        cube_alias="Cube",
        node_name="checkpoint_loader",
        node_class="CheckpointLoaderSimple",
        field_key="ckpt_name",
        field_type="COMBO",
        presentation="combo",
        result_type="SearchableComboBox",
        projection_mode="live",
    )

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert "node_card.field_factory" in messages[0]
    assert "field_key=ckpt_name" in messages[0]
    assert "field_type=COMBO" in messages[0]
    assert "presentation=combo" in messages[0]
    assert "result_type=SearchableComboBox" in messages[0]
    assert "source_text" not in messages[0].lower()


@pytest.mark.parametrize(
    "unsafe_field_name",
    [
        "prompt_text",
        "source_text",
        "selected_text",
        "token_payload",
        "trigger_words",
        "file_path",
        "api_key",
        "authorization_header",
        "cookie_value",
        "credential_name",
        "exception_message",
        "raw_exception",
        "prompt_node_name",
        "prompt_field_key",
        "field_value",
    ],
)
def test_panel_projection_logging_rejects_content_bearing_field_names(
    unsafe_field_name: str,
) -> None:
    """Panel projection logs should reject prompt-sensitive fields."""

    with pytest.raises(ValueError, match="not prompt-safe"):
        log_panel_projection_event(
            "full_projection.start",
            **{unsafe_field_name: "leak"},
        )


def test_panel_projection_logging_rejects_content_bearing_event_names() -> None:
    """Panel projection event labels should not describe prompt content."""

    with pytest.raises(ValueError, match="not prompt-safe"):
        log_panel_projection_timing(
            "prompt.text.probe",
            started_at=panel_projection_observability_started_at(),
            workflow_id="workflow",
        )
