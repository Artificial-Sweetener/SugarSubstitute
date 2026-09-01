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

"""Verify atomic, cancellable, side-by-side model acquisition."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPMessage
from io import BytesIO
from pathlib import Path
from threading import Barrier
import urllib.request

import pytest

from sugarsubstitute_shared.model_acquisition import (
    ModelAcquisitionCancelled,
    ModelAcquisitionError,
    ModelAcquisitionService,
)
from sugarsubstitute_shared.model_discovery.models import (
    DiscoveredModel,
    ModelCategory,
)
from sugarsubstitute_shared.model_acquisition import service as acquisition_service


class _Stream:
    """Yield deterministic response bytes through the production stream port."""

    def __init__(self, content: bytes, *, declared_length: int | None = None) -> None:
        """Store response bytes and optional header length."""

        self._content = content
        self._offset = 0
        self._declared_length = declared_length
        self.closed = False

    @property
    def content_length(self) -> int | None:
        """Return the injected Content-Length value."""

        return self._declared_length

    def read(self, size: int) -> bytes:
        """Read one deterministic chunk."""

        value = self._content[self._offset : self._offset + size]
        self._offset += len(value)
        return value

    def close(self) -> None:
        """Record transport cleanup."""

        self.closed = True


class _Cancellation:
    """Cancel the acquisition at its first probe."""

    def is_cancelled(self) -> bool:
        """Always report cancellation."""

        return True


def _model(
    content: bytes,
    *,
    download_url: str = "https://civitai.com/api/download/models/20",
    file_name: str = "sample.safetensors",
) -> DiscoveredModel:
    """Build one safe discovered model matching supplied bytes."""

    model = DiscoveredModel(
        category=ModelCategory.CHECKPOINTS,
        model_id=10,
        version_id=20,
        model_name="Sample",
        version_name="v1",
        creator="Creator",
        base_model="SDXL",
        file_name=file_name,
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        download_url=download_url,
        model_page_url="https://civitai.com/models/10",
        thumbnail_url=None,
        provider_rank=1,
    )
    return model


def test_acquisition_verifies_and_atomically_reveals_exact_file(tmp_path: Path) -> None:
    """Only complete bytes with the discovered SHA may appear at the final path."""

    content = b"safe-model-content"
    stream = _Stream(content, declared_length=len(content))
    captured_headers: dict[str, str] = {}

    def open_stream(
        _url: str,
        headers: Mapping[str, str],
        _timeout: float,
    ) -> _Stream:
        """Capture authentication headers and return the fake response."""

        captured_headers.update(headers)
        return stream

    model_root = tmp_path / "models"
    result = ModelAcquisitionService(
        allowed_roots=(model_root,),
        stream_opener=open_stream,
        api_key_provider=lambda: "secret-key",
    ).acquire(_model(content), destination_dir=model_root / "checkpoints")

    assert result.path.read_bytes() == content
    assert result.reused_existing is False
    assert captured_headers["Authorization"] == "Bearer secret-key"
    assert stream.closed
    assert not tuple(result.path.parent.glob("*.part"))


def test_hash_mismatch_removes_partial_and_owned_reservation(tmp_path: Path) -> None:
    """Corrupt provider bytes must leave no visible model or partial artifact."""

    expected = b"expected"
    actual = b"corrupt!"
    root = tmp_path / "models"
    destination = root / "checkpoints"
    service = ModelAcquisitionService(
        allowed_roots=(root,),
        stream_opener=lambda _url, _headers, _timeout: _Stream(actual),
    )

    with pytest.raises(ModelAcquisitionError, match="checksum"):
        service.acquire(_model(expected), destination_dir=destination)

    assert tuple(destination.iterdir()) == ()


def test_existing_name_is_preserved_and_new_version_uses_side_by_side_path(
    tmp_path: Path,
) -> None:
    """A different existing file must never be overwritten by acquisition."""

    content = b"new-version"
    root = tmp_path / "models"
    destination = root / "checkpoints"
    destination.mkdir(parents=True)
    existing = destination / "sample.safetensors"
    existing.write_bytes(b"user-owned-old-version")

    result = ModelAcquisitionService(
        allowed_roots=(root,),
        stream_opener=lambda _url, _headers, _timeout: _Stream(content),
    ).acquire(_model(content), destination_dir=destination)

    assert existing.read_bytes() == b"user-owned-old-version"
    assert result.path.name == "sample (v20).safetensors"
    assert result.path.read_bytes() == content


def test_cancellation_cleans_every_transaction_owned_file(tmp_path: Path) -> None:
    """Cancellation before transfer should not expose a reserved or partial model."""

    content = b"content"
    root = tmp_path / "models"
    destination = root / "checkpoints"

    with pytest.raises(ModelAcquisitionCancelled):
        ModelAcquisitionService(
            allowed_roots=(root,),
            stream_opener=lambda _url, _headers, _timeout: _Stream(content),
        ).acquire(
            _model(content),
            destination_dir=destination,
            cancellation=_Cancellation(),
        )

    assert tuple(destination.iterdir()) == ()


@pytest.mark.parametrize(
    ("download_url", "file_name", "destination"),
    [
        ("https://evil.example/api/download/20", "sample.safetensors", "inside"),
        (
            "https://civitai.com/api/download/models/20",
            "../escape.safetensors",
            "inside",
        ),
        (
            "https://civitai.com/api/download/models/20",
            "sample.safetensors",
            "outside",
        ),
    ],
)
def test_acquisition_rejects_hostile_url_name_and_destination(
    tmp_path: Path,
    download_url: str,
    file_name: str,
    destination: str,
) -> None:
    """External metadata cannot escape the trusted origin or configured roots."""

    content = b"content"
    root = tmp_path / "models"
    selected_destination = (
        root / "checkpoints" if destination == "inside" else tmp_path / "outside"
    )
    service = ModelAcquisitionService(
        allowed_roots=(root,),
        stream_opener=lambda _url, _headers, _timeout: _Stream(content),
    )

    with pytest.raises(ModelAcquisitionError):
        service.acquire(
            _model(content, download_url=download_url, file_name=file_name),
            destination_dir=selected_destination,
        )


def test_cross_origin_redirect_strips_authorization_and_rejects_downgrade() -> None:
    """Signed-storage redirects may proceed without leaking the CivitAI token."""

    request = urllib.request.Request(
        "https://civitai.com/api/download/models/20",
        headers={"Authorization": "Bearer secret"},
    )
    handler = acquisition_service._SafeRedirectHandler()

    redirected = handler.redirect_request(
        request,
        BytesIO(),
        302,
        "Found",
        HTTPMessage(),
        "https://signed-storage.example/model.safetensors",
    )

    assert redirected is not None
    assert redirected.get_header("Authorization") is None
    with pytest.raises(ModelAcquisitionError, match="unsafe route"):
        handler.redirect_request(
            request,
            BytesIO(),
            302,
            "Found",
            HTTPMessage(),
            "http://signed-storage.example/model.safetensors",
        )


def test_acquisition_does_not_hash_incomplete_model_sized_reservations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incomplete candidates must not enter installed-model identity checks."""

    content = b"complete-model"
    root = tmp_path / "models"
    destination = root / "checkpoints"
    destination.mkdir(parents=True)
    (destination / "sample.safetensors").write_bytes(b"reservation-marker")

    def reject_hash(_path: Path) -> str:
        """Fail if an incomplete candidate reaches the hashing boundary."""

        raise AssertionError("Incomplete candidates must not be hashed.")

    monkeypatch.setattr(acquisition_service, "_file_sha256", reject_hash)
    service = ModelAcquisitionService(
        allowed_roots=(root,),
        stream_opener=lambda _url, _headers, _timeout: _Stream(content),
    )

    result = service.acquire(_model(content), destination_dir=destination)

    assert result.path.name == "sample (v20).safetensors"
    assert result.path.read_bytes() == content


def test_concurrent_acquisitions_commit_distinct_side_by_side_files(
    tmp_path: Path,
) -> None:
    """Concurrent processes must not overwrite or steal each other's reservation."""

    content = b"concurrent-content"
    root = tmp_path / "models"
    destination = root / "checkpoints"
    opened = Barrier(2, timeout=30)

    def open_stream(_url: str, _headers: object, _timeout: float) -> _Stream:
        """Hold both transfers until both final paths have been reserved."""

        opened.wait(timeout=30)
        return _Stream(content)

    service = ModelAcquisitionService(
        allowed_roots=(root,),
        stream_opener=open_stream,
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                service.acquire,
                _model(content),
                destination_dir=destination,
            )
            for _index in range(2)
        ]
        results = tuple(future.result(timeout=45) for future in futures)

    assert len({result.path for result in results}) == 2
    assert all(result.path.read_bytes() == content for result in results)
    assert not tuple(destination.glob("*.part"))
