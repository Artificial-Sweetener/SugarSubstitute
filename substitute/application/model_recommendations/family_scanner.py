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

"""Identify supported families from bounded SafeTensor header inspection."""

from __future__ import annotations

from collections.abc import Callable, Iterator
import json
import os
from pathlib import Path
import struct
import time
from typing import Protocol

from substitute.domain.model_recommendations.catalog import (
    SUPPORTED_MODEL_FAMILIES,
    SupportedModelFamilyCatalog,
)
from substitute.domain.model_recommendations.models import ModelFamilyDefinition
from substitute.domain.model_recommendations.models import TensorShapeSignature
from substitute.domain.model_recommendations.scan_models import (
    DetectedModelFamily,
    ModelFamilyEvidenceKind,
    ModelFamilyScanResult,
    ModelFamilyScanStatus,
)

_MAX_HEADER_BYTES = 16 * 1024 * 1024


class ModelScanCancellation(Protocol):
    """Expose cancellation without coupling scanning to one executor."""

    @property
    def is_cancelled(self) -> bool:
        """Return whether the caller no longer needs this scan."""


class ExistingModelFamilyScanner:
    """Scan an explicit root without importing models or following links."""

    def __init__(
        self,
        *,
        catalog: SupportedModelFamilyCatalog = SUPPORTED_MODEL_FAMILIES,
        maximum_files: int = 5_000,
        timeout_seconds: float = 20.0,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """Store bounded traversal policy and the authoritative family catalog."""

        if maximum_files < 1:
            raise ValueError("Model scan file limit must be positive.")
        if timeout_seconds <= 0:
            raise ValueError("Model scan timeout must be positive.")
        self._catalog = catalog
        self._maximum_files = maximum_files
        self._timeout_seconds = timeout_seconds
        self._monotonic = monotonic

    def scan(
        self,
        root: Path,
        *,
        cancellation: ModelScanCancellation | None = None,
    ) -> ModelFamilyScanResult:
        """Return trusted family evidence from the explicitly selected root."""

        selected_root = root.resolve(strict=False)
        if not selected_root.is_dir():
            return ModelFamilyScanResult(
                selected_root,
                ModelFamilyScanStatus.FAILED,
                (),
                0,
                0,
                0,
                "The selected models folder is not an accessible directory.",
            )
        started = self._monotonic()
        detected: list[DetectedModelFamily] = []
        inspected = 0
        unreadable = 0
        unknown = 0
        try:
            for path in _iter_safetensors(selected_root):
                if cancellation is not None and cancellation.is_cancelled:
                    return _result(
                        selected_root,
                        ModelFamilyScanStatus.CANCELLED,
                        detected,
                        inspected,
                        unreadable,
                        unknown,
                    )
                if inspected >= self._maximum_files:
                    return _result(
                        selected_root,
                        ModelFamilyScanStatus.INCOMPLETE,
                        detected,
                        inspected,
                        unreadable,
                        unknown,
                        "The model scan reached its bounded file limit.",
                    )
                if self._monotonic() - started > self._timeout_seconds:
                    return _result(
                        selected_root,
                        ModelFamilyScanStatus.INCOMPLETE,
                        detected,
                        inspected,
                        unreadable,
                        unknown,
                        "The model scan reached its bounded time limit.",
                    )
                inspected += 1
                try:
                    header = _read_safetensor_header(path)
                except (OSError, ValueError, json.JSONDecodeError):
                    unreadable += 1
                    continue
                match = self._detect(path, header)
                if match is None:
                    unknown += 1
                else:
                    detected.append(match)
        except OSError as error:
            return _result(
                selected_root,
                ModelFamilyScanStatus.FAILED,
                detected,
                inspected,
                unreadable,
                unknown,
                f"Model folder traversal failed: {type(error).__name__}.",
            )
        return _result(
            selected_root,
            ModelFamilyScanStatus.COMPLETED,
            detected,
            inspected,
            unreadable,
            unknown,
        )

    def _detect(
        self,
        path: Path,
        header: dict[str, object],
    ) -> DetectedModelFamily | None:
        """Return the first catalog-ordered family with trusted evidence."""

        metadata_values = _normalized_metadata_values(header.get("__metadata__"))
        tensor_keys = tuple(key for key in header if key != "__metadata__")
        for family in self._catalog.families():
            if metadata_values.intersection(family.detection.metadata_values):
                return _match(
                    family,
                    path,
                    ModelFamilyEvidenceKind.SAFETENSOR_METADATA,
                )
            if _matches_tensor_shape_signatures(
                header,
                family.detection.tensor_shape_signatures,
            ):
                return _match(
                    family,
                    path,
                    ModelFamilyEvidenceKind.TENSOR_SIGNATURE,
                )
            if any(
                key.startswith(prefix)
                for prefix in family.detection.tensor_key_prefixes
                for key in tensor_keys
            ):
                return _match(
                    family,
                    path,
                    ModelFamilyEvidenceKind.TENSOR_SIGNATURE,
                )
        return None


def _matches_tensor_shape_signatures(
    header: dict[str, object],
    signatures: tuple[TensorShapeSignature, ...],
) -> bool:
    """Return whether every architecture marker matches one header tensor."""

    if not signatures:
        return False
    return all(
        any(
            key.endswith(signature.key_suffix)
            and _shape_matches(value, signature.shape)
            for key, value in header.items()
            if key != "__metadata__"
        )
        for signature in signatures
    )


def _shape_matches(value: object, expected: tuple[int | None, ...]) -> bool:
    """Match SafeTensor shape metadata without reading tensor payload bytes."""

    if not isinstance(value, dict):
        return False
    shape = value.get("shape")
    if not isinstance(shape, list) or len(shape) != len(expected):
        return False
    return all(
        isinstance(actual, int)
        and not isinstance(actual, bool)
        and (wanted is None or actual == wanted)
        for actual, wanted in zip(shape, expected, strict=True)
    )


def _iter_safetensors(root: Path) -> Iterator[Path]:
    """Yield candidate files without traversing symlinked directories."""

    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                if _is_linked_entry(entry):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                elif entry.is_file(
                    follow_symlinks=False
                ) and entry.name.casefold().endswith(".safetensors"):
                    yield Path(entry.path)


def _is_linked_entry(entry: os.DirEntry[str]) -> bool:
    """Return whether traversal would cross a symbolic link or Windows junction."""

    if entry.is_symlink():
        return True
    is_junction = getattr(entry, "is_junction", None)
    return bool(callable(is_junction) and is_junction())


def _read_safetensor_header(path: Path) -> dict[str, object]:
    """Read only a bounded SafeTensor JSON header from disk."""

    with path.open("rb") as stream:
        prefix = stream.read(8)
        if len(prefix) != 8:
            raise ValueError("SafeTensor header length is missing.")
        (header_size,) = struct.unpack("<Q", prefix)
        if header_size < 2 or header_size > _MAX_HEADER_BYTES:
            raise ValueError("SafeTensor header length is outside policy.")
        payload = stream.read(header_size)
    if len(payload) != header_size:
        raise ValueError("SafeTensor header is truncated.")
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("SafeTensor header must be a JSON object.")
    return {str(key): item for key, item in value.items()}


def _normalized_metadata_values(metadata: object) -> frozenset[str]:
    """Flatten string metadata values into case-insensitive evidence tokens."""

    if not isinstance(metadata, dict):
        return frozenset()
    values: set[str] = set()
    for key, value in metadata.items():
        if isinstance(key, str):
            values.add(key.strip().casefold())
        if isinstance(value, str):
            normalized = value.strip().casefold()
            values.add(normalized)
            try:
                nested = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                continue
            values.update(_flatten_strings(nested))
    return frozenset(values)


def _flatten_strings(value: object) -> set[str]:
    """Return normalized strings from decoded metadata containers."""

    if isinstance(value, str):
        return {value.strip().casefold()}
    if isinstance(value, dict):
        values: set[str] = set()
        for key, item in value.items():
            values.update(_flatten_strings(key))
            values.update(_flatten_strings(item))
        return values
    if isinstance(value, list):
        return {normalized for item in value for normalized in _flatten_strings(item)}
    return set()


def _match(
    family: ModelFamilyDefinition,
    path: Path,
    evidence_kind: ModelFamilyEvidenceKind,
) -> DetectedModelFamily:
    """Build one confident match from catalog-owned detection policy."""

    return DetectedModelFamily(family.family_id, path, evidence_kind)


def _result(
    root: Path,
    status: ModelFamilyScanStatus,
    detected: list[DetectedModelFamily],
    inspected: int,
    unreadable: int,
    unknown: int,
    diagnostic: str | None = None,
) -> ModelFamilyScanResult:
    """Build an immutable scan result with stable path ordering."""

    return ModelFamilyScanResult(
        root=root,
        status=status,
        detected=tuple(sorted(detected, key=lambda item: str(item.path).casefold())),
        inspected_count=inspected,
        unreadable_count=unreadable,
        unknown_count=unknown,
        diagnostic=diagnostic,
    )


__all__ = ["ExistingModelFamilyScanner", "ModelScanCancellation"]
