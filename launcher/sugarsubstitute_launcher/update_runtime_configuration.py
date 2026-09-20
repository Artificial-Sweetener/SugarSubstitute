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

"""Select the application runtime record with its paired release generation."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import json
import os
from pathlib import Path
import secrets

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout


_MAX_CONFIGURATION_BYTES = 64 * 1024
_READY_STATUS = "ready"


@dataclass(frozen=True, slots=True)
class RuntimeConfigurationSnapshot:
    """Preserve the exact pre-activation runtime record for durable rollback."""

    content_base64: str | None

    @classmethod
    def capture(cls, layout: InstallLayout) -> RuntimeConfigurationSnapshot:
        """Capture the canonical runtime record without synthesizing user state."""

        path = runtime_configuration_path(layout)
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            return cls(content_base64=None)
        if len(content) > _MAX_CONFIGURATION_BYTES:
            raise ValueError("Runtime configuration exceeds its supported size.")
        return cls(content_base64=base64.b64encode(content).decode("ascii"))

    @classmethod
    def from_json(cls, value: object) -> RuntimeConfigurationSnapshot:
        """Load one bounded snapshot while rejecting malformed journal data."""

        if not isinstance(value, dict) or set(value) != {"content_base64"}:
            raise ValueError("Runtime configuration snapshot is invalid.")
        encoded = value.get("content_base64")
        if encoded is not None and not isinstance(encoded, str):
            raise ValueError("Runtime configuration snapshot content is invalid.")
        snapshot = cls(content_base64=encoded)
        snapshot.content()
        return snapshot

    def to_json(self) -> dict[str, object]:
        """Return the stable journal representation."""

        return {"content_base64": self.content_base64}

    def content(self) -> bytes | None:
        """Return the validated original bytes or absence marker."""

        if self.content_base64 is None:
            return None
        try:
            content = base64.b64decode(self.content_base64, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError(
                "Runtime configuration snapshot encoding is invalid."
            ) from error
        if len(content) > _MAX_CONFIGURATION_BYTES:
            raise ValueError(
                "Runtime configuration snapshot exceeds its supported size."
            )
        return content


def runtime_configuration_path(layout: InstallLayout) -> Path:
    """Return the canonical application runtime record beneath the install root."""

    return layout.user_dir / "settings" / "runtime.json"


def select_candidate_runtime_configuration(
    *,
    layout: InstallLayout,
    candidate_layout: InstallLayout,
    snapshot: RuntimeConfigurationSnapshot | None,
) -> None:
    """Point an existing runtime record at the selected prepared generation."""

    if snapshot is None:
        return
    content = snapshot.content()
    if content is None:
        return
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Runtime configuration cannot be migrated safely.") from error
    if not isinstance(payload, dict):
        raise ValueError("Runtime configuration must be a JSON object.")
    _validate_runtime_configuration(payload)
    payload.update(
        runtime_root=str(candidate_layout.runtime_dir),
        python_executable=str(candidate_layout.runtime_python),
        bootstrap_status=_READY_STATUS,
    )
    _write_bytes_atomic(
        runtime_configuration_path(layout),
        (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )


def restore_runtime_configuration(
    layout: InstallLayout, snapshot: RuntimeConfigurationSnapshot | None
) -> None:
    """Restore the exact pre-activation runtime record during rollback."""

    if snapshot is None:
        return
    path = runtime_configuration_path(layout)
    content = snapshot.content()
    if content is None:
        path.unlink(missing_ok=True)
        return
    _write_bytes_atomic(path, content)


def _validate_runtime_configuration(payload: dict[str, object]) -> None:
    """Reject an unrecognized record rather than overwriting authoritative state."""

    runtime_root = payload.get("runtime_root")
    python_executable = payload.get("python_executable")
    bootstrap_status = payload.get("bootstrap_status")
    schema_version = payload.get("schema_version", "1")
    if (
        not isinstance(runtime_root, str)
        or not runtime_root
        or (python_executable is not None and not isinstance(python_executable, str))
        or not isinstance(bootstrap_status, str)
        or not bootstrap_status
        or not isinstance(schema_version, str)
        or not schema_version
    ):
        raise ValueError("Runtime configuration fields are invalid.")


def _write_bytes_atomic(path: Path, content: bytes) -> None:
    """Restore exact bytes through a same-directory durable replacement."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(
        f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    )
    try:
        with temporary_path.open("wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


__all__ = [
    "RuntimeConfigurationSnapshot",
    "restore_runtime_configuration",
    "runtime_configuration_path",
    "select_candidate_runtime_configuration",
]
