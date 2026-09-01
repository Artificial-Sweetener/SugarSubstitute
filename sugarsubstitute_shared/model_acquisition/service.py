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

"""Download hash-identified model files atomically without overwriting user data."""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
import hashlib
from http.client import HTTPMessage
import logging
import os
from pathlib import Path
import secrets
import ssl
from typing import IO, Protocol
import urllib.request
from urllib.parse import urlparse

from sugarsubstitute_shared.model_acquisition.models import (
    AcquisitionProgress,
    AcquisitionResult,
    ModelAcquisitionCancelled,
    ModelAcquisitionError,
)
from sugarsubstitute_shared.model_discovery.models import DiscoveredModel
from sugarsubstitute_shared.tls import SystemTrustTlsContext

_CHUNK_SIZE = 1024 * 1024
_LOGGER = logging.getLogger(__name__)
_WINDOWS_RESERVED_STEMS = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)


class CancellationProbe(Protocol):
    """Report whether a caller has cancelled one acquisition."""

    def is_cancelled(self) -> bool:
        """Return true after cancellation is requested."""


class DownloadStream(Protocol):
    """Read a bounded HTTPS response body and release its transport."""

    @property
    def content_length(self) -> int | None:
        """Return a valid declared body length when available."""

    def read(self, size: int) -> bytes:
        """Read up to size bytes from the response."""

    def close(self) -> None:
        """Release the response and its network resources."""


StreamOpener = Callable[[str, Mapping[str, str], float], DownloadStream]
ProgressCallback = Callable[[AcquisitionProgress], None]


class ModelAcquisitionService:
    """Own safe destinations, transfer integrity, cancellation, and atomic commit."""

    def __init__(
        self,
        *,
        allowed_roots: Collection[Path],
        stream_opener: StreamOpener | None = None,
        api_key_provider: Callable[[], str | None] | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        """Store explicit model roots and a bounded secret-aware HTTPS boundary."""

        roots = tuple(root.resolve() for root in allowed_roots)
        if not roots:
            raise ValueError("Model acquisition requires at least one allowed root.")
        if timeout_seconds <= 0:
            raise ValueError("Model acquisition timeout must be positive.")
        self._allowed_roots = roots
        self._stream_opener = stream_opener or _open_stream
        self._api_key_provider = api_key_provider
        self._timeout_seconds = timeout_seconds

    def acquire(
        self,
        model: DiscoveredModel,
        *,
        destination_dir: Path,
        cancellation: CancellationProbe | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> AcquisitionResult:
        """Download one exact model beside existing files and verify before reveal."""

        expected_hash = _normalized_sha256(model.sha256)
        if model.size_bytes <= 0:
            raise ModelAcquisitionError("Model download size must be positive.")
        _require_download_url(model.download_url)
        file_name = _safe_file_name(model.file_name)
        destination = self._require_destination(destination_dir)
        destination.mkdir(parents=True, exist_ok=True)
        existing = self._matching_existing(
            destination,
            expected_hash,
            expected_size=model.size_bytes,
        )
        if existing is not None:
            return AcquisitionResult(
                path=existing,
                sha256=expected_hash,
                size_bytes=existing.stat().st_size,
                reused_existing=True,
            )
        final_path, reservation_token = _reserve_destination(
            destination,
            file_name=file_name,
            version_id=model.version_id,
        )
        partial = destination / f".{final_path.name}.{secrets.token_hex(8)}.part"
        headers = {
            "Accept": "application/octet-stream",
            "User-Agent": "SugarSubstitute/1.0",
        }
        api_key = self._api_key_provider() if self._api_key_provider else None
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        stream: DownloadStream | None = None
        committed = False
        try:
            stream = self._stream_opener(
                model.download_url,
                headers,
                self._timeout_seconds,
            )
            if (
                stream.content_length is not None
                and stream.content_length != model.size_bytes
            ):
                raise ModelAcquisitionError(
                    "Model response size does not match provider metadata."
                )
            digest = hashlib.sha256()
            received = 0
            with partial.open("xb") as output:
                while True:
                    if cancellation is not None and cancellation.is_cancelled():
                        raise ModelAcquisitionCancelled("Model download was cancelled.")
                    chunk = stream.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > model.size_bytes:
                        raise ModelAcquisitionError(
                            "Model response exceeded its declared size."
                        )
                    output.write(chunk)
                    digest.update(chunk)
                    if on_progress is not None:
                        on_progress(AcquisitionProgress(received, model.size_bytes))
                output.flush()
                os.fsync(output.fileno())
            if received != model.size_bytes:
                raise ModelAcquisitionError(
                    "Model response ended before its declared size."
                )
            if digest.hexdigest() != expected_hash:
                raise ModelAcquisitionError("Model download checksum mismatch.")
            os.replace(partial, final_path)
            committed = True
            return AcquisitionResult(
                path=final_path,
                sha256=expected_hash,
                size_bytes=received,
                reused_existing=False,
            )
        except ModelAcquisitionError:
            raise
        except (OSError, TimeoutError) as error:
            raise ModelAcquisitionError(
                "Model download could not be completed."
            ) from error
        finally:
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
            partial.unlink(missing_ok=True)
            if not committed:
                _remove_owned_reservation(final_path, reservation_token)

    def _require_destination(self, destination_dir: Path) -> Path:
        """Return a destination only when it belongs to an explicit model root."""

        if destination_dir.is_symlink():
            raise ModelAcquisitionError(
                "Model destination must not be a symbolic link."
            )
        resolved = destination_dir.resolve()
        destination_identity = _path_identity(resolved)
        if not any(
            destination_identity == root_identity
            or destination_identity.is_relative_to(root_identity)
            for root in self._allowed_roots
            for root_identity in (_path_identity(root.resolve()),)
        ):
            raise ModelAcquisitionError(
                "Model destination is outside configured roots."
            )
        return resolved

    @staticmethod
    def _matching_existing(
        destination: Path,
        sha256: str,
        *,
        expected_size: int,
    ) -> Path | None:
        """Return an existing SafeTensor with the requested size and hash."""

        for candidate in destination.glob("*.safetensors"):
            try:
                if (
                    candidate.is_file()
                    and not candidate.is_symlink()
                    and candidate.stat().st_size == expected_size
                    and _file_sha256(candidate) == sha256
                ):
                    return candidate
            except OSError:
                _LOGGER.debug(
                    "Skipped an unreadable model candidate during acquisition.",
                    exc_info=True,
                )
        return None


class _UrllibDownloadStream:
    """Adapt urllib's response object to the narrow acquisition stream."""

    def __init__(self, response: object, *, content_length: int | None) -> None:
        """Store one open response and its validated length."""

        self._response = response
        self._content_length = content_length

    @property
    def content_length(self) -> int | None:
        """Return the parsed Content-Length header."""

        return self._content_length

    def read(self, size: int) -> bytes:
        """Read response bytes through urllib's file-like contract."""

        read = getattr(self._response, "read")
        value = read(size)
        if not isinstance(value, bytes):
            raise OSError("Model response returned non-byte content.")
        return value

    def close(self) -> None:
        """Close the underlying response."""

        close = getattr(self._response, "close")
        close()


def _open_stream(
    url: str,
    headers: Mapping[str, str],
    timeout: float,
    *,
    tls_context: ssl.SSLContext | None = None,
) -> DownloadStream:
    """Open one trusted HTTPS body through system certificate trust."""

    request = urllib.request.Request(url, headers=dict(headers), method="GET")
    opener = urllib.request.build_opener(
        _SafeRedirectHandler(),
        urllib.request.HTTPSHandler(
            context=tls_context or SystemTrustTlsContext.create()
        ),
    )
    response = opener.open(request, timeout=timeout)  # noqa: S310 - guarded HTTPS.
    _require_safe_redirect_target(str(response.geturl()))
    raw_length = response.headers.get("Content-Length")
    content_length = int(raw_length) if raw_length and raw_length.isdigit() else None
    return _UrllibDownloadStream(response, content_length=content_length)


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keep redirects on HTTPS and prevent CivitAI credentials crossing origins."""

    def redirect_request(
        self,
        request: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        """Validate redirect transport and strip authorization cross-origin."""

        _require_safe_redirect_target(newurl)
        redirected = super().redirect_request(
            request,
            fp,
            code,
            msg,
            headers,
            newurl,
        )
        if redirected is None:
            return None
        if _origin(request.full_url) != _origin(newurl):
            redirected.remove_header("Authorization")
            redirected.unredirected_hdrs.pop("Authorization", None)
            redirected.unredirected_hdrs.pop("authorization", None)
        return redirected


def _require_download_url(value: str) -> None:
    """Reject redirects or injected origins before authentication headers exist."""

    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"civitai.com", "www.civitai.com"}
        or not parsed.path.startswith("/api/download/")
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ModelAcquisitionError(
            "Model download URL is not a trusted CivitAI route."
        )


def _require_safe_redirect_target(value: str) -> None:
    """Reject credential-bearing or transport-downgrading download redirects."""

    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ModelAcquisitionError("Model download redirected to an unsafe route.")


def _origin(value: str) -> tuple[str, str, int]:
    """Return a normalized URL origin for authorization forwarding policy."""

    parsed = urlparse(value)
    hostname = parsed.hostname or ""
    port = parsed.port if parsed.port is not None else 443
    return parsed.scheme.casefold(), hostname.casefold(), port


def _safe_file_name(value: str) -> str:
    """Return a portable provider file name without path or device semantics."""

    name = value.strip()
    stem = Path(name).stem
    if (
        not name
        or len(name) > 180
        or Path(name).name != name
        or not name.casefold().endswith(".safetensors")
        or any(ord(character) < 32 or character in '<>:"/\\|?*' for character in name)
        or stem.upper() in _WINDOWS_RESERVED_STEMS
        or name.endswith((".", " "))
    ):
        raise ModelAcquisitionError("Model file name is unsafe.")
    return name


def _path_identity(path: Path) -> Path:
    """Normalize equivalent Windows device paths for containment comparison."""

    if os.name != "nt":
        return path
    value = str(path)
    extended_unc_prefix = "\\\\?\\UNC\\"
    extended_prefix = "\\\\?\\"
    if value.casefold().startswith(extended_unc_prefix.casefold()):
        return Path(f"\\\\{value[len(extended_unc_prefix) :]}")
    if value.startswith(extended_prefix):
        return Path(value[len(extended_prefix) :])
    return path


def _reserve_destination(
    directory: Path,
    *,
    file_name: str,
    version_id: int,
) -> tuple[Path, bytes]:
    """Reserve a side-by-side final path across concurrent processes."""

    token = secrets.token_hex(16).encode("ascii")
    original = Path(file_name)
    candidates = [original.name]
    candidates.extend(
        f"{original.stem} (v{version_id}{'' if index == 0 else f'-{index}'}).safetensors"
        for index in range(1000)
    )
    for candidate_name in candidates:
        candidate = directory / candidate_name
        try:
            descriptor = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            continue
        with os.fdopen(descriptor, "wb") as reservation:
            reservation.write(token)
            reservation.flush()
            os.fsync(reservation.fileno())
        return candidate, token
    raise ModelAcquisitionError("Could not reserve a side-by-side model destination.")


def _remove_owned_reservation(path: Path, token: bytes) -> None:
    """Remove only the exact reservation marker created by this acquisition."""

    try:
        if path.read_bytes() == token:
            path.unlink()
    except (FileNotFoundError, OSError):
        return


def _normalized_sha256(value: str) -> str:
    """Return one exact lowercase hexadecimal SHA256 identity."""

    normalized = value.casefold()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ModelAcquisitionError("Model SHA256 identity is invalid.")
    return normalized


def _file_sha256(path: Path) -> str:
    """Hash one existing model file without loading it into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "CancellationProbe",
    "DownloadStream",
    "ModelAcquisitionService",
    "ProgressCallback",
    "StreamOpener",
]
