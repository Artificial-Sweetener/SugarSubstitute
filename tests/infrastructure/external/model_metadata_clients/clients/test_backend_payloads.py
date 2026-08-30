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

"""Verify Substitute BackEnd model-metadata payload contracts."""

from __future__ import annotations

from substitute.domain.model_metadata import (
    BackendHashLookupStatus,
    FingerprintStatus,
    JobStatus,
    ModelDownloadStatus,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external import SubstituteBackendModelMetadataClient

from .support import (
    _FakeResponse,
    _backend_model_payload,
    _capabilities_payload,
    _download_job_payload,
    _fingerprint_job_payload,
    _hash_lookup_payload,
    _model_catalog_change_payload,
)


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
