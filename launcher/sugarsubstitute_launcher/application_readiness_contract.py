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

"""Negotiate and relay readiness contracts across historical launcher generations."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import secrets

from launcher.sugarsubstitute_launcher.application_startup_contract import (
    ApplicationReadinessError,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_readiness import (
    ApplicationReadinessReceipt,
    READINESS_ACCEPTED_SCHEMA_VERSIONS_ENV,
    READINESS_DELEGATION_PATH_ENV,
    READINESS_DELEGATION_SCHEMA_ENV,
    READINESS_DELEGATION_TOKEN_ENV,
    READINESS_PATH_ENV,
    READINESS_LEGACY_DELEGATION_SCHEMA_VERSION,
    READINESS_SCHEMA_ENV,
    READINESS_SCHEMA_VERSION,
    READINESS_TOKEN_ENV,
    WRITABLE_READINESS_SCHEMA_VERSIONS,
    publish_application_readiness_receipt,
)


@dataclass(frozen=True, slots=True)
class OuterReadinessReceipt:
    """Identify one supervising ancestor's authenticated receipt."""

    path: Path
    token: str
    schema_version: int


@dataclass(frozen=True, slots=True)
class ReadinessContract:
    """Separate the child proof from every supervising ancestor's proof."""

    child_receipt_path: Path
    child_token: str
    outer_receipts: tuple[OuterReadinessReceipt, ...]


def resolve_readiness_contract(
    *,
    layout: InstallLayout,
    environment: Mapping[str, str],
    token_factory: Callable[[], str],
) -> ReadinessContract:
    """Adopt a complete outer proof contract or create a private one."""

    external_path = environment.get(READINESS_PATH_ENV)
    external_token = environment.get(READINESS_TOKEN_ENV)
    external_schema = environment.get(READINESS_SCHEMA_ENV)
    delegated_path = environment.get(READINESS_DELEGATION_PATH_ENV)
    delegated_token = environment.get(READINESS_DELEGATION_TOKEN_ENV)
    delegated_schema = environment.get(READINESS_DELEGATION_SCHEMA_ENV)
    if bool(external_path) != bool(external_token):
        raise ApplicationReadinessError(
            "Application readiness path and token must be supplied together."
        )
    if bool(delegated_path) != bool(delegated_token):
        raise ApplicationReadinessError(
            "Application readiness delegation path and token must be supplied together."
        )
    if external_schema and not (external_path and external_token):
        raise ApplicationReadinessError(
            "Application readiness schema requires a path and token."
        )
    if delegated_schema and not (delegated_path and delegated_token):
        raise ApplicationReadinessError(
            "Application readiness delegation schema requires a path and token."
        )
    outer_receipts = tuple(
        OuterReadinessReceipt(
            path=Path(path).expanduser().resolve(),
            token=token,
            schema_version=_resolve_outer_schema_version(
                declared_schema=schema,
                advertised_versions=environment.get(
                    READINESS_ACCEPTED_SCHEMA_VERSIONS_ENV
                ),
            ),
        )
        for path, token, schema in (
            (external_path, external_token, external_schema),
            (delegated_path, delegated_token, delegated_schema),
        )
        if path and token
    )
    if len(outer_receipts) == 2 and (outer_receipts[0].path == outer_receipts[1].path):
        if outer_receipts[0] != outer_receipts[1]:
            raise ApplicationReadinessError(
                "Application readiness contracts conflict at one receipt path."
            )
        outer_receipts = outer_receipts[:1]
    if outer_receipts:
        return ReadinessContract(
            child_receipt_path=(
                layout.launcher_dir
                / "readiness"
                / f"candidate-{secrets.token_hex(16)}.json"
            ),
            child_token=token_factory(),
            outer_receipts=outer_receipts,
        )
    return ReadinessContract(
        child_receipt_path=layout.launcher_dir / "readiness" / "candidate.json",
        child_token=token_factory(),
        outer_receipts=(),
    )


def publish_outer_receipt(
    *,
    contract: ReadinessContract,
    receipt: ApplicationReadinessReceipt,
) -> None:
    """Preserve the painted process while attesting through this process hop."""

    for target in contract.outer_receipts:
        publish_application_readiness_receipt(
            receipt_path=target.path,
            receipt=ApplicationReadinessReceipt(
                pid=receipt.pid,
                token=target.token,
                surface=receipt.surface,
                parent_pid=(
                    receipt.parent_pid
                    if target.schema_version >= READINESS_SCHEMA_VERSION
                    else os.getpid()
                ),
                milestones=receipt.milestones,
                attester_pids=extended_attestation_chain(receipt),
            ),
            schema_version=target.schema_version,
        )


def _resolve_outer_schema_version(
    *,
    declared_schema: str | None,
    advertised_versions: str | None,
) -> int:
    """Resolve an explicit schema, negotiated capability, or legacy fallback."""

    if declared_schema is not None:
        return _compatible_outer_schema(declared_schema)
    if advertised_versions is None:
        return READINESS_LEGACY_DELEGATION_SCHEMA_VERSION
    raw_versions = advertised_versions.split(",")
    if not raw_versions or any(
        not raw_version or not raw_version.isdecimal() for raw_version in raw_versions
    ):
        raise ApplicationReadinessError(
            "Application readiness schema capabilities are invalid."
        )
    compatible_versions = {
        int(raw_version)
        for raw_version in raw_versions
        if int(raw_version) in WRITABLE_READINESS_SCHEMA_VERSIONS
    }
    if not compatible_versions:
        raise ApplicationReadinessError(
            "Application readiness schema capabilities are incompatible."
        )
    return max(compatible_versions)


def extended_attestation_chain(
    receipt: ApplicationReadinessReceipt,
) -> tuple[int, ...]:
    """Append this supervisor and its OS parent without duplicating prior hops."""

    process_ids = (*receipt.attester_pids, os.getpid(), os.getppid())
    return tuple(
        dict.fromkeys(process_id for process_id in process_ids if process_id > 0)
    )


def _compatible_outer_schema(raw_schema: str | None) -> int:
    """Return the richest schema a declared or pre-negotiation outer accepts."""

    if raw_schema is None:
        return READINESS_LEGACY_DELEGATION_SCHEMA_VERSION
    try:
        requested = int(raw_schema)
    except ValueError as error:
        raise ApplicationReadinessError(
            "Application readiness schema must be an integer."
        ) from error
    if requested <= 0:
        raise ApplicationReadinessError(
            "Application readiness schema must be positive."
        )
    return min(requested, READINESS_SCHEMA_VERSION)
