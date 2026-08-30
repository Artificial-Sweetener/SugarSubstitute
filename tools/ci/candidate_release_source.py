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

"""Expose exact release-candidate bytes to installer qualification children."""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from sugarsubstitute_shared.tls import EXTRA_CA_FILE_ENV
from tools.ci.local_release_server import LocalReleaseServer


@dataclass(frozen=True, slots=True)
class CandidateReleaseSource:
    """Describe one published or temporary candidate release source."""

    manifest_url: str | None
    certificate_path: Path | None
    request_log_path: Path | None = None


@contextmanager
def candidate_release_source(
    *,
    release_root: Path | None,
    manifest_url: str | None,
    certificate_root: Path,
) -> Iterator[CandidateReleaseSource]:
    """Serve temporary artifacts or retain one published manifest source."""

    if release_root is None:
        yield CandidateReleaseSource(
            manifest_url=manifest_url,
            certificate_path=None,
        )
        return
    with LocalReleaseServer(
        release_root=release_root,
        certificate_root=certificate_root,
    ) as server:
        yield CandidateReleaseSource(
            manifest_url=server.manifest_url,
            certificate_path=server.trust_bundle_path,
            request_log_path=server.request_log_path,
        )


def trust_candidate_source(
    environment: MutableMapping[str, str],
    candidate_source: CandidateReleaseSource,
) -> None:
    """Trust a temporary release certificate only in qualification children."""

    if candidate_source.certificate_path is None:
        return
    certificate_path = str(candidate_source.certificate_path)
    environment["SSL_CERT_FILE"] = certificate_path
    environment[EXTRA_CA_FILE_ENV] = certificate_path
    environment["UV_NATIVE_TLS"] = "1"
    environment["UV_SYSTEM_CERTS"] = "true"


__all__ = [
    "CandidateReleaseSource",
    "candidate_release_source",
    "trust_candidate_source",
]
