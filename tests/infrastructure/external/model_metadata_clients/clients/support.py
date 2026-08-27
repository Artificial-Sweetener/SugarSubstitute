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

"""Provide typed HTTP fakes and representative metadata payloads."""

from __future__ import annotations


class _FakeResponse:
    """Provide the response surface used by the metadata HTTP clients."""

    def __init__(
        self,
        payload: object,
        *,
        status_code: int = 200,
    ) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        """Accept successful responses."""

    def json(self) -> object:
        """Return the configured payload."""

        return self._payload


def _typed_headers(headers: object) -> dict[str, str]:
    """Return HTTP headers with a strict test type."""

    assert isinstance(headers, dict)
    return {str(key): str(value) for key, value in headers.items()}


def _capabilities_payload() -> dict[str, object]:
    """Return a minimal valid backend capabilities payload."""

    return {
        "apiVersion": 1,
        "extensionVersion": "1.4.0",
        "features": ["model-metadata", "cube-library"],
        "cubeLibrary": {
            "schemaVersion": 1,
            "available": True,
            "unavailableReason": "",
            "sugarCubesVersion": "0.9.0",
            "catalogSupported": True,
            "artifactLoadSupported": True,
            "workflowCompileSupported": False,
            "packManagementSupported": True,
            "dependencyReadinessSupported": True,
            "dependencyRepairSupported": True,
            "versionedDependencyReadinessSupported": True,
            "syncDependencyOrchestrationSupported": True,
        },
        "sugarCompile": {
            "schemaVersion": 1,
            "available": True,
            "unavailableReason": "",
            "compileRoute": "/substitute/v1/sugar/compile",
            "sugarDslVersion": "0.2.0",
        },
        "modelMetadata": {
            "schemaVersion": 1,
            "supportedModelKinds": ["checkpoints", "loras"],
            "backgroundHashing": True,
            "hashLookup": True,
            "localPreviewServing": True,
            "sidecarReading": True,
        },
    }


def _backend_model_payload() -> dict[str, object]:
    """Return a minimal valid backend model catalog entry."""

    return {
        "schemaVersion": 1,
        "targetId": "target-1",
        "kind": "loras",
        "value": "models/lora.safetensors",
        "displayName": "lora",
        "source": {"rootId": "root-1", "relativePath": "models/lora.safetensors"},
        "file": {
            "extension": ".safetensors",
            "sizeBytes": 123,
            "modifiedAt": "2026-04-14T01:00:00Z",
            "createdAt": None,
        },
        "fingerprint": {
            "status": "missing",
            "sha256": None,
            "source": None,
            "computedAt": None,
            "error": None,
        },
        "sidecar": {
            "found": False,
            "modelId": None,
            "modelVersionId": None,
            "sha256": None,
            "activationText": None,
            "description": None,
            "baseModel": None,
            "modifiedAt": None,
        },
        "localPreview": {
            "available": False,
            "previewId": None,
            "url": None,
            "source": None,
            "modifiedAt": None,
            "width": None,
            "height": None,
        },
    }


def _fingerprint_job_payload() -> dict[str, object]:
    """Return a complete backend fingerprint job payload."""

    return {
        "jobId": "job-1",
        "status": "complete",
        "entries": [
            {
                "kind": "loras",
                "value": "models/lora.safetensors",
                "status": "complete",
                "sha256": "ABC123",
                "error": None,
            }
        ],
    }


def _model_catalog_change_payload() -> dict[str, object]:
    """Return one model catalog change payload."""

    return {
        "schemaVersion": 1,
        "revision": "rev2",
        "previousRevision": "rev1",
        "generatedAt": "2026-05-26T12:00:01Z",
        "reason": "folder-changed",
        "kinds": ["loras"],
        "affectedNodeClasses": ["LoraLoader"],
        "added": [
            {
                "kind": "loras",
                "value": "models/lora.safetensors",
                "source": {
                    "rootId": "loras:0",
                    "relativePath": "models/lora.safetensors",
                },
                "file": {
                    "sizeBytes": 123,
                    "modifiedAt": "2026-04-14T01:00:00Z",
                },
            }
        ],
        "removed": [],
        "modified": [],
    }


def _hash_lookup_payload() -> dict[str, object]:
    """Return a complete backend hash lookup payload."""

    return {
        "schemaVersion": 1,
        "status": "complete",
        "kind": "loras",
        "sha256": "A" * 64,
        "matches": [
            {
                "kind": "loras",
                "value": "models/lora.safetensors",
                "displayName": "lora",
                "source": {
                    "rootId": "root-1",
                    "relativePath": "models/lora.safetensors",
                },
                "file": {
                    "extension": ".safetensors",
                    "sizeBytes": 123,
                    "modifiedAt": "2026-04-14T01:00:00Z",
                    "createdAt": None,
                },
            }
        ],
        "jobId": None,
    }


def _download_job_payload(*, status: str) -> dict[str, object]:
    """Return a backend model download job payload."""

    payload: dict[str, object] = {
        "schemaVersion": 1,
        "jobId": "download-1",
        "status": status,
        "kind": "loras",
        "sha256": "A" * 64,
    }
    if status == "complete":
        payload["value"] = "models/lora.safetensors"
        payload["bytesDownloaded"] = 123
        payload["bytesTotal"] = 123
        payload["detail"] = "Download complete."
        payload["result"] = {
            "kind": "loras",
            "value": "models/lora.safetensors",
            "displayName": "lora",
            "source": {
                "rootId": "loras:0",
                "relativePath": "models/lora.safetensors",
            },
            "sha256": "A" * 64,
            "file": {
                "extension": ".safetensors",
                "sizeBytes": 123,
                "modifiedAt": "2026-05-21T00:00:00Z",
                "createdAt": None,
            },
        }
    return payload


def _civitai_payload() -> dict[str, object]:
    """Return a representative CivitAI by-hash model-version payload."""

    return {
        "id": 200,
        "modelId": 100,
        "name": "Version A",
        "baseModel": "SDXL 1.0",
        "trainedWords": ["trigger", "style"],
        "description": "Version description",
        "files": [
            {
                "id": 300,
                "name": "model.safetensors",
                "sizeKB": 42.0,
                "type": "Model",
                "downloadUrl": "https://civitai.com/api/download/models/200",
                "pickleScanResult": "Success",
                "virusScanResult": "Success",
                "primary": True,
                "hashes": {"SHA256": "ABC123"},
                "metadata": {"format": "SafeTensor"},
            }
        ],
        "images": [
            {
                "id": 400,
                "url": "https://image.example/safe.jpg",
                "type": "image",
                "nsfw": False,
                "nsfwLevel": "None",
                "width": 512,
                "height": 768,
                "meta": {"prompt": "hello"},
            }
        ],
        "stats": {"downloadCount": 5},
        "model": {
            "id": 100,
            "name": "Model A",
            "type": "LORA",
            "description": "Model description",
            "tags": ["portrait"],
            "creator": {
                "username": "creator",
                "image": "https://image.example/avatar.jpg",
            },
            "nsfw": False,
            "nsfwLevel": "None",
            "mode": "Archived",
        },
    }
