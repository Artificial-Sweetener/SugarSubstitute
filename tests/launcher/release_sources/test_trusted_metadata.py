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

"""Tests for authenticated, rollback-resistant release metadata."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.hazmat.primitives.serialization import (
    NoEncryption,
    PrivateFormat,
)

from launcher.sugarsubstitute_launcher.trusted_metadata import (
    ReleaseMetadataVerifier,
    TrustedMetadataState,
)
from tests.support.execution.node_runtime import run_node


_NOW = datetime(2026, 9, 18, 12, tzinfo=UTC)


def test_verifier_accepts_exact_signed_manifest(tmp_path: Path) -> None:
    """A trusted Ed25519 key should authenticate canonical manifest content."""

    verifier, envelope = _signed_envelope(tmp_path, metadata_version=42)

    verified = verifier.verify(envelope)

    assert verified.metadata_version == 42
    assert verified.manifest == {"channel": "canary", "version": "0.23.0"}


def test_verifier_rejects_manifest_tampering(tmp_path: Path) -> None:
    """Changing signed target metadata must invalidate its signature."""

    verifier, envelope = _signed_envelope(tmp_path, metadata_version=42)
    signed = envelope["signed"]
    assert isinstance(signed, dict)
    manifest = signed["manifest"]
    assert isinstance(manifest, dict)
    manifest["version"] = "0.23.1"

    with pytest.raises(ValueError, match="signature verification failed"):
        verifier.verify(envelope)


def test_verifier_rejects_expired_metadata(tmp_path: Path) -> None:
    """An old signed feed must not freeze clients indefinitely."""

    verifier, envelope = _signed_envelope(
        tmp_path, metadata_version=42, expires_utc="2026-09-18T11:59:59Z"
    )

    with pytest.raises(ValueError, match="expired"):
        verifier.verify(envelope)


def test_trusted_state_rejects_rollback_and_equivocation(tmp_path: Path) -> None:
    """An install should remember the highest exact metadata sequence it trusted."""

    first = "1" * 64
    TrustedMetadataState.admit(
        install_root=tmp_path, metadata_version=42, signed_digest=first
    )
    TrustedMetadataState.admit(
        install_root=tmp_path, metadata_version=42, signed_digest=first
    )

    with pytest.raises(ValueError, match="rollback"):
        TrustedMetadataState.admit(
            install_root=tmp_path, metadata_version=41, signed_digest="2" * 64
        )
    with pytest.raises(ValueError, match="equivocation"):
        TrustedMetadataState.admit(
            install_root=tmp_path, metadata_version=42, signed_digest="2" * 64
        )


def test_release_signer_emits_metadata_accepted_by_runtime_verifier(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Keep the release-time JavaScript signer compatible with runtime verification."""

    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        Encoding.PEM,
        PrivateFormat.PKCS8,
        NoEncryption(),
    ).decode("ascii")
    public_der = private_key.public_key().public_bytes(
        Encoding.DER, PublicFormat.SubjectPublicKeyInfo
    )
    key_id = hashlib.sha256(public_der).hexdigest()
    trust_root = tmp_path / "root.json"
    trust_root.write_text(
        json.dumps(
            {
                "keys": {
                    key_id: {
                        "algorithm": "ed25519",
                        "public_key_der_base64": base64.b64encode(public_der).decode(),
                    }
                },
                "schema_version": 1,
                "threshold": 1,
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"channel": "canary", "version": "0.23.0"}),
        encoding="utf-8",
    )
    signed_manifest = tmp_path / "manifest.signed.json"
    monkeypatch.setenv("SUGAR_SUBSTITUTE_RELEASE_SIGNING_KEY", private_pem)

    result = run_node(
        (
            "scripts/sign-release-metadata.mjs",
            str(manifest),
            str(signed_manifest),
            "42",
            str(int(_NOW.timestamp())),
        ),
        cwd=Path(__file__).resolve().parents[3],
        check=False,
    )

    assert result.returncode == 0, result.stderr
    envelope = json.loads(signed_manifest.read_text(encoding="utf-8"))
    verified = ReleaseMetadataVerifier(
        trust_root_path=trust_root,
        now=lambda: _NOW,
    ).verify(envelope)
    assert verified.metadata_version == 42
    assert verified.manifest == {"channel": "canary", "version": "0.23.0"}


def _signed_envelope(
    tmp_path: Path,
    *,
    metadata_version: int,
    expires_utc: str = "2027-03-17T12:00:00Z",
) -> tuple[ReleaseMetadataVerifier, dict[str, object]]:
    """Create an isolated one-key trust root and signed envelope."""

    private_key = Ed25519PrivateKey.generate()
    public_der = private_key.public_key().public_bytes(
        Encoding.DER, PublicFormat.SubjectPublicKeyInfo
    )
    key_id = hashlib.sha256(public_der).hexdigest()
    trust_root = tmp_path / "root.json"
    trust_root.write_text(
        json.dumps(
            {
                "keys": {
                    key_id: {
                        "algorithm": "ed25519",
                        "public_key_der_base64": base64.b64encode(public_der).decode(),
                    }
                },
                "schema_version": 1,
                "threshold": 1,
            }
        ),
        encoding="utf-8",
    )
    signed: dict[str, object] = {
        "expires_utc": expires_utc,
        "manifest": {"channel": "canary", "version": "0.23.0"},
        "metadata_version": metadata_version,
    }
    canonical = json.dumps(
        signed, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    envelope: dict[str, object] = {
        "schema_version": 1,
        "signatures": [
            {
                "key_id": key_id,
                "signature_base64": base64.b64encode(
                    private_key.sign(canonical)
                ).decode(),
            }
        ],
        "signed": signed,
    }
    return (
        ReleaseMetadataVerifier(trust_root_path=trust_root, now=lambda: _NOW),
        envelope,
    )
