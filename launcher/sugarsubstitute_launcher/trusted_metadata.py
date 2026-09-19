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

"""Verify signed release metadata against the launcher-embedded trust root."""

from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Final, Self, cast

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_der_public_key

from sugarsubstitute_shared.launcher_update.persistence import write_json_atomic


_ENVELOPE_SCHEMA_VERSION: Final = 1
_STATE_SCHEMA_VERSION: Final = 1


@dataclass(frozen=True, slots=True)
class VerifiedReleaseMetadata:
    """Carry one authenticated manifest and its rollback-protection identity."""

    manifest: dict[str, object]
    metadata_version: int
    signed_digest: str


class ReleaseMetadataVerifier:
    """Validate threshold Ed25519 signatures and freshness."""

    def __init__(
        self,
        *,
        trust_root_path: Path | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        """Load the immutable trust root and clock boundary."""

        self._trust_root_path = trust_root_path or _packaged_trust_root_path()
        self._now = now or (lambda: datetime.now(UTC))

    def verify(self, payload: object) -> VerifiedReleaseMetadata:
        """Return authenticated release metadata or reject it completely."""

        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("Unsupported signed release metadata schema.")
        signed = payload.get("signed")
        signatures = payload.get("signatures")
        if not isinstance(signed, dict) or not isinstance(signatures, list):
            raise ValueError("Signed release metadata envelope is invalid.")
        metadata_version = signed.get("metadata_version")
        manifest = signed.get("manifest")
        expires_utc = signed.get("expires_utc")
        if type(metadata_version) is not int or metadata_version <= 0:
            raise ValueError("Signed metadata version must be positive.")
        if not isinstance(manifest, dict) or not isinstance(expires_utc, str):
            raise ValueError("Signed release metadata payload is invalid.")
        expires = _parse_utc(expires_utc)
        if expires <= self._now():
            raise ValueError("Signed release metadata has expired.")
        root = _load_trust_root(self._trust_root_path)
        canonical = _canonical_json(signed)
        valid_key_ids: set[str] = set()
        keys = cast(dict[str, object], root["keys"])
        for signature_payload in signatures:
            if not isinstance(signature_payload, dict):
                raise ValueError("Release metadata signature is invalid.")
            key_id = signature_payload.get("key_id")
            signature = signature_payload.get("signature_base64")
            if not isinstance(key_id, str) or not isinstance(signature, str):
                raise ValueError("Release metadata signature is invalid.")
            key_payload = keys.get(key_id)
            if key_payload is None or key_id in valid_key_ids:
                continue
            try:
                _public_key(key_payload).verify(
                    base64.b64decode(signature, validate=True), canonical
                )
            except (InvalidSignature, ValueError) as error:
                raise ValueError(
                    "Release metadata signature verification failed."
                ) from error
            valid_key_ids.add(key_id)
        threshold = cast(int, root["threshold"])
        if len(valid_key_ids) < threshold:
            raise ValueError("Release metadata signature threshold was not met.")
        return VerifiedReleaseMetadata(
            manifest=manifest,
            metadata_version=metadata_version,
            signed_digest=hashlib.sha256(canonical).hexdigest(),
        )


@dataclass(frozen=True, slots=True)
class TrustedMetadataState:
    """Persist the highest authenticated metadata sequence seen by an install."""

    metadata_version: int
    signed_digest: str

    @classmethod
    def admit(
        cls, *, install_root: Path, metadata_version: int, signed_digest: str
    ) -> None:
        """Reject rollback/equivocation and atomically remember newer metadata."""

        path = install_root.resolve() / "launcher" / "trusted-metadata.json"
        current = cls._load(path)
        if current is not None:
            if metadata_version < current.metadata_version:
                raise ValueError("Signed release metadata rollback was rejected.")
            if (
                metadata_version == current.metadata_version
                and signed_digest != current.signed_digest
            ):
                raise ValueError("Signed release metadata equivocation was rejected.")
            if metadata_version == current.metadata_version:
                return
        write_json_atomic(
            path,
            {
                "metadata_version": metadata_version,
                "schema_version": _STATE_SCHEMA_VERSION,
                "signed_digest": _required_digest(signed_digest),
            },
        )

    @classmethod
    def _load(cls, path: Path) -> Self | None:
        """Load the trusted sequence or fail closed on corruption."""

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("Trusted release metadata state is unreadable.") from error
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("Unsupported trusted release metadata state schema.")
        version = payload.get("metadata_version")
        if type(version) is not int or version <= 0:
            raise ValueError("Trusted release metadata version is invalid.")
        return cls(
            metadata_version=version,
            signed_digest=_required_digest(payload.get("signed_digest")),
        )


def _packaged_trust_root_path() -> Path:
    """Resolve the trust root from a bundle or source checkout."""

    packaged = Path(getattr(sys, "_MEIPASS", "")) / "launcher_assets"
    candidate = packaged / "release-trust-root.json"
    if candidate.is_file():
        return candidate
    return Path(__file__).resolve().parents[2] / "launcher" / "release-trust-root.json"


def _load_trust_root(path: Path) -> dict[str, object]:
    """Load and validate the minimal embedded trust-root contract."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Unsupported release trust-root schema.")
    keys = payload.get("keys")
    threshold = payload.get("threshold")
    if not isinstance(keys, dict) or not keys:
        raise ValueError("Release trust root has no keys.")
    if type(threshold) is not int or not 1 <= threshold <= len(keys):
        raise ValueError("Release trust-root threshold is invalid.")
    return payload


def _public_key(payload: object) -> Ed25519PublicKey:
    """Decode one Ed25519 SubjectPublicKeyInfo trust-root entry."""

    if not isinstance(payload, dict) or payload.get("algorithm") != "ed25519":
        raise ValueError("Release trust-root key is invalid.")
    encoded = payload.get("public_key_der_base64")
    if not isinstance(encoded, str):
        raise ValueError("Release trust-root key is invalid.")
    key = load_der_public_key(base64.b64decode(encoded, validate=True))
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("Release trust-root key is not Ed25519.")
    return key


def _canonical_json(payload: object) -> bytes:
    """Serialize signed content with one language-independent canonical form."""

    return json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _parse_utc(value: str) -> datetime:
    """Parse one timezone-aware ISO-8601 instant as UTC."""

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Signed metadata expiry is invalid.") from error
    if parsed.tzinfo is None:
        raise ValueError("Signed metadata expiry must include a timezone.")
    return parsed.astimezone(UTC)


def _required_digest(value: object) -> str:
    """Return one canonical SHA256 digest."""

    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("Trusted metadata digest is invalid.")
    return value


__all__ = [
    "ReleaseMetadataVerifier",
    "TrustedMetadataState",
    "VerifiedReleaseMetadata",
]
