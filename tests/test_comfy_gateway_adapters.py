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

"""Contract tests for Phase 7 Comfy gateway infrastructure adapters."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.prompt_gateway import (
    ComfyPromptGateway,
    ComfyPromptQueueError,
    queue_prompt,
)
from substitute.application.ports.comfy_gateway import (
    ListenerCallbacks,
    ListenerSessionHandle,
    ListenerStartRequest,
)


class _CapabilityResponse:
    """Return the backend prompt queue capability payload used by queue tests."""

    def raise_for_status(self) -> None:
        """Accept successful capability responses."""

    def json(self) -> dict[str, object]:
        """Return a compatible backend capability payload."""

        return {
            "features": ["prompt-queue-facade", "visual-routing"],
            "promptQueue": {
                "schemaVersion": 1,
                "queueRoute": "/substitute/v1/prompt/queue",
            },
            "visualRouting": {
                "schemaVersion": 1,
                "finalOutputIdentityRequired": True,
                "previewMetadataIdentitySupported": True,
                "previewMetadataKey": "substitute",
            },
        }


@pytest.fixture(autouse=True)
def _backend_prompt_queue_facade_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make queue tests see a compatible Substitute BackEnd capability contract."""

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.prompt_gateway.requests.get",
        lambda *_args, **_kwargs: _CapabilityResponse(),
    )


def _noop_callbacks() -> ListenerCallbacks:
    """Return listener callbacks that perform no side effects."""
    return ListenerCallbacks(
        on_progress=lambda _event: None,
        on_model_load_progress=lambda _event: None,
        on_preview=lambda _event: None,
        on_output_image=lambda _event: None,
        on_failed=lambda _event: None,
        on_timing=lambda _event: None,
        on_completed=lambda _event: None,
    )


def test_endpoint_builds_substitute_prompt_queue_url() -> None:
    """Comfy endpoint should expose the typed Substitute prompt queue URL."""

    endpoint = ComfyEndpoint(host="10.0.0.2", port=8189)

    assert (
        endpoint.substitute_prompt_queue_url()
        == "http://10.0.0.2:8189/substitute/v1/prompt/queue"
    )
    assert (
        endpoint.substitute_capabilities_url()
        == "http://10.0.0.2:8189/substitute/v1/capabilities"
    )


def test_queue_prompt_returns_prompt_id_when_payload_is_valid(monkeypatch) -> None:
    """Queue adapter should return queued status when prompt id exists."""
    gateway = ComfyPromptGateway()
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.prompt_gateway.queue_prompt",
        lambda *_args, **_kwargs: {"prompt_id": "pid-1"},
    )

    result = gateway.queue_prompt(
        {"N1": {"class_type": "KSampler"}}, client_id="client"
    )

    assert result.status == "queued"
    assert result.prompt_id == "pid-1"


def test_queue_prompt_returns_missing_prompt_id_when_response_lacks_id(
    monkeypatch,
) -> None:
    """Queue adapter should reject payloads that do not expose prompt id."""
    gateway = ComfyPromptGateway()
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.prompt_gateway.queue_prompt",
        lambda *_args, **_kwargs: {"status": "ok"},
    )

    result = gateway.queue_prompt(
        {"N1": {"class_type": "KSampler"}}, client_id="client"
    )

    assert result.status == "missing_prompt_id"
    assert result.prompt_id is None
    assert result.payload == {"status": "ok"}


def test_queue_prompt_posts_preview_method_extra_data(monkeypatch) -> None:
    """Queue transport should include Comfy preview method metadata when supplied."""

    post_calls: list[dict[str, object]] = []

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"prompt_id": "pid-1"}

    def _post(*args: object, **kwargs: object) -> _Response:
        kwargs["url"] = args[0]
        post_calls.append(kwargs)
        return _Response()

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.prompt_gateway.requests.post",
        _post,
    )

    payload = queue_prompt(
        {"N1": {"class_type": "KSampler"}},
        client_id="client",
        preview_method="none",
    )

    assert payload == {"prompt_id": "pid-1"}
    assert post_calls[0]["url"] == "http://127.0.0.1:8188/substitute/v1/prompt/queue"
    assert post_calls[0]["json"] == {
        "prompt": {"N1": {"class_type": "KSampler"}},
        "client_id": "client",
        "extra_data": {"preview_method": "none"},
    }


def test_queue_prompt_posts_ui_workflow_pnginfo(monkeypatch) -> None:
    """Queue transport should attach UI workflow metadata for Comfy image outputs."""

    post_calls: list[dict[str, object]] = []
    ui_workflow = {"version": 0.4, "nodes": []}

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"prompt_id": "pid-1"}

    def _post(*args: object, **kwargs: object) -> _Response:
        kwargs["url"] = args[0]
        post_calls.append(kwargs)
        return _Response()

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.prompt_gateway.requests.post",
        _post,
    )

    payload = queue_prompt(
        {
            "prompt": {"N1": {"class_type": "KSampler"}},
            "workflow": ui_workflow,
        },
        client_id="client",
        preview_method="latent2rgb",
        sugar_script='use "cube" as A',
    )

    assert payload == {"prompt_id": "pid-1"}
    assert post_calls[0]["url"] == "http://127.0.0.1:8188/substitute/v1/prompt/queue"
    assert post_calls[0]["json"] == {
        "prompt": {"N1": {"class_type": "KSampler"}},
        "client_id": "client",
        "extra_data": {
            "preview_method": "latent2rgb",
            "extra_pnginfo": {
                "workflow": ui_workflow,
                "sugar_script": 'use "cube" as A',
            },
        },
    }


def test_queue_prompt_preserves_prompt_validation_error_payload(monkeypatch) -> None:
    """Queue transport should preserve Comfy HTTP 400 prompt validation JSON."""

    class _Response:
        status_code = 400
        text = '{"error": "bad prompt"}'

        def raise_for_status(self) -> None:
            raise AssertionError("raise_for_status should not run first")

        def json(self) -> dict[str, object]:
            return {
                "error": {
                    "message": "Prompt outputs failed validation",
                    "details": "KSampler invalid",
                },
                "node_errors": {
                    "14": {
                        "class_type": "KSampler",
                        "dependent_outputs": [],
                        "errors": [
                            {
                                "message": "Value is required",
                                "details": "seed",
                                "extra_info": {"input_name": "seed"},
                            }
                        ],
                    }
                },
            }

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.prompt_gateway.requests.post",
        lambda *_args, **_kwargs: _Response(),
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.runtime_info_client.requests.get",
        lambda *_args, **_kwargs: SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "system": {
                    "comfyui_version": "0.3.1",
                    "pytorch_version": "2.8.0",
                    "python_version": "3.12.10",
                    "os": "Windows",
                    "argv": ["main.py"],
                },
                "devices": [{"name": "RTX 5090", "type": "cuda", "index": 0}],
            },
        ),
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.prompt_gateway._require_prompt_queue_facade",
        lambda *_args, **_kwargs: None,
    )

    try:
        queue_prompt({"N1": {"class_type": "KSampler"}}, client_id="client")
    except ComfyPromptQueueError as error:
        assert error.error_report is not None
        assert error.error_report.prompt_validation is not None
        assert error.error_report.runtime.comfy_version == "0.3.1"
        assert error.error_report.runtime.pytorch_version == "2.8.0"
        assert error.error_report.runtime.devices == ("RTX 5090 (cuda #0)",)
        assert error.error_report.prompt_validation.node_errors[0].node_id == "14"
        assert "Prompt outputs failed validation" in str(error)
    else:
        raise AssertionError("Expected ComfyPromptQueueError")


def test_queue_prompt_reports_missing_backend_queue_capability(monkeypatch) -> None:
    """Missing backend queue capability should surface as compatibility failure."""

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"features": []}

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.prompt_gateway.requests.get",
        lambda *_args, **_kwargs: _Response(),
    )

    with pytest.raises(ComfyPromptQueueError) as error:
        queue_prompt({"N1": {"class_type": "KSampler"}}, client_id="client")

    assert "Substitute BackEnd prompt queue facade is incompatible" in str(error.value)


def test_gateway_result_carries_prompt_validation_report(monkeypatch) -> None:
    """Infrastructure gateway should expose structured queue error reports."""

    report_error = ComfyPromptQueueError(
        "Prompt outputs failed validation",
        payload={"error": "bad"},
        error_report=None,
    )
    gateway = ComfyPromptGateway()
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.prompt_gateway.queue_prompt",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(report_error),
    )

    result = gateway.queue_prompt(
        {"N1": {"class_type": "KSampler"}},
        client_id="client",
    )

    assert result.status == "error"
    assert result.payload == {"error": "bad"}
    assert result.error == "Prompt outputs failed validation"


def test_start_listener_submits_long_lived_listener_task() -> None:
    """Listener adapter should start listener work through the injected task factory."""

    task = object()
    task_calls: list[dict[str, object]] = []

    def listener_task_factory(
        identity: object,
        context: object,
        work: object,
        thread_name: str,
    ) -> object:
        """Record one listener task request."""

        task_calls.append(
            {
                "identity": identity,
                "context": context,
                "work": work,
                "thread_name": thread_name,
            }
        )
        return task

    gateway = ComfyPromptGateway(
        listener_connect_timeout_seconds=1.5,
        listener_receive_timeout_seconds=9.0,
        listener_task_factory=listener_task_factory,
    )
    request = ListenerStartRequest(
        prompt_id="pid-1",
        generation_run_id="run-1",
        client_id="client",
        listener_session=ListenerSessionHandle(
            workflow_id="wf-1",
            generation_run_id="run-1",
            client_id="client",
            session=SimpleNamespace(),
        ),
        output_dir=Path("."),
        workflow_payload={"N1": {"class_type": "KSampler"}},
        sugar_script='use "cube" as A',
        workflow_id="wf-1",
        workflow_name="Workflow 1",
    )
    result = gateway.start_listener(request=request, callbacks=_noop_callbacks())

    assert result.started is True
    assert result.handle is not None
    assert result.handle.task is task
    assert len(task_calls) == 1
    assert task_calls[0]["thread_name"] == "substitute-generation-listener-client"
    identity = task_calls[0]["identity"]
    context = task_calls[0]["context"]
    assert getattr(identity, "domain") == "generation_listener"
    assert getattr(context, "operation") == "generation_listener"
    assert getattr(context, "lane") == "generation_listener"
    assert callable(task_calls[0]["work"])


def test_interrupt_returns_sent_status_on_http_200(monkeypatch) -> None:
    """Interrupt adapter should return sent status for HTTP 200 responses."""
    gateway = ComfyPromptGateway(interrupt_timeout_seconds=2.0)
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.prompt_gateway.requests.post",
        lambda *_args, **_kwargs: SimpleNamespace(status_code=200),
    )

    result = gateway.interrupt()

    assert result.status == "sent"
    assert result.status_code == 200
    assert result.error is None


def test_interrupt_returns_failed_status_when_transport_raises(monkeypatch) -> None:
    """Interrupt adapter should fail closed when HTTP transport raises."""
    gateway = ComfyPromptGateway(interrupt_timeout_seconds=2.0)
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.prompt_gateway.requests.post",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("network down")),
    )

    result = gateway.interrupt()

    assert result.status == "failed"
    assert result.status_code is None
    assert "network down" in (result.error or "")


def test_get_queue_extracts_prompt_ids_from_comfy_response(monkeypatch) -> None:
    """Queue adapter should normalize known Comfy queue entry shapes."""

    gateway = ComfyPromptGateway(queue_timeout_seconds=2.0)

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "queue_running": [[0.0, "running-1"], {"prompt_id": "running-2"}],
                "queue_pending": [["pending-1", 1], {"prompt_id": "pending-2"}],
            }

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.prompt_gateway.requests.get",
        lambda *_args, **_kwargs: _Response(),
    )

    result = gateway.get_queue()

    assert result.running_prompt_ids == ("running-1", "running-2")
    assert result.pending_prompt_ids == ("pending-1", "pending-2")


def test_delete_pending_prompt_posts_delete_payload(monkeypatch) -> None:
    """Queue adapter should delete pending prompts through Comfy's queue endpoint."""

    gateway = ComfyPromptGateway(queue_timeout_seconds=2.0)
    post_calls: list[dict[str, object]] = []

    def _post(*_args: object, **kwargs: object) -> object:
        post_calls.append(kwargs)
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.prompt_gateway.requests.post",
        _post,
    )

    result = gateway.delete_pending_prompt("pending-1")

    assert result.status == "deleted"
    assert result.status_code == 200
    assert post_calls[0]["json"] == {"delete": ["pending-1"]}
