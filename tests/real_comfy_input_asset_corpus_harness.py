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

"""Run semantic input asset discovery over the isolated managed Comfy corpus."""

from __future__ import annotations

from pathlib import Path

from tests.headless_comfy_workflow_corpus_harness import (
    HeadlessComfyWorkflowCorpusHarness,
    WorkflowCorpusReport,
)
from tests.real_comfy_direct_output_harness import ManagedComfyDirectOutputHarness


def run_real_comfy_input_asset_corpus_harness(
    repository_root: Path,
) -> WorkflowCorpusReport:
    """Import every bundled image workflow against isolated live definitions."""

    repository_root = repository_root.resolve()
    with ManagedComfyDirectOutputHarness(repository_root) as managed_comfy:
        template_root = managed_comfy.image_template_root()
        return HeadlessComfyWorkflowCorpusHarness(
            template_root=template_root,
            node_definitions=managed_comfy.node_definitions(),
        ).run()


if __name__ == "__main__":
    corpus_report = run_real_comfy_input_asset_corpus_harness(
        Path(__file__).resolve().parents[1]
    )
    print(corpus_report)
    raise SystemExit(0 if corpus_report.succeeded else 1)


__all__ = ["run_real_comfy_input_asset_corpus_harness"]
