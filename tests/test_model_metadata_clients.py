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

"""Contract tests for model metadata HTTP clients."""

from __future__ import annotations

import logging

import pytest

from substitute.domain.model_metadata import (
    CivitaiLookupStatus,
    FingerprintStatus,
    JobStatus,
    BackendHashLookupStatus,
    ModelDownloadStatus,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external import (
    CivitaiClient,
    SubstituteBackendModelMetadataClient,
)


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


def test_backend_client_builds_urls_and_parses_catalog_and_jobs() -> None:
    """Backend client should use the active Comfy endpoint and parse typed DTOs."""

    calls: list[tuple[str, str]] = []

    def fake_get(url: str, **_kwargs: object) -> _FakeResponse:
        """Return route-specific fake backend payloads."""

        calls.append(("GET", url))
        if url.endswith("/substitute/v1/capabilities"):
            return _FakeResponse(_capabilities_payload())
        if url.endswith("/substitute/v1/models?kind=checkpoints&kind=loras"):
            return _FakeResponse({"models": [_backend_model_payload()]})
        if url.endswith("/substitute/v1/models?kind=loras&refresh=1"):
            return _FakeResponse({"models": [_backend_model_payload()]})
        if url.endswith(f"/substitute/v1/models/by-hash/{'A' * 64}?kind=loras"):
            return _FakeResponse(_hash_lookup_payload())
        if url.endswith("/substitute/v1/models/fingerprints/jobs/job-1"):
            return _FakeResponse(_fingerprint_job_payload())
        if url.endswith("/substitute/v1/models/changes"):
            return _FakeResponse(
                {
                    "schemaVersion": 1,
                    "revision": "rev2",
                    "latestChange": _model_catalog_change_payload(),
                }
            )
        if url.endswith("/substitute/v1/models/downloads/jobs/download-1"):
            return _FakeResponse(_download_job_payload(status="complete"))
        raise AssertionError(f"unexpected GET {url}")

    def fake_post(url: str, **kwargs: object) -> _FakeResponse:
        """Return one fake backend fingerprint job payload."""

        calls.append(("POST", url))
        assert kwargs["json"] == {
            "entries": [
                {
                    "kind": "loras",
                    "value": "models/lora.safetensors",
                    "sizeBytes": 123,
                    "modifiedAt": "2026-04-14T01:00:00Z",
                }
            ]
        }
        return _FakeResponse(_fingerprint_job_payload())

    def fake_post_with_download(url: str, **kwargs: object) -> _FakeResponse:
        """Return route-specific fake backend POST payloads."""

        calls.append(("POST", url))
        if url.endswith("/substitute/v1/models/fingerprints/refresh"):
            assert kwargs["json"] == {
                "entries": [
                    {
                        "kind": "loras",
                        "value": "models/lora.safetensors",
                        "sizeBytes": 123,
                        "modifiedAt": "2026-04-14T01:00:00Z",
                    }
                ]
            }
            return _FakeResponse(_fingerprint_job_payload())
        if url.endswith("/substitute/v1/models/downloads/civitai"):
            assert kwargs["json"] == {
                "kind": "loras",
                "sha256": "A" * 64,
                "downloadUrl": "https://civitai.com/api/download/models/200",
                "fileName": "lora.safetensors",
                "fileType": "Model",
                "metadataFormat": "SafeTensor",
                "pickleScanResult": "Success",
                "virusScanResult": "Success",
                "downloadPathPattern": "{base_model}\\{file_name}",
                "downloadPathTokens": {
                    "baseModel": "Anima",
                    "modelName": "Anima",
                    "versionName": "base-v1.0",
                    "creator": "creator",
                    "fileName": "lora.safetensors",
                },
                "apiKey": "secret",
            }
            return _FakeResponse(_download_job_payload(status="queued"))
        if url.endswith("/substitute/v1/models/downloads/jobs/download-1/cancel"):
            assert kwargs["json"] == {}
            return _FakeResponse(_download_job_payload(status="cancelled"))
        raise AssertionError(f"unexpected POST {url}")

    client = SubstituteBackendModelMetadataClient(
        ComfyEndpoint(host="10.0.0.2", port=8189),
        http_get=fake_get,
        http_post=fake_post_with_download,
    )

    capabilities = client.get_capabilities()
    models = client.list_models(("checkpoints", "loras"))
    refreshed_models = client.list_models(("loras",), refresh=True)
    hash_lookup = client.lookup_model_by_hash(kind="loras", sha256="a" * 64)
    queued_job = client.refresh_fingerprints(models)
    polled_job = client.get_fingerprint_job("job-1")
    latest_change = client.get_latest_model_catalog_change()
    download_job = client.start_civitai_model_download(
        kind="loras",
        sha256="a" * 64,
        download_url="https://civitai.com/api/download/models/200",
        file_name="lora.safetensors",
        file_type="Model",
        metadata_format="SafeTensor",
        pickle_scan_result="Success",
        virus_scan_result="Success",
        download_path_pattern="{base_model}\\{file_name}",
        download_path_tokens={
            "baseModel": "Anima",
            "modelName": "Anima",
            "versionName": "base-v1.0",
            "creator": "creator",
            "fileName": "lora.safetensors",
        },
        api_key="secret",
    )
    completed_download = client.get_model_download_job("download-1")
    cancelled_download = client.cancel_model_download_job("download-1")

    assert capabilities is not None
    assert capabilities.extension_version == "1.4.0"
    assert capabilities.features == ("model-metadata", "cube-library")
    assert capabilities.cube_library.available is True
    assert capabilities.cube_library.sugar_cubes_version == "0.9.0"
    assert capabilities.cube_library.versioned_dependency_readiness_supported is True
    assert capabilities.sugar_compile.available is True
    assert capabilities.sugar_compile.sugar_dsl_version == "0.2.0"
    assert capabilities.supported_model_kinds == ("checkpoints", "loras")
    assert capabilities.hash_lookup is True
    assert models[0].fingerprint.status is FingerprintStatus.MISSING
    assert refreshed_models[0].kind == "loras"
    assert hash_lookup is not None
    assert hash_lookup.status is BackendHashLookupStatus.COMPLETE
    assert hash_lookup.matches[0].value == "models/lora.safetensors"
    assert queued_job.status is JobStatus.COMPLETE
    assert polled_job is not None
    assert polled_job.entries[0].sha256 == "ABC123"
    assert latest_change is not None
    assert latest_change.revision == "rev2"
    assert latest_change.added[0].value == "models/lora.safetensors"
    assert download_job is not None
    assert download_job.status is ModelDownloadStatus.QUEUED
    assert completed_download is not None
    assert completed_download.status is ModelDownloadStatus.COMPLETE
    assert completed_download.result is not None
    assert completed_download.result.value == "models/lora.safetensors"
    assert completed_download.bytes_downloaded == 123
    assert completed_download.bytes_total == 123
    assert cancelled_download is not None
    assert cancelled_download.status is ModelDownloadStatus.CANCELLED
    assert calls == [
        ("GET", "http://10.0.0.2:8189/substitute/v1/capabilities"),
        (
            "GET",
            "http://10.0.0.2:8189/substitute/v1/models?kind=checkpoints&kind=loras",
        ),
        (
            "GET",
            "http://10.0.0.2:8189/substitute/v1/models?kind=loras&refresh=1",
        ),
        (
            "GET",
            f"http://10.0.0.2:8189/substitute/v1/models/by-hash/{'A' * 64}?kind=loras",
        ),
        ("POST", "http://10.0.0.2:8189/substitute/v1/models/fingerprints/refresh"),
        (
            "GET",
            "http://10.0.0.2:8189/substitute/v1/models/fingerprints/jobs/job-1",
        ),
        ("GET", "http://10.0.0.2:8189/substitute/v1/models/changes"),
        ("POST", "http://10.0.0.2:8189/substitute/v1/models/downloads/civitai"),
        (
            "GET",
            "http://10.0.0.2:8189/substitute/v1/models/downloads/jobs/download-1",
        ),
        (
            "POST",
            "http://10.0.0.2:8189/substitute/v1/models/downloads/jobs/download-1/cancel",
        ),
    ]


def test_backend_client_refresh_raises_when_model_catalog_unavailable() -> None:
    """Fresh model-catalog requests should fail instead of returning fake emptiness."""

    def fake_get(_url: str, **_kwargs: object) -> _FakeResponse:
        """Raise a transport-shaped error for the refresh call."""

        raise ValueError("backend unavailable")

    client = SubstituteBackendModelMetadataClient(
        ComfyEndpoint(host="10.0.0.2", port=8189),
        http_get=fake_get,
    )

    assert client.list_models(("loras",)) == ()
    with pytest.raises(RuntimeError, match="model catalog refresh failed"):
        client.list_models(("loras",), refresh=True)


def test_backend_client_warns_once_for_repeated_get_failures(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Repeated backend GET outages should not flood the warning log."""

    def fake_get(_url: str, **_kwargs: object) -> _FakeResponse:
        """Raise a transport-shaped error for each backend GET."""

        raise ValueError("backend unavailable")

    client = SubstituteBackendModelMetadataClient(
        ComfyEndpoint(host="10.0.0.2", port=8189),
        http_get=fake_get,
    )

    with caplog.at_level(
        logging.DEBUG,
        logger=(
            "sugarsubstitute.infrastructure.external."
            "substitute_backend_model_metadata_client"
        ),
    ):
        assert client.get_capabilities() is None
        assert client.get_capabilities() is None

    failure_records = [
        record
        for record in caplog.records
        if record.message.startswith("Substitute BackEnd GET failed")
    ]
    assert [record.levelno for record in failure_records] == [
        logging.WARNING,
        logging.DEBUG,
    ]


def test_backend_client_defaults_missing_sugar_compile_capabilities() -> None:
    """Old Backends without Sugar compile facts should parse compatibly."""

    payload = _capabilities_payload()
    del payload["sugarCompile"]

    client = SubstituteBackendModelMetadataClient(
        ComfyEndpoint(host="10.0.0.2", port=8189),
        http_get=lambda *_args, **_kwargs: _FakeResponse(payload),
    )

    capabilities = client.get_capabilities()

    assert capabilities is not None
    assert capabilities.sugar_compile.schema_version == 0
    assert capabilities.sugar_compile.sugar_dsl_version == ""


def test_backend_client_allows_missing_sugar_dsl_version() -> None:
    """Backends can advertise Sugar compile before exposing Sugar-DSL version."""

    payload = _capabilities_payload()
    sugar_compile = payload["sugarCompile"]
    assert isinstance(sugar_compile, dict)
    del sugar_compile["sugarDslVersion"]

    client = SubstituteBackendModelMetadataClient(
        ComfyEndpoint(host="10.0.0.2", port=8189),
        http_get=lambda *_args, **_kwargs: _FakeResponse(payload),
    )

    capabilities = client.get_capabilities()

    assert capabilities is not None
    assert capabilities.sugar_compile.available is True
    assert capabilities.sugar_compile.sugar_dsl_version == ""


def test_civitai_client_parses_by_hash_response_and_uses_bearer_token() -> None:
    """CivitAI client should normalize by-hash model-version responses."""

    calls: list[tuple[str, dict[str, str]]] = []

    def fake_get(url: str, **kwargs: object) -> _FakeResponse:
        """Return one CivitAI by-hash payload."""

        calls.append((url, dict(_typed_headers(kwargs["headers"]))))
        return _FakeResponse(_civitai_payload())

    client = CivitaiClient(
        http_get=fake_get,
        api_key="secret-token",
        clock=lambda: "2026-04-14T12:00:00Z",
    )

    result = client.lookup_model_version_by_hash("abc123")

    assert result.status is CivitaiLookupStatus.FOUND
    assert result.version is not None
    assert result.version.model_id == 100
    assert result.version.model_version_id == 200
    assert (
        result.version.model_page_url
        == "https://civitai.com/models/100?modelVersionId=200"
    )
    assert result.version.trained_words == ("trigger", "style")
    assert result.version.files[0].hashes["SHA256"] == "ABC123"
    assert (
        result.version.files[0].download_url
        == "https://civitai.com/api/download/models/200"
    )
    assert result.version.files[0].file_type == "Model"
    assert result.version.files[0].pickle_scan_result == "Success"
    assert result.version.files[0].virus_scan_result == "Success"
    assert result.version.images[0].url == "https://image.example/safe.jpg"
    assert calls == [
        (
            "https://civitai.com/api/v1/model-versions/by-hash/ABC123",
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "SugarSubstitute/1.0",
                "Authorization": "Bearer secret-token",
            },
        )
    ]


def test_civitai_client_returns_not_found_for_404() -> None:
    """CivitAI client should turn 404 responses into typed not-found results."""

    def fake_get(_url: str, **_kwargs: object) -> _FakeResponse:
        """Return one not-found response."""

        return _FakeResponse({}, status_code=404)

    result = CivitaiClient(http_get=fake_get).lookup_model_version_by_hash("ABC")

    assert result.status is CivitaiLookupStatus.NOT_FOUND


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
