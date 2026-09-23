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

"""Verify mounted prompt-editor document replacement coordination."""

from __future__ import annotations

from dataclasses import dataclass, field

from substitute.application.prompt_editor.document.semantics import (
    OrdinaryPromptDocumentSemantics,
    PromptDocumentSemantics,
)
from substitute.presentation.editor.prompt_editor.document_facade import (
    PromptEditorDocumentBindings,
    PromptEditorDocumentFacade,
)


@dataclass(slots=True)
class _DocumentRecorder:
    """Record document commands and semantic invalidation order."""

    semantics_changed: bool
    calls: list[object] = field(default_factory=list)

    def replace_semantics(self, semantics: PromptDocumentSemantics) -> bool:
        """Record semantics replacement and return configured change state."""

        self.calls.append(("semantics", semantics))
        return self.semantics_changed

    def replace_baseline(self, text: str, *, exact_source: bool = False) -> None:
        """Record baseline source replacement."""

        self.calls.append(("baseline", text, exact_source))

    def interaction_changed(self) -> None:
        """Record interaction invalidation."""

        self.calls.append("interaction")

    def diagnostics_changed(self) -> None:
        """Record diagnostics invalidation."""

        self.calls.append("diagnostics")

    def lora_changed(self) -> None:
        """Record LoRA action invalidation."""

        self.calls.append("lora")

    def flush_semantic_refresh(self, *, reason: str) -> None:
        """Record synchronous semantic publication for document commands."""

        self.calls.append(("semantic_flush", reason))


def test_semantics_change_replaces_exact_baseline_before_invalidating_features() -> (
    None
):
    """Dependent features observe the new semantics and exact source together."""

    recorder = _DocumentRecorder(semantics_changed=True)
    facade = _facade(recorder)
    semantics = OrdinaryPromptDocumentSemantics()

    facade.replace_baseline_document("raw, source", semantics)

    assert recorder.calls == [
        ("semantics", semantics),
        ("baseline", "raw, source", True),
        ("semantic_flush", "replace_baseline_text"),
        "interaction",
        "diagnostics",
        "lora",
    ]


def test_stable_semantics_replaces_baseline_without_false_invalidation() -> None:
    """Restoring source under unchanged semantics avoids redundant feature work."""

    recorder = _DocumentRecorder(semantics_changed=False)
    facade = _facade(recorder)
    semantics = OrdinaryPromptDocumentSemantics()

    facade.replace_baseline_document("restored", semantics)

    assert recorder.calls == [
        ("semantics", semantics),
        ("baseline", "restored", True),
        ("semantic_flush", "replace_baseline_text"),
    ]


def _facade(recorder: _DocumentRecorder) -> PromptEditorDocumentFacade:
    """Bind one recorder to the production document facade."""

    return PromptEditorDocumentFacade(
        PromptEditorDocumentBindings(
            set_plain_text=lambda _text: None,
            set_source_text=lambda _text: None,
            replace_baseline_text=recorder.replace_baseline,
            replace_document_text=lambda _text: None,
            replace_document_text_with_prompt_state=(lambda _text, **_state: None),
            replace_semantics=recorder.replace_semantics,
            replace_conditioning_context=lambda _context: False,
            publish_interaction_semantics_changed=recorder.interaction_changed,
            publish_diagnostics_semantics_changed=recorder.diagnostics_changed,
            publish_lora_source_changed=recorder.lora_changed,
            flush_semantic_refresh=recorder.flush_semantic_refresh,
        )
    )
