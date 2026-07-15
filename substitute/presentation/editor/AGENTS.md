# AGENTS.md

## Scope

This file governs work under `substitute/presentation/editor/`.

It adds editor-specific engineering rules for the editor panel, prompt editor, node-card editing surfaces, field widgets, context menus, and editor lifecycle code. Repository-level `AGENTS.md` still applies.

## Source Ownership Standard

Editor work must preserve strict separation of concerns.

Every source file must have one coherent responsibility and one primary reason
to change. If a change touches a mixed-responsibility area, first identify the
actual owner for the behavior, then move new or changed behavior to that owner
instead of expanding the mixed file.

Behavior remains governed by the product contract below and by characterization
tests.

## Documentation Truthfulness

Document the product and code as they exist now.

- Describe implemented package shape and current ownership as facts.
- Label remediation targets as targets until code and guardrails prove they
  are current behavior.
- Do not describe removed features, imagined alternatives, or non-existent
  choices as current product behavior.

## Editor Mission

The editor must feel immediate, stable, and professional under normal and large workflows. The standard is mature desktop-editor responsiveness: typing, selection, scrolling, painting, context menus, and focus changes should feel predictable and uninterrupted.

The application is a PySide6 desktop app with qfluent styling. Preserve native desktop behavior, qfluent visual conventions, and prompt-specific rich editor features while keeping the GUI thread responsive.

## Product Contract

Performance work must not silently remove editor capabilities.

Preserve current behavior unless the maintainer explicitly approves a product change:

- Source-backed editing, cursor movement, anchor state, selection, clipboard, undo, and redo.
- Raw/source rendering and rich/projected rendering.
- Autocomplete, ghost text, keyboard and mouse acceptance, and panel geometry.
- LoRA syntax, chips, weights, picker, trigger words, banners, thumbnails, and model-page actions.
- Wildcard syntax, autocomplete, diagnostics, numeric tags, and step controls.
- Emphasis syntax, nested emphasis, weight mutation, exact edit mode, and feedback states.
- Diagnostics, diagnostic visibility policy, context actions, and stale async behavior.
- Draggable chip reorder mode, drag preview, keyboard reorder, commit, cancel, and undo.
- Scene-aware prompt behavior, scene autocomplete, effective scene prompt context, queue actions, and source-line chrome.
- Context-menu utilities, saved prompt segments, Danbooru URL import, Danbooru wiki lookup, and qfluent text-action parity.
- Restore, warmup, cache, lifecycle, deleted Qt wrapper tolerance, and prompt-safe observability behavior.

## Performance-First Architecture

Responsiveness is an architectural requirement, not a late optimization pass.

- Keep keypress, cursor movement, selection, scroll, paint, resize, focus, and context-menu open paths bounded and predictable.
- Do not perform parsing, catalog lookup, thumbnail IO, filesystem IO, network IO, diagnostics refresh, or full semantic recomputation directly inside hot GUI paths unless the work is proven trivial and covered by tests.
- Coalesce expensive work aggressively while preserving latest-source correctness.
- Prefer incremental updates only when ownership, invalidation, and fallback behavior are clear.
- Use full rebuilds when they are simpler and safe, but keep them off hot paths or behind measured/coalesced scheduling.
- Paint must consume prepared state. Paint must not discover semantic state, perform IO, or trigger expensive refreshes.
- Scroll and resize must update geometry and visibility, not rebuild unrelated semantic data.
- Context menus must not synchronously resolve catalogs, thumbnails, network-backed data, or slow diagnostics.
- Thumbnail, banner, autocomplete, diagnostics, and scheduled-LoRA work must be async, cached, cancellable or stale-safe, and best-effort where appropriate.
- Any new slow path must include characterization, regression, or instrumentation coverage that would catch user-visible latency or stale-state regressions.

## Separation Of Concerns

Keep one authoritative owner per concern.

- Editor shell widgets own PySide6/qfluent integration, focus, sizing, scrollbars, context-menu routing, host events, and public widget facade behavior.
- Projection surfaces own painting, caret drawing, selection geometry, source-to-projection mapping, hit testing, and viewport-local rendering caches.
- Interaction controllers own gesture orchestration, keyboard/mouse routing, transient editor modes, scheduling decisions, and coordination between services and widgets.
- Application services own document parsing, source queries, autocomplete ranges, normalization, scene materialization, feature-profile decisions, prompt mutations, and cacheable pure editor behavior.
- Domain code owns pure prompt semantics and persisted behavior contracts.
- Infrastructure/adapters own filesystem, model catalogs, thumbnails, network-backed services, subprocesses, and worker dispatch.

Do not create parallel owners for source text, cursor state, selection, projection geometry, feature gates, diagnostics state, scene context, or cache invalidation. If a change appears to require duplicated ownership, stop and correct the ownership boundary.

## Feature Completeness Expectations

The editor should remain a rich, professional prompt-authoring surface:

- Plain editing must be as dependable as a normal text editor.
- Prompt-specific rendering must enhance editing without making source behavior surprising.
- Autocomplete and ghost text must feel immediate and must never mutate source before acceptance.
- Semantic tokens must remain selectable, copyable, undoable, and source-backed.
- LoRA, wildcard, emphasis, diagnostics, scene, and reorder features are first-class editor behavior, not optional decoration.
- qfluent menus and actions must remain visually and behaviorally consistent with the rest of the app.
- Large prompts should remain usable without the user noticing background refresh, catalog, thumbnail, or diagnostics work.

## PySide6 And qfluent Rules

- Keep Qt types in presentation layers unless there is a deliberate adapter boundary.
- Keep pure application and domain services free of Qt objects where feasible.
- Use qfluent widgets, menus, icons, sizing, and styling conventions when extending editor UI.
- Never block the GUI thread on IO, network, catalog loading, thumbnail decoding, subprocesses, or backend calls.
- Use queued/deferred work deliberately. A timer or queued callback must have an ownership reason, cancellation/staleness behavior, and deterministic tests where practical.
- Treat deleted Qt wrappers as a lifecycle hazard only in narrow known cases. Catch deleted-object `RuntimeError` narrowly and re-raise unrelated failures.
- Keep event filters and signal connections owned, removable, and lifecycle-safe.

## Cache And Async Rules

- Cache keys must include every input that can affect output: source text or source hash, feature profile, syntax profile, catalog revision, wildcard revision, scene parsing version, viewport geometry, palette/font where relevant, and context tokens.
- Cache eviction must be bounded and deterministic.
- Async results must prove they still apply to the current source, query identity, feature profile, and context token before publishing.
- Failures must clear pending state and log actionable context without logging prompt text.
- Background warmup must never be required for immediate editor correctness.
- Synchronous fallback may preserve immediate correctness while warmup is pending
  only when it is cheap, bounded, behavior-preserving, and safe for the current
  GUI path.
- Synchronous fallback must not perform catalog listing or refresh, scene
  materialization, effective-prompt recomputation, diagnostics or spellcheck
  refresh, thumbnail or media IO/decode, filesystem IO, network IO, subprocess
  work, model listing, prompt-preset loading, wildcard traversal, or
  scheduled-LoRA resolution in keypress, cursor, selection, paint, scroll,
  resize, focus, hover, context-menu-open, popup-open, or panel-reveal paths.

## Testing Requirements

Before refactoring behavior-critical editor code, identify the characterization tests that protect that behavior. If coverage is missing, add characterization tests first.

Use the prompt editor characterization suites and contract tests as guardrails:

- `tests/test_prompt_editor_phase1_characterization.py`
- `tests/test_prompt_editor_phase2_characterization.py`
- `tests/test_prompt_editor_phase3_characterization.py`
- `tests/test_prompt_editor_phase4_characterization.py`
- `tests/test_prompt_editor_phase5_characterization.py`
- Existing prompt editor service, projection, autocomplete, diagnostics, context-menu, sizing, scene, and lifecycle contract tests.

For editor refactors:

- Run focused tests for the touched behavior.
- Run full repository gates before reporting completion.
- Do not claim behavior preservation from code inspection alone.
- Add tests for both success and stale/failure paths when touching async behavior.
- Add cache-boundary tests when introducing or changing cache keys, eviction, or invalidation.

## Observability

Editor observability must help diagnose performance and stale-state issues without exposing prompt content.

- Log slow paths with operation names, durations, counts, cache sizes, cache revisions, feature state, source lengths, query identities, and context tokens where useful.
- Do not log prompt text, selected prompt text, trigger words from user prompts, secrets, or unnecessary local paths.
- Preserve exception context for unexpected failures.
- Use debug logs for routine cache/scheduling detail, warning logs for recoverable async failures, and error logs for unexpected user-visible failures.

## Anti-Patterns

Avoid these in editor code:

- Growing monolithic widget or surface classes instead of extracting owned responsibilities.
- Duplicating source text, cursor, selection, projection geometry, or feature-gate state across components.
- Performing synchronous catalog, filesystem, network, thumbnail, diagnostics, or semantic refresh work on keypress, paint, scroll, resize, focus, or context-menu open paths.
- Using broad timers, sleeps, or retry loops to hide ownership or ordering bugs.
- Swallowing exceptions broadly or treating unrelated `RuntimeError` failures as deleted Qt wrappers.
- Adding internal compatibility shims after a refactor instead of updating call sites and removing obsolete paths.
- Replacing professional editor behavior with reduced behavior and calling it an optimization.
- Logging prompt content as part of performance or debug instrumentation.
