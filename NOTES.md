# Prompt Editor Architecture and Performance Review

> Architecture review baseline for `bc6c6a7b`. This is a self-contained
> implementation roadmap, not a chronological investigation log.

## Implementation ledger

This section is the authoritative migration status. Update it in the same
change as every completed authority transfer, deletion, performance result, and
verification result.

- Refactor branch: `refactor/prompt-editor-architecture`
- Behavioral baseline: `bc6c6a7b`
- Current slice: 2, pure domain/application package ownership
- Completion state: active
- Blocking regressions: none accepted

| Slice | Authority transfer | Status | Evidence |
|---:|---|---|---|
| 1 | Architecture and measurement guardrails | Complete | Import/debt guards, stable owner hooks, 68/68 structural coverage, clean-root performance comparison, and complete repository gates |
| 2 | Pure domain/application package ownership | Pending | — |
| 3 | Panel dependency inversion | Pending | — |
| 4 | Revisioned core state | Pending | — |
| 5 | Editing ownership | Pending | — |
| 6 | Immutable geometry authority | Pending | — |
| 7 | Canonical and incremental layout engines | Pending | — |
| 8 | Edit-to-frame pipeline | Pending | — |
| 9 | Prepared rendering and revision-keyed caches | Pending | — |
| 10 | Reorder feature slice | Pending | — |
| 11 | Remaining vertical feature slices | Pending | — |
| 12 | Thin Qt integration roots | Pending | — |
| 13 | Panel separation and migration cleanup | Pending | — |

### Current slice acceptance ledger

Slice 1 is complete only when:

- import boundaries and forbidden dependency directions are executable tests;
- designated integration-root growth and private-access debt are measured;
- hot-operation structural budgets cover ordinary text input, navigation,
  selection, paint, scroll, resize, canvas/workflow round trips, and reorder;
- owner instrumentation uses stable optional hooks rather than monkey-patching
  private implementation methods;
- disabled instrumentation overhead is measured and negligible;
- the exact slice worktree passes focused and complete repository gates;
- the baseline-versus-candidate performance report shows no regression.

### Slice 1 evidence

The candidate now has executable import-graph, cycle, integration-root growth,
and private-access/protocol debt guardrails. The guardrails freeze existing
debt for removal by later slices rather than legitimizing growth. In particular,
`projection/surface.py` remains at its 4,877-line ceiling after the fill-band
authority extraction, and newly added real-shell assertions consume the
harness's owner snapshot instead of adding private-state exemptions.

Stable optional work events now instrument authoritative owner boundaries
without performance tooling monkey-patching production internals. The disabled
decorator path adds approximately 53 ns per ordinary decorated call and 50 ns
per result-classified call in the local microbenchmark. Timing-only performance
runs disable event observation entirely. Performance summaries now retain
p50/p95/p99/max, and the runner settles semantic/projection state and uses the
same direct Alt-key and focus setup in baseline and candidate worktrees.

The structural policy covers all 68 declared operations, including ordinary
editing, navigation, selection, paint, scrolling, resize, autocomplete,
diagnostics, reorder, workflow switching, and unchanged canvas round trips.
The final complete instrumented campaign at
`build/prompt-editor-slice1-final-structural.json` completed 68
scenarios with 68/68 operation coverage, no correctness failures, and no
structural-budget violations. The max-span reorder visual campaign also passed
ten focused repetitions and the complete matrix after its stable-frame check
was made animation-aware. Failure reports now retain visible glyph geometry,
translation, and pixel-match strength so a future capture failure is
diagnosable rather than silently retried.

Performance investigation found one real candidate regression during this
slice: the extracted fill-band cache materialized the full prompt source and a
viewport rectangle before checking for a cache hit. The cache now performs a
cheap key-only lookup and constructs source-dependent miss data only on a miss.
An owner-level regression test fails if a warm-cache read calls
`toPlainText()`.

Timing evidence uses fresh processes, identical harness setup, timing-only
observation, fixed two-core affinity, and paired baseline/candidate order. Each
process asserts that every loaded `substitute` module belongs to the selected
worktree, preventing `sitecustomize` or import-cache contamination between
baseline and candidate:

- the clean-root adverse-lane campaign contains 60 samples per variant. The
  largest candidate median p95 deltas are 0.089 ms/1.5% for 5k Enter and
  0.088 ms/1.5% for horizontal Alt navigation. Danbooru import is
  0.066 ms/0.9%, 5k selection is 0.030 ms/1.1%, and 5k Delete is
  0.022 ms/0.4% with a negative 0.074 ms paired median. These sub-0.1 ms
  deltas are below the observed run-to-run noise floor and do not indicate a
  material latency regression;
- unwrapping all 56 optional owner hooks changes horizontal Alt p95 by only
  0.010 ms/0.2%, consistent with the approximately 50 ns disabled-path
  microbenchmarks;
- the clean-root six-lane call profile recorded 52,976,223 calls and
  20.498 profiled seconds for the candidate versus 52,892,493 calls and
  20.896 seconds for the baseline. Stable hooks add 83,730 calls across 120
  complete scenario instances, or 0.158%, while total profiled time is lower;
- aggregate process CPU was 19.547 seconds for the candidate and 19.328 seconds
  for the baseline across those 120 profiled instances. Individual Windows CPU
  samples are quantized at 15.625 ms, so the structural budgets, repeated
  latency distribution, disabled-path microbenchmark, and call profile are the
  authoritative evidence;
- wall-clock outliers correlated with bursty external system load. Those
  outliers are retained as non-representative diagnostics rather than used to
  claim either a regression or an improvement.

Focused verification passes the performance metrics, runner, reporting,
observability, CLI, Qt operations, instrumentation, work-observer, abuse-tool,
architecture-guardrail, real-shell harness, and fill-band suites, plus targeted
Ruff and strict mypy checks. The complete repository gates pass: repository
format and lint, strict mypy over 2,858 source files, the full non-serial suite,
and all 121 serial modules including prompt-editor and canvas real-shell
coverage. Slice 1 is complete.

## Review objective

Design a final prompt-editor architecture with one authoritative owner per
concern, cohesive single-responsibility source files, explicit typed dependency
boundaries, and performance mechanisms that are structural rather than
accidental. The migration must preserve all current behavior, improve editor
and canvas responsiveness, and make future performance regressions difficult to
introduce.

This review covers the complete prompt-editor system:

- prompt domain parsing, models, operations, scenes, syntax, weights, wildcards,
  regional structure, reordering, serialization, and preferences;
- application services for documents, semantics, mutation, normalization,
  autocomplete, syntax, diagnostics, LoRA behavior, scene analysis, regional
  topology, selection, and reordering;
- the production prompt editor, including editing, commands, interactions,
  features, async work, projection, layout, paint, overlays, shell integration,
  composition, and runtime services;
- editor-panel construction, binding, projection lifecycle, workflow/canvas
  integration, and prompt-specific context;
- performance instrumentation, deterministic real-shell harnesses, seeded abuse
  campaigns, and owner-level tests.

The report does not propose preserving current internal APIs. Public and
persisted behavior remains the compatibility boundary.

## Executive assessment

The prompt editor has unusually broad and serious behavior coverage and contains
several sophisticated responsiveness mechanisms. It is not slow by design, and
its current architecture should not be replaced with a generic text-widget
abstraction. Its strongest mechanisms are custom source-backed editing,
conservative incremental projection, lazy coordinate sequences, validated line
reuse, transient feedback while geometry catches up, latest-wins scheduling,
viewport clipping, revision-like cache keys, asynchronous feature preparation,
and structural performance instrumentation.

The system's principal weakness is that those mechanisms do not have equally
strong ownership boundaries. The central surface, layout, public widget,
interaction integration, and composition graph remain shared mutable meeting
points. Many newer files have good responsibility names but still call back into
private state on those meeting points. Performance depends on a distributed set
of exceptions, invalidations, and ordering rules that are difficult to change
atomically.

The correct cleanup is therefore not a file-splitting exercise. It is an
authority migration:

- retain the proven algorithms and behavioral contracts;
- introduce explicit source-to-paint revision identities;
- make one edit-to-frame pipeline own strategy selection;
- make immutable layout snapshots the sole geometry authority;
- make rendering a prepared-snapshot sink;
- turn product features into vertical slices over stable core ports;
- reduce widgets and composition to adapters;
- delete old state and control paths as each owner becomes authoritative.

Done this way, architecture and performance reinforce one another. An ordinary
edit has fewer decision points, consumers cannot trigger hidden rebuilds,
revision-keyed caches remove invalidation guesswork, paint cannot perform
semantic work, and structural budgets prevent features from attaching unrelated
work to typing, canvas, or workflow paths.

## Evidence and review method

The conclusions in this document are based on:

1. direct source inspection and dependency tracing;
2. test and harness behavior contracts;
3. performance counters, incremental-path classifications, cache ownership, and
   invalidation rules;
4. current module size and symbol inventories;
5. Git history where ownership intent or change pressure requires it.

Verified facts are stated directly. Architectural interpretations or predicted
risks are labeled as analysis.

### Initial scale snapshot

The broad review boundary contains 487 Python files and approximately 167,798
lines when the complete editor panel, prompt-editor tooling, and performance
packages are included. There are 251 prompt-named test modules. This count is a
discovery boundary rather than a claim that every panel file belongs in the
future prompt-editor package.

The largest directly relevant production files currently include:

| File | Lines | Initial observation |
|---|---:|---|
| `projection/layout_engine.py` | 5,682 | Requires responsibility and hot-path decomposition analysis |
| `projection/surface.py` | 4,978 | Central mutable presentation owner and integration hub |
| `panel/view.py` | 2,425 | Broad editor-panel composition and lifecycle surface |
| `projection/line_layout.py` | 2,139 | Text shaping, wrapping, fragments, caret geometry, and incremental reuse |
| `prompt_editor/widget.py` | 2,064 | Public widget facade plus feature/lifecycle integration |
| `overlays/reorder_landing_shadow.py` | 1,917 | Large reorder rendering/animation concern |
| `overlays/reorder_overlay_geometry.py` | 1,786 | Large reorder geometry concern |
| `projection/tokens.py` | 1,625 | Renderer registry and token presentation responsibilities |
| `overlays/token_weight_controls.py` | 1,560 | Weight-control interaction and presentation |
| `interactions/reorder_controller.py` | 1,465 | Reorder use-case coordination |
| `projection/incremental_apply_controller.py` | 1,423 | Incremental document/layout application policy |
| `projection/source_change_applier.py` | 1,419 | Source-change orchestration and fast-path selection |
| `projection/model.py` | 1,341 | Projection state model with multiple distinct model families |
| `projection/incremental_editor.py` | 1,230 | Incremental projection editing |
| `interactions/autocomplete_controller.py` | 1,215 | Autocomplete orchestration |
| `projection/builder.py` | 1,179 | Canonical projection construction |
| `interactions/controller.py` | 1,154 | General interaction integration |
| `projection/reorder_preview_projection.py` | 1,118 | Preview projection ownership |
| `composition/factory.py` | 1,098 | Editor composition root |

File size is only a signal. Each candidate must be judged by change reasons,
state ownership, dependency breadth, and whether its logic can evolve or be
tested independently.

## System boundary and feature inventory

The editor is not merely a syntax-highlighting text box. It is a custom source
editor, semantic projector, layout engine, rendering surface, feature host, and
workflow-integrated panel component. The following inventory is derived from
the feature registry, production entrypoints, performance corpus, and real-shell
contracts.

### Editing and document behavior

- exact raw-source ownership independent of the hidden `QTextEdit` document;
- insertion, replacement, Backspace, Delete, newline, line join/split, and
  programmatic full-source replacement;
- source normalization and special parenthesis transitions;
- cursor and anchor state, horizontal and vertical navigation, word movement,
  mouse placement, drag selection, double-click selection, and preferred-x
  preservation;
- clipboard copy/cut/paste, plain-text MIME drag/drop, paste import, and
  clipboard history;
- custom transaction-based undo/redo, baseline replacement, coalesced typing,
  and projection/layout checkpoints;
- Unicode and IME composition without persisting preedit text;
- read-only behavior, focus ownership, placeholder behavior, context menus,
  shell scrolling, manual resizing, and automatic height limits.

### Semantic and rich-prompt behavior

- emphasis parsing, implicit/explicit weights, exact-weight editing, keyboard
  and wheel adjustment, and token controls;
- wildcard syntax, catalog lookup, autocomplete, resolution state, and error
  presentation;
- Prompt Control LoRA syntax, scheduled LoRA analysis, catalog matching,
  autocomplete, picker insertion, inline metadata/thumbnails, and trigger-word
  suggestions;
- ordinary autocomplete, ranked suggestions, popup navigation, ghost text, and
  stale-result suppression;
- Danbooru URL paste import, wiki lookup, image/recent-post presentation, and
  context actions;
- spellcheck and duplicate-segment diagnostics, underline geometry, corrections,
  cleanup actions, and visible-range refresh;
- segment and line reordering by keyboard and drag, live/preview geometry,
  landing indicators, animation, and undo;
- scenes, scene errors, segment presets, source-line chrome, fill bands, and
  `[SEP]` regional structure/decorations;
- projected and exact-source display modes, feature profiles, syntax profiles,
  and the global rich-rendering enable/disable policy.

The persisted feature registry currently exposes thirteen user-controllable
capabilities: emphasis, Danbooru URL import, Danbooru wiki lookup, wildcard
syntax, wildcard autocomplete, autocomplete ghost text, LoRA syntax, LoRA
autocomplete, LoRA picker, LoRA trigger words, segment reorder, spellcheck, and
duplicate-segment diagnostics. Regional decoration exists as document semantics
rather than as a separately persisted feature preference.

### Integration and tooling behavior

- editor-panel construction from workflow field metadata, prompt semantics,
  feature decisions, services, model scope, and active workflow state;
- bindings between the editor, cube state, workflow/canvas projection, queueing,
  metadata changes, and persisted preferences;
- asynchronous task execution for autocomplete, diagnostics, Danbooru data,
  LoRA metadata/thumbnails, and other externally backed features;
- structured timing probes, cache counters, real-shell state snapshots,
  deterministic scenarios, seeded abuse actions, visual correctness checks,
  failure minimization, and revision-to-revision performance comparison.

## Current architecture

### Layer and dependency map

The broad boundary currently has the intended dependency direction in its pure
layers: `domain/prompt` imports no Qt, `application/prompt_editor` imports no Qt,
and presentation depends on both. The actual symbol inventory is:

| Layer | Classes | Protocols | Functions | Qt-importing modules |
|---|---:|---:|---:|---:|
| Domain prompt | 46 | 0 | 99 | 0 |
| Application prompt editor | 141 | 8 | 275 | 0 |
| Prompt-editor presentation | 828 | 206 | 610 | 117 |
| Editor panel | 302 | 102 | 277 | 42 |

The presentation layer's 308 local Protocol classes, especially the 206 under
the prompt editor itself, are not evidence of 308 stable architectural ports.
Many describe narrow slices of the same concrete widget or surface and are
paired with `cast(...Host, self)`. There are approximately 214 such host-cast or
host-Protocol occurrences in the prompt-editor presentation package. This
reduces static coupling at individual call sites while retaining a large shared
mutable object as the runtime service locator.

The internal import graph confirms the concentration:

- `projection.surface` has 43 internal outgoing dependencies;
- `panel.view` has 38;
- `application.prompt_editor.__init__` has 33;
- `overlays.reorder_overlay` has 29;
- `projection.layout_engine` has 23;
- `panel.projection_composition` has 18;
- `composition.factory` has 16.

The most depended-upon modules include `projection.model` (60 internal
dependents), `projection.observability` (22), `prompt_document_views` (22),
`layout_engine` (21), and `prompt_document_semantics` (20). These are high
change-amplification points and need stable, deliberately small contracts.

There are also concrete direction and cycle failures:

1. `features/prompt_segment_preset_source.py` imports editor-panel context and
   model-scope policy. A reusable prompt-editor feature therefore depends back
   on its host panel.
2. `panel.view` and `panel.widgets.cube_section` form a panel cycle.
3. `prompt_lora_catalog_service` and `prompt_lora_ranking` have entangled model
   ownership, partly hidden by `TYPE_CHECKING`.
4. Six projection modules form a tightly coupled component around
   `layout_engine`, including hit testing, painting, selection geometry,
   source-line geometry, and reorder paint snapshot construction.

The last item is especially important. `PromptProjectionHitTester` and
`PromptProjectionSelectionGeometry` call private `PromptProjectionLayout`
methods with `# noqa: SLF001`, while `PromptProjectionPainter` retains the
layout and reads `layout._snapshot`. The layout imports those apparent owners
in return. These files are delegation bookmarks around a god object, not final
single-responsibility ownership.

The 766-line `application/prompt_editor/__init__.py` is a lazy-export registry
with a large `_LAZY_EXPORTS` map, dynamic `__getattr__`, and giant `__all__`.
It hides concrete dependency locations, makes the package root a service barrel,
and amplifies changes. Internal code should import stable owner modules
directly; the barrel should exist only if a genuinely public API requires it.

### State and ownership matrix

| State or decision | Current apparent owner(s) | Ownership issue |
|---|---|---|
| Raw source and revision | `PromptEditingSession`, source buffer, surface mirrors, `QTextDocument` adapter | Multiple synchronized representations are necessary, but the authoritative-versus-derived contract is distributed |
| Cursor/anchor | Editing session and projection surface caret states | Projection mapping is mixed with widget event and paint behavior |
| Parsed document and render plan | Application services, surface `_document_view`/`_render_plan` | Optimistic and canonical states share types but freshness/authority is implicit |
| Projection document | Applicator/builder, session, surface base/active documents | Base, transient, reorder-preview, and exact/projected variants are coordinated centrally |
| Layout snapshot and geometry | 5,682-line layout plus helper wrappers and caches | Authority remains in one god object while supposed owners reach into its private state |
| Projection freshness | Freshness controller plus source-change and incremental-apply controllers | Policy is split across three large collaborators and host callbacks |
| Paint/cache state | Surface, layout, painter, paint cache, diagnostic painter, region/source chrome, reorder caches | Invalidations are numerous and coordinated manually from the surface |
| Feature enablement | Domain profile, registry, syntax profile, editor construction, individual controllers | Definition is centralized, runtime activation and lifecycle are scattered |
| Async request freshness | Per-feature controllers/executors/dispatchers | Similar revision, cancellation, visibility, and stale-result rules are reimplemented |
| Shell sizing/scrolling/focus | Public widget, shell, QFluent chrome, scroll delegate, sizing controller | Better decomposed than projection, but wired through many lambdas back to the facade |
| Panel/workflow context | Panel view, prompt factories, context modules, projection composition | Prompt-specific context sometimes leaks down into the reusable editor package |

The required end state is not one object per row. It is one authoritative owner
for each state transition, explicit immutable snapshots for consumers, and one
documented synchronization point for each necessary mirror.

### Editing transaction pipeline

The production path for a physical key currently is:

1. `PromptEditor` lets autocomplete/interactions pre-handle the event.
2. The event enters `PromptProjectionSurface` and its key handler/keymap.
3. An edit command mutates `PromptEditingSession`/source-buffer state and records
   undo/coalescing metadata.
4. `PromptProjectionSourceChangeApplier` mirrors the committed source into the
   `QTextDocument`, remaps diagnostics, derives an optimistic semantic view,
   updates caret state, emits signals, and selects immediate or deferred work.
5. `PromptProjectionIncrementalApplyController` chooses checkpoint restore,
   paint-only reuse, fast trailing edit, incremental edit, local canonical
   reflow, deferred wrap, transient overlay, or full rebuild.
6. Projection state, layout, caches, scroll metrics, caret visibility, and dirty
   paint regions are updated.
7. The public widget schedules feature follow-up such as autocomplete.

The editing-session package is one of the more coherent areas: source buffer,
cursor session, undo stack, edit transaction, source commands, normalization
port, and undo coalescing are recognizable responsibilities. Its use from
presentation, however, is mediated by multiple routers/adapters and then merged
back into the surface's large host protocol.

### Semantic, projection, layout, and paint pipeline

Canonical rendering starts with a semantic `PromptDocumentView` and
`PromptSyntaxRenderPlan`, builds a `PromptProjectionDocument`, shapes and wraps
it into a layout snapshot, and paints only viewport-relevant content plus
chrome/overlays. Ordinary edits attempt to patch all or part of that pipeline.

The current system has useful stages, but their boundaries are not final:

- builder/applicator/incremental editor/canonical reflow overlap on how a
  projection document changes;
- source-change applier/incremental-apply/freshness controller overlap on when
  work is safe, immediate, deferred, or canonical;
- line layout/layout engine/hit testing/selection/source-line geometry overlap
  on geometry authority;
- surface/painter/paint cache/diagnostic painter/chrome/reorder painters overlap
  on what gets invalidated and painted.

`PromptProjectionSurface` consequently has 279 methods and owns or coordinates
source adapters, semantic snapshots, projection variants, caret mapping, input
method handling, key/mouse/wheel/drag-drop events, scroll state, layout, paint,
diagnostics, LoRA thumbnails, regional chrome, reorder geometry, multiple cache
families, freshness, timers, and instrumentation. `PromptEditor` adds another
164 methods around shell integration, feature orchestration, public APIs, and
panel-facing behavior. This is the main reason apparently local changes can
produce distant correctness and performance failures.

### Async, lifecycle, and external integration

The async package and feature controllers correctly keep several external or
expensive operations away from direct painting. Nevertheless, cancellation,
revision identity, visibility checks, popup lifecycle, refresh coalescing, and
result application are spread across feature-specific controllers. The target
needs one small request-generation contract and scheduler primitive, while
keeping feature-specific query/result logic in separate modules.

The composition factory currently builds projection, service, syntax, feature,
and interaction collaborator groups. Its 1,098 lines and the editor constructor's
many optional dependencies show that composition is a real responsibility, but
construction policy and runtime bridging are mixed. Composition must remain
outside hot paths and should produce immutable dependency bundles for cohesive
feature modules rather than install dozens of callbacks into a central host.

## Responsiveness model

### Current hot paths

The latency-sensitive paths are:

1. physical key/IME event through source commit and immediate visual feedback;
2. cursor and selection movement through caret mapping and minimal repaint;
3. paint events, including repeated/exposed-region paints and scroll paints;
4. scroll and resize through visible geometry and scrollbar synchronization;
5. hover and wheel interaction over inline objects;
6. reorder pointer movement, target changes, preview scheduling, animation, and
   live/preview painting;
7. async result publication back onto the GUI thread.

The performance corpus exercises empty through 10k-character prompts,
syntax-heavy prompts, autocomplete/ghost text, context menus, diagnostics,
scroll, resize, hover, focus, reorder variants, cursor/selection changes,
paste/import, middle edits, trailing edits/newlines, syntax-triggered rebuilds,
and paint/diagnostic/fill-band cache behavior. Instrumentation distinguishes
full projection rebuilds, layout snapshots, fast insert/delete/newline paths,
incremental applied/deferred/rejected paths, wrap/fallback deferral, paint-cache
outcomes, diagnostic cache preservation, fill-band cache outcomes, geometry and
shell work, autocomplete phases, and reorder work.

### Mechanisms that currently preserve responsiveness

- The source edit is classified before expensive projection work.
- Safe common edits can use fast trailing or local incremental projection paths.
- Wrap-only work may be deferred and coalesced off the physical-key dispatch
  lane while transient caret/insertion/deletion geometry provides immediate
  feedback.
- Syntax/topology-sensitive edits force canonical work instead of corrupting an
  incremental state.
- Projection/layout checkpoints can restore history without recomputing all
  geometry.
- Paint is clipped to the viewport and supported by projection-content,
  diagnostic-fragment, fill-band, display-mode layout, thumbnail, and reorder
  caches.
- Incremental diagnostic edits can preserve and translate cached fragments.
- Reorder separates pointer movement from queued preview work and tracks exact,
  scroll-translated, and rebuilt geometry/raster outcomes.
- Expensive service work is dispatched asynchronously with stale-result checks.
- The real-shell and abuse tools expose structural work counters as well as wall
  time, so a fast machine cannot hide an algorithmic regression.

### Fragile or accidental performance properties

The performance mechanisms are valuable, but many are fragile because their
preconditions and invalidation decisions are spread across central mutable
hosts:

- fast-path eligibility is split among source change, incremental apply,
  applicator, freshness, surface callbacks, syntax sensitivity, region topology,
  and autocomplete-prefix exceptions;
- cache clearing is manually triggered from many surface methods, which makes
  both stale-cache bugs and unnecessary invalidation easy;
- helper owners require broad host Protocols or private layout access, so a
  structural move can silently add callbacks or work to the key/paint path;
- optimistic, transient, deferred, and canonical states are not represented by
  a single explicit revision graph;
- instrumentation monkey-patches private methods, coupling measurement to the
  current decomposition and leaving no immutable performance contract at the
  owner boundary;
- the standard performance scenario suite measures timings and counters, but
  durable checked-in per-operation structural budgets and revision baselines
  are not clearly owned alongside the production mechanism;
- the 10k corpus is useful, but long multi-line, regional, diagnostic-heavy,
  LoRA-thumbnail-heavy, IME, rapid resize/reflow, and combined-feature workloads
  need first-class performance contracts.

The abuse coverage catalog currently names 68 independently correct and
performant operations across text, selection, navigation, history, lifecycle,
paint, autocomplete, emphasis, LoRA, wildcards, diagnostics, Danbooru, scenes,
and reorder. It does not yet name regional-separator editing/navigation/paint,
IME, MIME drag/drop, exact-weight overlay editing, thumbnail publication, or
async stale-result races as independent coverage obligations. Some have tests,
but omission from the coverage enum means a “complete” campaign cannot prove
that they were exercised.

The safe-typing scheduler is also intentionally aware of recent canvas/output
load: it uses latest-wins coalescing, a 180 ms active-typing delay, a 240 ms
delay when prompt and output are both active, and a 750 ms maximum stale
window. That policy is valuable. Its default dependency on a process-global
`PromptProjectionUiLoadActivity` is hidden, however, and should become an
explicit load-signal port installed at composition.

### Concrete performance improvement opportunities

These are source-observed targets to benchmark during the migration:

- One committed source delta is repeatedly revalidated by constructing or
  comparing full-string prefixes/suffixes in semantic remap, freshness fallback,
  scene topology classification, regional topology rebuild, and source-change
  application. The editing owner already knows the exact applied edit. Validate
  it once at ingress, carry a trusted `SourceDelta`, and use revision identity
  thereafter. This removes repeated O(document length) copies/comparisons from
  fallback and topology-sensitive paths.
- Topology-preserving regional edits currently recreate tuples for all
  separators and partitions so every later source coordinate shifts. Use the
  same persistent/lazy shifted-sequence strategy already proven for projection
  runs and caret stops, or a compact suffix offset transform. Ordinary typing
  should be O(log region count) lookup plus O(1) delta publication, not O(region
  count) allocation.
- Projected-token intersection checks linearly scan every token for some edits.
  The canonical caret map/layout snapshot should expose an interval index or
  binary-searchable ordered ranges so local edit classification is O(log token
  count + overlaps).
- `_syntax_sensitive_characters()` allocates a new `frozenset` during typed
  character classification. It should be an immutable module/class constant.
  This is a small cost, but it is exactly the sort of unrelated allocation that
  should not survive on a keystroke path.
- Fast trailing insertion and some newline paths clear the complete diagnostic
  fragment cache, while the delete and general incremental paths already know
  how to preserve unaffected entries. Damage-based cache publication can retain
  all geometry before the changed tail and avoid unnecessary warm work.
- The document and render-plan LRUs are bounded by entry count, not retained
  bytes. The effective scheduled-LoRA provider has several ordinary dictionaries
  without explicit eviction. Cache contracts should include byte/lifecycle
  bounds, because 512 large prompt snapshots or many workflow revisions can
  retain substantially different memory than 512 small prompts.
- Canonical render-plan cache keys hash the complete source with SHA-256 and
  process-wide caches use locks. These are appropriate only off the ordinary
  incremental lane. Revision-based editor-local keys can avoid repeated hashing;
  content-addressed process-wide reuse can remain at ingestion/restore
  boundaries.
- The current surface often calls broad `viewport().update()` after a fast
  application even when exact changed geometry is available. Carrying a
  `DamageSet` from incremental layout to the viewport permits smaller repaints
  and makes full-viewport invalidation observable.
- Feature and composition callback chains can cause redundant state reads and
  signal-driven refreshes after one commit. A single completed `EditFrame`
  publication with explicit follow-up intents can coalesce those reads without
  placing a generic event bus on the hot path.

The target architecture must retain the algorithms while moving their policy
and state into explicit owners. Merely splitting files would risk adding
indirection, allocations, signal fan-out, duplicate snapshots, and repeated
scans to the hot path.

## Problem catalog

### P0: ownership failures on correctness and frame-critical paths

1. **The surface is both state container and subsystem integrator.**
   `PromptProjectionSurface` has 279 methods and directly participates in almost
   every key-to-paint concern. Its collaborators commonly accept a surface-host
   Protocol and mutate or query the same shared object. This permits state to
   change without passing through one authoritative transition.
2. **The layout decomposition is not real.** Hit testing, selection, source-line
   geometry, and painting still route through private layout state. Cyclic
   dependencies and private access prevent independent evolution and make cache
   invalidation inseparable from unrelated layout behavior.
3. **Incremental policy has multiple authorities.** Source-change application,
   edit-projection policy, freshness, incremental application, semantic remap,
   canonical reflow, and surface callbacks each decide part of the same path.
   A new syntax or structural feature must modify several of them consistently.
4. **Invalidation is imperative and distributed.** The surface manually clears
   or preserves projection, diagnostic, display-mode, reorder, thumbnail, and
   geometry caches in many event handlers. This is a primary source of stale
   visual state and unnecessary hot-path work.
5. **Canvas/workflow durability is only partially encoded.** The abuse policy
   correctly forbids full-source replacement, layout snapshots, projection
   rebuilds, and region-chrome preparation during canvas round trips. Comparable
   structural budgets do not yet cover all ordinary typing, navigation, paint,
   scroll, resize, async publication, and workflow-switch paths.

### P1: architecture and change-amplification failures

6. **The public widget is also a feature runtime.** `PromptEditor` has 164
   methods and a constructor with many feature and service inputs. It combines
   public compatibility, QFluent shell behavior, composition, feature lifecycle,
   workflow-facing APIs, and event routing.
7. **The general interaction controller is still a central coordinator.**
   It overlaps with keymap, command adapter/router, autocomplete, emphasis,
   exact weight, mouse selection, reorder, clipboard/history, and wheel owners.
8. **Protocol sprawl masks service-location.** Hundreds of local host Protocols
   duplicate fragments of concrete widgets rather than defining a small number
   of stable commands, queries, clocks, schedulers, and render ports.
9. **Package roots and barrels hide dependencies.** The application lazy-export
   registry and broad presentation `__init__` surfaces make imports convenient
   at the cost of discoverable ownership and enforceable layering.
10. **The prompt-editor package depends on its panel host.** Segment preset
    source logic imports panel context and policy, reversing the intended
    dependency direction.
11. **Feature modules are organized partly by technical mechanism and partly by
    product feature.** One feature can span application services, `features`,
    `interactions`, `commands`, `overlays`, projection, composition, and widget
    callbacks without one cohesive feature boundary.
12. **Application models and services are flat.** Fifty-plus files share one
    package namespace. Document, diagnostics, autocomplete, LoRA, reorder,
    structured semantics, scenes, preferences, and workflow graph concerns are
    logically distinct but not expressed as package boundaries.
13. **Projection models are over-concentrated.** `projection/model.py` is the
    fan-in center for several model families. Changes to runs, inline objects,
    caret mapping, display state, or regional structure all affect one module.
14. **Composition relies on callback webs.** Large collaborator bundles and
    lambdas reduce constructor length locally while making runtime direction,
    lifecycle, and ownership difficult to follow.

### P2: testability, observability, and maintainability failures

15. **Tests know too much private structure.** There are 323 `SLF001` exemptions
    across 32 prompt-named test modules. The real-shell harness is valuable, but
    its owner diagnostics must become supported immutable debug snapshots rather
    than private graph traversal.
16. **Large “contract” suites mix unrelated behavior.**
    `test_prompt_autocomplete_surface_contract.py` is 3,806 lines and covers
    autocomplete, LoRA, reorder, scrolling, lifecycle, and more. Failures are
    harder to localize and ownership migrations touch unrelated tests.
17. **Performance instrumentation monkey-patches implementation details.**
    This can measure the current code, but counters are not stable owner events
    and a refactor can accidentally stop measuring work.
18. **Observability is scattered.** Projection, reorder, async work, panel
    projection, and debug probes each expose useful context, but there is no one
    revision-safe editor diagnostic snapshot schema.
19. **Recent optimization history is extremely cross-cutting.** The primary
    interactive-editing optimization commit changed 119 files with roughly
    13,435 insertions. Some breadth was required by behavior coverage, but the
    scale confirms that performance policy and geometry ownership are not local.

### Important non-problems to preserve

- A cohesive parser or layout pass is not a god object merely because it is
  algorithmically substantial. Splitting one linear scan into multiple
  independently scanning “small” services would be worse architecture and worse
  performance.
- Multiple representations of source, semantic state, projection, and geometry
  are legitimate. The defect is ambiguous authority and ad hoc synchronization,
  not the existence of derived snapshots.
- Deferred work, lazy shifted sequences, cached immutable snapshots, and
  feature-specific controllers are strong ingredients. They should be moved
  behind better boundaries, not replaced with a generic reactive framework.

## Ideal target architecture

### Design rules

1. **One transition owner per mutable state.** Source, selection, semantic
   revision, projection revision, layout revision, viewport state, feature
   session, and async request generation each have one writer.
2. **Immutable snapshots cross boundaries.** Consumers receive value objects
   identified by source/semantic/projection/layout/viewport revisions. They do
   not read another owner's private fields.
3. **Commands mutate; queries inspect; events announce completed facts.**
   Commands return explicit outcomes and dirty regions. Signals do not initiate
   hidden chains of synchronous recomputation.
4. **The hot path is a named use case.** A `PromptEditPipeline` owns edit
   classification and produces one `EditFramePlan`. No unrelated feature may
   install work into it indirectly.
5. **Incremental and canonical engines share contracts, not control flow.**
   Incremental application either returns a validated new snapshot and bounded
   damage or rejects. A canonical builder is the single recovery path.
6. **Cache keys derive from revision identities.** Owners do not rely on
   callers remembering a list of invalidation methods. Bounded caches may evict,
   but correctness follows from keys.
7. **Geometry has one immutable authority.** Layout builds a `LayoutSnapshot`.
   Hit testing, selection, caret movement, source-line queries, chrome, reorder,
   and paint are pure queries over that snapshot.
8. **Qt stays at adapters and rendering edges.** Source/edit/semantic/projection
   policies remain pure. Text shaping necessarily uses Qt, but it consumes and
   returns immutable projection values rather than a widget host.
9. **Features are vertical slices outside the core.** Each feature owns its
   application policy, async session, prepared view state, commands, and optional
   overlay. It depends on stable core ports and cannot reach into the surface.
10. **Composition occurs once.** The composition root creates owners and passes
    narrow concrete ports. It performs no runtime feature logic and is absent
    from key, paint, and canvas paths.
11. **No shim extractions.** A responsibility is extracted only when its state,
    algorithms, tests, call sites, and obsolete private path move together.
12. **Performance is a correctness property.** Structural-work budgets are
    owner contracts checked in tests; wall timing is corroborating evidence.

### Target package and source-file structure

The exact names may change during migration, but the ownership graph should
have this shape:

```text
substitute/
  domain/prompt/
    document/                 # source ranges, document/segment/span values
      models.py
      parser.py               # one canonical bounded scan
      structural_scan.py      # shared quote/escape/parenthesis scanner
      serializer.py
    emphasis/
      semantics.py
      operations.py
      weights.py
    regions/
      models.py
      parser.py               # participates in canonical scan; no second scan
      edits.py
      normalization.py
    scenes/
      models.py
      parser.py
      materialization.py
    reorder/
      models.py
      derivation.py
      mutations.py
      serialization.py
    wildcards/
      models.py
      syntax.py
    preferences/
      models.py

  application/prompt_editor/
    document/
      views.py
      projector.py
      semantics.py
      selection.py
      cache.py
    editing/
      mutation_service.py
      normalization.py
      syntax_actions.py
      structured_mapping.py
    projection/
      semantic_snapshot.py    # semantic + render-plan revision
      syntax_plan.py
    autocomplete/
      queries.py
      ranges.py
      matching.py
      structured_mapping.py
    diagnostics/
      models.py
      coordinator.py
      display_policy.py
      duplicate_segments.py
      spellcheck.py
      wildcard.py
      unsupported_scenes.py
    lora/
      catalog_models.py
      catalog.py
      ranking.py
      resolution.py
      autocomplete.py
      scheduling.py
      trigger_words.py
    reorder/
      views.py
      projection.py
      drop.py
      serialization.py
      structured.py
    scenes/
      projection.py
      workflow_analysis.py
    features/
      definitions.py
      profile.py
      preferences.py
    ports/
      autocomplete.py
      catalogs.py
      diagnostics.py
      execution.py

  presentation/editor/prompt_editor/
    api/
      widget.py               # compatibility facade only
      signals.py
      debug_snapshot.py
    composition/
      inputs.py
      root.py
      bindings.py
    core/
      state/
        revisions.py
        editor_state.py       # aggregate references, not subsystem data dump
      editing/
        session.py
        source_buffer.py
        selection.py
        transactions.py
        undo.py
        clipboard.py
        ime.py
      pipeline/
        edit_classifier.py
        edit_pipeline.py
        frame_plan.py
        canonical_recovery.py
        frame_scheduler.py
      projection/
        models.py
        canonical_builder.py
        incremental_builder.py
        lazy_sequences.py
        caret_map.py
        transient_projection.py
      layout/
        models.py
        text_shaper.py
        line_builder.py
        canonical_layout.py
        incremental_layout.py
        metrics.py
        checkpoints.py
      geometry/
        queries.py
        hit_test.py
        caret_navigation.py
        selection.py
        source_lines.py
        visible_lines.py
      viewport/
        controller.py
        scroll.py
        damage.py
      rendering/
        renderer.py
        paint_plan.py
        content_cache.py
        diagnostic_cache.py
        chrome.py
        theme.py
      surface/
        widget.py             # Qt event ingress and paint sink only
        event_adapter.py
        mime_adapter.py
    shell/
      widget.py
      qfluent_chrome.py
      sizing.py
      scrolling.py
      context_menu.py
    features/
      autocomplete/           # session, async query, presenter, overlay
      diagnostics/            # refresh session, prepared actions, painter input
      emphasis/               # commands, controls, gestures
      lora/                   # metadata session, picker, thumbnails, actions
      wildcards/              # refresh session and actions
      danbooru/               # import/wiki async sessions and dialogs
      reorder/                # gesture, preview, geometry, caches, rendering
      regions/                # decoration policy and chrome adapter
      scenes/                 # context session and actions
      presets/                # caller-neutral preset contract and menu
      search/                 # search session and prepared highlights
    async_runtime/
      request_generation.py
      latest_wins.py
      debounce.py
      executor.py
      main_thread.py
      cancellation.py

  presentation/editor/panel/
    prompt/
      context.py              # panel-owned workflow/model context
      profile.py
      factory.py
      binding.py
      scene_diagnostics.py
      preset_adapter.py       # implements editor's caller-neutral preset port
```

This is not a request to create empty directories or one-class files. A file is
justified when it owns a cohesive state/algorithm/test boundary. Closely related
immutable values should stay together; independently changing policies should
not.

### Target state, command, query, and event contracts

The core revision model should make consistency mechanically inspectable:

```text
SourceSnapshot(source_revision, text)
  -> SemanticSnapshot(source_revision, semantic_revision, document, render_plan)
  -> ProjectionSnapshot(semantic_revision, projection_revision, runs, caret_map)
  -> LayoutSnapshot(projection_revision, layout_revision, width_key, geometry)
  -> PaintSnapshot(layout_revision, viewport_revision, paint_state_revision)
```

A snapshot can only derive from the exact upstream identity it records.
Transient visual feedback records both the live source revision and the last
committed projection/layout revision. Publishing a stale async result or mixing
revisions becomes a rejected operation, not a convention.

Core commands should be source-coordinate requests such as `ReplaceRange`,
`MoveCaret`, `SetSelection`, `Undo`, and `Redo`. The editing owner returns an
`EditCommit` containing source delta, selection, undo change, normalization
transitions, and origin. Feature commands prepare these same core commands; they
do not mutate widgets.

The geometry API should be a small, stable query surface over an immutable
snapshot: caret rectangle, position at point, movement target, selection
fragments, source-line rectangles, visible line range, inline object at point,
and reorder geometry input. None may call back into layout construction.

Completed owner events should include source committed, semantic published,
projection published, layout published, viewport changed, damage requested,
and feature snapshot published. Events carry identities and bounded results;
they must not expose mutable owners.

### Target editing and rendering pipelines

For a local edit:

1. The event adapter converts Qt input into one typed core intent.
2. The editing session commits exactly one source transaction.
3. The edit classifier computes topology/syntax/wrap risk from the edit delta
   and current indexed snapshot. It never performs an unrelated full scan.
4. The pipeline selects exactly one strategy:
   - paint-only/transient feedback;
   - bounded incremental projection and layout;
   - deferred coalesced wrap;
   - checkpoint restore;
   - canonical rebuild.
5. The selected engine returns a revision-validated snapshot plus a `DamageSet`
   describing changed rows/rectangles and cache-key changes.
6. The viewport publishes the new aggregate state and requests only bounded
   repaint. Feature refresh intents are queued after the core commit.

For canonical work, semantic projection, projection construction, and layout
each run once. Canonical recovery is not duplicated in feature controllers.
For paint, the renderer consumes immutable layout, paint state, viewport, and
prepared feature layers. It does not parse, query services, build layout,
prepare diagnostics, load images, or mutate editor state.

### Durable performance contracts

The following rules must be represented by counters/invariants in production
owners and asserted by the real-shell/performance/abuse suites:

- caret-only navigation performs zero parsing, semantic rebuilds, projection
  rebuilds, layout builds, region-chrome preparation, or cache-wide clearing;
- an ordinary non-wrapping character edit performs one source transaction and
  at most one bounded incremental projection/layout application, with no
  full-document scan or full layout snapshot;
- a burst of wrap-sensitive ordinary edits queues at most one coalesced frame
  update and retains immediate caret feedback;
- syntax/topology edits perform at most one canonical semantic scan, projection
  build, and layout build for the committed revision;
- a paint event performs no parsing, service lookup, source mutation, layout
  construction, thumbnail I/O, or cache-wide invalidation;
- a pure scroll reuses layout and semantic state and only translates/recomputes
  visible viewport data;
- canvas and workflow round trips do no prompt-source replacement or prompt
  semantic/projection/layout work when the prompt field is unchanged;
- reorder pointer movement remains geometry-only, schedules at most one preview
  unit, and performs no raster rebuild, full refresh, or projection rebuild in
  the direct pointer dispatch;
- async publication is O(result size), revision checked, and never triggers
  duplicate canonical work for the same source revision;
- all caches are bounded, revision-keyed, and expose hit/miss/eviction counters;
- instrumentation hooks are direct stable owner events and add effectively zero
  work when disabled.

The existing 16.667 ms reference frame target remains an outer envelope:
populated latency lanes require p95 at or below one frame, p99 at or below 1.5
frames, and maximum at or below two frames. The migration should also establish
checked-in revision baselines and require no statistically meaningful regression
for key dispatch, caret/selection, paint, scroll, resize, canvas/workflow switch,
and reorder workloads. Structural budgets take precedence over a fast local
machine's wall-clock result.

## Migration roadmap

### Characterization prerequisites

Before moving a responsibility, create or strengthen the contract at the owner
boundary that will replace private probing. The baseline must include:

- exact source, cursor/anchor, selection, undo/redo, normalization, IME, MIME,
  focus, sizing, and scroll behavior;
- canonical and incremental semantic/projection/layout equivalence for ordinary,
  syntax, structured-value, scene, regional, and reorder documents;
- visible geometry, caret stops, navigation, hit testing, source-line rectangles,
  selection fragments, inline objects, chrome, and pixel-level paint invariants;
- async generation, cancellation, latest-wins behavior, teardown safety, and
  stale-result rejection for every feature;
- workflow and canvas switches with unchanged and changed prompt fields;
- cache correctness, boundedness, invalidation-by-key, and exact structural
  work counts.

The abuse operation catalog must first add explicit obligations for regional
separators, IME, drag/drop, exact-weight edits, thumbnail publication, and async
races. Regional scenarios must include adjacent and empty partitions, marker
formation/invalidation at every character boundary, navigation through hidden
source, raw/rich toggles, selection across separators, undo/redo, paste, resize,
reflow, canvas/workflow round trips, and large documents.

Add a supported `PromptEditorDebugSnapshot` and `PromptEditorWorkCounters`
contract before removing private harness reads. Populate it from owners without
walking widget internals and keep collection disabled or constant-time outside
instrumented runs.

Capture a checked-in machine-independent structural baseline and a separately
stored revision timing report for:

- empty, 250-character, 1k, 5k, and 10k ordinary edits;
- long multi-line richly decorated and regional prompts;
- caret/selection movement at document start, middle, and end;
- paint, scroll, resize, raw/rich toggle, search, diagnostics, and thumbnails;
- autocomplete and async completion races;
- reorder keyboard, pointer, scroll, and preview;
- unchanged canvas/workflow switching while output activity is idle and busy.

Wall-clock comparisons need repeated runs, warmup exclusion, environment/load
metadata, p50/p95/p99/max, and baseline-versus-candidate deltas. Structural
budgets must pass even when wall timings are noisy.

### Dependency graph and vertical slices

This is an ordered migration, not a menu. Each slice lands with all call sites
updated and the old path deleted before the next slice begins.

1. **Install architecture and measurement guardrails.**
   - Add import rules for domain, application, core, features, panel adapters,
     and composition.
   - Add size/change-reason review gates for designated integration roots.
   - Replace monkey-patched measurement points with stable optional owner
     counters while proving disabled overhead.
   - Establish structural budgets for every hot operation, including “zero
     work” contracts.

2. **Normalize pure package ownership.**
   - Split domain and application flat packages into the target cohesive
     subpackages with direct imports.
   - Break the LoRA ranking/catalog type cycle by moving shared immutable catalog
     values to `lora/catalog_models.py`.
   - Remove the dynamic application lazy-export registry from internal imports.
   - Preserve the parser's single canonical scan and document cache behavior.

3. **Break the panel inversion.**
   - Define a caller-neutral preset snapshot/source port in the prompt feature.
   - Move model-scope resolution and active-model context entirely to
     `panel/prompt/preset_adapter.py`.
   - Remove all prompt-editor-to-panel imports and enforce the boundary.

4. **Establish revisioned core state.**
   - Introduce typed source, semantic, projection, layout, viewport, and paint
     revision identities around existing snapshots.
   - Add validation at publication boundaries without copying full documents.
   - Replace ad hoc freshness combinations with a single inspectable revision
     graph while retaining current behavior.

5. **Finish editing ownership.**
   - Move IME, deletion, clipboard/history, key edit coalescing, and command
     execution through the editing session's typed command API.
   - Collapse redundant command adapter/router/result application layers.
   - Make one `EditCommit` the only input to projection updates.
   - Delete the obsolete surface-host edit mutation paths.

6. **Extract immutable geometry authority.**
   - Add characterization for every current private geometry method.
   - Move layout snapshot models first, then hit test, caret navigation,
     selection, source-line, and visible-line queries as pure snapshot consumers.
   - Move the algorithms and their tests completely; do not leave methods on
     `PromptProjectionLayout` that wrappers call privately.
   - Delete the six-module cycle and private geometry access.

7. **Separate canonical and incremental layout engines.**
   - Retain lazy shifted sequences, reused suffixes, line semantics validation,
     checkpoint restore, and local text shaping.
   - Give both engines the same immutable input/output contract.
   - Require the incremental engine to return `Applied`, `Deferred`, or
     `Rejected` with a reason and bounded damage; it cannot trigger fallback
     itself.
   - Keep one canonical recovery owner.

8. **Consolidate the edit-to-frame pipeline.**
   - Move classification from source-change applier, freshness controller,
     incremental-apply controller, and surface callbacks into one pure
     `EditClassifier`.
   - Move strategy execution into `PromptEditPipeline`.
   - Keep adaptive latest-wins scheduling and output-load awareness, supplied by
     explicit ports.
   - Delete overlapping decision code and prove identical path classification
     over the corpus before optimizing further.

9. **Make rendering a pure sink.**
   - Build immutable paint plans/layers from prepared snapshots outside
     `paintEvent`.
   - Key content, diagnostic, fill-band, chrome, thumbnail, and reorder caches by
     explicit revision tuples.
   - Replace manual invalidation webs with damage and key changes.
   - Reduce surface paint to clip selection, cached-layer composition, caret,
     and overlay blits.

10. **Extract reorder as a complete feature slice.**
    - Reuse the canonical geometry query API.
    - Keep gesture state, target resolution, preview scheduling, preview
      projection, animation, raster warming, caches, and rendering in separate
      cohesive owners.
    - Preserve the direct pointer path's zero-heavy-work rule and one queued
      preview-unit rule.
    - Remove reorder state/caches/counters from the core surface.

11. **Convert remaining product features into vertical slices.**
    - Migrate autocomplete, diagnostics, emphasis, LoRA, wildcards, Danbooru,
      regions, scenes, presets, and search one at a time.
    - Each slice owns its session, async generation, prepared view snapshot,
      commands, and presentation; it uses only core commands/queries/events.
    - Consolidate common latest-wins and stale-result mechanics in the async
      runtime without a generic feature god-controller.

12. **Shrink Qt integration roots to their final shape.**
    - `surface/widget.py` receives Qt events, delegates typed intents, and paints
      prepared frames.
    - `api/widget.py` preserves the host-facing `PromptEditor` API/signals and
      contains no feature logic.
    - The shell owns QFluent chrome, sizing, scrolling, and context menus.
    - Composition constructs the graph once and contains no runtime callbacks
      that reach back into the facade for ordinary work.

13. **Finish panel separation and delete migration scaffolding.**
    - Move prompt factory/binding/context/scene diagnostics into the panel's
      prompt adapter package.
    - Break the panel view/cube-section cycle.
    - Remove legacy barrels, broad host Protocols, compatibility shims, obsolete
      callbacks, dead counters, and private harness paths.
    - Run dependency and dead-code audits before declaring the shape final.

The critical dependency order is:

```text
behavior/performance contracts
  -> revisioned state
  -> editing command boundary
  -> immutable geometry
  -> canonical/incremental engines
  -> edit-to-frame pipeline
  -> rendering/cache ownership
  -> feature slices
  -> thin surface/facade/panel adapters
  -> deletion of legacy graph
```

Trying to split the widget or surface before state, geometry, and pipeline
authority are explicit would reproduce the current shim pattern under new file
names.

### Cleanup and deletion requirements

Every slice must include a deletion ledger. Completion requires:

- all call sites use the new owner directly through its stable command/query
  contract;
- the previous state, algorithm, cache, timer, signal path, Protocol, callback,
  cast, export, and test helper are removed;
- no new module calls a private method on its predecessor;
- no compatibility layer remains for internal APIs;
- package roots do not re-export entire implementation graphs;
- no duplicated parser scan, semantic projection, layout build, geometry query,
  cache, stale-result guard, or feature decision remains;
- comments and docstrings describe the resulting architecture directly, not the
  migration;
- any temporary dual-run equivalence checker is removed after the new owner is
  authoritative and the final baseline is captured.

### Migration risk controls

- **No big-bang rewrite.** Land one complete authority transfer at a time behind
  characterization and performance contracts.
- **No behaviorless file movement.** Package-only moves are permitted only when
  they establish an enforced dependency boundary needed by the next slice.
- **No dual authority.** Temporary shadow calculation may compare outputs, but
  only one path may publish state. Remove the shadow path after equivalence is
  demonstrated.
- **No abstraction tax on hot paths.** Measure allocations, copies, signal
  emissions, virtual/protocol calls, and owner counters before and after each
  extraction. Prefer immutable references and compact lazy sequences over
  repackaging whole documents.
- **No repeated scans disguised as separation.** The canonical parser and
  canonical layout remain cohesive single-pass engines with focused internal
  collaborators; feature owners contribute prepared inputs rather than rescanning
  source or layout.
- **No paint-time preparation.** New paint layers must prove all semantic,
  geometry, I/O, and cache-key preparation occurs before `paintEvent`.
- **No timer proliferation.** New deferred work uses the bounded scheduler
  primitives and exposes cancellation, supersession, maximum-stale, and teardown
  behavior.
- **No unbounded caches.** Every cache declares key identity, maximum size or
  lifecycle bound, eviction behavior, memory observability, and correctness on
  a miss.
- **No silent fallback inflation.** Every incremental rejection has a typed
  reason counter. Canonical fallback rates are compared across the corpus.
- **No canvas regression.** Prompt refactors run unchanged-field canvas and
  workflow round trips under idle and active output load; any prompt work on
  those paths is blocking.
- **Rollback remains trivial.** Keep slices atomic and cohesive; do not combine
  architecture transfer with unrelated product behavior.

### Verification gates

For each slice:

1. Run owner-level pure tests.
2. Run affected Qt component tests.
3. Run deterministic real-shell scenarios for the changed behavior.
4. Run the complete seeded abuse matrix with coverage audit and structural
   instrumentation.
5. Run focused performance scenarios and compare with the exact pre-slice
   baseline.
6. Run targeted formatting, lint, and strict typing.

Before each commit, run the repository-mandated complete format, lint, strict
mypy, parallel-test, and serial-test gates against the exact final worktree.
Additionally require:

- zero missing required abuse operations;
- zero structural budget violations;
- zero correctness/invariant findings;
- no performance regression outside the agreed noise threshold, and an
  investigation for every adverse p95/p99/max delta;
- no new import cycles or forbidden layer edges;
- no prompt core/presentation import from editor panel;
- no increased private-access count;
- no increase in methods or dependencies on designated integration roots unless
  matched by removal in the same slice;
- disabled instrumentation overhead remains below measurement resolution;
- Windows verification locally and CI confirmation on Windows, Linux, and macOS
  before the migration is considered releasable.

## Definition of done

The review's target architecture is achieved only when:

- the complete feature inventory is preserved and every behavior has an
  authoritative owner-level contract plus real-shell coverage;
- domain, application, core presentation, feature presentation, shell,
  composition, and panel adapters follow one-way enforced dependencies;
- each mutable state has one writer and every derived snapshot records its
  upstream revision identities;
- source commit, edit classification, incremental/canonical projection, layout,
  geometry query, damage, and paint are distinct cohesive owners;
- hit test, caret movement, selection, source-line geometry, chrome, reorder,
  and paint consume immutable layout snapshots without private access;
- `PromptProjectionSurface`, `PromptEditor`, `PromptProjectionLayout`,
  interaction integration, and composition are thin final owners, not god
  objects or callback service locators;
- all features are vertical slices that use stable core ports and cannot add
  arbitrary work to key, paint, canvas, or workflow paths;
- every cache is bounded and revision-keyed, and cache correctness does not
  depend on scattered manual invalidation;
- adaptive coalescing, transient feedback, lazy sequences, viewport clipping,
  incremental reuse, checkpoint restoration, async stale rejection, and reorder
  frame protections are preserved or improved;
- ordinary editing, navigation, paint, scroll, resize, reorder, canvas, and
  workflow performance pass explicit structural budgets and show no regression
  against repeated baselines;
- the new architecture demonstrates measurable improvements in common and tail
  latency, rebuild counts, allocation/copy volume, and cache reuse;
- internal compatibility shims, delegation bookmarks, broad host Protocols,
  private test probes, import cycles, obsolete exports, and duplicate paths have
  been deleted;
- full repository quality and test gates pass on the exact final tree, and the
  cross-platform CI matrix is green.
