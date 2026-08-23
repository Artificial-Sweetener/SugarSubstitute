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

"""Provide deterministic environment HTTP responses and payloads."""

from __future__ import annotations


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
