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

"""Contract tests for Substitute BackEnd environment management clients."""

from __future__ import annotations

from substitute.application.comfy_environment import ComfyEnvironmentService
from substitute.domain.comfy_environment import (
    ComfyEnvironmentComponent,
    ComfyEnvironmentJobStatus,
    ComfyEnvironmentOperationPlan,
    ComfyEnvironmentPackage,
    ComfyMaintenancePlan,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external import SubstituteBackendEnvironmentClient


class _FakeResponse:
    """Provide the response surface used by the environment HTTP client."""

    def __init__(self, payload: object) -> None:
        """Store the response payload."""

        self._payload = payload

    def raise_for_status(self) -> None:
        """Accept successful responses."""

    def json(self) -> object:
        """Return the configured payload."""

        return self._payload


def test_environment_client_builds_urls_and_parses_payloads() -> None:
    """Environment client should use active endpoint and parse typed DTOs."""

    calls: list[tuple[str, str]] = []

    def fake_get(url: str, **_kwargs: object) -> _FakeResponse:
        """Return route-specific fake backend payloads."""

        calls.append(("GET", url))
        if url.endswith("/substitute/v1/environment/capabilities"):
            return _FakeResponse(_capabilities_payload())
        if url.endswith("/substitute/v1/environment/status"):
            return _FakeResponse(_status_payload())
        if url.endswith("/substitute/v1/environment/model-root"):
            return _FakeResponse(_model_root_payload())
        if url.endswith("/substitute/v1/environment/packages"):
            return _FakeResponse(_packages_payload())
        if url.endswith("/substitute/v1/environment/maintenance-plan"):
            return _FakeResponse(_maintenance_plan_payload())
        if url.endswith("/substitute/v1/environment/jobs/envjob-1"):
            return _FakeResponse(_job_payload("succeeded"))
        raise AssertionError(f"unexpected GET {url}")

    def fake_post(url: str, **kwargs: object) -> _FakeResponse:
        """Return route-specific fake POST payloads."""

        calls.append(("POST", url))
        if url.endswith("/substitute/v1/environment/restart"):
            assert kwargs["json"] == {}
            return _FakeResponse(_job_payload("queued"))
        if url.endswith("/substitute/v1/environment/operations/plan"):
            assert kwargs["json"] == {
                "operation": "update-component",
                "componentId": "pytorch",
            }
            return _FakeResponse(_operation_plan_payload())
        if url.endswith("/substitute/v1/environment/maintenance-plan/items"):
            assert kwargs["json"] == {
                "operation": "update-runtime",
                "runtimeId": "pytorch",
            }
            return _FakeResponse(_maintenance_plan_payload())
        if url.endswith("/substitute/v1/environment/maintenance-plan/items/reorder"):
            assert kwargs["json"] == {
                "revision": 4,
                "itemIds": ["plan-item-2", "plan-item-1", "plan-item-3"],
            }
            return _FakeResponse(_maintenance_plan_payload())
        if url.endswith("/substitute/v1/environment/maintenance-plan/validate"):
            assert kwargs["json"] == {}
            return _FakeResponse(_maintenance_plan_payload())
        if url.endswith("/substitute/v1/environment/maintenance-plan/apply"):
            assert kwargs["json"] == {"revision": 4}
            return _FakeResponse(_job_payload("queued"))
        raise AssertionError(f"unexpected POST {url}")

    def fake_delete(url: str, **_kwargs: object) -> _FakeResponse:
        """Return route-specific fake DELETE payloads."""

        calls.append(("DELETE", url))
        if url.endswith(
            "/substitute/v1/environment/maintenance-plan/items/plan-item-1"
        ):
            return _FakeResponse(_maintenance_plan_payload())
        if url.endswith("/substitute/v1/environment/maintenance-plan"):
            return _FakeResponse(_empty_maintenance_plan_payload())
        raise AssertionError(f"unexpected DELETE {url}")

    def fake_put(url: str, **kwargs: object) -> _FakeResponse:
        """Return the persisted BackEnd model-root response."""

        calls.append(("PUT", url))
        assert url.endswith("/substitute/v1/environment/model-root")
        assert kwargs["json"] == {"mode": "custom", "path": "E:\\SharedModels"}
        return _FakeResponse(
            {
                **_model_root_payload(),
                "configuredModelRoot": "E:\\SharedModels",
                "restartRequired": True,
                "usesDefault": False,
            }
        )

    client = SubstituteBackendEnvironmentClient(
        ComfyEndpoint(host="10.0.0.2", port=8189),
        http_get=fake_get,
        http_post=fake_post,
        http_put=fake_put,
        http_delete=fake_delete,
    )

    capabilities = client.get_environment_capabilities()
    status = client.get_environment_status()
    model_root = client.get_model_root()
    updated_model_root = client.update_model_root(
        use_default=False,
        path="E:\\SharedModels",
    )
    packages = client.list_packages()
    plan = client.plan_operation(
        {"operation": "update-component", "componentId": "pytorch"}
    )
    maintenance_plan = client.get_maintenance_plan()
    added_plan = client.add_maintenance_plan_item(
        {"operation": "update-runtime", "runtimeId": "pytorch"}
    )
    reordered_plan = client.reorder_maintenance_plan_items(
        revision=4,
        item_ids=("plan-item-2", "plan-item-1", "plan-item-3"),
    )
    removed_plan = client.remove_maintenance_plan_item("plan-item-1")
    validated_plan = client.validate_maintenance_plan()
    cleared_plan = client.clear_maintenance_plan()
    apply_job = client.apply_maintenance_plan(revision=4)
    queued_job = client.restart_comfy()
    polled_job = client.get_environment_job("envjob-1")

    assert capabilities is not None
    assert capabilities.restart_supported is True
    assert capabilities.model_root_management_supported is True
    assert status is not None
    assert status.python.version == "3.12.7"
    assert model_root is not None
    assert model_root.uses_default is True
    assert updated_model_root is not None
    assert updated_model_root.configured_model_root == "E:\\SharedModels"
    assert packages[0].name == "torch"
    assert packages[0].summary == "Tensors and dynamic neural networks in Python."
    assert packages[0].summary_source == "installed-metadata"
    assert packages[0].claimants[0].display_name == "ComfyUI-VFI"
    assert packages[0].claimants[0].required_via == "aiohttp"
    assert packages[0].management_tags[0].display_name == "PyTorch"
    assert plan is not None
    assert plan.affected_packages == ("torch", "torchvision", "torchaudio")
    assert maintenance_plan is not None
    assert maintenance_plan.items[1].title == "Reinstall Triton"
    assert maintenance_plan.items[1].target.target_id == "triton"
    assert maintenance_plan.items[1].install_requirements == ("triton-windows",)
    assert maintenance_plan.items[2].title == "Reinstall SageAttention"
    assert maintenance_plan.items[2].target.target_id == "sageattention"
    assert maintenance_plan.blockers[0].code == "package-mutation-unavailable"
    assert maintenance_plan.last_validation_message == (
        "Order adjusted because compatibility follow-ups must run after their parent."
    )
    assert added_plan is not None
    assert reordered_plan is not None
    assert removed_plan is not None
    assert validated_plan is not None
    assert cleared_plan is not None
    assert cleared_plan.items == ()
    assert apply_job is not None
    assert apply_job.status is ComfyEnvironmentJobStatus.QUEUED
    assert queued_job is not None
    assert queued_job.status is ComfyEnvironmentJobStatus.QUEUED
    assert polled_job is not None
    assert polled_job.status is ComfyEnvironmentJobStatus.SUCCEEDED
    assert calls == [
        ("GET", "http://10.0.0.2:8189/substitute/v1/environment/capabilities"),
        ("GET", "http://10.0.0.2:8189/substitute/v1/environment/status"),
        ("GET", "http://10.0.0.2:8189/substitute/v1/environment/model-root"),
        ("PUT", "http://10.0.0.2:8189/substitute/v1/environment/model-root"),
        ("GET", "http://10.0.0.2:8189/substitute/v1/environment/packages"),
        ("POST", "http://10.0.0.2:8189/substitute/v1/environment/operations/plan"),
        ("GET", "http://10.0.0.2:8189/substitute/v1/environment/maintenance-plan"),
        (
            "POST",
            "http://10.0.0.2:8189/substitute/v1/environment/maintenance-plan/items",
        ),
        (
            "POST",
            "http://10.0.0.2:8189/substitute/v1/environment/maintenance-plan/items/reorder",
        ),
        (
            "DELETE",
            "http://10.0.0.2:8189/substitute/v1/environment/maintenance-plan/items/plan-item-1",
        ),
        (
            "POST",
            "http://10.0.0.2:8189/substitute/v1/environment/maintenance-plan/validate",
        ),
        ("DELETE", "http://10.0.0.2:8189/substitute/v1/environment/maintenance-plan"),
        (
            "POST",
            "http://10.0.0.2:8189/substitute/v1/environment/maintenance-plan/apply",
        ),
        ("POST", "http://10.0.0.2:8189/substitute/v1/environment/restart"),
        ("GET", "http://10.0.0.2:8189/substitute/v1/environment/jobs/envjob-1"),
    ]


def test_environment_service_skips_status_when_capabilities_are_unavailable() -> None:
    """Environment service should not call status routes without capabilities."""

    class Backend:
        """Backend test double with unavailable capabilities."""

        status_calls = 0

        def get_environment_capabilities(self) -> None:
            """Return no capabilities."""

            return None

        def get_environment_status(self) -> None:
            """Track unexpected status calls."""

            self.status_calls += 1
            return None

        def restart_comfy(self) -> None:
            """Return no restart job."""

            return None

        def get_environment_job(self, _job_id: str) -> None:
            """Return no job."""

            return None

        def plan_operation(
            self,
            _request: dict[str, object],
        ) -> ComfyEnvironmentOperationPlan | None:
            """Return no operation plan."""

            return None

        def list_packages(self) -> tuple[ComfyEnvironmentPackage, ...]:
            """Return no packages."""

            return ()

        def list_components(self) -> tuple[ComfyEnvironmentComponent, ...]:
            """Return no components."""

            return ()

        def get_maintenance_plan(self) -> ComfyMaintenancePlan | None:
            """Return no maintenance plan."""

            return None

        def add_maintenance_plan_item(
            self,
            _request: dict[str, object],
        ) -> ComfyMaintenancePlan | None:
            """Return no maintenance plan."""

            return None

        def remove_maintenance_plan_item(
            self,
            _item_id: str,
        ) -> ComfyMaintenancePlan | None:
            """Return no maintenance plan."""

            return None

        def reorder_maintenance_plan_items(
            self,
            *,
            revision: int,
            item_ids: tuple[str, ...],
        ) -> ComfyMaintenancePlan | None:
            """Return no maintenance plan."""

            _ = (revision, item_ids)
            return None

        def clear_maintenance_plan(self) -> ComfyMaintenancePlan | None:
            """Return no maintenance plan."""

            return None

        def validate_maintenance_plan(self) -> ComfyMaintenancePlan | None:
            """Return no maintenance plan."""

            return None

        def apply_maintenance_plan(
            self,
            *,
            revision: int,
        ) -> None:
            """Return no apply job."""

            _ = revision
            return None

    backend = Backend()
    snapshot = ComfyEnvironmentService(backend).load_snapshot()

    assert snapshot.backend_available is False
    assert backend.status_calls == 0


def _capabilities_payload() -> dict[str, object]:
    """Return a minimal environment capabilities payload."""

    return {
        "schemaVersion": 1,
        "supportedFeatures": ["restart"],
        "restartSupported": True,
        "packageMutationSupported": False,
        "operationPlanningSupported": False,
        "modelRootManagementSupported": True,
    }


def _model_root_payload() -> dict[str, object]:
    """Return default BackEnd-owned model-root state."""

    return {
        "schemaVersion": 1,
        "defaultModelRoot": "E:\\ComfyUI\\models",
        "configuredModelRoot": None,
        "activeModelRoot": "E:\\ComfyUI\\models",
        "usesDefault": True,
        "restartRequired": False,
    }


def _status_payload() -> dict[str, object]:
    """Return a minimal environment status payload."""

    return {
        "schemaVersion": 1,
        "python": {
            "executable": "E:\\ComfyUI\\venv\\Scripts\\python.exe",
            "version": "3.12.7",
            "prefix": "E:\\ComfyUI\\venv",
            "basePrefix": "C:\\Python312",
            "isVirtualEnvironment": True,
        },
        "comfy": {
            "root": "E:\\ComfyUI",
            "processId": 1234,
            "restartSupported": True,
        },
        "environment": {
            "inventoryAvailable": False,
            "mutationAvailable": False,
        },
    }


def _job_payload(status: str) -> dict[str, object]:
    """Return a minimal environment job payload."""

    return {
        "jobId": "envjob-1",
        "operation": "restart-comfy",
        "status": status,
        "createdAt": "2026-04-16T00:00:00Z",
        "updatedAt": "2026-04-16T00:00:01Z",
        "message": "Comfy restart queued.",
        "hostProcessId": 1234,
        "events": [
            {
                "createdAt": "2026-04-16T00:00:00Z",
                "status": status,
                "message": "Comfy restart queued.",
            }
        ],
    }


def _packages_payload() -> dict[str, object]:
    """Return a minimal package inventory payload."""

    return {
        "schemaVersion": 1,
        "packages": [
            {
                "name": "torch",
                "normalizedName": "torch",
                "version": "2.8.0",
                "summary": "Tensors and dynamic neural networks in Python.",
                "summarySource": "installed-metadata",
                "claimants": [
                    {
                        "kind": "custom-node",
                        "id": "ComfyUI-VFI",
                        "displayName": "ComfyUI-VFI",
                        "requirement": "torch>=2.5",
                        "sourcePath": "E:\\ComfyUI\\custom_nodes\\ComfyUI-VFI\\requirements.txt",
                        "requiredVia": "aiohttp",
                    }
                ],
                "managementTags": [
                    {
                        "kind": "supported-runtime",
                        "id": "pytorch",
                        "displayName": "PyTorch",
                        "supportedActions": ["plan-update"],
                    }
                ],
                "attribution": "supported",
                "installer": "pip",
                "editable": False,
            }
        ],
    }


def _operation_plan_payload() -> dict[str, object]:
    """Return a minimal operation plan payload."""

    return {
        "schemaVersion": 1,
        "planId": "envplan-1",
        "operation": "update-component",
        "affectedPackages": ["torch", "torchvision", "torchaudio"],
        "summary": "Update PyTorch packages to the latest stable builds.",
        "warnings": ["PyTorch updates require restarting Comfy."],
        "requiresComfyStop": True,
        "requiresRestart": True,
        "requiresDetachedRunner": True,
        "displayCommands": [["python", "-m", "pip", "install", "--upgrade", "torch"]],
    }


def _maintenance_plan_payload() -> dict[str, object]:
    """Return a maintenance plan payload with generated runtime follow-ups."""

    return {
        "schemaVersion": 1,
        "planId": "current",
        "environmentId": "E:\\ComfyUI",
        "revision": 4,
        "items": [
            {
                "itemId": "plan-item-1",
                "operation": "update-runtime",
                "title": "Update PyTorch runtime",
                "target": {
                    "kind": "runtime-family",
                    "id": "pytorch",
                    "displayName": "PyTorch runtime",
                },
                "requested": {
                    "source": "user",
                    "packageName": "torch",
                },
                "generated": False,
                "generatedByItemId": None,
                "relationship": "user-requested",
                "affectedPackages": ["torch", "torchvision", "torchaudio"],
                "installRequirements": ["torch", "torchvision", "torchaudio"],
                "requiresComfyStop": True,
                "requiresComfyRestart": True,
                "lockedRelativeOrder": False,
                "canRemove": True,
                "canReorder": True,
                "warnings": [],
                "blockers": [],
            },
            {
                "itemId": "plan-item-2",
                "operation": "reinstall-package",
                "title": "Reinstall Triton",
                "target": {
                    "kind": "package",
                    "id": "triton",
                    "displayName": "triton",
                },
                "requested": {
                    "source": "backend-policy",
                    "packageName": "triton",
                },
                "generated": True,
                "generatedByItemId": "plan-item-1",
                "relationship": "required-compatibility-follow-up",
                "affectedPackages": ["triton"],
                "installRequirements": ["triton-windows"],
                "requiresComfyStop": True,
                "requiresComfyRestart": True,
                "lockedRelativeOrder": True,
                "canRemove": False,
                "canReorder": False,
                "warnings": [
                    {
                        "code": "runtime-compatibility",
                        "message": "Required by PyTorch update.",
                        "itemId": "plan-item-2",
                    }
                ],
                "blockers": [],
            },
            {
                "itemId": "plan-item-3",
                "operation": "reinstall-package",
                "title": "Reinstall SageAttention",
                "target": {
                    "kind": "package",
                    "id": "sageattention",
                    "displayName": "sageattention",
                },
                "requested": {
                    "source": "backend-policy",
                    "packageName": "sageattention",
                },
                "generated": True,
                "generatedByItemId": "plan-item-1",
                "relationship": "required-compatibility-follow-up",
                "affectedPackages": ["sageattention"],
                "installRequirements": ["sageattention"],
                "requiresComfyStop": True,
                "requiresComfyRestart": True,
                "lockedRelativeOrder": True,
                "canRemove": False,
                "canReorder": False,
                "warnings": [
                    {
                        "code": "runtime-compatibility",
                        "message": "Required by PyTorch update.",
                        "itemId": "plan-item-3",
                    }
                ],
                "blockers": [],
            },
        ],
        "executionPhases": [
            {
                "phaseId": "phase-1",
                "title": "Package maintenance",
                "itemIds": ["plan-item-1", "plan-item-2", "plan-item-3"],
                "requiresComfyStop": True,
                "requiresComfyRestart": True,
            }
        ],
        "warnings": [],
        "blockers": [
            {
                "code": "package-mutation-unavailable",
                "message": "Package execution is not available.",
            }
        ],
        "summary": {
            "itemCount": 3,
            "affectedPackageCount": 5,
            "requiresComfyStop": True,
            "requiresComfyRestart": True,
            "applyable": False,
        },
        "lastValidationMessage": (
            "Order adjusted because compatibility follow-ups must run after their parent."
        ),
    }


def _empty_maintenance_plan_payload() -> dict[str, object]:
    """Return an empty maintenance plan payload."""

    payload = _maintenance_plan_payload()
    payload["revision"] = 5
    payload["items"] = []
    payload["executionPhases"] = []
    payload["warnings"] = []
    payload["blockers"] = []
    payload["summary"] = {
        "itemCount": 0,
        "affectedPackageCount": 0,
        "requiresComfyStop": False,
        "requiresComfyRestart": False,
        "applyable": False,
    }
    payload["lastValidationMessage"] = "Planned changes cleared."
    return payload
