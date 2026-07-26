# Prompt Editor Architecture and Performance Review

> Architecture review baseline for `bc6c6a7b`. This is a self-contained
> implementation roadmap, not a chronological investigation log.

## Active refactor objective

Completely implement the prompt-editor refactor defined in this document,
keeping it authoritative and continuously current for work, evidence,
remaining slices, dependencies, deletions, structural measurements,
performance, and verification. Deliver the final architecture, not file
movement: cohesive single-responsibility modules; one authoritative owner per
concern and state transition; strict typed command/query/event and immutable
revisioned-snapshot boundaries; one-way dependencies; Qt-free lower layers;
one edit-to-frame owner; immutable snapshots as the sole geometry authority;
prepared-snapshot rendering; vertical features over stable core ports; thin
widget, surface, shell, composition, and panel adapters; and no obsolete paths,
internal shims, delegation bookmarks, broad host Protocol service locators,
duplicate authorities, cycles, dead exports, or migration scaffolding.

Define the permitted dependency graph in this document before transferring
further ownership and enforce it with focused architecture tests.
Responsibility must flow:

`widget/shell/panel -> presentation adapters -> application orchestration -> core contracts/policy`

It must never flow in reverse. Core layout policy, immutable core data, and
pure edit/reuse decisions must not import projection, presentation, widgets,
panels, shells, or Qt. Qt measurement, shaping, geometry adaptation, and
painting belong only in focused presentation-side owners. Every exceptional
boundary must be explicitly justified here, narrowly typed, and proven not to
invert ownership. An extraction cannot finish while any inverted edge, cycle,
duplicate owner, private cross-module API, or temporary compatibility bridge
remains.

Moving code is not progress by itself. An extraction is complete only when its
destination has one coherent reason to change, dependencies point in the
permitted direction, tests target the new authoritative owner, every caller
uses it directly, and the old authority and dead exports are deleted in the
same slice. Do not relocate a large mixed block into a second large module. If
moved code remains broad, split it by actual responsibility before advancing.
Thin adapters may translate typed inputs, invoke one use case, and publish
immutable results; they may not own algorithms, mutable domain state, caches,
fallback decisions, revision policy, layout construction, or feature rules.

Preserve every current behavior, feature, persisted format, public/host API,
Unicode/IME invariant, editing invariant, and workflow integration unless the
maintainer explicitly approves a change. Regressions, new bugs,
nondeterminism, weakened assertions, skips, retries, and concealed failures
are blocking. Add characterization before structural changes. Tests must
follow authoritative ownership rather than preserve access to moved private
helpers; replace stale implementation-coupled tests with public owner-level
contracts, and never weaken or rewrite an assertion merely because structure
moved. Expand owner, focused Qt, real-shell, and seeded abuse coverage whenever
a failure class is exposed, including regional separators, IME, drag/drop,
exact-weight editing, async races, navigation, selection, history, raw/rich
modes, reflow, paint/caches, reorder, workflow switching, and unchanged canvas
round trips. Fix every reproducible defect before advancing.

Make performance a correctness property. No editor, panel, workflow, output,
or canvas regression is acceptable; canvas is a protected verification
boundary, not a prompt-editor implementation owner. Preserve and improve
incremental work, topology-aware fallback, lazy shifts, validated reuse,
transient feedback, latest-wins scheduling, checkpoints, viewport clipping,
damage-bounded repaint, bounded revision-keyed caches, async stale rejection,
and zero unrelated prompt work during unchanged workflow/canvas operations.
Add no unnecessary allocations, scans, hashing, signals, callbacks,
invalidations, full-document work, layout construction, service queries, or
instrumentation to hot paths. Fast hardware cannot excuse algorithmic
regression.

For each hot-path slice, compare the unchanged baseline commit against the
candidate using identical seeded workloads, environment, warmup, and sample
policy. Record median and tail latency, allocations, peak memory, rebuild and
fallback counts, cache behavior, paint damage, and unchanged canvas/workflow
prompt work. Require per-slice structural-work budgets and repeated controlled
baseline-versus-candidate evidence. Any unexplained regression blocks
advancement.

Follow this document in dependency order through complete vertical authority
transfers. Work on one declared authority transfer at a time and do not broaden
it into opportunistic cleanup. Before beginning each slice, record its current
ownership, permitted dependency direction, behavior contracts, hot paths,
baseline structural measurements, baseline performance evidence, and exact
deletion target. For each slice: trace ownership; update the ledger; add
behavior, architecture, and performance contracts; transfer the complete
state, algorithm, lifecycle, cache, tests, and observability; update all
callsites; delete the old path in the same slice; prove equivalence; and run
only focused verification proportional to its ownership and blast area. Do not
advance until the authority transfer, callsite migration, deletion, focused
architecture checks, behavior evidence, and controlled performance comparison
are complete.

If an extraction introduces an inverted dependency, duplicate authority, broad
destination module, private cross-module API, compatibility shim, generic
event bus, repeated scan, empty abstraction, or delegation bookmark, stop that
extraction and correct it before touching the next responsibility. Do not
extend large or mixed-responsibility modules. Record before/after line counts,
method counts, dependency edges, mutable-state owners, and deleted paths for
every major god object. Line-count reduction alone is not success:
responsibility inventories, mutable-state ownership, dependency edges, and
caller surface must also shrink and match the target graph.

Autonomously run only focused checks proportional to ownership and blast area:
owner and characterization tests, focused Qt and real-shell scenarios,
targeted formatting, lint, and strict typing, and relevant abuse,
structural-budget, feature, performance, memory, canvas, and workflow lanes.
Abuse, feature, and controlled baseline-versus-candidate performance harnesses
are the primary regression loop. Expand missing coverage when a failure class
is not explained. Do not run unrelated or broad suites, rerun unchanged
evidence, loop tests, retry failures, or manufacture confidence. Keep progress
reporting factual and compact: authorities transferred, files and structural
measurements changed, old paths deleted, focused checks run, measured
performance, and remaining work.

Never autonomously run complete repository format, lint, strict mypy, parallel
tests, serial tests, other full gates, or commits. Only the maintainer's exact
instruction `commit your work` authorizes them; infer nothing from slice
completion, focused success, turn completion, pending changes, or other
wording. Until then keep work uncommitted.

After `commit your work`, run all complete repository format, lint, strict
typing, parallel-test, and serial-test gates plus applicable real-shell, abuse,
performance, memory, canvas, and workflow gates on the exact commit-relevant
tree. Fix failures at their authoritative owner with focused checks; preserve
unrelated work; never weaken gates; rerun only invalidated evidence unless
directed otherwise. Then create atomic Conventional Commits on the active
refactor branch with matching updates to this document.

Complete only when every migration, deletion, and verification item is
finished; all features retain authoritative coverage; the enforced dependency
graph has no forbidden or cyclic edges; god objects have thin final forms by
responsibility as well as size; private state access, duplicate paths, shims,
and migration scaffolding are gone; all reproducible defects are fixed;
controlled evidence proves performance equal or better without canvas/workflow
regression; the maintainer has said `commit your work`; authorized full gates
pass on the exact final tree; and this document records no remaining work.

## Implementation ledger

This section is the authoritative migration status. Update it in the same
change as every completed authority transfer, deletion, performance result, and
verification result.

- Refactor branch: `refactor/prompt-editor-architecture`
- Behavioral baseline: `bc6c6a7b`
- Current slice: 13, panel separation and migration cleanup
- Completion state: implementation complete, uncommitted verification pending maintainer authorization
- Blocking regressions: none accepted

| Slice | Authority transfer | Status | Evidence |
|---:|---|---|---|
| 1 | Architecture and measurement guardrails | Complete | Import/debt guards, stable owner hooks, 68/68 structural coverage, clean-root performance comparison, and complete repository gates |
| 2 | Pure domain/application package ownership | Complete | Direct-owner packages, deleted LoRA cycle and flat barrels, 68/68 structural coverage, paired performance evidence, and complete repository gates |
| 3 | Panel dependency inversion | Complete | Caller-neutral prompt preset port, panel-owned adapter and scope policy, zero reverse imports, 68/68 structural coverage, paired performance evidence, and complete repository gates |
| 4 | Revisioned core state | Complete | Typed source-to-paint lineage, deleted state mirrors, focused frame synchronization, allocation-safe hot paths, 68/68 structural coverage, paired performance evidence, and complete repository gates |
| 5 | Editing ownership | Complete | One typed core commit boundary, deleted router/adapter/session-facade graph, 68/68 three-pass structural coverage, and controlled baseline performance evidence |
| 6 | Immutable geometry authority | Complete, uncommitted | Focused owner and real-shell coverage, 204-run structural abuse, paired performance evidence, deleted geometry cycle, corrected dependency direction, and no regression |
| 7 | Canonical and incremental layout engines | Complete, uncommitted | Deleted 5,682-line host and mixed algorithm/engine modules; focused directional policy, mutation, recovery, strategy, state, frame, geometry, and paint owners; focused abuse/canvas and controlled performance evidence |
| 8 | Edit-to-frame pipeline | Complete, uncommitted | Deleted mixed controller/editor/source-applier roots; focused classification, strategy, commit, publication, and transaction owners; hostile behavior and controlled performance clean |
| 9 | Prepared rendering and revision-keyed caches | Complete, uncommitted | Immutable prepared layers, deterministic composition, revision/media-keyed caches, focused structural/behavior evidence, and repeated controlled paint/search/caret/canvas performance evidence |
| 10 | Reorder feature slice | Complete, uncommitted | Directional application-to-Qt ownership, focused owner/real-shell/abuse coverage, structural budgets, and maintainer-approved final timing override |
| 11 | Remaining vertical feature slices | Complete, uncommitted | Autocomplete, diagnostics, emphasis, LoRA metadata, wildcards, context-menu snapshots, and scenes each now have direct focused owners; obsolete controllers, forwarding paths, and feature host Protocols are deleted, and final scene/reorder debt guardrails pass. |
| 12 | Thin Qt integration roots | Complete, uncommitted | Direct construction-owned clipboard completion, strict public-widget typing, explicit root bindings, deleted composition casts, and fixed integration-root budgets. |
| 13 | Panel separation and migration cleanup | Complete, uncommitted | Prompt factory, context, scene diagnostics, profile policy, and direct controller bindings are owned by `panel/prompt`; the view/cube-section cycle and obsolete fallback paths are deleted, with focused architecture/import audits passing. |

### Slice 12 characterization: thin Qt integration roots

The final Qt-root transfer begins from the current guarded shape: `PromptEditor`
is 1,901 owned lines and 163 methods (ceilings 1,910/164),
`PromptProjectionSurface` is 3,836/258 (ceilings 3,858/258), and the
composition factory is 940/14 (ceilings 960/14). `PromptEditor` must retain the
documented public `PromptEditor` API and Qt overrides, but its internal methods
may only translate host events, delegate typed commands, or compose prepared
visual state. `PromptProjectionSurface` remains the custom projection widget;
Slice 12 must remove its remaining feature and orchestration responsibilities
by coherent concern rather than relocating its methods wholesale.

The first declared transfer is clipboard-paste completion. The current
`PromptProjectionEditingRuntimeBuilder` reaches through the composition context
with a private `PromptEditor._handle_clipboard_paste_completed` callback, which
then discovers the interaction controller. The permitted replacement is a
focused construction-owned completion owner: clipboard and MIME-drop command
paths publish a reason to it, and, after construction, it invokes only the
interaction controller's semantic-refresh command. It must preserve ordinary
paste/drop behavior, issue no work before that command owner is bound, add no
work to keyboard, paint, canvas, or workflow paths, and delete both the private
widget callback and factory cast in the same transfer. Focused clipboard,
MIME-drop, and owner contracts are the characterization and acceptance set.

The clipboard-paste completion transfer is complete. The construction-owned
`PromptClipboardPasteCompletionOwner` now receives the runtime callback before
projection construction and binds once to the focused interaction controller
after syntax construction. Clipboard and MIME-drop paths notify that owner
directly; `PromptEditor._handle_clipboard_paste_completed` and the factory's
private-widget cast are deleted. The owner is inert before its interaction
binding, preserving construction behavior without adding a keyboard, paint,
canvas, or workflow path. Its direct-owner, clipboard-command, MIME-policy,
and paste-import contracts pass with targeted Ruff and strict mypy. The public
widget facade is also now strict-mypy clean: its projection forwards declare
the immutable types published by the surface instead of untyped compatibility
values, and construction uses concrete callable aliases rather than two broad
factory Protocols. The focused host-boundary and architecture suites remain
green after this tightening.

Context insertion is the next completed construction boundary. Its factory now
receives explicit cursor, focus-restoration, and source-text callbacks from the
public widget instead of recovering `context.editor` through a cast. The
service still owns the same command preparation and commits, while composition
owns its exact host bindings. A dedicated composition guard rejects a return to
the context-editor reach-through; focused context-menu and architecture
coverage, targeted Ruff, and strict mypy pass.

Scene prepared-position construction now likewise receives the public widget's
direct source-text callback. The factory retains only its legitimate QWidget
parent/executor construction inputs and no longer discovers source text through
the composition context. The composition guard and focused scene-owner plus
architecture coverage pass with targeted Ruff and strict mypy.

Search highlight publication now consumes the core source-identity command
directly. The former one-method search host Protocol and the composition cast
to the public widget are deleted; the controller still owns only immutable
search snapshot derivation and prepared surface publication. Focused search,
composition, and architecture coverage passes with targeted Ruff and strict
mypy.

Wildcard autocomplete stale-result validation now receives that same core
source-identity callback directly. Its one-method widget identity Protocol and
factory cast are deleted without changing the prepared-cache or latest-wins
request lifecycle. Focused wildcard/autocomplete and architecture coverage,
targeted Ruff, and strict mypy pass.

Prompt-segment preset presentation no longer receives a broad editor host. Its
adapter consumes only source cursor/read/restore callbacks, the source-identity
command, and the concrete QWidget hierarchy used for save-dialog parenting.
The cursor contract now records selection restoration explicitly. Focused
segment-preset/menu and architecture coverage, targeted Ruff, and strict mypy
pass.

Autocomplete panel presentation now receives the concrete QWidget only for
overlay parenting plus separate viewport and caret-rectangle callbacks for
geometry. The presentation editor Protocol and composition cast are deleted;
focused panel/presentation and architecture coverage, targeted Ruff, and strict
mypy pass.

Autocomplete query-result freshness now reads the core source-identity command
directly rather than asking the composition context to rediscover the public
widget. Focused query/result and architecture coverage, targeted Ruff, and
strict mypy pass.

Autocomplete ghost-text publication now invokes the projection surface's
prepared preview-state command directly. Its widget-shaped preview-sink Protocol
and factory cast are deleted while preserving the revision-safe publication
lifecycle. Focused ghost/session/result and architecture coverage, targeted
Ruff, and strict mypy pass.

Autocomplete acceptance now receives only its four required bindings: cursor
position, current core source identity, acceptance-command execution, and LoRA
replacement completion. The acceptance cursor, command-factory, and
editor-shaped Protocols and the corresponding composition cast are deleted;
Qt input still owns focus translation and the lifecycle still owns session
closure. Focused acceptance, lifecycle, coordinator-baseline, and architecture
coverage pass with targeted Ruff and strict mypy.

The final autocomplete Qt-input binding is now direct as well. The input
adapter receives a concrete focus host solely for focus-loss ancestry checks
and a separate restoration callback for row activation. The former autocomplete
editor, cursor, and query Protocols and the factory's editor cast are deleted.
The shared test assembly supplies explicit inert acceptance callbacks only for
query-focused doubles that never exercise acceptance. Focused autocomplete
acceptance, lifecycle, session, result, presentation, baseline, and
architecture coverage pass with targeted Ruff and strict mypy.

Autocomplete source snapshots now receive direct source-text, source-identity,
document-view, and one concrete cursor-state callbacks. This deletes the
source-editor and timing-cursor Protocols and their factory cast while retaining
the original single cursor read per snapshot; the characterization test rejects
a second read. The public widget and composition root remain at their existing
line ceilings after the replacement. Focused timing, query, result, session,
baseline, and architecture coverage pass with targeted Ruff and strict mypy.

Reorder-preview publication now receives direct clear and prepared-preview
publication callbacks from the projection surface plus the core source-identity
command. Its editor publication Protocol and both composition editor casts are
deleted without changing scheduler or preview-build ownership. Focused preview
publication, scheduler, LoRA-projection refresh, and architecture coverage pass
with targeted Ruff and strict mypy.

Syntax state now receives direct source-text, cursor-position, active-span, and
stable editor-session collaborators. The syntax editor and cursor Protocols,
factory cast, and optional host `getattr` are deleted; source identity remains
authoritatively derived from the already-published core document state. Focused
syntax/reorder and architecture coverage pass with targeted Ruff and strict
mypy, while the public widget and composition root remain at their fixed line
ceilings.

Wheel routing now receives direct surface-scroll permission, scroll handling,
and panel-forwarding operations. Its wheel-host Protocol and composition cast
are deleted while token-weight wheel-intent ownership remains unchanged.
Focused wheel intent, integration, contract, and architecture coverage pass
with targeted Ruff and strict mypy; the integration roots remain at their fixed
line ceilings.

Weight interaction and general interaction retain their distinct feature-owned
typed ports because each owns a coherent, stateful contract beyond a small
callback set. Composition now receives those ports explicitly from the public
widget, removing its final `context.editor` casts without weakening either
contract. Focused architecture, syntax/reorder, LoRA refresh, and wheel
contracts pass with targeted Ruff and strict mypy, and both integration roots
remain at their fixed line ceilings.

Projection construction now returns the parenthesis-education controller as a
typed collaborator. The Qt facade retains that signal-connected owner directly;
the former factory-side private widget assignment and cast are deleted. Focused
parenthesis-education and architecture coverage pass with targeted Ruff and
strict mypy while retaining the root ceilings.

### Slice 13 characterization: panel separation and migration cleanup

Slice 13 completes the remaining panel boundary after the prompt-editor roots
are thin. The panel owns prompt factory construction, prompt binding, prepared
prompt context, and scene-diagnostic presentation. Prompt-editor code may
consume caller-neutral ports but may not import panel context, policy, or view
implementation. The prior `view`/`widgets.cube_section` type-only cycle was
the first removal: the cube-section builder consumes a focused panel
construction port rather than referencing `EditorPanel`. Subsequent transfers
move each panel concern with its state and tests, and remove obsolete migration
barrels, compatibility shims, private callbacks, and dead harness paths. Panel
projection, prompt-factory, context, scene-diagnostic, cube-section layout,
real-shell workflow, and dependency-graph checks are the characterization and
acceptance evidence; no panel change may add typing, canvas, or workflow-path
work outside its owning adapter.

The view/cube-section cycle is now deleted. `CubeSectionBuilder` no longer
references `EditorPanel`; the cube-section module owns a caller-neutral QWidget
adapter that derives the focused parent, registries, state reader, and metrics
callback. `EditorPanel` supplies that adapter at its two construction sites, and
focused test panels use the same path. The architecture guard now requires no
import cycles. Cube-section layout, theme, and architecture coverage pass with
targeted Ruff. Panel prompt/context/diagnostic transfer and migration cleanup
are complete; the later records below capture the final direct owners and
verification.

Prompt scene diagnostics is now owned by `panel/prompt/scene_diagnostics.py`.
The panel view and focused diagnostic tests import that owner directly; its
logger namespace follows the new package location, and the former panel-root
module is deleted. Focused diagnostics and architecture coverage pass with
targeted Ruff and strict mypy.

Prompt context is now owned by `panel/prompt/context.py`. The panel view and
behavior logging contract import or observe that package owner directly; the
former panel-root module is deleted. Focused prompt-context, panel behavior,
and architecture coverage pass with targeted Ruff and strict mypy.

Prompt factory is now owned by `panel/prompt/factory.py`. The field pipeline
and focused factory tests import that owner directly, and the former
`panel/factories` module is deleted. Focused factory and architecture coverage
pass with targeted Ruff and strict mypy.

Prompt field-profile policy is now owned by `panel/prompt/profile_policy.py`.
The prompt context, field pipeline, node-card builder, panel type surface, and
their focused contracts import the new owner directly; the former panel-root
module is deleted. Focused profile-policy, context, panel behavior, node-card,
and architecture coverage pass with targeted Ruff and strict mypy.

The panel now binds prompt context and scene diagnostics during construction and
uses those typed controller fields directly. The lazy `view.py` discovery
helpers, their `getattr`/`setattr` fallback creation, and their broad host casts
are deleted. Partial panel characterization hosts now explicitly bind the real
controller required by the method under test, preserving the direct production
contract. Focused context, scene-diagnostics, panel-behavior, and architecture
coverage pass with targeted Ruff.

Prompt factory construction now calls the typed `PromptEditor` constructor and
its canonical `replaceBaselineSourceText()` API directly. The factory's dynamic
constructor cast and baseline-text fallback are deleted. Scene diagnostics reads
the current behavior snapshot through its declared host method, and field-state
prompt restoration invokes the required panel scene-refresh method directly;
the corresponding availability callbacks are deleted. Focused factory, scene,
field-state, panel-behavior, cube-section, theme, architecture-boundary,
architecture-guard, and startup-composition coverage pass with targeted Ruff
and strict mypy for the changed prompt adapters. Import and dead-path audits
find no old panel-prompt modules, package barrels, or allowed import cycles;
`git diff --check` is clean. Slice 13 is complete, uncommitted.

### Slice 5 acceptance ledger

Slice 5 is complete only when:

- `core/editing` is the sole owner of source text, source revision, cursor and
  selection state, normalization, source deltas, undo/redo transactions,
  clipboard edit intent, IME composition state, and key-edit coalescing policy;
- every source mutation enters that owner as a typed core command and returns
  one immutable `PromptEditCommit`; feature commands may prepare core commands
  but cannot mutate the session or projection through another path;
- `PromptEditCommit` records the exact previous and next source identities,
  bounded source delta, cursor/selection result, origin, normalization
  transitions, undo availability transition, and optional prepared semantic
  value without copying or hashing the full source;
- projection receives committed source and history changes only through
  `apply_edit_commit(commit)`; no router result, application tuple, restore
  callback, source-change wrapper, or direct session result can enter
  projection independently;
- IME commit, Backspace, Delete, selection deletion, typed insertion, newline,
  paste, cut, programmatic replacement, autocomplete, diagnostics, emphasis,
  reorder, trigger words, Danbooru import, undo, and redo all use the same
  command/commit boundary while preserving exact current behavior;
- transient IME preedit remains outside persisted source and undo history,
  UTF-16 replacement ranges remain correct for Unicode, and unrelated source
  changes cancel composition deterministically;
- typing and delete coalescing state and timers call typed editing-session
  commands directly, emit each undo/redo availability transition once, and add
  no source reads, snapshots, signals, or timer work to unrelated navigation,
  paint, canvas, or workflow paths;
- clipboard interaction separates operating-system clipboard I/O and Danbooru
  scheduling from pure copy/cut/paste commands; cut and paste each perform one
  source transaction rather than planning through one command and mutating
  through another;
- projection-aware deletion resolves one immutable deletion intent and submits
  one core command; the broad deletion surface-host Protocol and private
  mutation callbacks are deleted;
- the redundant command dispatcher, edit controller, edit command router,
  host command adapter, projection application/result wrappers, surface runtime
  mutation attachment, and their internal compatibility exports are deleted,
  with every callsite transferred to focused owners;
- the command package root is inert, the command import cycle is removed, and
  executable architecture policy rejects restoration of the deleted graph or
  any new direct source mutation outside `core/editing`;
- owner contracts cover typed insertion/replacement, no-op, stale rejection,
  normalization, selection, grapheme deletion, regional-separator boundaries,
  IME commit/preedit/cancel, clipboard, coalescing, nested edit blocks,
  undo/redo, prepared semantic adoption, and exact single-commit publication;
- real-shell and seeded abuse coverage proves keyboard, mouse, selection,
  history, IME, MIME, regional, raw/rich, autocomplete, diagnostics, emphasis,
  reorder, Danbooru, workflow, and unchanged-canvas behavior;
- structural budgets prove one source transaction and one projection commit per
  edit, no full-source scan or snapshot construction is added to ordinary
  typing/deletion, and zero prompt work remains the unchanged canvas/workflow
  contract;
- repeated pre-slice baseline comparison shows no latency, allocation,
  rebuild, fallback, cache, memory, canvas, or workflow regression, and focused
  plus complete repository gates pass for the exact slice worktree.

### Slice 5 ownership inventory

The pre-transfer editing graph has six overlapping mutation authorities:

- `editing_session/session.py` owns the real source, cursor, normalization, and
  history state, but exposes imperative mutation methods rather than one typed
  command/commit boundary;
- `commands/__init__.py` defines an executable command Protocol and dispatcher
  while importing the editing-session package root, and
  `editing_session/edit_controller.py` imports that command package back. The
  resulting eight-module command cycle is explicitly frozen in architecture
  tests;
- `PromptEditController` snapshots history and sometimes publishes projection
  applications, while `PromptEditCommandRouter` repeats command execution,
  edit-block policy, signal policy, source-application construction, semantic
  preparation, and publication. `PromptEditorCommandAdapter` adds a third
  host-facing forwarding layer and also owns context-insertion policy;
- `PromptProjectionSourceChangeApplication`,
  `PromptProjectionRestoreApplication`, and `PromptEditControllerResult` form a
  second mutation result model after the editing-session result. Projection can
  also accept restore results directly, so no single committed value is its
  authoritative input;
- Delete/Backspace, IME, clipboard/history, and undo coalescing each depend on a
  separate broad host/action Protocol. They query mutable surface state,
  calculate an edit, and then call private surface callbacks that re-enter the
  router. Cut and paste first dispatch planning commands and then dispatch a
  second replacement command for the actual source transaction;
- `PromptProjectionSurface` stores four late-wired mutation collaborators,
  exposes source replacement, IME replacement, clipboard cursor/restore, edit
  block, and source-application methods, and remains the service locator joining
  those paths.

Slice 5 transfers the complete editing lifecycle, not merely command type
names. Qt event decoding, system clipboard access, candidate-window geometry,
and projection-aware token queries remain presentation adapters, but they
produce typed immutable intents and cannot mutate source except through the
editing owner. Projection classification and layout strategy remain assigned to
Slices 7 and 8; this slice replaces their input with one commit without moving
those algorithms prematurely.

### Slice 5 evidence

The source, cursor, normalization, history, clipboard-intent, IME, and
coalescing owners now live under `core/editing`. Typed
`PromptReplaceRangeEdit`, `PromptReplaceDocumentEdit`, `PromptUndoEdit`, and
`PromptRedoEdit` commands are executed by the core session and return one
immutable `PromptEditCommit`. `PromptEditExecution` is the sole application
boundary that commits a command, reads the resulting source snapshot once, and
publishes undo/redo availability transitions once. Projection consumes the
same value through `apply_edit_commit`; there is no second source-change or
restore result model.

Focused command services now own the remaining presentation policies without
becoming mutation authorities:

- `PromptSourceCommandService` owns edit-block and explicit coalescing
  boundaries while forwarding one typed command to `PromptEditExecution`;
- `PromptContextInsertionService` owns captured-position and selection
  replacement, structured rejection, focus restoration, and its required
  pending-key-edit boundary;
- clipboard, Danbooru import, autocomplete, diagnostics, emphasis, reorder,
  trigger-word, and weight commands prepare one core command and consume one
  commit;
- `PromptDeletionResolver` converts a compact immutable projection context into
  one deletion intent. Grapheme, selection, raw, projected token, and
  structural separator deletion use the same command service. The keymap
  depends only on focused deletion actions rather than a broad surface host.

The previous command dispatcher, edit controller, command router, host command
adapter, editing-session presentation package, application/restore wrappers,
surface runtime attachment, and broad deletion host were deleted completely.
The command package root is inert. Architecture policy rejects restoration of
those files, symbols, or the former command import cycle. The surface retains
only narrow adapters that expose deletion context and projection effects; it
no longer owns a parallel source-mutation API. The production prompt-editor
graph passes strict mypy across all 246 modules, and the focused modified-test
set plus new execution, context-insertion, and deletion owner suites pass. The
test private-access debt ratchet falls from 307 to 305 while production private
exemptions, casts, and broad Protocol counts do not grow.

One behavioral regression was found during the transfer: the initial source
command service ended pending key edits before every range command. That split
ordinary typing and deletion undo groups and double-flushed clipboard
boundaries. Coalescing completion is now explicit; only policies that own a
real boundary request it. Owner tests assert one source commit, one snapshot
read, one projection publication, correct no-op behavior, and one history
transaction.

The complete source-policy gate also rejected an ASCII-only eligibility check
in the lazy caret transform. Eligibility now uses a bounded Unicode grapheme
boundary check over only the edited payload; it never scans the full document.
Simple Unicode text retains the incremental path, joined graphemes use the
canonical caret map, and a real-surface regression proves that `A日B` exposes
all valid caret boundaries while `A👩‍🚀B` exposes no interior caret position.
The shared projection invariant now derives its expected positions from the
same Unicode coordinate authority instead of incorrectly requiring one caret
stop per code point. The bounded check costs approximately 1.9 microseconds for
a one-character payload in the local microbenchmark.

Serial real-shell verification found that a same-text document command still
entered semantic/projection preparation. It advanced a staged semantic
identity without a corresponding current semantic publication, so a no-op Tab
or Escape interaction could expose stale revision lineage even though source
text stayed unchanged. Document no-ops now update only cursor and requested
viewport intent unless they carry an explicit prepared semantic state. An
owner test locks the zero source-mirror, semantic, projection, and incremental
work contract, and the real-shell Tab/Escape lineage scenarios pass. This
removes unnecessary work from initialization and other same-text document
commands.

The final instrumented abuse report at
`build/prompt-editor-slice5-commit-structural.json` contains 204
production-shell runs: 68 scenarios across repetitions 0, 1, and 2. It records
68/68 operation coverage, no missing operations, zero invariant violations,
zero structural violations, and no stale projection or semantic end states.
The corpus includes the regional-separator hostile cases, navigation and
selection, IME, clipboard/history, syntax and feature commands, raw/rich
transitions, workflow switching, and unchanged canvas round trips. A focused
separator delete/join/split campaign and an earlier complete smoke campaign are
also clean.

Performance verification found and repaired a stale measurement-harness access
to a deleted diagnostic-painter layout revision. The harness now consumes the
authoritative immutable layout identity. The complete candidate timing tool
then runs successfully, including diagnostic-cache preservation. Comparison
workers run in fresh processes, assert that every loaded `substitute` module
belongs to the selected worktree, disable observation, and use fixed affinity.
Sequential results were strongly order-correlated while an active external
ComfyUI process changed CPU load and clock state; paint-only controls moved by
the same proportion as editing lanes. A simultaneous same-core comparison
removed that order bias: aggregate process CPU was 13.188 seconds for the
candidate and 13.516 seconds for the pre-slice baseline. Candidate common edit
lanes were equivalent or faster within the shared load window. Structural
evidence independently proves one source transaction and one projection commit
per edit, no extra full-source read or snapshot construction in ordinary
typing/deletion, and zero prompt work on unchanged canvas/workflow paths. No
stable hot-path regression remains.

The exact Slice 5 source tree passes repository formatting and lint, strict
mypy over 2,900 source/test files, the complete non-serial suite, the license
header audit, and all 122 isolated serial modules. Serial coverage includes the
production real-shell prompt-editor, autocomplete, output-canvas, workflow,
toolbar, and widget abuse harnesses.

### Slice 6 acceptance ledger

Slice 6 is complete only when:

- immutable layout snapshot models have one foundational owner under
  `core/layout`; projection building, incremental reuse, geometry, rendering,
  feature overlays, diagnostics, and tests import that owner directly, and the
  former flat snapshot module is deleted without an internal compatibility
  export;
- one immutable geometry input records the exact projection document, layout
  snapshot, font/metrics, document inset, renderer registry, and layout identity
  consumed by every query; it is published once with a layout snapshot and is
  never reconstructed by caret movement, hit testing, selection, paint, scroll,
  canvas, or workflow paths;
- one focused `core/geometry` query authority owns caret rectangles, visual-line
  lookup, horizontal and vertical navigation, pointer and drag hit testing,
  selection fragments, source-range fragments, logical source-line rectangles,
  visible source bounds, token rectangles and anchors, and viewport damage
  rectangles as pure consumers of that immutable input;
- source-line geometry reuse remains exact and revision keyed, and lazy fragment
  indexes remain lazy; warm geometry reads perform no source copy, projection
  rebuild, layout build, cache-wide clearing, or full-document work that the
  previous path avoided;
- inline-object geometry is supplied through a narrow renderer geometry port
  already present in the immutable input; geometry cannot call back into
  `PromptProjectionLayout`, the surface, or a feature controller;
- `PromptProjectionPainter` consumes an immutable prepared paint input and the
  geometry authority directly; it does not retain a layout object or read layout
  private state. Reorder paint snapshot construction follows the same rule, so
  removing the geometry cycle does not defer a private callback through paint;
- every production and test callsite uses the geometry owner directly. Public
  host-facing widget geometry APIs remain stable, but internal layout geometry
  forwarding methods, hit/selection delegation objects, private geometry
  methods, broad geometry host protocols, obsolete imports, and temporary
  adapters are deleted;
- `PromptProjectionLayout` owns layout construction and incremental publication,
  not geometry algorithms. Its method and line budgets materially decrease, the
  six-module layout/hit-test/painter/reorder-paint/selection/source-line cycle is
  deleted, and executable architecture policy rejects its return;
- owner-level characterization covers every transferred query, including empty
  documents, blank and wrapped lines, Unicode graphemes, inline objects,
  collapsed emphasis, regional separator rows, soft-wrap affinity, edge
  clamping, drag selection, scrolling, clipping, source-line caching, token
  anchors, and reorder geometry inputs;
- production real-shell scenarios preserve pointer placement, horizontal and
  vertical caret movement, selection, search/source-line chrome, diagnostics,
  IME candidate geometry, token controls, regional separators, reorder, resize,
  scroll, raw/rich transitions, and undo/redo; the complete abuse matrix has
  full structural coverage with no invariant, freshness, or geometry failure;
- ordinary typing and deletion still perform one source transaction and no
  additional canonical work; caret-only navigation performs zero semantic,
  projection, or layout rebuilds; warm paint/cache lanes add no layout or
  geometry preparation; unchanged canvas/workflow round trips perform zero
  prompt work;
- a controlled repeated comparison against the exact pre-slice commit
  `765ee265` demonstrates no statistically meaningful common or tail latency
  regression. Any adverse p95, p99, maximum, allocation, copy, or structural
  count is investigated and corrected before completion;
- targeted format, lint, strict typing, owner tests, real-shell tests, and
  performance checks pass continuously, followed by the complete repository
  format, lint, license, strict mypy, parallel-test, serial-test, structural
  abuse, and performance gates for the exact final worktree before the slice is
  committed.

### Slice 6 evidence

Immutable snapshot models now have one foundational presentation owner under
`layout`.
The former flat snapshot module and the separate hit-testing, selection,
source-line, and visible-line geometry modules are deleted without compatibility
exports. `geometry` owns one immutable `PromptProjectionGeometryInput` and
focused caret-navigation, hit-test, selection, source-line, token, viewport,
and visible-line query objects. These are Qt-backed presentation queries rather
than lower-layer policy. `PromptProjectionGeometry` is only the frozen
aggregate of those owners: it has no forwarding query methods and cannot become
a delegation bookmark.

The dependency-direction correction removes `core/layout` and `core/geometry`
as source packages. The prompt-editor `core` tree now imports neither Qt nor
outer presentation modules, enforced by executable architecture policy.
Layout cannot depend on geometry, and neither layout nor geometry can depend on
mutable surface, painter, widget, shell, panel, overlay, feature, interaction,
or composition hosts. The former 520-line mixed `geometry.py` helper is also
deleted: its three used concerns now occupy focused widget-mapping,
flow-layout, and autocomplete-panel modules totaling 274 lines, while unused
document-range and emphasis geometry duplicates are removed. Focused strict
typing across the 34 affected source files and 26 architecture/geometry owner
tests pass.

`PromptProjectionLayout` publishes the geometry aggregate once whenever it
publishes an immutable layout snapshot. Every owner shares the exact projection
document, snapshot, font, metrics, inset, renderer registry, and snapshot
identity. Repeated reads retain those owners and their exact-keyed source-line
cache; publishing a new snapshot replaces the aggregate while previously
published geometry remains immutably bound to its original snapshot. Owner
contracts prove those identities, non-reconstruction, cache reuse, and
replacement rules.

All production, test, and abuse-harness callsites now address the focused owner
that answers their query. Layout no longer exposes geometry forwarding methods.
Its owned size falls from 5,586 lines and 115 methods to 4,001 lines and 52
methods. The six-module layout, hit-test, painter, reorder-paint, selection, and
source-line strongly connected component is deleted; executable architecture
policy permits only the independently tracked panel cycle. Production private
access exemptions fall from 11 to zero, and the broad Protocol count falls from
201 to 200 without increasing casts or test-private debt.

`PromptProjectionPainter` is stateless with respect to layout. It consumes
explicit immutable projection, snapshot, paint, geometry, font, palette,
renderer, and semantic inputs and retains no layout object. Reorder paint
snapshot construction uses the same concrete geometry owners. The abuse
harness's independent reference-frame renderer uses this public input surface,
so visual parity does not depend on a private production painter or layout
callback. Transient insertion and deletion overlays likewise consume only the
caret-navigation owner, selection owner, and immutable content bounds.

Focused owner, layout, caret, selection, incremental-editing, transient-overlay,
reorder, rendering, and feature suites pass, as do the complete real-shell
prompt-editor and autocomplete scenario suites. The final instrumented report
at `build/prompt-editor-slice6-final-structural.json` contains 204 production
shell runs: 68 scenarios across repetitions 0, 1, and 2. It records 68/68
operation coverage, no missing operations, zero invariant violations, zero
structural violations, zero text mismatches, zero diagnostics, and no stale
semantic or projection final states. Regional separator topology, adjacent
separators, hostile authoring, caret traversal, delete/join/split, raw/rich
transitions, selection, history, visual reference frames, reorder, workflow,
and unchanged canvas lifecycles remain clean.

Performance comparison uses the exact pre-slice commit `765ee265` in a detached
worktree and the candidate in fresh processes. Each process asserts module
provenance, disables owner observation, and runs on the same logical processor.
Six reversed-order pairs provide 30 samples for each of six lanes. Aggregate
elapsed time is 50.958 seconds for the candidate and 52.558 seconds for the
baseline; measured process CPU is 28.172 seconds and 28.938 seconds,
respectively. Candidate p95 median deltas are -1.603 ms for horizontal Alt
navigation, -3.124 ms for 5k selection changes, -4.910 ms for Danbooru paste,
-3.385 ms for 5k Delete, and -12.568 ms for 5k Enter. The paint-cache lane is
+0.009 ms by unpaired median and -0.013 ms by paired median. Windows per-sample
CPU values are quantized to 15.625 ms, while aggregate CPU is lower. No
repeatable latency, CPU, rebuild, fallback, cache, canvas, or workflow
regression remains.

The final focused architecture, diagnostics, and reorder suites pass after
test-only cache observations were moved from the deleted layout forwarding
method to the authoritative selection-geometry owner. Complete repository
commit gates remain intentionally deferred until the maintainer explicitly
authorizes them with `commit your work`; Slice 6 remains uncommitted.

### Slice 7 acceptance ledger

Slice 7 is complete only when:

- `layout/contracts.py` owns one immutable engine request and one immutable
  published output shared by canonical and incremental layout;
- every request contains exact previous projection, prompt document, snapshot,
  metrics/configuration, renderer registry, and optional source edit references
  without copying the source or materializing lazy snapshot sequences;
- `layout/canonical_engine.py` is the sole owner of full layout and bounded
  canonical recovery, including deterministic suffix convergence and validated
  suffix reuse;
- `layout/same_line_engine.py`, `layout/hard_line_engine.py`, and
  `layout/trailing_engine.py` each own their cohesive fast-edit mechanism and
  return a typed `APPLIED`, `DEFERRED`, or `REJECTED` outcome with a reason and
  bounded line/content damage;
- the incremental strategy owners never invoke canonical fallback. Their caller may
  select canonical recovery only after consuming the typed outcome;
- lazy shifted source positions, fragments, caret stops, lines, flattened
  fragment sequences, and caret mappings retain their current allocation and
  materialization behavior under a focused shifted-snapshot owner;
- local text shaping, tag-keep validation, region structural rows, reusable
  line sequences, semantic suffix validation, and checkpoint restoration each
  have one focused owner and remain exact;
- immutable projection tokens, runs, mappings, caret values, and documents live
  below layout in focused Qt-free `core/projection` modules; layout may consume
  those values, but projection values cannot import layout, geometry, paint,
  surfaces, widgets, shells, panels, or Qt;
- a small published-layout state owner contains only current immutable
  projection/layout/configuration references and atomic publication. It owns no
  line-building, incremental-edit, paint, reorder, or feature algorithm and is
  not a forwarding facade;
- painting consumes explicit immutable paint inputs, reorder consumes explicit
  geometry inputs, token measurement has its focused renderer-backed owner, and
  history/display-mode caches consume checkpoint values directly;
- all callsites use the new owners directly and the former
  `projection/layout_engine.py`, `projection/model.py`,
  `incremental_text_layout.py`, `line_layout.py`, `region_line_layout.py`,
  layout checkpoint, and layout reuse modules are deleted without compatibility
  exports;
- owner characterization proves canonical equality, local reflow convergence,
  every incremental acceptance/rejection reason, deferred wrap behavior,
  bounded damage, lazy reuse, checkpoints, Unicode/IME geometry, region rows,
  exact weights, reorder preview layout, resize/reflow, and history;
- focused real-shell and seeded abuse lanes preserve separators, editing,
  navigation, selection, IME, raw/rich transitions, diagnostics, paint/cache,
  reorder, workflow, and unchanged canvas behavior;
- structural counters show no additional canonical layout, source scan,
  snapshot materialization, fallback, signal, callback, or prompt work on hot
  or unchanged canvas/workflow paths;
- repeated controlled comparison against the exact pre-slice tree shows equal
  or better latency, CPU, memory, allocation, rebuild, rejection/fallback, and
  cache behavior;
- only focused owner/blast-area format, lint, typing, Qt, real-shell, abuse, and
  performance checks run autonomously. Complete repository gates and commits
  remain forbidden until the maintainer says `commit your work`.

### Slice 7 ownership inventory

At the start of Slice 7, `projection/layout_engine.py` was the primary layout
god object. It combined lazy shifted snapshot views, flattened fragment/caret
collections, canonical
reflow with suffix convergence, same-line and hard-line incremental layout,
four trailing fast paths, rejection strings, checkpoint capture/restoration,
mutable projection/configuration state, geometry publication, painting, reorder
geometry and paint snapshots, source-row queries, and token measurement.

The nominal canonical builder in `projection/line_layout.py` is another broad
module containing line assembly, wrapping, shaping, token-group handling,
tag-keep policy, region row integration, and boundary helpers.
`incremental_text_layout.py`, `reused_line_sequence.py`,
`reused_line_semantics.py`, `layout_checkpoint.py`, and
`region_line_layout.py` hold useful focused mechanisms, but their authoritative
lifecycle remains inside the god object.

Incremental ownership is also split across layers. `incremental_editor.py`
builds projection-document edits, calls separate layout mutation methods,
reads a mutable rejection string, and translates selected rejection strings
into deferred wrap status. `incremental_apply_controller.py` owns four separate
trailing strategies and invokes bounded canonical recovery after rejection.
Slice 8 will consolidate edit classification and strategy orchestration; Slice
7 first gives that pipeline one typed engine contract and removes layout
mutation and rejection side channels.

The final Slice 7 shape uses:

- `PromptLayoutState` for immutable current references and atomic publication;
- `PromptLayoutEditToFrameCoordinator` for the single outward transition from
  canonical or incremental layout work to the prepared frame, without
  presentation-value forwarding;
- `PromptCanonicalLayoutEngine` for full and bounded recovery builds;
- `PromptSameLineLayoutEngine`, `PromptHardLineLayoutEngine`, and
  `PromptTrailingLayoutEngine` for non-fallback local attempts;
- `PromptLayoutRequest`, `PromptLayoutOutput`, `PromptLayoutOutcome`, typed
  status/reason values, and `PromptLayoutDamage` at the engine boundary;
- focused shifted-snapshot, line reuse, text shaping, checkpoint, paint-input,
  token-measurement, and reorder-input owners.

`core/layout` is not a valid destination: layout is a Qt-backed presentation
service and must not masquerade as lower-layer policy. The focused layout
package may depend on Qt, application document views, renderer ports, and
Qt-free `core/projection` values. `core/projection` may depend on application
and domain values only. Geometry and layout may depend on projection values;
projection values may not depend on either. Surface, paint, reorder, shell, and
panel code depend inward on those owners and never the reverse.

The existing `PromptProjectionLayout` API is internal and is not preserved as a
compatibility surface. Callsites transfer to these owners in the same slice,
and the old class and module are deleted.

### Slice 7 progress

Immutable projection values now live in focused Qt-free `core/projection`
modules, and the former 1,341-line `projection/model.py` compatibility barrel is
deleted. Qt-backed layout and geometry live in their correct presentation
packages. The former mixed 520-line geometry module is deleted in favor of
focused aggregate, caret, hit-test, selection, source-line, token, viewport,
flow-layout, widget-mapping, and autocomplete geometry owners. Executable
architecture tests forbid core-to-Qt/presentation edges, layout-to-geometry
edges, and layout/geometry dependencies on mutable outer hosts.

`PromptCanonicalLayoutEngine` now owns canonical build and bounded recovery.
The focused same-line, hard-line, and trailing engines return typed non-fallback
outcomes for their respective edit paths. The old mutable rejection
side channel is deleted. Incremental publication returns an immutable
`PromptIncrementalFrameApplyResult` containing bounded damage or an explicit
rejection reason, and the caller consumes that value directly.

`PromptLayoutState` now atomically owns the current immutable
`PromptLayoutOutput`. It contains only reference publication and restoration;
an architecture test fixes that exact responsibility so engines, paint,
reorder, and features cannot accumulate there. The transitional layout host no
longer owns duplicate mutable projection, prompt-document, snapshot, font,
metrics, width, inset, or margin state. Canonical and incremental outcomes are
published atomically through the state owner, geometry is rebound from the
published output, and the revisioned frame publisher consumes explicit layout
output and paint state rather than the mixed layout host. Real-shell
diagnostics now read the published configuration instead of private mutable
layout fields.

Caret movement, source-line chrome, LoRA viewport features, and diagnostic
painting now consume explicit `PromptProjectionGeometry` inputs supplied by
their surface adapter. They no longer import or retain the mixed layout host,
and no geometry-provider callback was added to navigation or paint hot paths.
The surface passes the already-published geometry reference at the existing
operation boundary.

Pointer selection now receives the prepared-frame publication owner explicitly
at its Qt event boundary instead of reaching through a layout-host Protocol.
It resolves geometry only after any required freshness flush, so the explicit
boundary cannot retain a stale pre-flush geometry aggregate.
Token-under-pointer resolution moved from the broad surface into
`PromptTokenGeometry`; mouse, LoRA, and the preserved public surface query now
derive from that owner. The final layout-host geometry forwarding property is
deleted, and an architecture test prevents every removed value façade,
including geometry, from returning.

`PromptProjectionPaintInput` now owns the complete prepared projection,
snapshot, paint-state, geometry, renderer, font, palette, and semantic-palette
references used for drawing. `PromptProjectionPainter.draw()` consumes that
single explicit input. Reorder drag-proxy payloads and chip text painting retain
the prepared paint input rather than the mutable layout host, and effective
run/token paint-state resolution moved out of the host to this focused paint
owner. The transitional host lost two paint-policy methods while publishing
the prepared input, and its executable growth ceiling was tightened from the
Slice 6 baseline to 546 owned lines and 32 methods.

The paint cache now renders explicit prepared paint inputs and has no layout
host dependency. Direct, cached, preview, chip, and drag-proxy paint paths use
the same prepared input without per-paint discovery. Token measurement moved
to a focused renderer-backed layout owner. Reorder paint extraction, chip
geometry, placement geometry, scroll reuse, and fill-band row queries now call
their focused owners with explicit prepared inputs; the corresponding paint,
measurement, and reorder forwarding methods and retained helper objects were
removed from the transitional host.

Checkpoint keying, capture validation, and restoration validation now live in
the focused checkpoint owner and operate on immutable layout output and
configuration values. Undo capture, display-mode caching, and history
restoration now call that owner directly with already-published output and
paint identity. The transitional host only publishes an accepted restored
output and refreshes its derived geometry/paint input; its former checkpoint
capture and restore forwarding methods have been deleted.

The immutable projection undo payload moved out of the surface into its own
Qt-free value module, and every composition/test callsite now imports that
owner directly. This keeps checkpoint capture at the surface's existing
history-provider boundary without making the surface the payload contract
owner, and ratchets the surface ceiling down to 4,634 owned lines.

`PromptProjectionPreparedFrame` now owns the one-way publication boundary from
an applied immutable layout output to its exact geometry and paint inputs. It
contains no canonical, incremental, fallback, or edit-selection algorithm;
an executable import guard locks that direction. The transitional layout host
no longer retains layout state, geometry, paint state, palette, semantic
palette, or prepared paint input independently, and publication is atomic
through the prepared-frame owner. Paint-state reference validation and
publication also moved to that owner; paint-only applicator paths now consume
the prepared frame directly, and the former layout-host paint validation and
mutation methods are deleted.

Reorder geometry and scroll reuse now consume the published geometry aggregate
directly. They no longer import the prepared paint input or transitional layout
host, and an executable dependency guard prevents either upward edge.

Lazy inline-fragment index warming now calls the immutable snapshot owner
directly. The previous host method performed a redundant run traversal after
the index scan; the snapshot now builds the same lazy index once with no run
loop, and the dead single-fragment-size host helper was deleted.

Regional separator chrome now consumes `PromptLayoutOutput` directly and keys
its bounded cache by immutable snapshot identity. Its broad layout-host
Protocol and host import path are deleted, production paint/synchronization
callers pass published output, and real-shell plus abuse diagnostics read the
same owner. Centering, continuous rails, raw-mode absence, ordinary-prompt
zero-scan behavior, and bounded long-prompt lookup tests pass.

The abuse diagnostic driver no longer replaces a deleted layout-host helper.
Canonical suffix recovery now exposes a focused optional mismatch observer
that executes only after a candidate already fails; the disabled/successful
convergence path performs no diagnostic callback or mismatch analysis. The
driver uses that owner hook, preserving mismatch evidence without a
compatibility export or module-function monkey patch.

A focused `PromptLayoutConfigurationFactory` now owns normalized wrapping
width, content inset, immutable layout configuration, and matching renderer
metrics. The transitional host and reorder preview builder consume that owner
instead of independently constructing or mutating configuration inputs.

Reorder preview layout construction no longer creates, forks, or imports the
transitional layout host. Its focused builder invokes the canonical engine
directly for full builds and bounded target reflow, then publishes
`PromptProjectionPreparedFrame` values. The preview service owns those frames,
their exact/LRU reuse, and geometry-input staleness; width and font checks are
allocation-free queries, and palette/theme acquisition plus layout
construction occur only after a geometry mismatch. Generic frame
synchronization remains paint-only for preview frames. An executable import
guard prevents the preview builder or service from regaining a layout-host
dependency.

A focused resize test exposed the remaining old assumption that generic frame
sync could mutate cached preview layout width. The preview service now rebuilds
its own frames before publication when width or font changes, while unchanged
target and autoscroll paths retain zero preview rebuilds. The active cache,
incremental target reflow, LRU revisit, base-drag reuse, resize invalidation,
paint extraction, and geometry callers all consume prepared frames directly;
the old preview-layout properties and cache entries are deleted.

The seeded abuse diagnostics now inspect prepared preview frames directly.
Stale private `preview_layout` reads had allowed preview fragment-ownership and
regional checks to be skipped after the transfer; owner-state, wildcard,
reorder-render, and scene-title probes now validate immutable output plus
prepared paint input. The focused pointer-reorder diagnostic is correct and
structurally clean with one bounded two-line canonical reflow and zero
projection rebuilds.

A focused reorder-proxy scenario exposed a renderer-registry identity mismatch
in forked immutable layout output. Fork publication now rebinds the exact
configuration to the fork's renderer registry before bounded reflow; direct
owner coverage asserts the identity, and the projection/LoRA drag-proxy
scenarios pass.

Focused evidence for the current state-publication transfer:

- strict mypy passed the seven affected source modules;
- targeted Ruff passed layout contracts/state, the transitional host, frame
  publication, owner tests, architecture guardrails, and real-shell diagnostics;
- 127 focused state, canonical/incremental layout, revision-lineage, and
  architecture tests pass;
- an additional focused diagnostics/incremental set passed before the final
  state-owner guard was added;
- six selected real-shell horizontal/vertical separator navigation scenarios
  pass through the geometry-input caret boundary;
- focused source-line, LoRA, diagnostic-cache, projection paint, immutable-fork,
  and reorder drag-proxy scenarios pass;
- all 19 focused reorder-surface contracts and 12 reorder-service contracts
  pass after direct prepared-frame migration;
- unchanged-target, autoscroll, cache-hit, and target-change performance
  contracts pass without extra preview rebuilds;
- the final focused pointer-reorder abuse diagnostic reports
  `correct=True` and `structural=True`; its timing lane is instrumented and
  therefore intentionally not treated as controlled comparison evidence;
- the transitional layout host is now 449 owned lines and 20 methods, down
  from the prior 546/32 ceiling; the surface remains at 4,632 owned lines and
  is now 271 methods, down from 4,634/276 despite completing the preview and
  pointer-geometry migrations;
- the LoRA thumbnail-ready Qt signal now has one narrow surface adapter that
  supplies the current published geometry to the focused feature owner, and
  its isolated ordering test now creates its own `QApplication` rather than
  depending on test order;
- no complete repository gate, commit, or unrelated suite was run.

Focused pointer verification exposed reproducible blank-line click,
reverse-newline drag, pre-release selection-paint, and manual
expansion/scrollbar failures. Their common owner defect was a missed dynamic
widget callsite for the deleted layout `metrics` façade: it silently fell back
to a one-pixel line height, collapsed the shell, and shifted pointer geometry
through forced scrolling. The callsite now reads the authoritative published
layout configuration, three focused sizing contracts and all six selected
pointer contracts pass, and the fallback path is gone.

The first post-transfer separator abuse run correctly failed because final
real-shell invariants still queried deleted layout façades and therefore
reported empty layout ownership despite valid per-action owner state. Harness
capture now derives projection, snapshot, metrics, content size, selection
geometry, visible rows, and visible fragments from explicit
`PromptLayoutOutput` and prepared geometry inputs. Its deliberate stale-preview
invariant still detects the forced fault, while separator mouse placement,
vertical navigation, and multi-line topology abuse runs now report
`correct=True` and `structural=True`.

The former `PromptProjectionLayout` host and
`projection/layout_engine.py` are now deleted. Their remaining coherent
responsibility is owned by `projection/edit_to_frame.py`:
`PromptLayoutEditToFrameCoordinator` selects canonical or incremental engines,
owns one prepared frame, and performs configuration-to-frame transitions. It
does not forward output, geometry, paint, palette, restore, or fork values;
callers consume `PromptProjectionPreparedFrame` and its immutable output
directly. Palette and restore operations moved to the frame owner, preview
forking remains with its dedicated builder/service, and executable guards
prevent the deleted module or value facades from returning. The new owner is
449 owned lines and 19 methods, replacing the original 5,682-line host.

The final host-deletion integration pass found and removed two stale parallel
representations. Source-change tests now use the real edit-to-frame coordinator
instead of a private fake shaped like the deleted host. Widget sizing now asks
the surface adapter for the prepared layout's text-line height rather than
reaching through private layout state; production private-access exemptions
remain zero. The same pass corrected real-shell, abuse owner-state, and optional
debug probes to derive layout output and geometry from the coordinator's
prepared frame rather than silently querying deleted facade names.

Focused post-deletion evidence:

- targeted Ruff and strict mypy pass for the coordinator, all migrated
  production consumers, owner tests, real-shell diagnostics, abuse owner state,
  and the optional debug probe;
- all 24 architecture guardrails pass, including dependency direction, deleted
  host, no-facade, integration-root budget, and zero production private-access
  debt;
- 95 canonical/incremental layout and paint-cache owner contracts pass;
- 108 focused incremental editing, source application, layout-surface,
  lifecycle, display-mode, and reorder integration contracts were exercised;
  106 passed initially, and the two obsolete-fake failures pass after removal
  of that fake;
- focused sizing contracts pass through the new public surface query;
- separator mouse placement, vertical navigation, and multi-line topology
  abuse reports at
  `artifacts/prompt_editor_abuse/slice7-edit-to-frame-*.json` are each
  `correct=True` and `structural=True`; pointer/navigation perform zero
  projection rebuilds, while the topology case retains one incremental apply
  and one required full rebuild;
- no complete repository gate, commit, or unrelated suite was run.

The mixed 1,740-line `layout/edit_algorithms.py` is also deleted rather than
retained as a renamed utility bucket. Its responsibilities now flow inward
through focused owners:

- `tag_keep_policy.py` owns the shared short comma-tag grouping rules consumed
  by canonical construction and incremental classification;
- `edit_policy.py` owns edit-to-line classification and the decision to defer
  to canonical tag/wrap policy;
- `line_break_edits.py` owns hard-line split/join construction;
- `snapshot_edits.py` owns same-line snapshot mutation and coordinate remapping;
- `canonical_edit_window.py` owns rebuilt-window composition and deterministic
  suffix convergence.

This corrects the previous dependency direction in which incremental policy
reached upward into the 2,149-line canonical builder for shared tag rules. Both
paths now depend inward on `tag_keep_policy.py`; the canonical builder falls to
1,921 lines, and the replacement modules are respectively 255/10, 475/14,
409/9, 689/19, and 289/5 lines/top-level functions. Executable graph guards
forbid the focused lower owners from depending on canonical construction or on
sibling mutation paths, freeze their growth ceilings, and prevent
`edit_algorithms.py` from returning. Targeted Ruff and strict mypy pass, 33
architecture/policy contracts pass, and 100 canonical, incremental, surface,
fragment-ownership, and reuse contracts pass after the transfer.

The former 1,013-line `layout/incremental_engine.py` is now deleted rather than
retained as a delegation list. `PromptSameLineLayoutEngine` owns one 304-line
same-line attempt, `PromptHardLineLayoutEngine` owns the 299-line split/join
strategy, and `PromptTrailingLayoutEngine` owns the 505-line four-path trailing
strategy. The edit-to-frame coordinator composes those concrete owners at its
existing use-case boundary; there is no aggregate incremental-engine shim and
the three strategies cannot depend on one another. The valid empty projection
factory moved to the immutable projection document owner, offsetting the
explicit strategy composition so the coordinator remains below its existing
449-owned-line ceiling instead of raising the guard. Targeted Ruff and strict
mypy pass, all 25 architecture guards pass, and 166 focused layout,
incremental-editor, source-application, and integration contracts pass.

Final Slice 7 abuse exercises separator topology, seeded hostile churn, and
canvas/workflow lifecycle behavior through the production shell. Each report is
`correct=True` and `structural=True`; topology retains the expected one
incremental apply plus one structural rebuild, hostile churn retains bounded
typed rejection/recovery, and unchanged canvas/workflow round trips perform
zero projection rebuilds. Reports are stored as
`artifacts/prompt_editor_abuse/slice7-strategy-*.json`.

Controlled performance evidence uses the exact pre-slice `765ee265` detached
worktree and the candidate in fresh processes, with module-provenance
assertions, owner observation disabled, high process priority, and affinity
fixed to logical processor 31. Two reversed-order pairs cover large-prompt
typing, Delete, Enter, coalesced typing, paint-cache, and fill-band-cache lanes.
Candidate aggregate wall time is 27.58 seconds versus 29.39 seconds and process
CPU is 26.66 seconds versus 28.45 seconds. Individual tail samples vary with
Windows scheduling in both directions, while paired and aggregate results show
no stable latency, CPU, rebuild, fallback, cache, canvas, or workflow
regression. The four raw reports are under
`build/prompt-editor-slice7-performance`.

Slice 7 is complete and remains uncommitted. No complete repository format,
lint, strict-mypy, parallel-test, serial-test, or other full gate was run.

### Slice 8 acceptance ledger

Slice 8 is complete only when:

- one immutable, Qt-free edit-classification request contains the already-known
  edit shape, topology/freshness state, checkpoint eligibility, syntax and token
  sensitivity, deferred-chain eligibility, and available strategy capabilities
  required to select a path without reaching into a widget, surface, session,
  service locator, or mutable host;
- one pure `PromptEditClassifier` returns one typed decision for checkpoint
  restore, paint-only reuse, deferred-wrap extension, trailing plain/newline
  insert/delete, same-line incremental edit, bounded canonical recovery,
  transient deferred fallback, or full rebuild, including the reason and
  permitted fallback sequence;
- one `PromptEditPipeline` owns execution of that decision, explicit fallback
  transitions, typed outcome publication, damage/cache consequences, and
  latest-wins scheduling requests through narrow concrete collaborators or
  stable ports;
- strategy owners build projection/layout results but do not select the next
  strategy; the source-change applier applies the core commit but does not
  classify projection work; the freshness controller owns freshness state and
  queued publication but not edit-path selection;
- output-load awareness, reorder/preview blockers, display-mode policy,
  syntax-sensitive autocomplete, token intersections, region topology,
  diagnostic-cache preservation, transient feedback, checkpoint restoration,
  and canonical fallback retain their exact behavior through explicit typed
  inputs and outcomes;
- the current broad `incremental_apply_controller.py` host Protocol, duplicated
  source-change/freshness classification helpers, stringly fallback rules, and
  surface callback service-locator boundary are deleted; all callsites use the
  classifier and pipeline directly without a compatibility controller or
  delegation bookmark;
- path-equivalence characterization covers every existing classification
  branch and rejection reason before transfer, including range/document/history
  commits, raw/rich mode, separators, IME, exact weight, autocomplete prefixes,
  projected tokens, trailing and middle edits, wrap deferral chains, checkpoint
  restore, reorder, async scheduled updates, and full-rebuild recovery;
- focused real-shell and seeded abuse scenarios preserve text, caret,
  selection, history, transient overlays, diagnostics, projection/layout
  lineage, rendering, workflow, and unchanged canvas behavior;
- classification adds no source copy, full-source scan, hash, layout build,
  signal, callback, allocation-heavy request construction, or instrumentation
  to ordinary edit hot paths. Existing bounded checks are computed once by
  their owner and supplied to the classifier;
- structural budgets retain one source transaction, one selected projection
  path, bounded fallback, zero canonical work for accepted fast edits, zero
  prompt work on unchanged canvas/workflow paths, and no additional paint,
  cache, or async work;
- repeated controlled comparison against the exact pre-slice tree shows equal
  or better common/tail latency, CPU, memory, allocation, rebuild, fallback,
  scheduling, and cache behavior;
- only focused owner/blast-area format, lint, typing, Qt, real-shell, abuse, and
  performance checks run autonomously. Complete repository gates and commits
  remain forbidden until the maintainer says `commit your work`.

### Slice 8 ownership inventory

`projection/incremental_apply_controller.py` is currently 1,505 lines. Its
single controller selects every projection path, executes those paths, restores
checkpoints, builds fast trailing documents, attempts same-line incremental
projection, invokes bounded canonical recovery, mutates freshness scheduling,
constructs transient insertion/deletion feedback, coordinates diagnostic-cache
policy, updates paint/layout state, logs outcomes, and reaches through a
122-line `PromptProjectionIncrementalApplyHost` Protocol containing layout,
state, session, viewport, signals, cache, feature, and surface callbacks. It is
both classifier and executor over a service locator.

`projection/incremental_editor.py` is 1,261 lines. Its class combines four
trailing projection-document constructors, same-line layout publication, and
plain-edit construction, while module functions combine edit eligibility,
grapheme/token/syntax intersection, run/token remapping, render-plan range
comparison, and source-coordinate remapping. These are separable mechanism
owners; none should decide the outer fallback path.

`projection/source_change_applier.py` is 1,422 lines. It correctly receives the
sole core `PromptEditCommit`, but it also decides immediate versus deferred
projection, duplicates transient-feedback eligibility and token/syntax checks,
coordinates mirrors/signals/caret/cache state through another broad host
Protocol, and invokes the incremental controller for another round of path
selection.

`projection/freshness_controller.py` owns revision freshness, pending work,
coalescing, and output-load-aware scheduling. It must retain those state
transitions and latest-wins semantics while exposing typed facts and scheduling
commands to the classifier/pipeline; classification policy must not move into
or remain duplicated inside the freshness owner.

Slice 8 proceeds in this order:

1. characterize every current path decision and structural count through the
   existing controller boundary;
2. extract pure edit facts and classification decisions without changing
   execution;
3. transfer one complete strategy execution at a time into the pipeline,
   update all callsites, and delete the old branch in the same step;
4. split projection-document edit/remap mechanisms by responsibility as their
   pipeline strategies transfer;
5. replace broad host Protocol access with concrete construction-owned
   collaborators and narrow sinks, then delete the controller and duplicate
   source-applier classification;
6. prove path equivalence, hostile behavior, structural budgets, and controlled
   performance before marking the slice complete.

### Slice 8 progress

The pure classification vocabulary and existing strategy order are now
characterized in `projection/edit_classifier.py`: bounded edit shape, immutable
facts, typed strategy candidates, and terminal fallback order contain no Qt,
application, domain, layout, surface, session, or service dependencies. Thirteen
owner cases cover topology-forced rebuild, checkpoint priority,
deferred-chain extension, delete/newline/plain fast candidates,
syntax-sensitive immediate projection, wrap deferral, and transient/prebuilt/
canonical/full-rebuild recovery order. An architecture guard freezes its pure
dependency boundary and 152-line ceiling.

This is not yet an authority transfer: the classifier is deliberately not
called from the hot path until the current controller branches can be replaced
in the same step without adding parallel decisions or per-edit plan work.

Bounded source-edit facts now have one direct owner. The Qt-free
`PromptEditFactResolver` derives focused-token, comma, autocomplete-prefix, and
token-intersection facts from immutable projection state, while
`PromptSourceEditProjectionPolicy` owns the corresponding pure rules and keeps
its syntax-character set module-cached. Both the source-change applier and the
incremental apply path call that owner directly; the five duplicate surface
policy methods and their host-Protocol query methods are deleted. The surface
integration root drops from 271 to 265 methods and is frozen at 4,520 owned
lines. Focused architecture policy prevents these rules from returning to the
surface or acquiring Qt, session, freshness, application, or domain
dependencies. All 37 fact-policy, source-application, and incremental-edit
contracts pass with targeted Ruff and strict mypy.

The next step is to make the classifier consume the already-allocated
source-change request without constructing a parallel per-edit fact object,
then transfer complete strategy execution into the pipeline and delete each
corresponding controller branch.

The source-change request now is that classification input. The source applier
computes topology, syntax, autocomplete-prefix, deferred-chain, and wrap facts
once and adds them to the request it already allocates; the classifier returns
module-lifetime immutable plans from a prebuilt index, so classification adds
no source copy, scan, hash, plan allocation, or mutable-state query. Immutable
strategy contracts live separately from the 127-line pure classifier rather
than turning that policy module into a mixed vocabulary owner.

`PromptEditPipeline` now directly receives every immediate source change and
owns ordered fallback execution, typed terminal outcomes, deferred-cache
consequences, and timing publication. The old 294-line selection/execution
branch and its duplicate deferred-chain classifier are deleted from
`incremental_apply_controller.py`; the controller falls from 1,505 inventory
lines to 1,141 current lines and no longer exposes
`apply_source_change_projection`. Six direct pipeline owner cases lock topology
short-circuiting, plain/delete priority, deferred wrap, prebuilt/canonical
fallback, and deferred-chain extension. Seventy-seven focused editor
characterization contracts, eleven production real-shell path probes, and
hostile separator, history, LoRA syntax, and canvas/workflow abuse lanes are
behaviorally and structurally clean. Unchanged canvas round trips perform no
prompt document or projection build.

The first controlled timing pair was noisy and adverse, so it was not accepted.
Four quieter reversed-order pairs plus a direct profile found no structural
work increase and no measurable pipeline self time. Removing an unnecessary
per-strategy edit-bounds tuple allocation improved the quiet comparison:
candidate p50 is 0.52 ms faster for 5k Delete, effectively equal for large
typing, and within 0.11 ms for syntax rebuild; remaining p95 differences are
0.36 ms for Delete, 0.50 ms for coalesced typing, and 0.84 ms for Enter.
Those sub-millisecond tails remain open performance evidence until subsequent
strategy extraction removes the transitional executor boundary; Slice 8 is not
performance-complete.

The next authority transfer is to split trailing, incremental/canonical,
deferred-feedback, and semantic/checkpoint execution into focused strategy
owners that return typed results to the pipeline. The pipeline must then own
publication and damage/cache consequences directly, and the remaining
1,141-line mixed controller and its broad host Protocol must be deleted.

The trailing transfer is now complete. `PromptTrailingDocumentEditor` owns the
four bounded projection-document transitions, `PromptTrailingEditStrategy`
owns their eligibility and edit-to-frame attempts, and `PromptEditPublication`
owns the resulting revision, caret, diagnostic-cache, prepared-paint, and
viewport effects. `PromptEditPipeline` selects those owners directly through
narrow typed ports. Scheduled prompt-state catch-up uses the same trailing
strategy instead of retaining a second controller path. The four trailing
branches and prompt-state eligibility policy are deleted from
`incremental_apply_controller.py`; the four document constructors are deleted
from `incremental_editor.py`. Their current sizes are 898 and 820 lines,
respectively, down from the 1,505- and 1,261-line Slice 8 inventories. Source
edit differencing and render-plan range equivalence also have independent
Qt-free owners instead of remaining unrelated module functions in the
incremental editor.

The transferred hot path creates no wrapper result or per-edit strategy plan:
successful strategies return the projection document already required by the
edit, and the pipeline supplies the preceding layout identity only for the
plain-deletion cache-preservation transition that already required it.
Thirteen direct pipeline/owner/architecture cases, seven focused trailing
layout/mechanism cases, and five production surface cases cover all four
trailing operations, scheduled semantic catch-up, canonical fallback, cache
publication, and the original retry behavior. Focused Ruff and strict mypy are
clean.

Controlled timing remains open rather than being treated as complete. Against
the frozen pre-slice worktree, the latest quiet two-pair comparison has 5k
typing p50 0.26 ms faster, p95 0.34 ms faster, and 15.62 ms less process CPU;
middle edit and syntax rebuild are also faster. Single-operation Enter and
Delete samples remain 1.48 ms and 0.90 ms adverse at p95, and the tiny
coalesced-typing scenario is 0.44 ms adverse. These do not show additional
structural work, but they remain unresolved tail evidence until the
incremental/canonical and deferred strategy transfers remove the transitional
executor boundary.

The incremental/canonical transfer is now complete.
`PromptIncrementalReflowStrategy` owns topology rejection, incremental
document/layout attempts, retained prebuilt recovery, and bounded canonical
reflow. It returns the existing typed plain-edit result; the source-edit
pipeline owns candidate order and sends accepted results to
`PromptEditPublication`, which now owns layout-lineage publication,
diagnostic-cache preservation or invalidation, prepared-paint refresh, and
damage-bounded repaint. `PromptStateProjectionStrategy` separately owns
prepared semantic-snapshot catch-up, so prompt-state policy does not broaden
the source-edit pipeline. Both use the same trailing, reflow, and publication
owners.

The incremental, scheduled-incremental, prebuilt, and canonical branches and
their publication effects are deleted from
`incremental_apply_controller.py`, which is now 636 lines. The source-edit
pipeline is 348 lines; its ports, immutable request/outcome contracts, pure
classifier, and prompt-state strategy remain separate focused modules.
Thirty-six production surface contracts and thirty-six source-applier/editor
owner contracts pass, along with direct pipeline, trailing, architecture,
Ruff, and strict-mypy checks. Hostile separator churn, long history, LoRA
syntax formation, and canvas/workflow lifecycle campaigns are all
`correct=True` and `structural=True`; the unchanged canvas round trip still
performs no prompt document or projection build.

The latest quiet controlled comparison improves the earlier tails after
removing controller re-entry: 5k typing p95 is now within 0.21 ms of baseline,
while Enter, Delete, and coalesced typing remain 1.03 ms, 0.88 ms, and 0.42 ms
adverse. Process CPU is equal or better for the large typing, deletion,
middle-edit, and syntax scenarios; coarse single-operation accounting remains
one 7.8125 ms quantum adverse for Enter and coalesced typing. Performance
evidence therefore remains open through the deferred-feedback transfer, which
is next. No complete repository gate or commit is authorized.

The source-edit pipeline also no longer performs the dead prepared-state
candidate call that every edit previously made before useful strategy work.
The transitional executor implementation was permanently `False`, so it
provided no behavior, geometry reuse, or fallback capability. The classifier,
pipeline port, executor branch, and controller method are deleted together;
ordinary classification now begins with the first strategy that can actually
apply. This removes one virtual call and conditional from every source edit
without changing the allocated request, adding a scan, or broadening another
owner. Twenty-one focused classifier/pipeline cases and the frozen architecture
boundary pass with targeted Ruff and strict mypy.

History checkpoint restoration now has a complete focused owner.
`PromptHistoryCheckpointStrategy` validates projected-mode blockers, source
identity, and exact checkpoint geometry before restoring the immutable prepared
frame; `PromptEditPublication` owns projection revision, cache, prepared-paint,
transient-geometry, and viewport consequences. The pipeline selects both
directly, and the checkpoint branch plus its layout/cache/widget effects are
deleted from `incremental_apply_controller.py`, now 582 lines.

The existing request did not grow: its redundant checkpoint-availability
boolean became a derived property, and that slot now carries the immutable
blocker snapshot only for an actual history restore. Ordinary edits allocate no
blocker snapshot or checkpoint request and perform no new query. Seven
strategy-owner cases cover successful structural sharing, every transient mode,
source mismatch, and width mismatch; seven pipeline cases, focused source-state
restore cases, and the production paste/undo/redo real-shell path pass. The
focused long-history abuse diagnostic is `correct=True` and `structural=True`
with 64 checkpoint restores, 32 bounded reflows, and zero projection rebuilds
in `build/prompt-editor-slice8-history-checkpoint-owner.json`.

That real-shell probe also exposed stale diagnostic instrumentation still
reading the incremental editor through the deleted controller branch. The
instrumentation exception escaped during native key-event dispatch and made Qt
report a deleted `QKeyEvent`; the frozen baseline passed, confirming a
refactor-only harness regression. Incremental rejection evidence now travels
in the existing typed strategy and pipeline outcomes, and both the real-shell
and abuse diagnostics consume that evidence instead of private controller
state. This adds no callback or instrumentation to the production hot path and
makes disabled diagnostics cost-free.

Same-source semantic projection changes now follow the same direction.
`PromptSemanticTransitionStrategy` owns blocker validation, semantic range
derivation, projection construction, and bounded edit-to-frame application;
`PromptEditPublication` owns revision, caret remap, session sync, cache,
prepared-paint, transient geometry, and damage-bounded repaint. The prepared
prompt-state strategy consumes those focused owners directly. The transition
branch, effects, and migration Protocol are deleted from the mixed controller,
now 502 lines.

The incremental and semantic builders share one narrow
`PromptProjectionBuildContext` port rather than duplicating mutable feature
queries or depending on each other. Composition owns access to the applicator,
editor state, and edit-to-frame coordinator through a separate construction
port; the shrinking deferred controller no longer claims those semantic-build
dependencies. Three direct strategy cases cover bounded publication,
transient-mode rejection, and range-stable canonical fallback. All 36 focused
production incremental/prompt-state contracts and the lifecycle,
pipeline, and owner cases pass. The focused LoRA syntax abuse diagnostic is
`correct=True` and `structural=True` in
`build/prompt-editor-slice8-semantic-transition-owner.json`; its one completed
syntax topology change performs a one-line reflow and the expected canonical
projection rebuild.

A production reorder-preview crash interrupted the slice and is fixed at the
canonical edit-window owner. Removing the first chip after a structural
separator selected that caretless separator line as the recovery start. The
canonical engine then paired source boundary `6` with projection boundary `0`,
and the line builder failed while looking up the separator's actual projection
boundary. `canonical_edit_window.py` now owns the bounded rule that backs
recovery over caretless structural rows to their preceding caret-hosting text
line; the ordinary path performs one caret-stop check, adjacent separator rows
walk only their local structural prefix, and the builder receives consistent
source/projection coordinates without a catch, fallback rebuild, or document
scan.

Focused evidence covers leading, single, and adjacent separators with
incremental-to-full geometry equivalence; the production reorder projection
service reproduces the original preview/base-drag sequence; and all 136
architecture, canonical layout, and reorder service contracts pass. A hostile
real-shell pointer drag over two adjacent separators is `correct=True` and
`structural=True` in
`build/prompt-editor-slice8-separator-reorder.json`; it rebuilds three local
lines and performs no projection rebuild. An additional deterministic sweep of
15 single, adjacent, and blank-line separator topologies across every valid
source/target chip pair completed without failure. No complete repository gate
or commit was run. The same production recovery workload remains
`correct=True`, `structural=True`, and within its timing target after the Slice
9 paint transfers in
`build/prompt-editor-slice9-reorder-separator-recovery.json`.
The maintainer's later two-separator school-uniform prompt is also retained as
an exact owner regression: consecutive target publications cross the second
structural row at projection position 234, and both the preview and its
incrementally derived caret-host geometry remain complete. Its production-shell
pointer lifecycle is `correct=True` and `structural=True` in
`build/prompt-editor-slice9-later-separator-reorder-recovery.json`.
The hostile extension also exposed a separate non-no-op reorder-animation
candidate for Slice 10: while moving chip 11 toward chip 13 in this prompt,
the presenter retained an active paint override for displaced chip 12 while
the prepared render state omitted that chip, and one drain unit performed two
full preview-geometry builds. This evidence is not accepted as clean and must
be visually characterized and fixed at the reorder render owner before that
slice can complete.

The deferred-feedback transfer is now complete.
`PromptDeferredFeedbackStrategy` owns latest-wins wrap scheduling, eligibility
for transient fallback, and immediate caret/insertion/deletion feedback.
`PromptEditTerminalEffects` owns the only terminal full-rebuild and
diagnostic-cache-clear effects, while `PromptProjectionViewport` is the narrow
Qt viewport boundary consumed by publication and feedback. Composition creates
these owners directly and the pipeline selects them through focused typed
ports. The former 1,505-line `incremental_apply_controller.py` is deleted
completely: it was not renamed, reduced to delegations, retained as an internal
shim, or replaced by another mixed controller. Production and diagnostic code
have no reference to it; the executable architecture guard requires its
absence.

Deferred fallback reuses facts already resolved for the source-edit decision.
The existing request now carries that one typed decision instead of copying
three topology, typed-character, and syntax-prefix booleans, and the decision
also carries the bounded token-intersection facts used by fallback. The edit
does not repeat token scans, syntax-prefix parsing, or blocker queries when it
reaches that strategy. `PromptSourceLineChrome` construction moved earlier in
composition because deferred feedback is now an explicit dependency; no
runtime lookup or lazy initialization was added to the edit path. The focused
owners are 343 lines for deferred feedback, 56 for terminal effects, and 42 for
the viewport port. The source-edit pipeline remains a 369-line orchestration
owner.

Focused behavior evidence is clean after deleting the controller. The direct
deferred owner, pipeline, source policy/applier, production incremental editor,
architecture, and real-shell bounded-paste contracts pass. The seeded separator
campaign is `correct=True` and `structural=True` in
`build/prompt-editor-slice8-deferred-separator.json`; the separator
canvas/workflow lifecycle campaign is equally clean in
`build/prompt-editor-slice8-deferred-canvas.json`. The long history diagnostic
in `build/prompt-editor-slice8-deferred-history.json` retains 64 checkpoint
restores and 32 bounded reflows with zero projection rebuilds. No stale private
controller instrumentation remains.

Controlled timing uses the frozen pre-slice worktree, fresh processes, fixed
CPU 31 affinity, identical timing-only paths, and repeated baseline/candidate
order. In
`build/prompt-editor-slice8-deferred-controlled-performance/comparison.json`,
candidate p95 ratios are 0.98 for 5k typing, 0.87 for coalesced projected
typing, 0.95 for a middle edit, 0.93 for syntax rebuild, and 1.01 for 5k
Delete; Delete p50 is 0.96. The mixed corpus initially made 5k Enter appear
adverse, so it was isolated rather than accepted or dismissed. Two fresh
process pairs with six repetitions each in
`build/prompt-editor-slice8-enter-controlled-performance/comparison.json`
measure equal average latency, p50 ratio 1.01, p95/p99/max ratio 0.95, and CPU
ratio 0.97. The transfer therefore adds no demonstrated latency, CPU, rebuild,
fallback, or cache regression. Complete repository gates and commits remain
unauthorized.

The incremental mechanism split is complete. The former 824-line
`incremental_editor.py` is deleted rather than retained as a forwarding shell.
Its contracts, bounded layout mutation, plain-document editing, remapping, and
eligibility policy now have separate authoritative owners of 80, 136, 195,
404, and 165 lines. Production and tests import those owners directly; there
is no compatibility export or test-local alias preserving the mixed owner.

Source-edit decision ownership now flows from one
`PromptSourceEditProjectionFactResolver` through the pure
`PromptEditClassifier` into `PromptEditPipeline`. The resolver computes
topology, blocker, syntax, autocomplete, token-intersection, and overlay facts
once; the classifier returns module-lifetime immutable plans from a flat
prebuilt index. `PromptSourceChangeApplier` no longer decides projection
fallback, performs transient geometry policy, or applies a separate deferred
projection path. All source edits enter the same pipeline.

Direct single-character feedback and scheduled wrap feedback are distinct
strategies. `PromptDirectFeedbackStrategy` owns only the bounded
single-character caret and insertion-overlay path. It returns one immutable
module-lifetime outcome, performs no generalized geometry fallback, and does
not construct diagnostic timing dictionaries on every keypress.
`PromptDeferredFeedbackStrategy` owns latest-wins wrap scheduling and the
generalized fallback path. Typed outcomes distinguish direct feedback from
deferred wrap work, preventing direct edits from clearing diagnostic caches or
running scheduled-wrap terminal handling. A provisional wrap schedule also
retains semantic replacement eligibility, so authoritative semantic refresh
cannot cancel required geometry catch-up at a wrap edge.

Focused classifier, pipeline, fact-resolver, source-applier, freshness,
incremental-mechanism, and production Qt contracts pass. The exact word-wrap
edge regression passes. Seeded separator churn is `correct=True` and
`structural=True` in
`build/prompt-editor-slice8-upstream-separator.json`; the matching unchanged
canvas/workflow lifecycle is clean in
`build/prompt-editor-slice8-upstream-canvas.json` and performs no prompt
document or projection build during the canvas round trip.

The controlled direct-feedback comparison uses two reversed-order fresh
process pairs on the same quiet CPU, with 60 samples per variant. Candidate
median average latency is 4.81 ms versus 4.86 ms, median p50 is 4.19 ms versus
4.30 ms, median p95 is 5.55 ms versus 5.79 ms, and median process CPU is equal
at 46.88 ms. Both variants perform zero projection rebuilds and zero preview
layout work. The evidence is retained under
`build/prompt-editor-slice8-direct-feedback-performance`.

The final source-commit authority transfer is complete. The 1,422-line
inventory root `source_change_applier.py` is deleted, not retained as an
adapter or delegation bookmark. Commit-scope dispatch, document prepared-state
handling, range semantic preparation, history restoration, the atomic
source/semantic/mirror/signal transaction, and projection-pipeline/caret
publication now have focused owners of 69, 136, 168, 202, 304, and 241 lines.
Their construction depends on explicit caret, revision, pointer, and
presentation-effect ports instead of the former broad host Protocol. The
surface holds only the commit application boundary; no old applier field,
compatibility export, duplicate path, or migration shim remains.

The common transaction publishes source identity, stages optimistic semantics,
remaps diagnostics, updates the Qt source mirror, executes exactly one
projection request, publishes caret state, and emits source/caret signals.
Document, range, and history owners prepare their scope-specific inputs and do
not repeat those effects. The abandoned 150-line source-state outcome graph
had no production producer or consumer and is deleted with its test-only
assertions. The one live bounded mirror-edit value belongs to
`source_document.py`, removing the former reverse dependency.

The seeded mixed abuse lane exposed one source-commit regression before this
transfer was accepted. A syntax edit could leave authoritative semantic state
pending while projection geometry was current; an immediately following plain
edit that could not produce transient feedback inherited a wrap-deferrable
reason and published stale geometry with no visible overlay. The projection
application now uses existing revision identities, freshness, and the explicit
deferral decision to distinguish three bounded cases: approved direct
feedback, extension of an established stale-safe wrap chain, and a first wrap
deferral from current semantic state. It rejects an otherwise unrepresented
second deferral and performs immediate canonical recovery. This adds no source
copy, scan, hash, layout construction, service query, signal, or callback to
the hot path; it is identity and enum comparison only.

The exact hostile prefix and the complete 247-dispatch seeded mixed campaign
are `correct=True` and `structural=True` in
`build/prompt-editor-slice8-source-commit-mixed-prefix-refined.json` and
`build/prompt-editor-slice8-source-commit-mixed-refined.json`. The original
word-wrap coalescing contract remains clean. Seeded separator churn and
separator canvas/workflow lifecycle are clean in
`build/prompt-editor-slice8-separator-churn.json` and
`build/prompt-editor-slice8-separator-canvas.json`; the canvas round trip
performs no prompt document or projection build. Forty-eight serial production
source/incremental/deferred contracts and 63 focused pure owner/architecture
contracts pass with targeted Ruff and strict mypy.

The previously retained two-pair controlled direct-feedback comparison remains
the exact pre-slice baseline. A post-transfer fresh-process run adds 60
candidate operations: median average latency is 3.63 ms, median p50 is
3.16 ms, median p95 is 3.95 ms, and median process CPU is 31.25 ms, all below
the retained baseline medians of 4.86, 4.30, 5.79, and 46.88 ms. Structural
abuse confirms no added rebuild, fallback, canvas, or workflow work. Slice 8 is
complete and uncommitted. No complete repository gate or commit is authorized.

### Slice 9 acceptance ledger

Slice 9 is complete only when:

- one immutable prepared render frame contains the exact layout, viewport,
  paint-state, theme, asset, diagnostic, search, source-line, and regional
  chrome inputs consumed by a paint pass, each with explicit upstream revision
  identities;
- content, selection, diagnostics, search, source-line chrome, regional chrome,
  transient overlays, IME, caret, and reorder composition have one named layer
  owner and deterministic z-order; no layer discovers semantic or mutable
  editor state while painting;
- the content renderer consumes prepared draw commands and viewport clipping
  only. It performs no run/token lookup, dataclass replacement, font/style
  derivation, palette query, source scan, layout query construction, service
  lookup, async scheduling, or cache invalidation;
- visible-line selection is bounded by the layout viewport index without
  materializing a tuple from every layout line on each paint;
- projection content, diagnostics, fill bands, source/search chrome, region
  chrome, thumbnails, and applicable raster layers use bounded explicit
  revision keys. Cache hits perform no font/palette/source preparation, and
  eviction is bounded rather than clear-all;
- palette, font, theme, device-pixel-ratio, thumbnail publication, diagnostics,
  search state, selection, focus/caret visibility, scroll, resize, source,
  projection, layout, and paint-state changes advance their owning identity or
  prepared layer exactly once. Correctness does not depend on scattered manual
  cache clears or “skip next build” flags;
- diagnostic visibility filtering, fragment geometry, wave-tile selection, and
  warm scheduling occur outside `paintEvent`; paint consumes only prepared
  visible underline commands, and stale warm results cannot publish across
  layout/viewport/diagnostic identities;
- source-line and search-highlight geometry and colors are prepared outside
  paint. Regional chrome retains its existing bounded immutable preparation
  and becomes an ordinary prepared layer rather than a surface special case;
- the core paint compositor is extracted completely from the large surface.
  The surface paint adapter creates the `QPainter`, supplies the event clip,
  and delegates one prepared frame; it owns no layer policy, cache policy,
  feature queries, or invalidation web;
- preview/reorder rendering continues to consume prepared frames through the
  same core contracts while reorder-specific gesture, preview, raster, and
  animation ownership remains reserved for Slice 10;
- paint performs zero prompt parsing, semantic/projection/layout construction,
  source mutation, thumbnail I/O, service query, async submission, cache-wide
  invalidation, or unrelated signal/callback work. Scroll and caret-only work
  preserve layout and semantic identities;
- focused owner, pixel/visual, real-shell, hostile abuse, paint/cache
  structural-budget, scroll/resize, theme, diagnostics, search, separator,
  thumbnail, workflow, and unchanged-canvas coverage proves exact behavior;
- controlled pre-slice comparisons show equal or better paint, scroll, resize,
  caret/selection, typing, memory, allocation, cache hit/miss, and canvas/
  workflow performance. Full repository gates and commits remain forbidden
  until the maintainer says `commit your work`.

### Slice 9 ownership inventory

The current system already has useful prepared foundations, but paint is not
yet a pure sink. `paint_input.py` carries immutable layout, geometry, paint
state, font, palette, and semantic palette references; `prepared_frame.py`
publishes geometry and that input atomically; `frame_state.py` records layout,
viewport, and paint lineage. `region_chrome.py` is also a correct model for the
target direction: it prepares bounded immutable line geometry outside paint,
retains at most four exact-layout entries, and paints an allocation-free tuple.

The remaining core paint path is split across a 4,774-line surface, 401-line
painter, 340-line content cache, 625-line diagnostic painter, 168-line
source/search chrome owner, and several feature/reorder caches. The surface
`paintEvent` still selects live versus preview state, queries source/search/
diagnostic/IME/caret/reorder feature state, derives viewport and selection
values, chooses cache bypasses, and manually orders every layer. This is layer
policy inside the integration root rather than a thin paint adapter.

`PromptProjectionPainter.draw()` is snapshot-backed but allocates and derives
on every direct paint: it materializes a visible-line tuple by filtering all
layout lines, creates a run-style dictionary, constructs fonts and colors,
looks up runs/tokens, and may create replaced run/token dataclasses for active,
ghosted, accented, and scene-error state. Selection painting also performs
geometry queries and text slicing inside the paint pass. These are preparation
responsibilities, not renderer responsibilities.

`PromptProjectionPaintCache` has one viewport pixmap and an explicit
`PromptPaintIdentity`, but it reconstructs a multi-field key on every
cache-eligible paint by querying `QFont.toString()`, `QPalette.cacheKey()`, four
palette colors, and semantic colors. It also relies on surface-owned manual
invalidations for source, preview, restored layout, and LoRA thumbnail changes,
plus a `skip_next_cache_build` state flag. Thumbnail content has no explicit
asset revision in the key. The cached value is bounded, but correctness is
still partly invalidation-driven.

`PromptDiagnosticPainter` combines four responsibilities: visible diagnostic
selection, layout/viewport cache-key construction and preservation, budgeted
timer warming, and QPainter wave rendering. A paint miss schedules new GUI
work from inside paint. The fragment cache is bounded at 512 entries but evicts
by clearing the entire dictionary; the module-global wave-pixmap cache is
unbounded. Source/search chrome similarly computes visible source rows, search
fragments, theme colors, and palette colors during paint. Fill-band geometry is
already a one-entry source-revision/viewport-keyed cache with miss-only parsing,
but preparation is still exposed through the surface.

Paint-only state publication also performs hidden document-scale work:
`PromptProjectionPreparedFrame.try_set_paint_state()` rebuilds complete token-id
and run-id frozensets for every validation. That makes hover, focus, active
span, decoration, scene-error, and autocomplete visual updates proportional to
document size even though their geometry is unchanged.

Slice 9 proceeds in this dependency order:

1. characterize current layer order, pixels, cache identity, style/theme,
   diagnostics, selection, scroll, and paint structural work at their owners;
2. introduce explicit immutable render-layer and render-frame contracts,
   including theme and media revisions, without routing them through a new
   surface host Protocol;
3. prepare effective run/token styles and viewport-bounded content commands
   once per relevant revision, then make the content renderer an allocation-
   bounded command sink;
4. split diagnostic selection/cache warming from diagnostic rendering and
   replace clear-all/global-unbounded caches with bounded revision-keyed owners;
5. prepare source-line and search chrome outside paint and fold the existing
   region snapshot into the same layer boundary;
6. transfer content cache policy and layer composition into focused owners,
   update every caller, and delete surface invalidation and bypass paths in the
   same vertical slices;
7. extract the complete paint compositor from the surface and enforce the
   final dependency direction and source-size budgets;
8. prove exact visual/behavior equivalence and controlled performance before
   marking Slice 9 complete.

Slice 9 progress:

- `PromptProjectionPreparedFrame` now constructs projection token/run identity
  indexes only when geometry is published and reuses those immutable indexes
  for paint-only state validation. Hover, focus, decoration, scene-error, and
  autocomplete paint-state publication no longer rebuild document-scale
  frozensets.
- `PromptProjectionPaintInput` now prepares immutable effective run/token
  replacements once per paint-state publication. Repeated drawing of active,
  ghosted, accented, or scene-error fragments no longer allocates replacement
  dataclasses.
- core content painting now consumes that prepared input directly and uses the
  shared viewport-indexed visible-line owner instead of filtering and
  materializing all layout lines for every direct paint.
- font, palette, semantic-color, and display-mode cache identity is prepared
  once in `PromptProjectionPaintStyleKey`. A content-cache hit compares the
  existing revision identity and prepared style without querying Qt font or
  palette state and without allocating a candidate cache key. Probe payloads
  are also constructed only when the probe is enabled.
- focused prepared-frame, paint-input, paint-cache, visible-line, style, and
  reorder-render contracts pass. Targeted Ruff format/lint and strict mypy pass
  for the transferred owners. Slice 9 remains in progress; controlled
  paint-performance evidence and the remaining render/cache ownership audit
  remain.
- the obsolete mixed `diagnostics_painter.py` owner is removed. Diagnostic
  visibility, immutable input capture, cache preparation, bounded warm
  scheduling, wave-asset selection, immutable scalar render commands, and
  allocation-bounded drawing now have explicit owners. Fragment overflow
  evicts one least-recently-used entry instead of clearing all 512, and wave
  tiles no longer accumulate in an unbounded module-global cache. The owner
  rejects superseded warm snapshots by exact diagnostic, selection, viewport,
  layout, color, and device-pixel-ratio identity.
- paint now only draws the published diagnostic layer. It cannot filter
  diagnostics, query geometry, prepare fragments, select wave assets, or
  schedule work. Empty diagnostic refreshes return before layout, geometry,
  palette, or device-pixel-ratio queries, so the ordinary no-diagnostic edit
  path gains no unrelated work. Diagnostics, selection, layout, viewport, and
  cache transitions publish before requesting repaint. The surface falls from
  the 4,521-line/265-method integration budget to 4,457 owned lines and 262
  methods while the former paint helpers and scheduling path are deleted.
- ten focused diagnostic render/remap/publication contracts, two bounded-cache
  owner contracts, three phase-3 lifecycle/preview contracts, targeted Ruff,
  strict mypy, and the directional architecture budgets pass. The real-shell
  `spellcheck-diagnostic-action` campaign is `correct=True` and
  `structural=True` in
  `build/prompt-editor-slice9-diagnostic-publication.json`; diagnostic geometry
  lookup occurs only in bounded event-loop warm units, while paint events
  consume the retained layer. These are focused structural observations, not
  an exact controlled pre-slice latency comparison.
- search highlights now have an immutable revision-keyed layer owner. Search
  range-to-fragment geometry, active/passive palette colors, viewport, scroll,
  and layout identity are prepared on their owning transitions; drawing
  consumes scalar rectangle commands and cannot query projection geometry.
  Search responsibility is removed from `source_line_chrome.py`, and its
  focused layout/scroll/composition characterizations plus a geometry-rejection
  draw contract pass. The surface integration-root budget and import-cycle
  guards remain clean.
- source-line chrome now publishes immutable, revision-keyed fill commands on
  layout, viewport, caret, focus, theme, enablement, and reorder-preview
  transitions. Paint performs no source-line geometry query, theme lookup,
  color derivation, or command construction. Focused source-line scroll,
  composition, and geometry-rejection contracts pass, as do both real-shell
  wildcard Alt-preview and mouse-drag zebra preservation cases. The
  `search-highlight-scroll-paint` campaign is `correct=True` and
  `structural=True` in
  `build/prompt-editor-slice9-search-source-chrome.json`. Surface size and
  import-cycle guardrails remain clean after removing its source-line paint
  policy method.
- projection text fonts and colors are now prepared once per projection/theme
  publication in `content_text_styles.py`; paint-state-only updates reuse that
  document-wide base map and prepare overrides only for affected run IDs.
  Inline fragments similarly resolve renderer, run, and token collaborators
  once per layout in `content_inline_bindings.py`, with run/token indexes
  limiting paint-state override work to affected fragments. Core painting no
  longer builds a per-pass style dictionary or performs renderer, run, or token
  lookup for inline drawing. Eight focused prepared-frame/input/cache contracts
  and five semantic style/selection contracts pass with targeted Ruff and
  strict mypy. A fresh focused `projection-paint-cache` observation retains two
  cache hits and zero paint events at 1.50 ms average; controlled pre-slice
  comparison remains required before Slice 9 completion.
- selection backgrounds, selected text spans, inline selected state, and
  highlight color now publish as a viewport-bounded immutable content layer.
  `PromptProjectionPainter` performs no selection geometry query or inline
  selection lookup. `PromptProjectionSelectionLayerOwner` owns transition
  refresh and an O(1) layout/selection/viewport/style key, so duplicate
  caret/scroll lifecycle notifications reuse the same layer rather than repeat
  geometry preparation. The selection geometry-rejection contract, focused
  composition/cache contracts, and integration-root guards pass. The hostile
  `caret-selection-repaint` campaign is `correct=True` and `structural=True` in
  `build/prompt-editor-slice9-selection-layer.json`. Fresh-process candidate
  observations are 2.32 ms average for `1k-selection-change` and 7.78 ms for
  `5k-selection-change`; these are structural/current-candidate evidence, not
  the still-required controlled pre-slice comparison.
- regional chrome is now activated as an ordinary prepared layer by the frame
  synchronizer. Its paint call performs no display/structure policy check and
  no snapshot-cache lookup; ordinary and raw documents publish an empty active
  layer without preparing geometry, preserving zero regional work during
  ordinary typing. Seven region owner/architecture contracts and the focused
  real-shell ordinary-typing and raw-mode contracts pass.
- architecture guardrails now freeze every new content/chrome/diagnostic
  preparation owner at its current source budget and enforce dependency
  direction from lifecycle owners through immutable layers to render/cache
  sinks. Lower command, style, binding, cache, and raster owners cannot import
  the surface or upper paint coordinators; source/search/region owners cannot
  depend on the surface. The focused size, direction, integration-root, and
  import-cycle guards pass.
- `PromptProjectionRenderFrameOwner` now atomically publishes one immutable
  frame containing the exact content mode, paint input and identity, viewport,
  scroll, device-pixel ratio, selection, source-line, region, reorder, search,
  transient-edit, diagnostic, IME, and caret layers. Live and reorder-preview
  no-op publications retain the exact same frame object. Reorder timing starts
  only when composition begins and is not part of semantic frame identity, so
  a changing clock cannot force allocations or invalidate otherwise stable
  preview frames.
- source-line, search, region, diagnostics, transient edit, IME, and caret
  rendering now have separate immutable state, preparation owner, and render
  sink modules. Their dependency direction is executable policy:
  immutable state cannot import preparation or orchestration; preparation
  cannot import render sinks, frames, the compositor, or the surface; render
  sinks cannot import owners or aggregate frames; the frame owner cannot
  import the compositor; and the compositor cannot import feature owners or
  the surface. Mixed state/owner exports and the intermediate caret, IME, and
  transient render-layer modules are deleted rather than retained as shims.
- `PromptProjectionRenderCompositor` owns the complete prepared z-order:
  source-line chrome, region chrome, reorder chrome, search, content,
  transient insertion, diagnostics, transient deletion, IME, and caret.
  `PromptProjectionSurface.paintEvent()` now creates the `QPainter`, reads one
  published frame, intersects the event clip, and delegates. It does not
  select preview/live state, query feature owners, prepare assets or geometry,
  publish layers, or choose cache policy. The former surface content,
  diagnostic, transient, and reorder paint helpers are deleted. The surface
  falls from the Slice 9 starting budget of 4,521 owned lines/265 methods to
  4,394 owned lines/261 methods, and the architecture guard is tightened to
  those exact current limits.
- focused render-frame, reorder-preview, transient, IME, diagnostic, cache,
  phase-4 composition, visual-parity, size, dependency-direction, and
  import-cycle contracts pass with targeted Ruff and strict mypy. Focused
  real-shell campaigns are `correct=True` and `structural=True` in
  `build/prompt-editor-slice9-render-spellcheck.json`,
  `build/prompt-editor-slice9-render-search.json`,
  `build/prompt-editor-slice9-render-caret.json`, and
  `build/prompt-editor-slice9-render-reorder.json`. These campaigns cover
  diagnostic publication, search/scroll/paint, caret/selection repaint, and
  the exact later-separator reorder recovery without adding document,
  projection, or layout work to paint. Controlled pre-slice paint, scroll,
  caret/selection, memory, allocation, cache, workflow, and canvas comparison
  remains required as Slice 9 completion evidence.
- `PromptProjectionRenderCompositor` now owns the sole bounded projection
  content cache. Its immutable key contains paint, prepared style, viewport,
  selection, and explicit thumbnail-media identities. The surface no longer
  clears the cache for source, autocomplete-preview, restored-layout, or
  thumbnail transitions, and no one-shot “skip next cache build” state
  remains. Source and projection revisions reject stale content naturally;
  relevant ready-thumbnail and cache-reset publications advance a focused
  media owner, while unrelated thumbnail events retain the exact render frame
  and cache identity. Direct preview painting does not mutate the retained
  live cache.
- focused content-cache, render-frame, phase-4 preview, incremental-source,
  and LoRA-thumbnail contracts pass. The viewport repaint, caret/selection
  repaint, and unchanged canvas/workflow abuse lanes remain `correct=True`
  and `structural=True` in the retained Slice 9 reports. Targeted Ruff and
  strict mypy pass for the transferred cache/media owners.
- the separator continued-authoring lane exposed an independent transient
  lineage defect while validating source/cache transitions: fallback feedback
  replaced the accumulated insertion with the newest character because the
  pipeline request did not carry the authoritative pre-edit source identity.
  `PromptProjectionSourceChangeApplyRequest` now carries that immutable
  identity from the source transaction, and both direct and fallback feedback
  validate and extend the exact prior overlay. The correction retains the
  valid base content cache beneath the overlay; the rejected direct-paint
  experiment was removed so no extra paint work entered the hot path. Owner
  and surface regressions pass, and
  `build/prompt-editor-slice9-content-cache-editing-fixed.json` is
  `correct=True` and `structural=True` for the exact terminal-separator
  multi-character authoring cycle.
- the render/cache audit also exposed cumulative boundary debt from earlier
  uncommitted edit-to-frame work. The edit pipeline now depends directly on
  its concrete authoritative strategy/publication owners; the eight redundant
  strategy Protocols, `edit_pipeline_ports.py`, and the forwarding
  `edit_terminal_effects.py` shim are deleted. Terminal rebuild/cache outcomes
  belong to `PromptEditPublication`, and undo restoration narrows to the real
  immutable `PromptProjectionUndoPayload` instead of a parallel value-shaped
  Protocol and cast.
- source-state composition no longer accepts an untyped host and rediscovers
  fifteen roles through casts. The surface supplies one explicit immutable
  bindings value, and the wiring owner consumes each named focused dependency
  directly. The global Protocol/cast ceiling, import-cycle, direction, focused
  pipeline, and integration-root guards pass without raising the debt
  ceilings. Explicit binding declarations increase the surface from 4,394 to
  4,407 owned lines while retaining 261 methods; this replaces hidden
  cast/service-locator edges and is frozen at the new exact ceiling for the
  later thin-surface authority transfer.
- focused edit-pipeline, source-commit/history, deferred-feedback, semantic
  transition, strict typing, and Ruff checks pass after the boundary transfer.
  `build/prompt-editor-slice9-directional-editing.json` and
  `build/prompt-editor-slice9-directional-canvas.json` are both
  `correct=True` and `structural=True`, including accumulated terminal
  separator typing and unchanged canvas/workflow lifecycle behavior.
- controlled Slice 9 measurement first exposed repeated unchanged style
  publication during every frame synchronization. `PromptProjectionPreparedFrame`
  now retains its exact paint input when Qt and semantic palette identities are
  unchanged, while changed palettes still publish a new input. This removes
  document-wide text-style preparation from scroll, caret, search, workflow,
  and canvas synchronization.
- search highlights now retain document-space geometry by layout/range
  identity, retain that geometry across active-match recoloring, and publish a
  separate immutable presentation layer. The render sink binary-searches the
  sorted prepared commands and draws only the viewport intersection. Scroll
  does not rebuild search geometry, active-index changes do not query geometry,
  and paint does not discover source, layout, or palette state. The hostile
  search workload now supplies the production `(start, length)` contract; its
  previous `(start, end)` values accidentally created expanding invalid ranges,
  and a workload contract test freezes the corrected 36-match input.
- repeated fixed-affinity timing-only reports under
  `build/prompt-editor-slice9-controlled-performance` are all behavior-clean.
  Viewport paint improves from baseline p50 pairs of 6.92/7.22 ms and p95
  pairs of 11.59/12.25 ms to 5.22/6.46 ms and 8.19/10.01 ms. Caret/selection
  p95 improves from 18.41/25.22 ms to 17.42/16.73 ms while p50 remains in the
  same 2.61-3.20 ms band. Unchanged canvas/workflow p50 improves from
  10.67/11.48 ms to 10.04/7.47 ms and p95 from 395.88/351.95 ms to
  353.48/247.55 ms. The corrected low-contention search pair improves average
  total governed work from 71.70 ms to 63.93 ms, median total work from
  66.59 ms to 64.70 ms, and p95 from 19.79 ms to 18.36 ms. Search publication
  deliberately moves bounded preparation ahead of paint; the final structural
  run measures 0.410 ms search publication, 0.333 ms scroll p95, 0.316 ms
  overall p50, exact cache/layout budgets, and no violations in
  `search-corrected-final-structural.json`.
- focused deep allocation/GC diagnostics retain bounded, source-size-
  independent paint work. Caret/selection drops from 5,070 to 211 net allocated
  blocks and five collections to zero; canvas/workflow drops from 3,630 to
  3,005 blocks. Viewport repaint retains a fixed few-block event-loop variance
  while improving latency and preserving one cache event per paint; the
  result-classifying compositor wrapper was replaced by an explicit disabled
  observer fast path so ordinary paint does not allocate an argument tuple or
  keyword dictionary for instrumentation. Cache hit/miss observability and
  structural counts remain exact.
- focused prepared-frame, paint/cache, render-frame, search owner, current
  real-shell, abuse-workload, import-cycle, dependency-direction,
  integration-root, Protocol/cast-debt, format, lint, and strict typing checks
  pass. The new single-responsibility owner budgets are frozen exactly at
  `prepared_frame.py` 275 lines, `render_compositor.py` 183,
  `search_highlight_layer.py` 83, `search_highlight_owner.py` 143, and
  `search_highlight_renderer.py` 73; no forbidden edge or debt ceiling changed.
  Slice 9 is complete and uncommitted. Complete repository gates and commits
  remain unauthorized.

### Slice 10 acceptance ledger

Slice 10 is complete only when:

- reorder responsibility flows in one direction from pure prompt structure and
  mutation rules, through application session/preview/commit policy, into
  immutable presentation projection and geometry snapshots, prepared visual
  state, and finally thin Qt input, timer, overlay, and paint adapters;
- domain reorder models, derivation, mutation, and serialization remain Qt-free
  and presentation-free; application reorder owners consume those values
  directly and never depend on prompt-editor widgets, overlays, layout engines,
  paint types, or mutable presentation hosts;
- one application use-case boundary owns reorder-session truth, commit intent,
  latest-wins preview revision policy, stale rejection, and lifecycle
  transitions; presentation adapters may report input facts and publish
  results, but cannot keep a second authoritative session, order, revision, or
  commit snapshot;
- preview scheduling policy is deterministic and Qt-free. A focused Qt timer
  adapter owns only wake-up lifecycle; it cannot decide freshness, pointer
  deferral, starvation limits, immediate-versus-deferred work, or which
  revision may publish;
- one preview-projection owner maps an immutable application preview request to
  immutable document, prepared-frame, and geometry inputs. Projection build
  reuse, base-drag reuse, active-preview reuse, cache keys, cache bounds,
  stale-publication rejection, and counters each have one focused owner rather
  than being duplicated across service, surface, controller, and overlay;
- published layout snapshots remain the sole source of reorder chip, cursor,
  row, gap, placement, scroll, pointer, and keyboard geometry. Reorder geometry
  owners consume immutable geometry values and may not query paint, a layout
  engine, the surface, the overlay, or a broad mutable host;
- pointer hit testing, drop-target policy, keyboard navigation, placement
  derivation, and geometry caching have separate focused ownership and stable
  typed inputs. A Qt event adapter translates pointer and key events into typed
  intents without owning reorder policy or geometry;
- animation planning, displacement state, held-chip presentation, landing
  feedback, drag-proxy state, surface chrome, visual reuse, raster reuse, and
  paint ownership consume immutable prepared inputs. Paint and animation
  cannot infer missing chips from mutable overlay state, retain overrides for
  absent prepared chips, or perform layout/projection work;
- the overlay is a thin lifecycle, event-routing, and paint adapter composed
  from explicit focused owners. It has no dynamic service locator, cross-mixin
  private-state contract, broad self-shaped host Protocol, duplicated
  instrumentation authority, or hidden geometry/cache/policy ownership;
- commit, cancel, mouse drag, keyboard reorder, selection restoration,
  autoscroll, drag threshold, Alt-key lifecycle, preview close, source change,
  resize, scroll, font/palette change, focus loss, and editor destruction each
  have one explicit transition and dispose every timer, preview, animation,
  raster warm-up, and transient overlay deterministically;
- regular prompts, structured workflow prompts, emphasis shells, LoRAs, scene
  markers, blank-line gaps, adjacent regional separators, wrapped rows,
  Unicode, rich/raw mode transitions, undo/redo, and post-reorder editing
  preserve their exact current source, selection, preview, and commit behavior;
- the known later-separator animation failure is characterized and fixed: a
  displaced chip omitted from prepared render state cannot retain an active
  paint override, and one coalesced drain unit cannot perform two full
  preview-geometry builds;
- owner tests, real-shell scenarios, and seeded abuse invariants cover every
  lifecycle and hostile transition above, including repeated target changes,
  target oscillation, no-op targets, pointer movement during scheduled work,
  stale timer delivery, release/cancel races, resize/reflow during drag,
  viewport autoscroll, cache invalidation, and source/workflow replacement;
- performance remains a correctness property. Pointer motion and prepared
  painting perform no document parse, serialization, projection build, layout
  construction, full geometry rebuild, raster build, service query, broad
  hashing, or unrelated allocation. Repeated same-target input is a no-op,
  rapid targets coalesce latest-wins, structural fallback is bounded and
  counted, warmed caches are revision-keyed and bounded, and unchanged
  workflow/canvas round trips perform zero reorder work;
- controlled baseline-versus-candidate evidence covers pointer latency,
  scheduling/coalescing, preview publication, geometry/cache rebuilds,
  animation planning, prepared paint, raster reuse, allocation/GC, memory, and
  unchanged canvas/workflow behavior. Equal or better latency is required and
  every structural counter must remain within its explicit budget;
- all old authorities, internal shims, forwarding exports, broad Protocols,
  cross-mixin accessors, dynamic lookups, duplicate counters, dead caches, and
  migration scaffolding are deleted in the same sub-slice that replaces them.

### Slice 10 ownership inventory

The lower reorder layers already flow correctly:

- `domain/prompt/reorder` owns immutable chip/state models, structural
  derivation, typed mutations, and canonical serialization without Qt or
  presentation dependencies;
- `application/prompt_editor/reorder` owns document-to-reorder projection,
  layout/drop transformations, serialization bookkeeping, and structured
  workflow translation over application views;
- presentation layout already consumes canonical layout engines and immutable
  prepared frames, and the existing architecture guard forbids reorder geometry
  from depending on the transitional layout host or paint input.

The remaining presentation vertical is fragmented and contains duplicate or
reversed authority:

- `interactions/reorder_controller.py` is 1,475 lines and combines seven broad
  Protocol boundaries, overlay lifecycle, mode/session orchestration, preview
  scheduling, preview construction/publication, commit execution, keyboard
  policy, selection restoration, and diagnostic forwarding;
- `interactions/reorder_preview_sync.py` is 619 lines and combines Qt timer
  construction, latest-wins freshness policy, pointer-starvation policy,
  mutable pending sync state, execution, timing, and diagnostic classification;
- `projection/reorder_preview_projection.py` is 1,226 lines and combines a
  snapshot provider, active projection service, preview/base-drag lifecycle,
  two cache families, cache recency, geometry rebuilding, frame reuse,
  publication identity, and counters;
- `projection/reorder_interaction_geometry.py` is 1,244 lines behind the upward
  `PromptReorderGeometryHost` Protocol and combines pointer queries, keyboard
  queries, placement policy, partitioning, and host access;
- `projection/reorder_geometry_cache.py` is 881 lines with 25 mutable fields
  spanning geometry identity, chip/placement caches, invalidation, reuse,
  lifecycle, and observability;
- `overlays/reorder_overlay.py` is 1,394 lines with 109 mutable fields spanning
  widget lifecycle, gesture state, geometry, placement, proxy, animation,
  raster, landing feedback, telemetry, and instrumentation;
- `overlays/reorder_overlay_interaction.py` and
  `overlays/reorder_overlay_geometry.py` are 1,097 and 1,790 lines and use a
  dynamic `_OverlayShellAccess.__getattr__` service-locator pattern to mutate
  another class's private state across mixin boundaries;
- `overlays/reorder_landing_shadow.py` is 1,917 lines and combines landing
  policy, geometry, retained feedback, caches, logging, and counters;
- `overlays/reorder_view.py`, keyboard navigation, visual/raster caches,
  animation presenters, drag-proxy owners, and paint-snapshot builders are
  individually narrower but currently depend on mutable overlay-owned
  coordination rather than one immutable prepared visual publication.

The current focused reorder suites already expose semantic, projection,
surface, overlay, scheduler, interaction-owner, and structural-counter
contracts. The seeded abuse harness covers decorated, wrapped, maximum-span,
scene-partition, regional-separator, later-separator, post-reorder typing, and
wildcard lifecycles. Slice 10 extends those owners rather than replacing them
with private implementation assertions.

### Slice 10 target dependency graph

The permitted direction is:

1. `domain.prompt.reorder`: pure source structure, values, derivation,
   mutation, and serialization;
2. `application.prompt_editor.reorder`: document semantics, typed reorder
   requests/results, session and commit policy, preview revision/freshness
   policy, and structured workflow translation;
3. presentation preview layout/projection: immutable application request to
   immutable document, prepared-frame, and geometry publication;
4. presentation geometry: immutable layout inputs to chip, row, gap,
   placement, hit-test, navigation, and scroll snapshots;
5. presentation visual preparation: immutable projection/geometry state to
   animation, landing, held-chip, drag-proxy, chrome, raster-key, and paint
   snapshots;
6. presentation interaction adapters: Qt pointer/key/timer facts to typed
   application or geometry intents, consuming published snapshots only;
7. overlay/view/render adapters: lifecycle and clipped drawing of prepared
   values only;
8. composition: construct and connect the graph once without becoming a
   runtime service locator.

Dependencies may remain within one numbered layer only between focused value
and algorithm owners with an acyclic graph. No lower numbered layer may import
a higher one. Interaction adapters cannot be used as policy/model owners, and
overlay/view classes cannot be imported by projection, geometry, application,
or domain owners.

### Slice 10 migration order

Slice 10 proceeds through complete vertical authority transfers:

1. freeze the dependency graph, mixed-root budgets, known animation defect,
   scheduler semantics, interaction lifecycles, structural counters, seeded
   abuse scenarios, and controlled baseline timing/allocation evidence;
2. transfer latest-wins revision, staleness, pointer-deferral, starvation, and
   immediate/deferred policy into a Qt-free application owner; reduce the Qt
   timer to a wake-up adapter, update every callsite, and delete the mixed
   scheduler path and forwarding exports;
3. transfer session, commit, cancel, selection-restoration, and preview
   lifecycle transitions behind typed application requests/results; shrink the
   presentation controller to input/result orchestration and delete duplicate
   truth;
4. split projection build, reuse/cache, lifecycle/publication, and geometry
   input ownership; route controller and surface through one immutable result
   and delete duplicate projection/frame/cache authorities;
5. split chip/placement construction, pointer hit testing, keyboard navigation,
   regional placement coverage, scroll geometry, and bounded caches over published
   snapshots; delete `PromptReorderGeometryHost` and all upward host queries;
6. transfer animation/displacement, held chip, landing feedback, drag proxy,
   surface chrome, visual reuse, raster reuse, and paint ownership into one
   prepared visual publication, fixing the known omitted-chip override and
   duplicate-build failure at its owner;
7. replace dynamic interaction/geometry/animation mixins with focused typed
   gesture, autoscroll, and presentation owners; update all callsites and delete
   `_OverlayShellAccess`, cross-mixin private state, and broad overlay ports;
8. reduce the overlay, view, controller, surface hooks, and composition factory
   to thin final adapters; remove dead exports, counters, caches, protocols,
   shims, and scaffolding; then run the full focused behavior, abuse, structural,
   performance, allocation, memory, canvas, and workflow evidence required by
   this ledger before marking Slice 10 complete.

No sub-slice may leave two owners active. Characterization precedes each
transfer, every old path is deleted with its replacement, and controlled
measurement follows each change that can affect pointer, preview, geometry,
paint, workflow, or canvas work. Complete repository gates and commits remain
unauthorized.

Slice 10 progress:

- the pre-transfer owner characterization is frozen. The mixed
  `PromptReorderController` and `SegmentReorderOverlay` integration roots are
  capped at 1,412 owned lines/53 methods and 1,272/72 respectively, so every
  later transfer must shrink rather than extend them. The target dependency
  graph is executable for preview scheduling, and the existing import-cycle,
  preview-layout, geometry-direction, and integration-root guards remain clean;
- the pre-transfer later-separator abuse report is retained at
  `build/prompt-editor-slice10-baseline-later-separator.json`. Source, caret,
  projection, semantic, and visual correctness pass, while the required
  structural invariant fails because one drain work unit can perform two full
  preview-geometry builds. This is the already identified Slice 10 defect, not
  accepted completion evidence;
- latest-wins preview scheduling now has final directional ownership.
  `application/prompt_editor/reorder/preview_schedule.py` owns revision
  replacement, stale rejection, pointer deferral, and the 96 ms starvation cap
  using constant mutable state and module-lifetime enum decisions.
  `application/prompt_editor/reorder/preview_sync.py` owns requested, pending,
  active, and published revision truth plus immediate/deferred and
  stale-publication decisions. Both owners are Qt-free and presentation-free;
- `interactions/reorder_preview_timer.py` is the sole `QTimer` owner and only
  starts, stops, or restarts wake-ups according to application decisions.
  `reorder_preview_sync.py` now performs publication execution and telemetry
  around application policy rather than retaining parallel revision state.
  The old `PromptReorderPreviewScheduler`, timer Protocols, mixed policy state,
  package-barrel exports, and all callsites of that class are deleted rather
  than forwarded;
- six direct Qt-free policy cases cover latest-wins replacement, pointer
  starvation, cancellation, immediate/deferred selection, stale rejection, and
  failed-versus-successful publication. The 14 scheduler/interaction-owner
  cases, 14 projection-service cases, 28 focused reorder performance-counter
  cases, and 20 focused reorder-surface cases pass. Targeted Ruff and strict
  mypy pass for the complete transfer;
- the post-transfer later-separator report at
  `build/prompt-editor-slice10-preview-policy-later-separator.json` preserves
  behavior and the same structural failure class; projection rebuilds remain
  zero. A focused five-scenario reorder measurement retains same-target
  no-op behavior, one coalesced preview run for target-change scenarios, and
  bounded cache/animation counts, but it ran beside other diagnostics and is
  not accepted as controlled latency evidence. The isolated same-seed report
  `prompt-editor-slice10-preview-policy-later-separator-isolated.json` supplies
  the controlled comparison: median repetition p50 improves from 7.21 ms to
  5.87 ms and median p95 from 14.95 ms to 14.33 ms, with identical source and
  projection correctness, zero projection rebuilds, and the same already
  ledgered two-build defect. The policy path adds no per-request result object,
  scan, hash, layout, or service query. The scheduling authority transfer is
  complete; the structural defect remains assigned to the later prepared
  visual/geometry transfer.
- reorder session and commit policy now have final application ownership.
  `application/prompt_editor/reorder/session.py` owns one frozen session
  snapshot, authoritative preview/commit snapshot adoption, complete commit
  disposition, and selection-restoration policy.
  `application/prompt_editor/reorder/intents.py` owns the typed commit, cancel,
  and keyboard-move requests. Both modules are Qt-free and
  presentation-free;
- the old presentation `reorder_session.py`, the session and intent values in
  mixed presentation `models.py`, their package-barrel forwarding exports,
  and every old callsite are deleted. The presentation controller now performs
  only Qt source mutation, selection application, and overlay lifecycle from
  the application commit plan. Its session query returns the owner's existing
  immutable snapshot without copying or allocating on pointer reads;
- direct application tests cover frozen state, complete relative-selection
  commit policy, unchanged and missing-state outcomes, and deterministic reset.
  The 42 focused session/controller/architecture cases, 20 overlay cases, 28
  reorder structural-counter cases, and 13 reorder autocomplete-surface cases
  pass with targeted Ruff and strict mypy. The post-reorder hostile report at
  `build/prompt-editor-slice10-session-post-reorder.json` preserves source,
  projection, caret, typing, and commit behavior;
- the same-seed later-separator report at
  `build/prompt-editor-slice10-session-later-separator-isolated.json` remains
  behavior-correct with zero projection rebuilds and exposes only the already
  ledgered two-full-preview-build failure. Its repetition medians vary from
  5.87 to 6.95 ms p50 and 14.33 to 17.42 ms p95 while competing CPU load
  exceeds 70 percent, so those latency values are not accepted as evidence of
  either improvement or regression. The transferred session policy runs only
  at session start, accepted preview publication, commit, cancel, or close;
  unchanged pointer movement still performs no session mutation or allocation.
  Focused structural counters remain the accepted hot-path evidence for this
  transfer. Session and commit authority transfer is complete.
- projection build, cache/reuse, metrics, and lifecycle/publication now have
  explicit directional owners. The 1,226-line mixed
  `projection/reorder_preview_projection.py` is deleted rather than retained as
  a facade. `reorder_projection_snapshot_provider.py` owns semantic snapshot
  construction and its 64-entry content LRU;
  `reorder_preview_frame_cache.py` owns complete frame identity, the bounded
  16-entry target-revisit LRU, eviction, and prompt-safe cache diagnostics;
  `reorder_preview_frame_builder.py` owns full versus incremental prepared-frame
  construction; and `reorder_preview_projection_metrics.py` owns the stable
  typed structural counters;
- `reorder_preview_projection_owner.py` owns one frozen
  `PromptReorderPreviewProjectionPublication`. Preview request, preview
  document/frame/key, and base-drag document/frame/key are built in locals and
  replace the active publication once, so exceptions cannot expose the partial
  combinations previously possible through seven independently mutable fields.
  The owner consumes the lower builder/cache owners in one direction and has no
  widget, overlay, controller, or surface dependency. The semantic provider is
  independent of the frame lifecycle and no longer accepts the unused active
  target argument;
- the semantic provider now uses `OrderedDict.move_to_end()` rather than a
  parallel dictionary plus linear list removal on each hit. The final focused
  modules are 323 lines for semantic construction, 124 for immutable contracts,
  69 for typed metrics, 260 for frame cache identity/reuse, 113 for frame
  construction, and 622 for atomic lifecycle/publication and its projection
  geometry queries. An executable direction guard freezes these ownership
  boundaries and requires the old mixed module to remain absent;
- all 16 direct provider/publication cases, 68 focused reorder surface,
  structural-counter, and overlay cases, and the relevant architecture and
  host-boundary cases pass. Targeted format, Ruff, and strict mypy pass. The
  same-seed report at
  `build/prompt-editor-slice10-projection-owner-later-separator-isolated.json`
  preserves source, caret, semantic, projection, and visual correctness with
  zero projection rebuilds. Against the preceding isolated report, median
  repetition p50 falls from 6.95 to 3.12 ms and p95 from 17.42 to 7.69 ms;
  competing CPU also falls from 70.6 to 22.5 percent, so the latency delta is
  corroborating rather than sole evidence. Focused counters preserve active-hit,
  exact-reuse, incremental, LRU revisit, cache-invalidation, unchanged-target,
  coalescing, and autoscroll budgets. The already ledgered two-full-preview-
  geometry-build failure remains reproducible in one repetition and is still
  blocking Slice 10 completion.
- geometry-authority characterization for migration step 5 is now explicit.
  `projection/reorder_interaction_geometry.py` is a 1,244-line mutable
  coordinator with 40 methods and 24 independently assignable session,
  preview, chip, placement, lane, order, and identity fields. It reaches upward
  through the four-method `PromptReorderGeometryHost`, which is inherited by
  the already broad overlay/editor Protocols and implemented by widget-to-
  surface forwarding methods. `projection/reorder_geometry_cache.py` is 881
  lines and combines five cache families, complete key construction, LRU
  policy, scroll-candidate policy, immutable-object reuse, timing maxima,
  counters, and diagnostic hashing. `reorder_keyboard_navigation.py` is 819
  lines/31 methods, while drop-target resolution is 503 lines and the overlay
  geometry mixin is 1,790 lines/54 methods. These are the next deletion and
  transfer targets; extending any of them is prohibited.
- the geometry transfer must first publish one immutable environment from the
  current live frame, preview/base frames, viewport, scroll, and layout-width
  authorities. A focused concrete geometry owner will consume that snapshot
  and own chip/placement construction plus bounded caches. Interaction state,
  pointer resolution, and keyboard policy will then consume its immutable
  results directly. The overlay factory will inject the concrete owner, and
  `PromptReorderGeometryHost`, widget-to-surface internal geometry queries,
  Protocol inheritance, casts, and duplicate cache authorities will be removed
  in the same vertical transfer. Public shell compatibility may remain only at
  the outer widget adapter and cannot be used by internal reorder code.
- the first geometry vertical transfer is complete. The surface no longer owns
  chip/placement key construction, cache lookup, scroll-window reuse,
  immutable-chip reuse, geometry construction, placement construction, timing
  maxima, or their diagnostic events. Those responsibilities moved together
  into `reorder_geometry_owner.py`, which consumes one frozen
  `PromptReorderGeometryEnvironment` containing the authoritative live frame,
  source identity, viewport, scroll, and layout width plus the atomic
  preview/base-frame publication. The environment is captured only for actual
  geometry work; missing-frame queries do not flush projection, and nested
  base-placement construction reuses the same environment rather than adding a
  second flush or allocation;
- `PromptReorderGeometryHost`, `_geometry_host`, the composition cast, Protocol
  inheritance in the overlay ports, and every widget-upward geometry query used
  by internal reorder code are deleted. Composition passes the concrete
  geometry owner from the surface directly into interaction geometry. Live chip
  construction now publishes through `PromptReorderInteractionGeometry`, so
  the overlay no longer asks its editor for geometry. The surface retains only
  public compatibility adapters and one immutable-environment publication
  adapter;
- this transfer removes 549 owned lines and three methods from
  `PromptProjectionSurface`, lowering its frozen budget from 4,407/261 to
  3,858/258. The geometry owner is capped at 610 owned lines and interaction
  geometry at 1,168, so subsequent cache, pointer, keyboard, and state transfers
  must shrink them. A direction guard requires geometry construction to remain
  independent of surface, widget, overlay, composition, and interaction
  modules and requires interaction geometry to depend downward on the owner;
- 69 focused interaction, projection-surface, structural-counter, and overlay
  cases pass, along with targeted format, Ruff, strict mypy, architecture, and
  host-boundary checks. The first post-transfer same-seed hostile report at
  `build/prompt-editor-slice10-geometry-owner-later-separator-isolated.json`
  preserves behavior and, for the first time, passes the two-full-preview-build
  structural budget in all repetitions. Its latency sample ran under 61.8
  percent competing CPU and is not accepted as controlled timing evidence.
  Focused cache/scroll/coalescing counters show no added rebuild, scan, layout,
  or unchanged-pointer work. The later cache and prepared-visual transfers must
  preserve this structural result and obtain a controlled low-contention
  comparison before Slice 10 completes.
- geometry cache identity, storage, reuse policy, diagnostics, and metrics now
  have focused one-way owners. The 881-line/25-field mixed
  `projection/reorder_geometry_cache.py` is deleted rather than retained as a
  coordinator or compatibility facade. `reorder_geometry_cache_keys.py` owns
  immutable complete identity only; `reorder_chip_geometry_cache.py` owns the
  live/base slots and bounded 16-entry preview LRU;
  `reorder_placement_geometry_cache.py` owns the stable placement slot;
  `reorder_geometry_metrics.py` owns the typed harness schema; and
  `reorder_geometry_diagnostics.py` owns prompt-safe hashing and context.
  `reorder_chip_visual_identity.py` is the single pure authority shared by chip
  object reuse and overlay visual reuse, replacing the duplicate algorithm;
- `PromptReorderGeometryOwner` composes those owners directly, with no
  replacement cache facade or delegation bookmark. The final raw module sizes
  are 348 lines for identity, 307 for chip storage/reuse, 73 for placement
  storage, 115 for metrics, 104 for diagnostics, and 61 for visual identity.
  The geometry owner remains below its 610-owned-line guard. A new executable
  direction guard requires the deleted mixed file to remain absent and keeps
  identity/metrics independent, storage below orchestration, diagnostics
  independent of caches, and every focused module below surface, widget,
  controller, and overlay adapters;
- all 11 direct identity/cache policy cases, 14 cache/architecture cases, and
  19 focused chip, placement, scroll, interaction, surface, overlay, and
  structural-counter cases pass. Targeted format, Ruff, and strict mypy pass.
  The same-seed hostile report at
  `build/prompt-editor-slice10-geometry-cache-owners-later-separator-isolated.json`
  preserves every source, caret, semantic, projection, and visual invariant
  with no invariant failures. It ran under 73.9 percent competing CPU, so its
  7.67-10.19 ms p50 and 18.30-22.50 ms p95 range is not controlled timing
  evidence. The already ledgered duplicate preview-visual build remains
  reproducible after preview publication plus a queued surface resize: two of
  three repetitions report two full visual builds where the structural budget
  permits one. Cache counters show the cache split did not add geometry,
  layout, scan, or unchanged-pointer work. Migration step 6 must fix the
  duplicate at the prepared-visual publication owner rather than conceal it by
  weakening the budget or patching the mixed overlay geometry file.
- interaction geometry now publishes one frozen
  `PromptReorderInteractionGeometryState` instead of exposing 23 independently
  mutable document, layout, reorder-state, preview, chip, placement, lane,
  order, and identity fields. Every session, drag, preview, geometry, keyboard,
  commit, restore, and active-placement transition replaces that publication
  atomically. Overlay readers consume the publication and issue typed owner
  transitions; every direct cross-object geometry field write is deleted.
  `reorder_interaction_geometry_identity.py` is the sole pure owner of source,
  layout, snapshot, target, prepared-geometry, and base-drag identities.
- the remaining migration-step-5 policies now have directional focused
  ownership rather than stateless facades on the interaction coordinator.
  `reorder_drop_targets.py` contains only immutable lane and target geometry
  values; `reorder_pointer_hit_testing.py` owns pointer resolution;
  `reorder_drop_geometry_builder.py` publishes one synchronized
  placement/target/lane snapshot containing every structural destination; and
  `reorder_keyboard_geometry.py` indexes concrete lane occurrences once per
  keyboard action for `reorder_keyboard_navigation.py`. The interaction owner
  consumes those results and has no pointer-policy dependency. The old
  keyboard query facades and duplicated lane scans were deleted rather than
  forwarded.
- synchronized drop publication keeps placement, pointer visuals, and keyboard
  lanes on the same complete structural target set. Regional separators remain
  fixed document structure rather than drag chips, while chips may move to any
  row or blank-line destination and adopt that destination's partition. The
  obsolete regional target filter is deleted, and direct regression contracts
  require all cross-separator placements to remain available.
- the focused owner sizes are now 74 owned lines for target values, 431 for
  pointer resolution, 107 for synchronized drop
  construction, 257 for keyboard geometry, 455 for navigation, 53 for
  immutable interaction state, 249 for identity, and 900 for interaction
  coordination. The former 819-line navigation mixed owner is 470 raw lines,
  the former 503-line mixed drop-target module is 82 raw value lines plus a
  460-line pointer owner, and interaction coordination is 946 raw lines versus
  the characterized 1,244. An executable direction and exact owned-line budget
  guard prevents these concerns from merging or depending back on surface,
  widget, overlay, or controller adapters.
- all direct pointer, drop-publication, keyboard, and interaction cases and 22
  focused interaction-owner, controller, projection-surface, overlay, and
  structural-counter cases pass. The focused architecture, format, Ruff, and
  strict mypy checks pass. The same-seed production real-shell report at
  `build/prompt-editor-slice10-interaction-owners-later-separator-isolated.json`
  passes every source, caret, semantic, projection, visual, and structural
  invariant in all three repetitions, including the full-preview-build budget.
  Under 19.85 percent competing CPU its median repetition p50 is 3.68 ms and
  p95 is 6.88 ms. Compared with the earlier low-contention projection-owner
  evidence, p95 improves from 7.69 ms while p50 varies from 3.12 ms; this is
  provisional scenario timing rather than a claim of a completed paired
  performance comparison. Structural evidence confirms the transfer adds no
  pointer-time parse, projection, layout, full-geometry, scan, or service
  query. Migration step 5 is complete; the final controlled slice comparison
  remains required after prepared visual ownership is transferred.
- migration step 6 has begun with one complete prepared-preview publication
  boundary, not a replacement facade over mirrored overlay state.
  `reorder_preview_visual_owner.py` owns the immutable geometry-plus-visual
  publication, exact source-identity reuse, bounded per-chip visual reuse, and
  typed preparation metrics. Its key retains authoritative source objects and
  compares them by identity in constant work, avoiding document hashing, deep
  equality, and integer-identity reuse. `reorder_visual_geometry.py` is the
  focused Qt geometry adapter formerly embedded in `reorder_view.py`;
  composition injects the visual owner and the overlay consumes its frozen
  mapping directly;
- the overlay copies of preview/base chip geometry, placement, active
  placement, drop visuals, drop lanes, preview target identity, and prepared
  preview visuals are deleted. Geometry readers now consume the one immutable
  interaction publication and visual readers consume the one prepared visual
  publication. The direction guard requires interaction geometry to feed
  visual preparation and visual preparation to remain independent of the
  view, overlay, widget, surface, controller, and composition adapters. Exact
  owned-line ceilings are 64 for the visual adapter, 303 for the prepared
  owner, and 759 for the reduced `reorder_view.py`; the mixed overlay and
  geometry mixin have fallen to 1,249 and 1,590 owned lines while remaining
  prohibited extension targets;
- focused real-shell tracing exposed the remaining duplicate activation build
  precisely: the initial Qt theme event prepared empty preview geometry before
  the overlay had received a document or chips, then `set_chips()` discarded
  that publication and correctly rebuilt it. Theme invalidation still updates
  colors, fonts, proxy invalidation, and initialized sessions, but it no longer
  performs geometry work for an uninitialized overlay. The abuse structural
  policy now rejects more than one full preview build during the Alt activation
  unit, so the failure cannot be hidden by the more general queued-work budget;
- the 29 direct visual-owner, interaction, pointer, drop-publication, keyboard, and
  host-resolution cases pass, as do six focused direction/immutability cases
  and the two activation structural-policy contracts. Targeted format, Ruff,
  and strict mypy checks pass. The three-repetition production report at
  `build/prompt-editor-slice10-preview-visual-owner-final.json` has zero
  behavior, visual, or structural violations and records exactly one full
  preview build on Alt activation in every repetition. Its 49.97 percent
  competing CPU makes the 5.94-10.28 ms p50 and 15.61-21.63 ms p95 ranges
  unsuitable for performance comparison; structural work is the accepted
  evidence from this run, and no timing regression or improvement is claimed.
  Step 6 remains active: animation/displacement, held-chip, landing, drag
  proxy, surface chrome, raster reuse, and final paint ownership still require
  complete transfer into the prepared publication before advancing.
- the former mixed `reorder_view.py` no longer owns style derivation,
  interaction-state mapping, paint-state preparation, and Qt painting in one
  file. `reorder_visual_style.py` owns immutable palette/style preparation,
  `reorder_interaction_visual.py` maps interaction facts to visual facts,
  `reorder_render_state.py` prepares immutable overlay paint state, and the
  reduced `reorder_view.py` is a paint-only widget adapter. The old mixed
  implementation was replaced directly; no forwarding module or compatibility
  shim remains. Exact owned-line ceilings are 228, 101, 252, and 259
  respectively, and the direction guard prevents these value/preparation
  owners from depending back on the view, overlay, surface, controller, or
  composition adapters;
- overlay render state, surface chrome, suppression snapshots, unsafe
  transient indices, and paint mode now publish atomically through one frozen
  revisioned `PromptReorderPreparedVisualPublication` prepared by
  `reorder_prepared_visual.py`. The overlay no longer assembles suppression
  and surface state in a second imperative sync path.
  `reorder_animation_paint_policy.py` separately owns the pure complete-paint
  ownership rule, and the obsolete mixed `reorder_paint_ownership.py` is
  deleted. Direct characterization proves an omitted displaced chip cannot
  survive as an active paint override when it is absent from the prepared
  render state;
- the first post-publication abuse run exposed a distinct queued height-only
  rebuild after drag release. The authoritative interaction publication was
  geometry-free at that point: no preview or base chip snapshot, placement,
  target lanes, target visuals, target identity, or prepared visual remained.
  `PromptReorderPreviewVisualOwner` now rekeys that exact empty publication
  when only viewport/content height changes, without calling geometry
  construction. Populated publications and every width change still rebuild;
  direct contracts freeze both sides of the rule. This avoids general
  stale-geometry reuse and adds no document scan, hash, layout, service query,
  or pointer-time work;
- the final three-repetition real-shell abuse report at
  `build/prompt-editor-slice10-paint-publication-height-reuse-final.json`
  records zero invariant and zero structural violations. Alt activation
  performs exactly one full preview-visual build in every repetition, and the
  queued post-release height change performs the geometry-free rekey rather
  than a second build. Competing CPU was 48.85 percent, so the run is accepted
  only as behavior and structural evidence. The focused visual-owner,
  render-state, landing-shadow, animation, and architecture contracts pass,
  with exact owned-line ceilings of 64 for animation paint policy, 129 for
  atomic paint publication, 374 for the visual owner, and 259 for the view.
  `reorder_overlay_geometry.py` is down to 1,561 owned lines but remains a
  prohibited extension target. Step 6 is still active for the remaining
  landing, animation/held-chip, drag-proxy, raster-reuse, and final prepared
  publication authority transfers.
- raster publication and warm-up lifecycle now have one focused owner.
  `reorder_raster_publication.py` owns the live and preview publication
  identities, immutable entry mappings, exact reuse, lower-cache access,
  bounded warm scheduling, invalidation, and combined diagnostics. Keys retain
  the actual visual snapshot objects and compare them by identity; the old
  integer `id()` tuple, four overlay-owned key/entry fields, two overlay
  counters, duplicate live/preview branches, and overlay invalidation helper
  are deleted. `reorder_raster_cache.py` remains the bounded pixmap owner and
  `reorder_raster_warm_scheduler.py` remains the zero-delay Qt batch adapter;
  neither depends back on the publication owner or overlay;
- direct raster-publication coverage proves cold publication, one bounded warm
  completion, immutable exact-map reuse, placement-independent pixmap reuse
  across a new snapshot identity, and stable structural counters. Four focused
  Alt, animation-frame, suppression, displaced-neighbor, and raster-churn
  contracts pass, as do the 40 focused overlay/surface contracts in their
  required in-process Qt lane. Targeted format, Ruff, strict mypy, and the
  executable direction/budget guard pass. The owner is capped at 236 owned
  lines; the overlay and geometry mixin fall to 1,230 and 1,463 owned lines;
- the production smoke report at
  `build/prompt-editor-slice10-raster-publication-smoke.json` preserves every
  source, caret, semantic, projection, visual, and structural invariant. Alt
  activation retains one full preview build and the established raster
  hit/miss budget. Its 52.66 percent competing CPU and cold 203.76 ms outlier
  make the run invalid for timing comparison, so it supplies structural
  evidence only. Animation/held-chip publication, landing feedback, drag proxy,
  and final prepared publication ownership remain active step-6 work.
- displacement and keyboard-held animation now publish through one focused
  `PromptReorderAnimationVisualOwner`. The two timer presenters retain only
  their individual interpolation lifecycles; the owner batches plan, cancel,
  and settle transitions and publishes one immutable revision containing
  displacement, held-chip, and combined paint rectangles. Pointer-region
  geometry and paint now consume that exact same publication instead of asking
  both presenters for separately allocated dictionaries at different points in
  one frame. Overlay-owned batch depth, pending-frame truth, presenter fields,
  duplicate merge work, and the dead package-barrel presenter export are
  deleted;
- direct owner coverage proves the first held/displacement frame publishes
  atomically and that cancel clears both in one later revision. All 28 focused
  reorder structural/performance contracts pass, including coherent first
  frame, resize preservation, blank-line return, wrapped displacement,
  incomplete-paint fallback, suppression, raster-churn, and rapid-target
  coalescing. Targeted format, Ruff, strict mypy, and the executable direction
  guard pass. The new owner is capped at 172 owned lines; the overlay and
  animation mixin fall to 1,224 and 238 owned lines. The geometry mixin is
  1,464 owned lines and remains a prohibited extension target;
- `build/prompt-editor-slice10-animation-publication-smoke.json` preserves all
  source, caret, semantic, projection, visual, and structural invariants in the
  known later-separator pointer lifecycle, including one Alt activation build
  and no duplicate queued visual build. Competing CPU was 60.60 percent, so
  its latency is not accepted as comparison evidence. Landing feedback, drag
  proxy coordination, and the final prepared-publication boundary remain
  active step-6 work.
- landing feedback is now being decomposed by authoritative concern rather
  than by delegating the old presenter through a facade.
  `reorder_landing_models.py` owns the immutable capture, request, geometry,
  sync, and counter contracts below paint;
  `reorder_landing_paint_cache.py` owns exact paint key construction, strong
  object identity, the single complete cached publication, and its metrics.
  The presenter no longer owns cache fields, integer `id()` keys, duplicated
  geometry-key helpers, or hit/miss truth. The initial-shadow readiness
  transition remains part of the complete key and is directly characterized;
- held-chip source selection and normalization now belong to the pure
  `reorder_landing_capture.py` algorithm. It chooses live geometry, base-drag
  geometry, live visual, widget, or proxy fallback in priority order and
  returns bounded failure diagnostics; the presenter owns only adoption,
  counters, and telemetry for that result. Bubble-union geometry moved from
  telemetry into `chip_visuals.py`, removing the reversed dependency from
  geometry policy to diagnostics. The old presenter capture algorithm and
  storage helper were deleted;
- placement-target derivation, pending/translated shadow construction,
  viewport clamping, chip-shape classification, and active-target matching now
  belong to the pure `reorder_landing_geometry.py` policy. The presenter
  supplies immutable inputs and owns only the state transition and bounded
  mismatch telemetry around the result. The executable import graph requires
  `chip_visuals` and landing values to flow outward through this geometry
  owner, forbids it from importing capture, cache, presenter, render,
  publication, view, or outer adapter concerns, and caps it at 267 owned
  lines. The old low-level geometry, translation, clamping, shape, and target
  policy methods were deleted from the presenter;
- landing diagnostic classification and structured context publication now
  belong to `reorder_landing_diagnostics.py`. It owns pending-versus-held and
  pending-versus-authoritative shape comparison, wrap-delta classification,
  stale-rejection context, target/placement alignment diagnostics, preview
  identity context, and the anomaly/expected counters. The presenter retains
  the stale-rejection state transition and delegates no state ownership to
  diagnostics. The old diagnostic methods and duplicate counter mutations
  were deleted. Direct characterization freezes stale-target fallback events,
  wrapped pending-shape comparison, owner counter classification, and reset;
- retained landing interaction state and operational counters now belong to
  `reorder_landing_state.py`. Its sole immutable revisioned publication owns
  held geometry, the last prepared preview, target/event/skip/rejection state,
  and initial-sync readiness. Outer geometry and interaction adapters consume
  that publication instead of mutable presenter fields. Duplicate skip reasons
  do not allocate; counter-only observations do not republish state; reset,
  capture, rejection, readiness, preview, and fallback transitions each have
  one typed owner. Direct owner coverage freezes revision, identity reuse,
  duplicate-capture rejection, counter separation, and reset;
- all 15 direct landing contracts and four focused pointer/target hot-path
  contracts pass with targeted format, Ruff, strict mypy, and direction
  checks. Exact owned-line ceilings are 126 for landing values, 145 for held
  capture, 269 for landing geometry, 561 for diagnostics, 257 for paint
  caching, 220 for landing state, and 223 for shared chip geometry. The mixed
  legacy landing coordinator falls from 1,917 raw/characterized lines to 922
  raw and 872 owned lines. It is now the explicitly named
  `reorder_landing_visual_owner.py`, every production and test callsite uses
  `PromptReorderLandingVisualOwner` and the immutable `publication`, and the
  obsolete `reorder_landing_shadow.py` path and presenter type are deleted
  under an executable absence guard. The owner remains under a no-regrowth
  ceiling;
- narrow prompt-safe event and timing callbacks now enter through
  `reorder_event_ports.py`, while `reorder_landing_events.py` owns operational
  landing event names, skip classification, timing publication, and structured
  context assembly. The visual owner no longer assembles capture, initial
  synchronization, placement, pending-marker, suppression, preview-skip,
  rejection, or paint event payloads. Landing diagnostics now use the existing
  interaction-geometry preview-identity context owner instead of maintaining a
  duplicate formatter. Direct event-owner coverage freezes skip-event mapping
  and bounded context. Executable direction guards keep the port dependency
  free, keep events below the visual owner and independent of diagnostics,
  geometry, paint cache, and outer adapters, and cap them at 42 and 430 owned
  lines. Diagnostics fall to 529 owned lines and the final visual coordinator
  falls to 703 raw and 661 owned lines;
- `reorder_landing_paint_policy.py` now owns the active and provisional
  outline-style constants and construction of immutable landing paint state.
  The visual coordinator applies state transitions and observability around
  that result without rebuilding style policy. The paint policy is pure,
  independent of landing state, cache, geometry policy, diagnostics, events,
  telemetry, and outer adapters, and capped at 59 owned lines. The final
  `PromptReorderLandingVisualOwner` is 706 raw and 660 owned lines with one
  remaining reason to change: coordinating the focused landing collaborators
  into prepared visual publication. Seventeen direct landing-owner contracts,
  four focused pointer hot-path contracts, strict typing/lint/format, and the
  executable dependency/budget graph pass. Landing ownership transfer is
  complete; drag-proxy coordination and the final combined prepared-visual
  publication remain active step-6 work;
- `build/prompt-editor-slice10-landing-owners-smoke.json` is source, caret,
  semantic, projection, visual, and structurally clean with one activation
  preview build. Its instrumented single repetition meets the timing target at
  5.33 ms p50 and 12.14 ms p95 under 34.01 percent competing CPU, but it is
  retained as provisional structural evidence rather than a controlled
  baseline comparison;
- `build/prompt-editor-slice10-landing-geometry-smoke.json` repeats the exact
  later-separator pointer lifecycle after the pure-geometry transfer with zero
  source, caret, semantic, projection, visual, or structural violations and
  one activation preview build. Its instrumented single repetition records
  2.98 ms p50, 6.59 ms p95, and 7.60 ms maximum under 28.05 percent competing
  CPU. It is focused structural evidence, not the controlled
  baseline-versus-candidate performance comparison required to accept the
  completed slice;
- `build/prompt-editor-slice10-landing-diagnostics-smoke.json` preserves the
  same source, caret, semantic, projection, visual, and structural invariants
  after diagnostic ownership transfer, with one activation preview build and
  no new pointer-time rebuild, fallback, or cache work. Its instrumented
  single repetition records 2.52 ms p50, 6.24 ms p95, and 8.42 ms maximum
  under 27.83 percent competing CPU; it remains focused structural evidence,
  not the controlled acceptance comparison;
- `build/prompt-editor-slice10-landing-state-publication-smoke.json` preserves
  all source, caret, semantic, projection, visual, and structural invariants
  after the immutable-state transfer, including one activation preview build
  and no added pointer-time rebuild, fallback, or cache work. Competing CPU was
  48.18 percent and the instrumented maximum was 24.75 ms, so no latency claim
  is accepted from this run; it supplies structural evidence only;
- `build/prompt-editor-slice10-landing-event-owner-smoke.json` remains source,
  caret, semantic, projection, visual, and structurally clean after event
  ownership transfer, with one activation preview build and no added
  pointer-time rebuild, fallback, or cache work. Competing CPU was 61.25
  percent and the timing target was not met, so this instrumented run is
  accepted only as structural evidence and makes no latency claim;
- `build/prompt-editor-slice10-landing-final-owner-smoke.json` preserves the
  exact later-separator pointer lifecycle after the final paint-policy split
  with zero source, caret, semantic, projection, visual, or structural
  violations, one activation preview build, and no added pointer-time rebuild,
  fallback, or cache work. Competing CPU was 54.18 percent and the
  instrumented timing target was not met, so this is structural evidence only
  and no latency claim is accepted;
- drag-proxy visual coordination now belongs to the focused
  `PromptReorderDragProxyVisualOwner`. It owns the widget boundary, immutable
  render-state publication through a narrow local port, exact cached-state
  reuse, font and palette invalidation, host-relative placement, timing
  publication, z-order, visibility, lifecycle, and operational counters. The
  overlay no longer mirrors the proxy widget, host, render-state factory, or
  placement as four independent fields; geometry and interaction adapters
  consume the owner directly. The obsolete broad
  `PromptReorderDragProxyStateFactory` service-locator protocol and package
  export are deleted rather than retained as compatibility scaffolding;
- direct drag-proxy-owner characterization and the focused production overlay
  scenarios cover render publication and reuse, placement timing, parent
  changes, show/hide/close, Escape bounds, projection-engine movement, LoRA
  chips, split emphasis, counter reset, font invalidation, unchanged-target
  pointer work, target changes, pointer release, and paint. Targeted format,
  Ruff, strict mypy, and the executable direction/budget guard pass. The
  focused owner is capped at exactly 233 owned lines. The guard requires state,
  widget, and gesture policy to flow into the visual owner, prohibits that
  owner from depending on landing, preview-paint, raster, render, view, or
  outer-adapter concerns, and forbids restoration of the deleted overlay
  mirrors or broad protocol. Drag-proxy ownership transfer is complete;
- `build/prompt-editor-slice10-drag-proxy-owner-smoke.json` preserves the exact
  later-separator pointer lifecycle with zero invariant and zero structural
  violations, current semantic and projection state, and no exposed new
  pointer-time rebuild or fallback. Its instrumented single repetition records
  8.27 ms p50, 19.63 ms p95, and 22.36 ms maximum under 48.69 percent competing
  CPU. The run is accepted only as behavioral and structural abuse evidence;
  no performance comparison or latency claim is accepted. The final combined
  prepared-visual publication remains the active migration-step-6 transfer;
- the final combined visual-frame authority is now
  `PromptReorderPreparedVisualOwner`, not a stateless paint helper or overlay
  mirror. It owns the monotonically revisioned immutable publication containing
  passive overlay render state, atomic surface chrome/suppression state, paint
  mode, and unsafe transient ownership. The former
  `reorder_paint_publication.py`, free preparation function, overlay
  `_render_state_sync_revision`, overlay suppression dictionary, and
  imperative suppression sync helper are deleted. Drag-start synchronization
  now observes the authoritative prepared publication revision rather than a
  second shell counter;
- `PromptReorderSurfaceVisualStateOwner` owns the receiving surface's chrome
  snapshot, exact suppression identities, projection-context binding, no-op
  reuse, and revision as one immutable state transition. The projection
  surface no longer stores independent chrome and suppression fields. The
  production prepared-visual path publishes both together and therefore
  performs at most one render-frame publication and viewport invalidation per
  logical visual frame; equal state is an exact no-op, while value-equal but
  identity-distinct suppression snapshots are republished to reject stale
  ownership. The former host-facing partial setters are deleted across the
  owner, surface, widget, protocol, stub, and shell inventories; production
  and tests publish the same atomic value;
- direct owner and in-process production contracts cover combined publication,
  revision and current-publication identity, exact no-op reuse, stale-equal
  suppression replacement, preview teardown, atomic surface frame count,
  chrome-only surface text, animation suppression, raster stability, pointer
  release, unchanged-target work, target-change work and paint, font
  invalidation, passive-view hosting, and stale preview snapshots. Targeted
  format, Ruff, strict mypy for the changed typed owners, and the executable
  dependency/budget graph pass. Exact owned-line ceilings are 173 for
  `reorder_prepared_visual.py` and 165 for
  `projection/reorder_surface_visual_state.py`; the mixed overlay and geometry
  mixin fall to 1,218 and 1,409 owned lines and remain prohibited extension
  targets. The direction graph requires render and projection-surface values
  to flow into prepared visual state, then outward to surface, view, overlay,
  widget, and composition adapters, and enforces absence of the old module and
  shell mirrors;
- `build/prompt-editor-slice10-prepared-visual-owner-smoke.json` preserves the
  exact later-separator pointer lifecycle with zero invariant and zero
  structural violations, current semantic and projection state, and the
  established one-build activation budget. The harness diagnostics now consume
  the animation and surface visual publications instead of deleted presenter
  and shell fields. Its instrumented single repetition records 8.01 ms p50,
  16.19 ms p95, and 18.76 ms maximum under 56.55 percent competing CPU. The
  run is accepted only as behavioral and structural abuse evidence; no timing
  comparison or latency claim is accepted. Migration step 6 is complete. The
  controlled slice comparison remains required after the remaining adapter
  reductions so it measures the exact final candidate rather than an
  intermediate tree;
- migration step 7 has begun with a complete autoscroll authority transfer.
  `PromptReorderAutoscrollOwner` now owns the timer, pointer-edge policy,
  scrollbar mutation, latest pending invalidation, rapid-tick coalescing,
  consume/clear lifecycle, target-refresh observation, and all associated
  counters. The old controller type, overlay pending-invalidation field, four
  duplicate overlay counters, counter resets, and the forwarding clear helper
  are deleted. Its callback is now a zero-argument outer refresh notification;
  mutable invalidation state never flows back into the dynamic shell;
- direct owner coverage freezes moved and boundary-no-op ticks, exact latest
  invalidation consumption, coalescing, pending truth, flush, target refresh,
  and counter reset. Focused in-process production contracts preserve
  scrollbar movement and projection-rebuild budgets. Targeted format, Ruff,
  strict mypy, and a dedicated dependency/absence/budget guard pass. The owner
  is capped at 253 owned lines, while the overlay, geometry mixin, and
  interaction mixin fall to 1,211, 1,395, and 1,037 owned lines. Autoscroll
  depends only on the lower observability port; composition constructs it,
  overlay ports type it, and the overlay shell receives the instance without
  importing its implementation;
- `build/prompt-editor-slice10-autoscroll-owner-smoke.json` drives the
  production wildcard pointer-drag autoscroll and cancel lifecycle with zero
  invariant and zero structural violations. It records one scheduled, one
  flushed, and one target-refresh invalidation under the sole owner with no
  unexpected projection rebuild. Its instrumented repetition records 0.76 ms
  p50, 27.98 ms p95, and a harness wait-inclusive 140.39 ms maximum under 50.88
  percent competing CPU. The run is accepted only as behavioral and structural
  evidence; no latency comparison or claim is accepted. Animation
  presentation, gesture lifecycle, and the remaining dynamic mixin contracts
  remain active migration-step-7 work;
- animation presentation no longer enters through a dynamic shell mixin.
  `PromptReorderAnimationPresentationOwner` now owns generation truth,
  displacement-session lifecycle, plan construction and count, held-chip
  target derivation, visual presenter publication, raster generation,
  animation cancellation/settlement, currently painted start rectangles, and
  animated pointer-region state. Its APIs consume explicit typed geometry,
  layout, visual, region, target, and order inputs; it has no overlay host
  Protocol, `Any`, dynamic attribute access, widget query, or dependency on
  render/view/surface/controller/composition adapters;
- the old `reorder_overlay_animation.py` mixin is deleted with all shell-owned
  animation presenter, planner, displacement, generation, animated-region, and
  plan-counter fields. The overlay retains only the two required public
  animation-port methods and one outer frame adapter that fans an immutable
  publication into pointer regions and prepared paint. Interaction and geometry
  paths call the typed owner directly; the forwarding cancel/settle helpers are
  deleted. Presenter duration control now flows through the visual and
  presentation owners rather than tests mutating nested presenter fields;
- the first focused production run exposed a real equivalence defect in the
  extracted start-rectangle policy: when preview mode was active but a segment
  had no preview visual yet, the new owner failed to fall back to its stable
  live visual, producing an inert plan. The owner now preserves the former
  preview-first/live-fallback rule in one helper used by both planning and
  pointer synchronization. A direct owner regression freezes the partial
  preview case. All 34 focused animation, pointer-target, paint, suppression,
  wrapped-layout, and overlay contracts then pass;
- targeted format, Ruff, strict mypy, direct owner tests, and the executable
  dependency/absence/budget graph pass. Exact ceilings are 337 owned lines for
  animation presentation and 178 for its visual lifecycle owner; the overlay,
  geometry mixin, and interaction mixin are 1,242, 1,399, and 1,030 owned
  lines. Although the overlay retains its required public adapter surface, the
  deleted 245-line dynamic mixin and six duplicate shell authorities cannot
  return under the guard;
- `build/prompt-editor-slice10-animation-presentation-smoke.json` preserves
  the later-separator pointer reorder lifecycle with zero invariant and zero
  structural violations, including the one-build activation budget and current
  semantic/projection state. Its instrumented repetition records 8.64 ms p50,
  14.44 ms p95, and 20.16 ms maximum under 52.45 percent competing CPU. The
  run is accepted only as behavioral and structural evidence; no latency
  comparison or claim is accepted. Gesture lifecycle and the remaining
  geometry/interaction dynamic contracts remain active migration-step-7 work.
- reorder gesture instrumentation now has one typed
  `PromptReorderInteractionMetricsOwner`. It owns gesture/event/work-unit
  identities, pointer-loop lifecycle, structural classifications, counter
  resets, timing maxima, and immutable on-demand diagnostics. The overlay
  shell's 37 instrumentation and pointer-loop fields are deleted, and the
  geometry and interaction paths can record only semantic outcomes through
  constant-time owner methods. Snapshot and dictionary construction occur only
  when diagnostics or the harness explicitly query them; no scan, hash,
  allocation, service query, layout work, or instrumentation fan-out was added
  to paint or ordinary pointer processing;
- direct owner coverage freezes reset and completed-gesture behavior, event and
  work identities, exceptional pointer-loop exit, unexpected-work
  classification, scheduler decisions, geometry reuse, target results, timing
  maxima, and the stable harness schema. All 28 serial performance-counter
  contracts, 20 serial overlay contracts, 48 focused interaction, geometry,
  autoscroll, animation, and landing contracts, targeted format, Ruff, strict
  mypy, and the executable dependency/absence/budget guard pass. The focused
  owner is capped at 398 owned lines; the overlay, geometry mixin, and
  interaction mixin fall to 1,203, 1,396, and 892 owned lines. The guard
  rejects restoration of any shell instrumentation or pointer-loop field;
- `build/prompt-editor-slice10-interaction-metrics-owner-smoke.json` preserves
  the later-separator pointer reorder lifecycle with current semantic and
  projection state and zero invariant or structural violations. Its
  instrumented repetition records 6.28 ms p50, 13.04 ms p95, and 14.85 ms
  maximum under 48.35 percent competing CPU. The run is accepted only as
  behavioral and structural evidence; no latency comparison or claim is
  accepted. The remaining migration-step-7 work is the complete typed gesture
  lifecycle and geometry/interaction adapter transfer; the two dynamic mixins
  are still forbidden as a final shape.
- keyboard reorder now flows through one typed
  `PromptReorderKeyboardInteractionOwner`. It owns readiness checks, one-time
  base-drag preparation, horizontal and vertical navigation coordination,
  committable-target policy, gesture target/preferred-x publication, and
  keyboard displacement intents. It consumes only focused geometry, gesture,
  animation, and prepared-visual ports and returns one immutable result bound
  to the authoritative interaction-geometry publication. The outer adapter
  only mirrors that publication into the still-active shell and emits its
  existing notifications; the former duplicated preparation, target
  resolution, navigation, animation, and gesture-write algorithms are deleted
  from the dynamic interaction mixin;
- direct owner coverage freezes first-move preparation, subsequent reuse,
  horizontal/vertical routing, displacement intent publication, gesture state,
  committable target resolution, and missing-context no-op behavior. Twelve
  production keyboard reorder, blank-line, separator, animation, suppression,
  boundary, and commit contracts pass, as do 17 focused owner/geometry and
  dependency tests plus targeted format, Ruff, and strict mypy. The owner is
  capped at 283 owned lines with no dependency on overlay, view, surface,
  widget, controller, composition, or either dynamic mixin. The interaction
  mixin falls from 892 to 813 owned lines; the overlay is 1,208 and geometry
  mixin remains 1,396;
- `build/prompt-editor-slice10-keyboard-interaction-owner-smoke.json` exercises
  the production wildcard-document Alt+Right reorder and release lifecycle.
  All four applicable operation classes are covered, semantic/projection state
  is current, and correctness and structural budgets pass. The instrumented,
  externally contended single repetition is retained only as behavioral and
  structural evidence; its timing target is explicitly not accepted or used
  for a latency claim.
- interaction observability now has one typed
  `PromptReorderInteractionDiagnosticsOwner`. It owns validated event/timing
  dispatch, correlated slow-path attribution, anomaly and expected-geometry
  classification, protected-pointer unexpected-work logging, and the complete
  gesture-summary schema. The telemetry and metrics authorities flow into this
  owner; outer interaction and geometry adapters only supply explicit semantic
  context. Five duplicate logging/anomaly methods and the 107-line mixed
  summary algorithm are deleted from the dynamic interaction mixin. Landing
  and drag-proxy collaborators receive the focused owner's bound event/timing
  ports directly;
- direct diagnostics coverage freezes gesture/event correlation, anomaly and
  expected-outcome counts, pointer-loop gating, timing/slow-path forwarding,
  collaborator-counter merging, missing-geometry derivation, and summary
  formatting. All 28 serial performance-counter and 20 serial overlay
  contracts pass on the exact tree, together with direct owner and executable
  dependency/absence/budget coverage plus targeted format, Ruff, and strict
  mypy. Diagnostics are capped at 237 owned lines and depend only on lower
  interaction metrics and immutable landing counter values; they cannot import
  telemetry implementation, overlay, view, surface, widget, controller,
  composition, or either mixin. The interaction mixin falls to 669 owned
  lines; overlay and geometry mixin are 1,212 and 1,396;
- `build/prompt-editor-slice10-interaction-diagnostics-owner-smoke.json`
  preserves the later-separator pointer reorder lifecycle with current
  semantic/projection state and zero invariant or structural violations. Its
  instrumented repetition records 6.51 ms p50, 15.80 ms p95, and 20.33 ms
  maximum. This is behavioral and structural evidence only; no controlled
  baseline comparison or latency claim is inferred.
- optional host intent callbacks now belong to one
  `PromptReorderInteractionIntentOwner`. Drag, commit, and preserved public
  cancel ports have one typed replacement/disconnection lifecycle; the three
  shell callback fields and three dynamic emission helpers are deleted.
  Pointer start/move/end and commit publication call the owner directly. Direct
  owner tests cover disconnected, connected, replaced, and preserved cancel
  behavior; focused controller, production pointer-release/keyboard-commit,
  dependency, format, Ruff, and strict mypy checks pass. The owner is capped at
  74 owned lines and depends only on application intents and the typed drag
  value. The interaction mixin falls to 651 owned lines and the overlay to
  1,210;
- `build/prompt-editor-slice10-interaction-intent-owner-smoke.json` preserves
  adjacent-regional-separator pointer reorder and release with current
  semantic/projection state and zero invariant or structural violations. Its
  one instrumented repetition records 3.47 ms p50, 8.08 ms p95, and 11.49 ms
  maximum; it is structural/behavioral evidence rather than a controlled
  latency comparison;
- `PromptReorderInteractionGeometryState` is now the sole session-side
  document, layout, reorder-state, preview-snapshot, preview-target, and chip
  order publication consumed by the overlay vertical. Fourteen independently
  mutable shell mirrors are deleted across the overlay and both dynamic
  mixins; every read derives from one immutable geometry publication and every
  transition remains inside `PromptReorderInteractionGeometry`. Direct-overlay
  characterization now carries its immutable document input explicitly and
  queries the public current/base-drag layout ports. The abuse host also uses
  the base-drag query port, while rendered-preview diagnostics read the
  authoritative geometry publication rather than deleted shell state. The
  executable architecture guard rejects restoration of any deleted session
  mirror. The overlay, geometry mixin, and interaction mixin are now 1,190,
  1,395, and 590 owned lines;
- all 15 direct interaction-geometry/owner contracts, 28 structural-counter
  cases, 20 production overlay contracts, the focused abuse-host and
  structural-policy contracts, targeted format, Ruff, and strict mypy checks
  pass. `build/prompt-editor-slice10-geometry-session-authority-smoke.json`
  preserves the known later-separator pointer lifecycle with zero source,
  caret, semantic, projection, visual, or structural violations.
  `build/prompt-editor-slice10-geometry-session-authority-visual.json` also
  preserves the rendered maximum-span pointer preview with zero correctness or
  structural violations. Both are instrumented structural evidence; their
  cold/contended latency outliers support no performance claim;
- gesture identities, pointer-loop state, scheduler/sync classifications, and
  timing maxima now belong to one interaction-layer
  `PromptReorderInteractionMetricsOwner` shared explicitly by controller and
  overlay through composition. The owner no longer lives under overlay visual
  adapters. Eight overlay metric callback/query methods, controller-side
  optional `getattr` probes, and the duplicate metrics API on controller test
  overlays are deleted. Preview scheduling and projection timing call the
  shared owner directly with no per-request lambda allocation on the active
  overlay path. Composition provides the owner through the typed overlay
  factory boundary, and the executable graph rejects restoration of the old
  overlay module or adapter methods. The reorder controller falls to 1,337
  owned lines/48 methods and the interaction mixin to 590 owned lines;
- 25 focused metrics, diagnostics, scheduler, controller, LoRA-refresh, and
  direction cases plus 28 structural-counter and 20 production overlay
  contracts pass. Targeted format, Ruff, and strict mypy checks pass.
  `build/prompt-editor-slice10-shared-interaction-metrics-final.json`
  preserves the later-separator pointer lifecycle with zero source, caret,
  semantic, projection, visual, or structural violations and the established
  one-build activation budget. Its cold instrumented activation is structural
  evidence only and supports no latency claim;
- post-drop release geometry and checkpoint classification now belong to one
  focused `PromptReorderDropCommitDiagnostics` owner. Its immutable
  `PromptReorderDropCommitState` is the sole retained authority for shadow
  visual, shadow geometry, target, placement, segment, gesture, and event
  identity between pointer release and surface republish. Seven independently
  mutable shell fields, the geometry mixin's release/checkpoint algorithms, and
  its duplicate mismatch policy are deleted. The owner consumes immutable
  landing and interaction-geometry publications and emits only diagnostic
  outcomes; the geometry mixin cannot import it. Gesture-summary aggregation
  likewise consumes immutable geometry publications through the existing
  interaction-diagnostics owner, so the dynamic interaction mixin returns to
  its pre-transfer 590-line ceiling instead of absorbing the new boundary.
  The geometry mixin falls from 1,395 to 1,111 owned lines; the overlay remains
  below its existing ceiling at 1,203 owned lines. Executable graph and
  source-state guards cap both focused diagnostic owners and reject restoration
  of any deleted post-drop shell mirror;
- three direct post-drop owner contracts, two interaction-diagnostics
  contracts, the focused direction guard, all 20 production overlay contracts,
  and all 27 reorder structural-counter contracts pass. Targeted format, Ruff,
  and strict mypy checks pass for the changed owner, adapters, and tests.
  `build/prompt-editor-slice10-drop-commit-diagnostics-owner.json` preserves
  the exact later-separator pointer lifecycle with zero source, caret,
  semantic, projection, visual, or structural violations and no added
  pointer-time rebuild or fallback work. Its single instrumented repetition is
  structural evidence only and supports no latency claim;
- raw pointer ingress now depends on three directionally narrow boundaries:
  semantic gesture control, QWidget focus/cursor effects, and the existing
  prompt-safe event logger. The former seven-purpose
  `PromptReorderPointerController`, its generic `_controller` reference, and
  the dynamic interaction mixin's telemetry forwarding method are deleted.
  The input owner stores the bound logger once and calls it directly, removing
  one shell dispatch without adding per-event allocation or lookup;
- drag-proxy press preparation, stale-preparation rejection, render-input
  construction, cached state publication, placement, and widget lifecycle now
  stay in `PromptReorderDragProxyVisualOwner`. The shell's uninitialized
  `_prepared_drag_proxy_segment_index` authority and four geometry-mixin proxy
  adapter methods are deleted. A focused
  `PromptReorderPerformanceCountersOwner` derives snapshots from the geometry,
  interaction, proxy, autoscroll, animation, raster, and landing owners without
  copying their state; it is queried only by gesture summaries and explicit
  diagnostics, never by ordinary pointer movement. The geometry mixin falls to
  1,049 owned lines and the interaction mixin to 583. The outer overlay is
  1,231 owned lines, below its unchanged 1,272 ceiling; its added lines are
  explicit construction and Qt-event wiring for the transferred owners rather
  than feature policy;
- the direct drag-proxy owner contract, direction/source guards, all 20
  production overlay contracts, and all 27 structural-counter contracts pass,
  with targeted format, Ruff, and strict mypy checks clean.
  `build/prompt-editor-slice10-pointer-ingress-proxy-owner.json` preserves the
  exact later-separator pointer lifecycle with zero source, caret, semantic,
  projection, visual, or structural violations, and no added pointer-time
  rebuild or fallback work. Its instrumented timing is structural evidence,
  not a controlled latency claim;
- keyboard reorder now carries the existing typed
  `PromptReorderKeyboardMoveIntent` through the controller and overlay boundary
  without converting it into four direction-specific methods. The controller's
  branch ladder, four broad overlay-port methods, four test-double methods, and
  the interaction mixin's private horizontal/vertical adapter are deleted.
  `PromptReorderKeyboardInteractionOwner.move()` is the single direction
  decoder and continues to publish the same immutable result. Eighteen focused
  keyboard/controller/keymap contracts and all 48 production
  overlay/structural-counter contracts pass. The reorder controller falls from
  1,337 to 1,322 owned lines and the interaction mixin from 583 to 549;
- allocation-neutral pointer destination resolution now belongs to
  `PromptReorderPointerTargetResolutionOwner`. It owns logical held-rect
  construction, tracker invocation, active-placement publication, changed and
  no-change classification, target mutation, structural counters, and
  fast-path diagnostics. It returns the tracker's existing result object, so
  ordinary pointer movement gains no result allocation. The shell-owned
  tracker, geometry mixin's drag-rect builder, and private harness monkeypatches
  into the tracker are deleted; production counter assertions and two direct
  owner contracts cover the same obligations through supported owner state.
  The owner depends only inward on immutable geometry state, the projection
  tracker, gesture state, metrics, telemetry, and diagnostics. The executable
  graph prevents the geometry mixin from importing back outward. The geometry
  mixin falls from 1,049 to 956 owned lines while the overlay remains below its
  unchanged ceiling at 1,237;
- the focused hostile
  `later-regional-separator-pointer-reorder-recovery` scenario remains
  behaviorally and structurally clean after the pointer-target transfer.
  `build/prompt-editor-slice10-pointer-target-owner.json` records no source,
  caret, selection, feature, visible-state, visual-caret, projection,
  semantic, or structural violation. The lane is instrumented structural
  evidence only and is not treated as a controlled latency comparison;
- live reorder visual preparation now has one authoritative
  `PromptReorderLiveVisualOwner`. Its immutable publication owns the bounded
  source/range/viewport identity, projection-owned chip geometry, adapted live
  visuals, semantic owned ranges, and complete projection visual snapshots.
  The owner alone decides unchanged reuse versus structural rebuild, reports
  geometry-count anomalies, and records live-build timing. The shell no longer
  mirrors live visuals, live chip geometry, live snapshot mappings, or the last
  live key, and the geometry mixin no longer builds source ranges, geometry
  keys, snapshots, or visuals. The unused `PromptReorderVisualSnapshotCache`
  and its counters are deleted rather than retained as migration scaffolding;
- the refresh shell asks the live owner for one bounded candidate key and
  passes that same value back only when preparation runs. This deletes the
  former second full segment-range/key construction on changed refreshes while
  preserving the allocation-free unchanged overlay-refresh exit and the
  no-layout clearing behavior. Three direct owner contracts freeze immutable
  publication, exact-key reuse, invalidation, rebuild, and key inputs. The 48
  production overlay/structural-counter contracts, the executable dependency
  graph, targeted format/Ruff/strict-mypy checks, and the updated harness owner
  diagnostics pass. The dynamic geometry mixin falls from 956 to 837 owned
  lines/30 methods. The new focused owner is capped at 308/11, and the passive
  visual snapshot value module is 62/2;
- `build/prompt-editor-slice10-live-visual-owner.json` preserves the exact
  later-regional-separator pointer lifecycle with `correct=True` and
  `structural=True`, no source/caret/selection/feature/visual/projection/
  semantic violation, and no added projection rebuild or fallback work. The
  first run correctly exposed two abuse-harness reads of deleted shell mirrors;
  both invariant paths now read the authoritative owner publication. The
  report remains instrumented structural evidence, not a controlled latency
  claim;
- logical hotspot positioning and interaction styling now belong together in
  `PromptReorderPointerRegionVisualOwner`. It consumes only immutable live and
  preview visual publications, immutable interaction geometry state, gesture
  state, the stable region collection, drag-proxy stacking, visual style,
  metrics, and diagnostics. It owns region materialization, live-versus-preview
  placement, held-region exclusion, visibility, cursor shape, active/pressed/
  hovered/drag state, transparent-border validation, and correlated timing.
  Neither the geometry owner nor the visual sources depend back outward on it;
  the executable graph enforces that direction;
- the dynamic geometry mixin's `_update_pointer_region_geometry` and
  `_update_chip_states` algorithms are deleted, all callsites use the focused
  owner, and theme changes explicitly update its style. Start, end, and cancel
  no longer run the interaction-state pass twice after geometry sync; geometry
  sync already publishes that exact state. Two direct owner contracts cover
  live placement/state and held-chip preview exclusion. All 48 production
  overlay/structural-counter contracts, the dependency graph, and targeted
  format/Ruff/strict-mypy checks pass. The geometry mixin falls from 837 to 719
  owned lines/28 methods and the interaction mixin from 549 to 546/9. The new
  owner is capped at 221/5;
- `build/prompt-editor-slice10-pointer-region-visual-owner.json` remains
  `correct=True` and `structural=True` for the exact later-separator pointer
  lifecycle, with no source, caret, selection, feature, visual, projection,
  semantic, rebuild, or fallback violation. Its timing is instrumented and is
  not promoted to controlled baseline-versus-candidate evidence;
- pointer-selected target application now belongs to
  `PromptReorderPointerTargetTransitionOwner`. The existing resolution owner
  remains the sole allocation-neutral hit-test and target/placement mutator;
  the transition owner consumes its typed result and, only when `changed`,
  owns displacement intent, lazy viewport identity lookup, preview-layout
  publication, proxy stacking, preview event emission, surface-sync
  diagnostics, anomaly classification, and total timing. Three direct
  transition contracts cover unchanged input, a complete changed transition,
  and autoscroll signal suppression. The unchanged contract proves zero
  animation, viewport query, preview-layout build, proxy raise, or signal work
  after the resolver returns the same target;
- the dynamic geometry mixin's 102-line
  `_update_drop_target_from_global_position` path is deleted. All pointer and
  autoscroll callsites pass only overlay-local pointer facts into the typed
  transition owner. The former private viewport-key and preview-signal methods
  are explicit narrow adapter ports rather than cross-mixin private lookups.
  The unused `PromptReorderOverlayRenderState`, its no-op shell method, internal
  port method, and exports are deleted as dead migration scaffolding. Five
  focused resolver/transition contracts, all 48 production
  overlay/structural-counter contracts, the executable dependency graph, and
  targeted format/Ruff/strict-mypy checks pass. The geometry mixin falls from
  719 to 609 owned lines/27 methods. The focused transition owner is capped at
  293/3, and the outer overlay remains below its unchanged ceiling at
  1,270/71;
- `build/prompt-editor-slice10-pointer-target-transition-owner.json` preserves
  the exact later-regional-separator pointer lifecycle with `correct=True` and
  `structural=True`, no source/caret/selection/feature/visual/projection/
  semantic violation, and no added rebuild or fallback work. Its instrumented
  timing is not treated as controlled latency evidence;
- held-drag intent and retained shadow capture now belong to
  `PromptReorderHeldDragContextOwner`. One drag-start call selects the prepared
  pointer-region rect, then live-visual fallback, then the canonical 1x1
  fallback; publishes logical grab size/offset; resolves live and base-drag
  projection geometry; and captures the matching landing shadow with prepared
  region/proxy dimensions and gesture identity. Teardown clears the same
  gesture-owned context through this owner. Two direct contracts cover
  materialized-region precedence, complete shadow input, visual fallback, and
  atomic cleanup;
- the dynamic geometry mixin's drag-intent capture, source-rect fallback,
  clear, and held-shadow capture methods are deleted, and all start/end/cancel/
  session-reset callsites use the focused owner. The package façade now imports
  drag intent/phase, layout policy, overlay ports, and factories from their
  authoritative modules; six forwarding exports are removed from
  `reorder_overlay.py`. All 48 production overlay/structural-counter contracts,
  the executable dependency graph, two direct owner contracts, and targeted
  format/Ruff/strict-mypy checks pass. The geometry mixin falls from 609 to 548
  owned lines/23 methods. The held-context owner is capped at 159/4 and the
  outer overlay remains at its unchanged 1,272-line ceiling with 71 methods;
- `build/prompt-editor-slice10-held-drag-context-owner.json` remains
  `correct=True` and `structural=True` for the exact later-separator pointer
  lifecycle with no source/caret/selection/feature/visual/projection/semantic,
  rebuild, or fallback violation. Its timing remains instrumented rather than
  controlled comparison evidence;
- viewport identity for reorder projection reuse now belongs to
  `PromptReorderViewportGeometryOwner`. It derives the bounded position key
  solely from the editor viewport, document margins, and vertical scroll
  position. The overlay's duplicate `reorder_position_geometry_key` method is
  deleted, and the pointer-target transition depends directly on the focused
  viewport owner instead of querying the outer overlay;
- one direct viewport-owner contract, all three pointer-target transition
  contracts, all 48 production overlay/structural-counter contracts, the
  executable dependency graph, and targeted format/Ruff/strict-mypy checks
  pass. The outer overlay falls from 1,272 owned lines/71 methods to 1,259/70;
  the viewport owner is capped at 67/2. The graph guard enforces its one-way
  dependency on widget mapping and reorder state and forbids dependencies back
  to interaction geometry, transition, prepared/render/view, or outer-overlay
  modules;
- `build/prompt-editor-slice10-viewport-geometry-owner.json` remains
  `correct=True` and `structural=True` for the exact later-regional-separator
  pointer lifecycle with no invariant or structural violation and no text,
  projection, or semantic mismatch. Its timing remains instrumented rather
  than controlled comparison evidence;
- logical pointer-region placement identity now belongs to
  `PromptReorderPointerRegionVisualOwner` with the visual geometry it
  identifies. The shell's key cache, key builder, skip coordinator, and three
  private paths are deleted. Direct drag lifecycle syncs publish the same key,
  so a following unchanged refresh performs zero redundant region or proxy
  work. One owner contract covers initial publication, unchanged reuse,
  explicit invalidation, and rematerialization;
- broad refresh identity now belongs to
  `PromptReorderRefreshIdentityOwner`. It owns the last complete position and
  refresh publications, session reset, explicit invalidation, and construction
  from immutable geometry facts. Prompt source is fingerprinted once when the
  reorder session begins; repeated refresh-key construction consumes the
  cached fingerprint and performs no full-source scan. The former shell fields,
  key builder, layout/snapshot wrappers, and live-visual owner's duplicate key
  builder are deleted. Two direct contracts lock publication/invalidation
  semantics and exactly one fingerprint operation per session;
- autoscroll timer mutation, edge policy, pending invalidation, coalescing,
  scroll-step invalidation, animation settlement, geometry flush, pointer
  target refresh, diagnostics, and counters now belong to the single
  `PromptReorderAutoscrollOwner`. The composition-only autoscroll factory,
  callback/context-provider hooks, public pending-state mutation methods, and
  mixed geometry-mixin lifecycle methods are deleted. The overlay retains only
  its required thin host-facing flush adapter. Three direct contracts cover
  deferred step work, latest-only coalescing and target refresh, and the
  boundary no-op path;
- all 21 focused refresh/autoscroll/live/pointer/projection contracts, all 48
  production overlay and structural-counter contracts, both executable
  dependency-direction guards, targeted format/Ruff/strict-mypy checks, and
  diff hygiene pass. `SegmentReorderOverlay` falls from 1,259 owned lines/70
  methods to 1,162/66 and the dynamic geometry mixin falls from 548/23 to
  505/21. The focused pointer-region, refresh-identity, autoscroll, and
  live-visual owners are frozen at 272/11, 127/7, 315/17, and 278/12
  respectively;
- `build/prompt-editor-slice10-refresh-autoscroll-owner.json` remains
  `correct=True` and `structural=True` for the exact later-regional-separator
  pointer lifecycle with no invariant, source, caret, selection, feature,
  visual, projection, semantic, rebuild, or fallback violation. Comparison
  against the immediately preceding viewport-owner artifact preserves
  correctness and reports p50 4.521 -> 3.976 ms and p95 8.844 -> 6.683 ms;
  both runs are instrumented under uncontrolled system load, so the latency
  delta is diagnostic and not promoted to controlled performance evidence.
- projection-owned preview paint snapshots now have one focused
  `PromptReorderPreviewPaintSnapshotOwner`. It owns cache clearing, selected
  projection-snapshot requests, prepared-visual binding, and immutable
  publication. The shell's mutable preview-snapshot mapping and the geometry
  mixin's snapshot construction/preparation algorithms are deleted. Two direct
  contracts cover empty and selected publication; preview raster/render input
  reads the owner publication directly;
- `PromptReorderVisualModeOwner` is now the sole policy for changed-order,
  painted-layout, and live-versus-preview selection. Pointer-region and
  pointer-target owners depend inward on that concrete policy rather than
  retaining structurally similar local policy ports. The geometry mixin's
  duplicated preview-mode and painted-layout methods are deleted.
  `PromptReorderVisualSessionOwner` atomically publishes immutable
  source-lineage and display-chip facts; the shell's mutable source identity
  and segment mapping are deleted, and intent/render collaborators consume the
  revisioned publication. Three visual-mode contracts and one immutable
  session contract freeze these decisions;
- landing-request assembly now belongs to
  `PromptReorderLandingRequestOwner`. One build reads the authoritative
  geometry, gesture, metrics, preview visual, visual session, visual mode, and
  viewport owners once, selects landing geometry and target visual, and
  derives expected preview identity from one bounded viewport key. This
  removes the geometry mixin's target scan, preview-chip lookup, request
  builder, and the outer shell's two duplicate preview-identity helpers. It
  also removes the former second viewport/content lookup inside each request
  without adding a source scan, layout build, hash, callback, or service query
  to the hot path. The direct owner contract freezes coherent request facts
  and exactly one viewport lookup;
- focused owner and landing contracts pass, as do all 48 production overlay
  and structural-counter contracts: the first production pass exposed two
  tests coupled to the deleted private preview-chip helper, while the other 46
  passed; those two now assert the same rendered geometry through the existing
  public preview-rect adapter and pass. The executable direction/absence/budget
  guard and strict mypy pass. Focused formatting and Ruff are clean. The
  overlay falls to 1,158 owned lines/64 methods and the dynamic geometry mixin
  to 374/14. Exact focused ceilings are 119 lines for preview paint snapshots,
  77 for visual mode, 94 for visual session, and 118 for landing requests;
  restored shell mirrors, duplicate policies, target scans, request builders,
  and identity helpers are rejected by the guard.
- `PromptReorderPreviewGeometryRefreshOwner` now owns the complete
  changed-preview transition: one bounded viewport identity read, prepared
  visual publication, unchanged suppression, structural reuse/build counters,
  preview paint-snapshot invalidation, landing-placement attachment,
  initial-shadow readiness, and correlated timing/budget diagnostics. The
  dynamic geometry mixin's 84-line refresh coordinator is deleted, and both
  shell callsites consume the focused owner directly. Two direct contracts
  prove that unchanged input performs no paint, landing, or diagnostic
  follow-up work and that changed input publishes the complete lifecycle;
- all 48 production overlay/structural-counter contracts, the two direct
  transition contracts, the executable dependency/absence/budget guard,
  targeted format/Ruff, and strict mypy checks pass. The new owner is capped at
  129 owned lines/2 methods and cannot depend on outer overlay, mixin, view,
  surface, controller, widget, composition, render, raster, or prepared-paint
  adapters. The geometry mixin falls from 374 owned lines/14 methods to
  292/12; the overlay is 1,169/64 because it retains only explicit construction
  wiring for the transferred owner;
- `build/prompt-editor-slice10-preview-refresh-owner.json` preserves the exact
  later-regional-separator pointer lifecycle with `correct=True` and
  `structural=True`, no invariant or owner-work violation, and the established
  one-build activation budget. Its p50 4.033 ms and p95 9.091 ms are retained
  only as instrumented structural diagnostics, not as controlled performance
  evidence.
- ordinary pointer movement now has one
  `PromptReorderPointerMoveOwner`. It owns stale-region rejection, typed move
  intent publication, event/work-unit/pointer-loop accounting, proxy
  movement, allocation-bounded local coordinate mapping, target transition,
  autoscroll, sampled diagnostics, elapsed classification, and the slow-path
  budget check. The owner stores the bound coordinate adapter once; the
  unchanged/stale path performs no intent, proxy, mapping, target, autoscroll,
  or metric work, and the ordinary unsampled path adds no result object,
  context dictionary, callback lookup, scan, hash, layout, projection, paint,
  or service query;
- the dynamic interaction mixin's 142-line pointer-move algorithm is deleted.
  The outer overlay retains only the required three-line input adapter.
  Direct contracts cover stale zero-work rejection and one complete unsampled
  transition with balanced pointer-loop state. All 48 production
  overlay/structural-counter contracts, the executable dependency/absence/
  budget guard, targeted format/Ruff, and strict mypy checks pass. The focused
  owner is frozen at 200 owned lines/2 methods; the interaction mixin falls
  from 544 owned lines/9 methods to 399/8. The overlay is 1,186/65 because its
  only added method is the final host-facing pointer adapter;
- `build/prompt-editor-slice10-pointer-move-owner.json` preserves the exact
  later-regional-separator pointer lifecycle with `correct=True` and
  `structural=True`, no invariant or owner-work violation, and unchanged
  projection/geometry budgets. Its p50 4.996 ms and p95 10.025 ms remain
  instrumented structural diagnostics and are not promoted to controlled
  performance evidence.
- held/base drag teardown now completes atomically in
  `PromptReorderHeldDragContextOwner`: drag-intent geometry, base-drag segment,
  interaction geometry context, retained held shadow, and keyboard preferred-x
  are cleared by one lifecycle owner. The interaction mixin's duplicate
  `_clear_base_drag_context` path and its two callsites are deleted. Direct
  cleanup plus focused pointer drop/cancel contracts pass; the focused owner
  grows deliberately from 159 to 169 owned lines to absorb the complete
  responsibility rather than leave a forwarding shim;
- the final host-facing drag preparation, keyboard move, keyboard visual-event,
  and performance-counter queries now live directly on the outer overlay
  adapter. Their duplicate dynamic-mixin methods and result adapter are
  deleted; no policy moved outward, because keyboard direction/placement stays
  in `PromptReorderKeyboardInteractionOwner`, proxy rendering stays in its
  visual owner, and counters remain on the diagnostics-only counter owner.
  Focused pointer-preparation and keyboard changed/no-op contracts pass with
  targeted format/Ruff/strict-mypy checks;
- gesture-driven preview-layout publication now belongs to
  `PromptReorderPreviewLayoutTransitionOwner`. It rejects missing-document
  state before viewport work, otherwise performs one bounded viewport lookup,
  publishes one geometry update from immutable gesture facts, and restacks the
  proxy. The geometry mixin's cross-mixin update method is deleted and start,
  end, cancel, and refresh callsites consume the focused owner directly. Two
  direct changed/unchanged contracts, three focused pointer finish/cancel
  contracts, and the executable dependency/absence/budget guard pass. The
  owner is frozen at 59 owned lines/2 methods; the geometry mixin is 278/11,
  and the interaction mixin is now exactly the three remaining start/end/
  cancel transitions at 340/3. The overlay is 1,233/68, still under its frozen
  1,272/72 ceiling, with those added methods limited to its intended final
  host-adapter surface.
- four geometry-mixin landing methods had no caller anywhere in source, tests,
  or harnesses and are deleted as dead migration scaffolding rather than moved.
  The remaining insertion-marker policy now belongs to
  `PromptReorderInsertionMarkerOwner`: inactive-gesture rejection, landing
  suppression, prepared target selection, fixed-width marker geometry,
  fallback counting, and missing-target diagnostics have one inward-only
  owner. A direct zero-work inactive contract and focused landing/target paint
  contracts pass with targeted format/Ruff/strict-mypy and executable
  dependency/absence/budget checks. The owner is frozen at 95 owned lines/2
  methods, the geometry mixin falls from 278 to 182 owned lines, and the
  overlay remains under its ceiling at 1,242/68;
- `build/prompt-editor-slice10-preview-layout-marker-owner.json` preserves the
  exact later-regional-separator pointer lifecycle with `correct=True` and
  `structural=True`, no invariant or owner-work violation, and unchanged
  projection/geometry budgets. Its p50 4.599 ms and p95 10.607 ms are
  instrumented diagnostics only.
- prepared reorder frames now have one
  `PromptReorderRenderPublicationOwner`. It reads each immutable geometry,
  gesture, live-visual, preview-visual, paint-snapshot, animation, and metrics
  publication once; selects one active raster lane; prepares one atomic
  overlay/surface publication; diagnoses unsafe transient ownership; and
  publishes through construction-bound passive surface/view adapters. The
  prepared-visual revision and clear lifecycle moved with the transition
  instead of remaining shell state. Preview order is scanned once rather than
  twice, the landing request is built at most once and shared with marker
  suppression, inactive frames stop before landing construction, inactive
  paint lanes reuse immutable empty mappings, and no per-frame callback,
  service query, layout build, projection build, full-document scan, or
  instrumentation was added;
- post-drop actual visual selection and live geometry lookup now belong to the
  immutable `PromptReorderDropActualObservation` resolver. The resolver was
  extracted from the already-large diagnostic classifier, reducing
  `reorder_drop_commit_diagnostics.py` to 437 owned lines/6 methods while
  preserving preview-first visual fallback and live projection-geometry
  authority. Both callsites consume the resolver directly. The obsolete
  `reorder_overlay_geometry.py` mixin is deleted completely, together with its
  dynamic host access and every render, style, visual, and geometry adapter;
- two direct render-publication contracts prove live zero-landing work,
  preview single-request preparation, single active raster-lane work, atomic
  two-surface publication, and clear republishing. Direct insertion-marker and
  post-drop observation contracts, all 48 production overlay/structural-counter
  contracts, the executable dependency/deletion/absence/budget guard,
  targeted formatting/Ruff, and strict mypy pass. The render owner is capped at
  256 owned lines/10 methods after absorbing the authoritative visual-style
  query used by drag preparation, the observation resolver at 77/1, and the
  insertion-marker owner remains below its frozen ceiling at 93/2. The outer
  overlay remained below its frozen 1,272/72 ceiling through the transfer;
- `build/prompt-editor-slice10-render-publication-owner.json` preserves the
  exact later-regional-separator pointer lifecycle with `correct=True` and
  `structural=True`, exact source/caret/selection/feature state, current
  projection and semantics, and no invariant, diagnostic, or owner-work
  violation. Its p50 3.671 ms and p95 8.055 ms are instrumented structural
  diagnostics only, not controlled performance evidence.
- pointer drag lifecycle now has two cohesive transition owners.
  `PromptReorderPointerDragStartOwner` owns pre-threshold held-chip preparation
  and the complete threshold-crossing transition into a drag, including
  coherent geometry selection, counters, base layout, intent capture, initial
  target resolution, proxy publication, autoscroll, and diagnostics.
  `PromptReorderPointerDragCompletionOwner` owns release commit, cancellation,
  visual teardown, actual-drop observation, final intent publication, summary
  diagnostics, and gesture completion. The start and completion owners cannot
  import each other or any overlay, view, widget, controller, composition, or
  panel root. Their exact collaborators are bound once at construction;
  duplicate starts and stale releases return before geometry, mapping,
  publication, allocation, scan, hash, layout, projection, paint, or service
  work;
- immutable geometry-to-application commit conversion now belongs to the pure
  `prompt_reorder_commit_snapshot` function below both lifecycle transitions.
  Per-gesture geometry and autoscroll counter reset now belongs to
  `PromptReorderPerformanceCountersOwner`, and refresh event classification
  belongs to the refresh-identity policy module. The outer overlay retains only
  final host adapters and construction wiring. The complete obsolete
  `reorder_overlay_interaction.py` mixin, its dynamic host access, and its
  duplicated lifecycle algorithms are deleted rather than replaced by a
  delegation bookmark;
- direct owner contracts prove duplicate-start and stale-release zero-work
  rejection. All 48 production overlay/structural-counter contracts, the
  focused dependency/deletion/absence/budget guard, targeted formatting/Ruff,
  and strict mypy pass. The start owner is frozen at 251 owned lines/3 methods,
  completion at 228/4, and the pure snapshot helper at 39 owned lines. The
  resulting `SegmentReorderOverlay` is 1,266/68 against its frozen 1,272/72
  ceiling;
  both dynamic reorder mixins are now deleted completely;
- `build/prompt-editor-slice10-pointer-drag-lifecycle-owners.json` preserves
  the exact later-regional-separator pointer lifecycle with `correct=True` and
  `structural=True`, current projection and semantics, and no invariant,
  diagnostic, structural-budget, or owner-work violation. Its p50 3.063 ms and
  p95 5.998 ms are instrumented structural diagnostics only, not controlled
  baseline-versus-candidate performance evidence.
- the active step-8 transfer is reorder frame transition ownership. Before
  transfer, `SegmentReorderOverlay.set_preview_snapshot`,
  `refresh_geometry`, `needs_position_refresh`, and four private refresh
  helpers span 284 source lines and retain frame invalidation, viewport
  capture, geometry reuse, preview adoption, animation planning, prepared
  snapshot selection, pointer-region synchronization, render publication, and
  diagnostics on the QWidget integration root. The permitted destination is
  one inward-only presentation owner between immutable
  projection/geometry/visual publications and the passive render publisher.
  It may consume explicit focused owners plus exact bound overlay-geometry
  adapters, but cannot import overlay, view, widget, controller, composition,
  panel, surface, or application orchestration. The old algorithms and
  `_content_rect` mirror must be deleted from the overlay in the same transfer;
  the public overlay methods remain only as typed host adapters. The unchanged
  refresh path must retain zero rebuild/publication work and viewport capture
  must stop querying viewport/content geometry twice per broad refresh. Direct
  owner contracts, the 48 production overlay contracts, architecture budgets,
  hostile pointer lifecycle, and focused baseline-versus-candidate evidence
  are required before this transfer can complete;
- `build/prompt-editor-slice10-frame-refresh-baseline.json` is retained only as
  a rejected pre-transfer timing attempt: correctness and structural behavior
  remained clean, but 53.8% competing CPU load made timing confidence
  `contended`. It is not accepted as controlled baseline evidence and will not
  be used to excuse a candidate delta.
- the maintainer-reported Alt-drag regression is corrected at its lifecycle
  owner. The repeated scene-partition campaign showed that successful pointer
  completion cleared committed preview geometry while its derived visual
  publication remained live; queued preview work could consequently publish
  preview mode with no matching geometry and flag most chips as unsafe
  transient paint owners. Successful completion now retires only drag-only
  base geometry, placements, lanes, and target identity while retaining the
  already prepared committed preview frame. Cancellation still clears the
  complete preview context. Direct geometry and held-context contracts freeze
  this distinction, the abuse harness now rejects any nonempty prepared
  `unsafe_transient_indices`, and visual failures include the exact overlay,
  surface, suppression, snapshot, visual, geometry, and unsafe ownership
  publication. `build/prompt-editor-alt-drag-context-completion.json` passes
  the exact five-drop scene-partition workload with `correct=True`,
  `structural=True`, and zero invariant or owner-budget violations.
  `build/prompt-editor-alt-drag-adjacent-abuse.json` passes all six focused
  decorated, wrapped, maximum-span, scene-marker, regional-separator, and
  later-separator pointer workloads with zero correctness and structural
  violations. The first broader hostile run also exposed and removed one
  obsolete harness read of `_preview_visual_snapshots_by_index`; diagnostics
  now read the authoritative preview-paint-snapshot owner. Timing from these
  instrumented structural runs is diagnostic only. The frame-transition
  transfer remains active and unaccepted until its focused architecture
  budgets and controlled baseline-versus-candidate performance evidence pass.
- the frame-transition extraction is divided by lifecycle responsibility
  instead of relocating one mixed block. `PromptReorderPreviewFrameTransitionOwner`
  owns adoption and publication of controller preview frames, while
  `PromptReorderViewportFrameRefreshOwner` owns viewport-driven live/preview
  geometry refresh and bounded overlay synchronization. The rejected combined
  transition owner is deleted. Their owned ceilings are 201 and 392 lines;
  `PromptReorderHeldDragContextOwner` remains at its existing 169-line ceiling,
  and executable dependency guards require both transition owners to depend
  inward on focused projection/geometry/publication collaborators rather than
  back on the overlay, view, widget, surface, or composition roots. Nineteen
  focused lifecycle/geometry/performance/architecture contracts pass. The
  exact five-drop scene-partition replay and the six adjacent hostile pointer
  workloads were rerun after this split with `correct=True`,
  `structural=True`, and no unsafe transient paint ownership.
- one attempted fixed-affinity pre-slice timing run was stopped and rejected
  after a separate active Python workload contaminated the selected processors
  and the run exceeded a representative duration. It produced no accepted
  report and will not be retried while the machine is occupied or used as
  evidence for either regression or improvement.
- reorder surface visuals now have exactly one host publication path. The
  obsolete split suppression and chrome methods are deleted from the state
  owner, projection surface, widget, widget stub, overlay port, and shell
  inventories; tests publish the same atomic immutable value used by
  production instead of retaining compatibility-only APIs. Preview teardown
  publishes the canonical empty live visual state, clearing chrome and
  suppression in one revision. Executable absence checks prevent any split
  method from returning. `PromptEditor` falls from 1,893 owned lines/165
  methods to 1,875/163, `PromptProjectionSurface` from 3,866/260 to
  3,836/258, and `PromptReorderSurfaceVisualStateOwner` from 218 owned lines
  to 165/3; the combined integration-root guard is green without raising a
  ceiling. Twenty-nine focused atomic-publication, projection-surface,
  animation, and architecture contracts pass with targeted Ruff and strict
  typing. `build/prompt-editor-slice10-atomic-surface-publication.json`
  repeats the five-drop scene-partition lifecycle with `correct=True`,
  `structural=True`, and no unsafe transient paint ownership. Its timing is
  instrumented and machine-load affected, so no latency claim is accepted.
- the observability transfer leaves `PromptInteractionController` at
  1,070/93 against 1,071/94; typed keyboard and pointer-owner wiring leave
  `PromptReorderController` at 1,322/48 against 1,412/53 and the completed
  lifecycle transfer leaves `SegmentReorderOverlay` at 1,266/68 against
  1,272/72 with both dynamic reorder mixins deleted. These remaining roots
  stay frozen for the final step-8 adapter reduction.
- current/base-drag/active preview snapshot coordination now belongs to
  `PromptReorderPreviewStateBuilder`. One immutable request captures the
  document, current preview/base layouts and states, order, dragged chip,
  target, source/viewport identity, instrumentation identity, and reason. The
  owner constructs current, base, and target semantic snapshots through the
  lower bounded provider, preserves exact preview/base reuse, and returns one
  immutable surface/overlay publication without mutating either adapter. It is
  Qt-free and cannot import overlay, widget, surface, interaction controller,
  or composition roots. Production viewport width is bound directly from the
  projection surface at composition; the builder performs no widget/service
  lookup.
- the seven controller algorithms for base-only construction, active
  construction, projection-result building, drop-target identity, dynamic
  viewport lookup, and split publication are deleted. The controller now
  captures one overlay fact set, invokes the builder, and applies its result
  inside the existing reentrancy guard. `PromptReorderController` falls from
  1,322 owned lines/48 methods to 1,072/41 and its integration-root ceiling is
  lowered accordingly. The builder is frozen at 309/5; its exact inward
  dependency set and the obsolete-method absence are executable architecture
  policy. The unused duplicate preview interval constant is also deleted from
  `PromptInteractionController`, which remains within 1,071/93.
- four direct builder contracts cover atomic clear, base-only publication,
  active/base exact reuse, and safe target identity. Twenty-four focused
  builder, scheduling, controller, and architecture contracts pass with
  targeted Ruff and strict mypy. The production later-regional-separator
  report at `build/prompt-editor-slice10-preview-state-builder.json` is
  `correct=True` and `structural=True`, with one activation preview build and
  no unsafe transient paint ownership. Its instrumented timing is diagnostic
  only; the final controlled comparison remains pending.
- preview scheduling context now captures dragged index, base-layout
  readiness, base-placement readiness, and initial-shadow readiness exactly
  once through the typed overlay port. The two dynamic `getattr` query helpers
  and their repeated overlay calls are deleted, so request scheduling adds no
  service lookup or duplicate geometry-state query. The same focused
  scheduling and architecture contracts pass with targeted Ruff and strict
  mypy; `PromptReorderController` is frozen lower again at 1,031 owned
  lines/39 methods.
- cursor-to-chip selection capture now belongs to the Qt-free application
  `PromptReorderSelectionCapturePolicy`. The interaction adapter reads one Qt
  cursor snapshot and passes immutable positions inward; the policy resolves
  containment, separator-boundary fallback, captured source bounds, and
  chip-relative offsets in one bounded chip traversal. The five duplicate
  controller algorithms and their repeated cursor reads are deleted. Exact
  dependency policy permits only the application document view contract,
  forbids Qt and presentation imports, requires the controller to depend
  outward on the policy, and prevents every obsolete method from returning.
  `PromptReorderController` falls from 1,031 owned lines/39 methods to 939/34;
  the policy is frozen at 129/3.
- six direct policy contracts cover caret capture inside a chip, separator
  boundary fallback, self-contained selections, cross-chip selections,
  containment priority, and the pre-chip boundary. Focused controller,
  ownership-direction, cycle, integration-root, Ruff, and strict-mypy checks
  pass. The production
  `build/prompt-editor-slice10-selection-policy.json` hostile
  later-regional-separator pointer lifecycle is `correct=True` and
  `structural=True`, with source, caret, selection, projection, semantic, and
  ownership invariants preserved. Its instrumented timing remains diagnostic
  only.
- application session completion is now one authoritative transition.
  `PromptReorderSessionOwner.finish_commit()` captures and classifies the final
  snapshot, returns the immutable command and close effects, and deactivates
  session/commit truth atomically; cancel uses the same typed `close()`
  transition. The Qt controller disposes the overlay and applies only the
  returned optional source selection. It no longer reads session selection
  state, resets application truth, or independently decides the commit close
  policy. The obsolete `prepare_commit`, reset, controller close, and
  controller selection-restoration paths are deleted, and executable absence
  checks prevent their return.
- viewport positioning now calls the declared overlay port directly; the
  dynamic `getattr`/callable/cast lookup is deleted. Application session
  ownership is frozen at 213 owned lines/eight methods with an exact inward
  dependency on reorder views, while `PromptReorderController` is frozen at
  938/34. Thirty-one focused session, commit, cancel, keyboard, text-change,
  and interaction contracts pass alongside targeted ownership, Ruff, and
  strict-mypy checks. The production
  `build/prompt-editor-slice10-session-close-transition.json` later-regional
  pointer lifecycle is `correct=True` and `structural=True`; its timing target
  was not met under the instrumented run, so it is retained only as behavior
  and structural evidence and makes no latency claim.
- the immutable reorder commit request and its stale-source matching policy now
  live in the application reorder layer. `finish_commit()` accepts primitive
  source identity facts and returns the complete request only for an approved
  commit; unchanged and missing-state outcomes allocate no request. The
  presentation command executes that application value and no longer defines,
  exports, or depends on the presentation revision model for reorder
  freshness. The interaction controller no longer reconstructs state, layout,
  active-chip, relative-selection, or source-freshness fields after policy has
  decided them.
- exact dependency guards permit the commit request to depend only on
  application reorder views, require both session and editing adapters to
  depend outward on it, and forbid the old presentation request definition and
  export. Invalid negative or incomplete source identities fail at the
  application boundary. The commit request is frozen at 62 owned lines/two
  methods, the expanded session boundary at 224/eight, and
  `PromptReorderController` lower again at 935/34. Forty-seven focused request,
  session, command, commit, interaction, host-boundary, and architecture
  contracts pass with targeted Ruff and strict mypy.
- `build/prompt-editor-slice10-application-commit-request.json` preserves the
  production later-regional-separator pointer commit with `correct=True` and
  `structural=True`; its instrumented timing is diagnostic only. An
  accidentally over-broad architecture selection also exposed the existing
  `reorder_interaction_geometry.py` owner at 907 owned lines against its
  frozen 900-line ceiling. The ceiling was not raised and the failure was not
  retried or counted against this commit-policy evidence; it became the next
  owning transfer instead of being waived.
- preview/base-drag chip construction, exact base-generation reuse,
  placement/lane publication, preview identity, and stale-value retirement now
  belong to `PromptReorderPreviewGeometryTransitionOwner`. The interaction
  geometry coordinator publishes the returned immutable state and exposes the
  existing refresh value; it no longer implements that 128-line algorithm.
  Painted-layout selection is a separate pure policy, while synchronized
  placement-to-target/lane construction and its bounded structural diagnostic
  have one drop-publication owner used by both live priming and preview
  rebuilding. The old coordinator result definition, private layout helper,
  drop-publication method, and duplicate diagnostic classification are
  deleted.
- the transition returns the next state on the existing refresh result rather
  than allocating a wrapper, preserving the pre-transfer hot-path allocation
  count. Exact dependency and absence guards freeze the one-way graph and lower
  `PromptReorderInteractionGeometry` from the exposed 907 owned lines/24
  methods to 743/23. The new focused ceilings are 186/two methods for the
  transition owner, 57/one for drop publication, and 38 lines for painted
  layout policy. Fifteen focused transition, interaction-geometry,
  preview-visual, refresh, and architecture contracts pass with targeted Ruff
  and strict mypy.
- `build/prompt-editor-slice10-preview-geometry-transition-final.json`
  preserves the exact production later-regional-separator pointer lifecycle
  with `correct=True`, `structural=True`, one bounded preview geometry build,
  and no unsafe ownership finding. Its instrumented timing is diagnostic only;
  controlled baseline comparison remains pending.
- target-driven preview layout, reorder-state, target-identity, and flattened
  chip-order publication now belong to
  `PromptReorderPreviewLayoutStateOwner`. It consumes one immutable interaction
  state plus typed target/viewport facts and returns either the same state for
  unavailable inputs or one replacement publication; it adds no wrapper,
  signal, scan, or extra allocation to the target-change path. The existing
  overlay transition remains the outer gesture/viewport adapter and no longer
  shares the layout algorithm with the geometry coordinator.
- the coordinator's 134-line preview-layout algorithm and unused boolean
  result are deleted; production callers already consumed only the published
  state. Exact dependency and absence guards freeze the state owner at 168
  owned lines/two methods and lower `PromptReorderInteractionGeometry` again
  from 743/23 to 631/23. Twelve focused state, coordinator, pointer-target,
  outer-transition, and architecture contracts pass with targeted Ruff and
  strict mypy. `build/prompt-editor-slice10-preview-layout-state-owner.json`
  preserves the production later-regional-separator target/preview/commit
  lifecycle with `correct=True`, `structural=True`, and one bounded preview
  geometry build; its instrumented timing is diagnostic only.
- the next declared transfer is keyboard projection-state ownership.
  `PromptReorderKeyboardNavigator` already owns destination policy, but
  `PromptReorderInteractionGeometry` still constructs navigator inputs,
  translates successful navigation results into coherent layout/reorder/base
  state, and contains an unused second keyboard-context preparation algorithm.
  The permitted edge is
  `reorder_interaction_geometry -> keyboard projection transition ->
  keyboard navigation/layout policy/immutable interaction state`; neither
  keyboard owner may import the coordinator, overlays, widgets, surface,
  composition, or interaction controller. Characterization must freeze
  missing-context no-ops, live-chip center capture, original-layout identity
  restoration, successful horizontal/vertical adoption, and structural
  logging. The complete transition, including state replacement and input
  projection, will move to one focused owner; the dead
  `ensure_keyboard_context` path and the coordinator's private keyboard
  helpers will be deleted in the same transfer. Ordinary pointer movement,
  paint, editing, canvas, and workflow paths must gain no keyboard work or
  allocation. The baseline coordinator is 631 owned lines/23 methods; focused
  keyboard abuse and controlled performance evidence remain required before
  accepting the transfer.
- keyboard projection-state ownership now belongs to
  `PromptReorderKeyboardProjectionTransitionOwner`. It constructs the bounded
  navigator input from one immutable interaction-state publication and
  atomically adopts valid navigator results, including original-layout/state
  identity restoration and structural event publication. The navigator remains
  the sole destination-policy owner; the interaction-geometry coordinator now
  supplies current state and publishes the returned state only. Invalid and
  incomplete results return the exact existing state object, and successful
  moves retain the pre-transfer input and state-replacement allocation shape.
- the coordinator's duplicate keyboard input/adoption/logging algorithms and
  dead `ensure_keyboard_context` path are deleted. Exact import-direction and
  absence guards freeze
  `interaction geometry -> keyboard projection transition -> keyboard
  navigation/layout policy/immutable interaction state`; the transition cannot
  import the coordinator, overlays, widgets, surface, composition, or
  interaction controllers. `PromptReorderInteractionGeometry` is reduced from
  631 owned lines/23 methods to 454/19; the focused transition owner is frozen
  at 148/three.
- live-center, invalid/no-op identity, successful adoption, original-state
  restoration, horizontal/vertical navigation, keyboard integration,
  interaction-geometry, metrics, overlay, and dependency-direction contracts
  pass across 25 focused cases with targeted Ruff and strict mypy. A stale
  architecture assertion that required the preview visual owner to import the
  concrete interaction coordinator was corrected to require its narrow visual
  geometry and immutable-state ports and forbid that inward dependency.
- hostile repeated Alt-session evidence exposed a probe lifecycle defect:
  interaction metrics outlived the overlay instance, so the second session's
  first geometry build was reported as count two even though observability
  recorded one runtime build. `PromptReorderInteractionMetricsOwner` now begins
  a fresh metrics generation before the overlay publishes its first session
  geometry. The owner retains its exact 398-line budget and the adapter adds
  one constant-time session-boundary call, with no ordinary pointer, typing,
  paint, canvas, or workflow work.
  `build/prompt-editor-slice10-keyboard-projection-transition.json` now preserves
  the production wildcard Alt-keyboard lifecycle with `correct=True`,
  `structural=True`, exactly one full geometry build in each Alt session, one
  bounded keyboard placement miss, and no invariant violation.
- controlled fixed-affinity timing used two order-reversed, fresh-process
  baseline/candidate pairs with three repetitions each under representative
  load. Across the combined six runs, median p50 is 1.023 -> 1.014 ms, median
  p95 is 12.040 -> 12.034 ms, median maximum is 14.673 -> 13.931 ms, and settle
  is 0.011 -> 0.010 ms. The individual paired comparisons move in opposite
  directions within run variance (+5.0% and -5.1% p95), while the combined
  distribution is neutral-to-better and behavior stays exact. Focused deep
  telemetry records the keyboard action at 2,263 -> 2,244 net allocated blocks
  with three collections in both runs; process peak working set is 269,852,672
  -> 269,053,952 bytes. The candidate removes the false cross-session rebuild
  attribution and adds no scan, hash, layout, service query, signal, callback,
  or unrelated hot-path work. Timing and allocation reports are
  `build/prompt-editor-slice10-keyboard-transition-{baseline,candidate}-{a,b}.json`,
  `build/prompt-editor-slice10-keyboard-transition-comparison-{a,b}.json`, and
  `build/prompt-editor-slice10-keyboard-transition-{baseline,candidate}-allocation.json`.
- the next declared transfer is drag-geometry preparation ownership.
  `PromptReorderInteractionGeometry` still combines mutable publication with
  base-drag layout/state derivation, painted-projection placement priming,
  drop-lane publication, and their structural timing. Its direct live-chip
  query plus atomic publication remains state-owner work; wrapping that single
  call would be a delegation bookmark and add an avoidable first-use frame to
  Alt activation.
  Existing focused interaction-geometry contracts plus the accepted
  `wildcard-alt-zebra-reorder` structural and controlled-performance reports
  characterize missing-session no-ops, coherent base-drag replacement,
  painted-geometry reuse, bounded placement/lane publication, and cache/build
  counts before structural change; unchanged evidence will not be rerun.
  The permitted edge is
  `interaction geometry -> drag geometry preparation ->
  layout policy/narrow geometry-source port/drop publication/immutable
  interaction state`.
  The preparation owner must not import overlays, widgets, surface,
  composition, interaction controllers, keyboard/preview transition owners, or
  the coordinator. It must return the exact input state for unavailable/empty
  work and one replacement state for successful publication, without result
  wrappers, duplicate layout/geometry work, extra scans, or hot-path
  instrumentation. The coordinator will retain only atomic state/live-chip
  publication and the existing outward result shape; the complete base-drag
   preparation algorithms, observability, and dependencies will move, and their
   old coordinator paths will be deleted in the same transfer. The accepted
   454-line/19-method coordinator and keyboard timing/allocation reports are
   this transfer's structural and performance baseline.
- the main refactor was paused for the maintainer-reported Alt-drag repair.
  Characterization proved that `reorder_partition_targets.py` removed every
  destination outside the dragged chip's source partition and domain mutation
  independently rejected any cross-partition target. Both unauthorized paths
  are removed. Drop publication now carries the already-built complete
  placement snapshot without the former hidden-chip scan, partition row/gap
  set construction, filtered tuple allocation, or unused layout-view argument.
  Domain line and blank-line mutations assign the chip to the destination
  partition while keeping `[SEP]` slots structural; removing the only chip from
  a leading or trailing partition retains a canonical edge separator.
- the production abuse harness now requires the terminal pointer position to
  resolve to its semantic target and requires every active target to own a
  matching active placement plus a prepared geometry- or visual-backed landing
  shadow. Four permanent real-shell scenarios cover a regional-to-global move,
  both sole-chip edge-partition exits, and movement across two separators.
  The original cross-partition scenario failed before the repair with
  `semantic_target=None` and unchanged source. All four now pass with
  `correct=True` and `structural=True`; focused same-partition, wrapped,
  maximum-span, and later-separator scenarios also retain their landing
  previews. The focused owner/domain/projection/landing/view/commit set passes
  118 cases, the four real-shell regression cases pass, and a direct view
  contract proves a prepared shadow reaches paint dispatch. Unchanged-pointer,
  target-change, and unchanged-canvas structural contracts pass; the canvas
  round trip records zero region preparation, projection rebuild, or layout
  snapshot work. The three-repetition instrumented cross-partition campaign is
  behavior- and structure-clean in every repetition. The exact pre/post
  non-instrumented later-separator comparison remains correct and moves p50
  2.372 -> 2.133 ms, p95 6.194 -> 5.646 ms, and maximum 8.819 -> 6.395 ms;
  settle changes by 0.004 ms. The comparison is retained at
  `build/prompt-editor-drag-repair-shadow-comparison.json`; the instrumented
  campaign is `build/prompt-editor-drag-repair-cross-final.json`. Targeted
  formatting, Ruff, and strict mypy pass. The declared drag-geometry
  preparation transfer was suspended until the direct application behavior
  was accepted.
- the subsequent maintainer traceback invalidated that repair handoff. The
  exact mixed regional prompt published row 7 from a base layout with eight
  rows while preview mutation used an independently rebuilt authoritative
  state with seven rows. Pointer movement therefore raised `ValueError` from
  `apply_line_drop_target_to_state()` inside `QWidget.mouseMoveEvent`.
  Reorder session transitions now return one immutable prepared value pairing
  authoritative state with its derived layout. Pointer and keyboard consumers
  use that pair directly; the four split state/layout session APIs and
  presentation-side reconstruction paths are deleted. Target resolution is
  proposal-only, and the transition owner publishes the target and placement
  only after preview construction succeeds.
- the stricter all-placement sweep exposed two additional target-authority
  defects. Structural `[SEP]` rows were counted as blank-line destinations,
  and provisional live-gap mapping assumed gap ordinal equaled row ordinal.
  Blank targets now require a genuinely empty intervening row. Provisional
  ranges now resolve from the exact source-owned separator after the actual
  preceding chip, so regional boundary rows cannot shift later gaps onto
  unrelated populated rows.
- the abuse sweep now sends real pointer moves through every published
  placement and, after every move, requires the intended semantic target, a
  matching active placement, the exact domain mutation in preview state, and
  a geometry- or visual-backed landing shadow. The formerly crashing
  13-line/multi-`[SEP]` topology passes 36 moves/35 target changes with no Qt
  callback exception. The all-source campaign passes nine lifted chips and
  198 placement moves. All-target commit/cancel, repeated cross-partition,
  leading/trailing empty-partition, and multi-partition campaigns are
  behavior- and structure-clean. The focused structural probe passes its
  budgets. Representative multi-partition evidence records p95 2.979 ms and
  maximum 4.840 ms; the mixed-topology before/after diagnostic comparison is
  non-regressive, though its contended timing is not acceptance evidence.
  Artifacts are retained under `artifacts/prompt_editor_abuse/alt-drag-*-verified.json`.
  The main refactor and drag-geometry transfer remained suspended pending the
  maintainer's direct application test. The maintainer accepted the repaired
  behavior and explicitly unblocked this objective.
- drag-geometry preparation ownership is complete.
  `PromptReorderDragGeometryPreparationOwner` now owns coherent base-drag
  state/layout construction, stale-preview retirement, painted-projection
  placement priming, synchronized target/lane publication, and their bounded
  structural timing. It consumes the atomic application prepared-state
  transition introduced by the regression repair, so state and layout cannot
  diverge. `PromptReorderInteractionGeometry` retains only publication of the
  returned immutable state and its existing outward result shape.
- the coordinator's former base-drag derivation, independent state/layout
  calls, placement construction, target/lane publication, and timing paths are
  deleted. The executable direction/absence guard freezes
  `interaction geometry -> drag preparation -> layout policy/narrow geometry
  source/drop publication/immutable state`, caps the preparation owner at 157
  owned lines, and lowers the coordinator from 454 owned lines/19 methods to
  399/19 without a result wrapper or compatibility bridge.
- focused preparation, interaction-geometry, application transition, pointer
  transaction, architecture, and real-shell abuse contracts pass. The retained
  order-reversed controlled comparison is neutral-to-better at the tail:
  pair A p95 7.634 -> 7.409 ms and maximum 11.196 -> 10.416 ms; the noisier
  pair B p95 7.723 -> 8.250 ms was followed by the accepted low-load run at
  p95 4.330 -> 4.391 ms and maximum 5.818 -> 6.173 ms, within run variance.
  Current-tree structural evidence additionally passes the exact formerly
  crashing 36-move mixed-boundary sweep, the 198-move all-source sweep, and
  representative multi-partition latency at p95 2.979 ms/max 4.840 ms. No
  ordinary pointer, paint, editing, canvas, or workflow path gains an extra
  scan, hash, service query, signal, layout build, or projection build.
- the proposed preview-snapshot state extraction was rejected rather than
  normalized into the architecture. Characterization now freezes atomic
  snapshot/order/identity adoption and clear-snapshot stale-geometry
  retirement through the authoritative interaction-state owner. Moving the
  24-line transition behind a new owner left the existing coordinator method
  as a delegation bookmark and added a second method dispatch to every preview
  publication. A controlled ten-sample, order-alternated microbenchmark
  measured the unchanged inline transition at 6.566 microseconds median and
  the delegated candidate at 7.500 microseconds, a 0.934-microsecond/14.2%
  regression. The candidate module, direct tests, imports, dependency edge,
  and budget were removed; the characterization tests remain, and focused
  behavior, architecture, Ruff, and strict mypy checks pass. The hostile
  36-placement mixed-regional real-shell sweep also remains behavior- and
  structure-clean. This is the enforced final-shape and hot-path rule in
  practice: a coherent transition remains with its sole state owner until a
  future complete authority replacement can update callers directly and
  remove that owner.
- the next declared transfer is interaction-geometry public-surface
  contraction. `layout_for_painted_preview()` and
  `ordered_indices_for_layout()` have no production or test callers; their
  actual policies already have authoritative focused owners used directly by
  preview transitions. Keeping the unused forwarding queries broadens the
  mutable coordinator and preserves false API surface. The transfer deletes
  both methods without replacement, freezes their absence and the lower owned
  line/method budget, and verifies interaction geometry plus keyboard,
  preview, pointer, and overlay consumers. It changes no runtime call path and
  therefore must preserve identical structural counters with zero new
  allocation, scan, dispatch, query, layout, projection, paint, canvas, or
  workflow work.
- interaction-geometry public-surface contraction is complete.
  `layout_for_painted_preview()` and `ordered_indices_for_layout()` are deleted
  without replacement after repository-wide caller characterization proved
  both were dead. The coordinator no longer imports preview-layout query
  policy merely to expose a duplicate forwarding API. Executable absence,
  dependency-direction, exact 376-owned-line, and 17-method guards replace the
  former 399-line/19-method ceiling. Focused interaction-geometry, keyboard,
  preview-refresh, preview-transition, pointer-move, overlay, Ruff, and strict
  mypy checks pass across 18 cases. Because no runtime caller existed, this
  transfer adds and changes zero runtime operations; the already clean
  structural abuse evidence remains valid and was not rerun.
- the next declared transfer is preview-build fact publication ownership.
  `PromptReorderController._sync_reorder_preview_from_overlay()` currently
  reaches through the broad overlay port for commit order, preview/base layout,
  preview/base reorder state, dragged index, and drop target in seven separate
  calls. `SegmentReorderOverlay` duplicates the assembly policy across six
  forwarding queries even though immutable interaction geometry, gesture, and
  visual-mode owners already hold the authoritative facts.
  The permitted direction is
  `controller -> narrow preview-fact port -> focused preview-fact owner ->
  immutable geometry/gesture/visual-mode/keyboard publications`.
  A frozen Qt-free fact snapshot will replace the existing commit-snapshot
  allocation in the preview-build path, not add another allocation. The
  controller will read one coherent generation and construct the existing
  projection request; the focused owner cannot import controller, widget,
  surface, composition, projection builder, layout engine, paint, or mutable
  overlay host. Composition will expose the focused owner directly through a
  typed overlay assembly, eliminating the `object` return and cast rather than
  adding a forwarding method to the large overlay. All superseded overlay
  preview queries and broad Protocol members will be deleted in the same
  transfer. Characterization must first freeze pointer and keyboard target
  selection, active/base-only preview facts, and generation coherence.
  Controlled evidence must show one snapshot allocation, fewer dispatches,
  unchanged projection/layout/cache/build counters, and equal-or-better
  preview publication latency; no ordinary pointer, paint, typing, canvas, or
  workflow path may gain work.
- preview-build fact publication ownership is complete.
  `PromptReorderPreviewBuildFactsOwner` now reads one immutable geometry
  generation and one gesture generation, applies the shared pure visual-mode
  policy, and publishes one frozen projection-value snapshot. Pointer targets
  never query keyboard policy; keyboard targets resolve only for a changed
  order. The pure `reorder_visual_mode_policy.py` is shared by painting and
  preview-fact publication, so generation coherence does not duplicate visual
  selection rules.
- composition now returns a typed `PromptReorderOverlayAssembly` containing
  separate overlay command/lifecycle, preview-fact, and Qt-signal authorities.
  The factory's `object` return and controller cast are deleted. The controller
  consumes the preview-fact owner directly and reads exactly one snapshot per
  preview sync. Four broad overlay preview queries and their Protocol members
  are deleted; the 22-method overlay port falls to 18. The concrete overlay
  falls from 1,063 physical lines/64 methods to 1,039/60, while the mixed
  controller file falls from 1,007 physical lines to 883 and no longer owns
  overlay Protocol declarations. Exact directional and absence guards freeze
  the 36-owned-line immutable value, 47-line pure policy, 118-line fact owner,
  151-line typed port, 897-line overlay, and 816-line controller ceilings.
- focused fact, visual-mode, controller, preview-builder/scheduler,
  performance-counter, overlay, architecture, Ruff, and strict mypy checks
  pass across 30 cases. The production hostile 36-placement regional sweep is
  behavior- and structure-clean with the same one preview full-build budget;
  its timing sample was explicitly rejected as contended. The controlled
  ten-sample, order-alternated owner benchmark replaces the old commit-snapshot
  allocation plus seven overlay dispatches with one fact snapshot: median
  publication cost improves from 1.390 to 1.224 microseconds (-12.0%) and the
  maximum sample improves from 1.669 to 1.354 microseconds. The report is
  retained at
  `build/prompt-editor-slice10-preview-build-facts-microbenchmark.json`.
- the next declared transfer is preview-sync context publication ownership.
  `PromptReorderController._preview_sync_context()` still reaches into the
  overlay for dragged index, base-layout readiness, prepared placement
  geometry, and the one-shot initial landing-shadow decision, mixing
  application scheduling input construction with presentation state and a
  consumptive visual transition. The permitted direction is
  `controller -> narrow sync-context port -> focused sync-context owner ->
  immutable geometry/gesture/landing/metrics publications -> application
  preview-sync value`.
  The focused owner must return the existing
  `PromptReorderPreviewSyncContext`, replacing its current allocation rather
  than adding one. Composition will expose it directly in the typed assembly;
  controller reach-through, the four corresponding overlay Protocol methods,
  and superseded overlay forwarding methods will be deleted. Initial-shadow
  consumption remains with the landing visual owner, pointer activity remains
  with interaction metrics, and geometry readiness remains derived from the
  immutable state generation. No timer, scheduling, starvation, preview,
  pointer, paint, canvas, or workflow policy may be duplicated or moved
  upward. Characterization must freeze no-overlay, keyboard, pointer-before-
  geometry, first-shadow one-shot, and already-prepared contexts before
  migration; controlled evidence must show the same single context allocation,
  fewer dispatches, unchanged scheduler/build counters, and equal-or-better
  cost.
- preview-sync context publication ownership is complete.
  `PromptReorderPreviewSyncContextOwner` now reads one immutable interaction-
  geometry generation and one gesture generation, derives base-layout and
  placement readiness, invokes the existing landing-request/landing-visual
  owners only for an eligible pointer drag, republishes the selected active
  placement through the geometry owner, and returns the existing application
  `PromptReorderPreviewSyncContext`. It does not own or duplicate timer,
  scheduling, starvation, landing-consumption, pointer-metrics, projection,
  layout, or paint policy.
- typed composition now publishes the sync-context owner beside the overlay
  command port, preview-build facts, and preview-changed signal. The
  controller consumes only that narrow port and no longer imports the overlay
  package barrel. Four overlay reach-through queries and their broad Protocol
  members are deleted:
  `dragged_segment_index()`, `base_drag_layout_view()`,
  `has_base_drag_placement_geometry()`, and
  `should_flush_initial_landing_shadow_sync()`. The abuse host reads the
  already-public pointer state and preview-build fact publication rather than
  restoring the removed surface.
- owner characterization freezes keyboard/no-drag, pointer-before-base-layout,
  pointer-before-placement, prepared-placement, and first-shadow one-shot
  behavior. Scheduler/controller tests use separately composed context and
  preview-fact authorities and keep the no-overlay empty context safe.
  Direction/absence guards enforce
  `controller -> typed context port -> context owner -> immutable
  geometry/gesture/landing/metrics publications -> application context` and
  forbid reverse dependencies into controller, overlay, composition, widget,
  surface, projection builder, layout engine, or paint owners.
- the overlay falls from 897 owned lines/60 methods to 876/56, the typed port
  falls from 151 owned lines/18 overlay methods to 149/14, and the mixed
  controller falls from 816 owned lines to 801 while retaining 34 methods.
  The context owner is capped at 142 owned lines. Focused owner, scheduler,
  controller, overlay, performance-counter, visual-architecture, publication-
  architecture, Ruff, and strict-mypy checks pass across 24 cases.
- the production 36-placement regional mixed-boundary sweep remains
  `correct=True` and `structural=True` with the same one preview full-build
  budget. Its instrumented timing is diagnostic and is not acceptance
  evidence. A controlled ten-sample, order-alternated, 200,000-iteration
  comparison replaces the deleted controller `getattr` fallbacks and repeated
  overlay forwarding calls with one direct owner snapshot: median context
  publication improves from 1.717 to 0.894 microseconds (-47.9%), and maximum
  sample improves from 2.526 to 1.175 microseconds. Evidence is retained at
  `artifacts/prompt_editor_abuse/slice10-preview-sync-context-structural.json`
  and
  `build/prompt-editor-slice10-preview-sync-context-microbenchmark.json`.
- the next declared transfer is reorder-preview publication transaction
  ownership. `PromptReorderController` still owns preview-build invocation,
  projection/cache lifecycle calls, editor-plus-overlay publication, the
  publication reentrancy flag, and the position-refresh exclusion that
  protects the same transaction. Before changing it, trace every public and
  private caller and characterize no-overlay clear, base-only, active preview,
  exact base reuse, cache reset/close, autoscroll flush ordering, publication
  failure cleanup, and position suppression.
  The permitted direction is
  `interaction orchestration/scheduler -> focused preview-publication command
  owner -> immutable preview facts + application preview builder/projection
  provider + narrow editor/overlay publication ports`.
  Transfer the complete transaction, lifecycle, state, cache authority, tests,
  and observability; update all callers to the final owner and delete the
  controller algorithm, state flag, superseded helpers, and any temporary
  bridge in the same slice. The final controller must not retain a forwarding
  bookmark. No additional context/fact/publication allocation, full-document
  scan, layout/projection build, signal, invalidation, paint work, service
  query, or canvas/workflow work is permitted; controlled evidence must show
  unchanged owner counters and equal-or-better base-only and active-preview
  publication latency.
- reorder-preview publication transaction ownership is complete.
  `PromptReorderPreviewPublicationOwner` owns the bounded latest-wins
  scheduler, immutable sync-context consumption, autoscroll-before-facts
  ordering, preview-build invocation, projection-cache lifecycle, atomic
  editor-plus-overlay publication, reentrancy state, failure cleanup, and
  post-overlay preview clear. It consumes one composed overlay command port,
  preview-fact port, and sync-context port; no production caller reaches back
  through the broad overlay for these concerns.
- composition constructs this owner from the canonical document, syntax,
  projection-provider, metrics, editor, source-identity, and viewport
  collaborators before it constructs the interaction controller. The
  interaction controller passes the owner to reorder orchestration; the
  reorder controller only binds and releases one overlay session and invokes
  the owner directly for keyboard lifecycle work. There is no optional
  controller-side construction, compatibility fallback, forwarding preview
  schedule API, or temporary bridge.
- controller-owned preview build/state-builder/provider fields, scheduler,
  sync-context fallback allocation, preview cache helpers, publication flag,
  preview method wrappers, and their tests' private hooks are deleted. The
  old controller-to-preview algorithm is absent by executable guard. The
  remaining explicit position check reads the publication owner's state so it
  cannot observe the atomic editor/overlay handoff half-applied; the owner
  performs the final editor clear only after the covering overlay has closed.
- direct owner characterization covers unbound clear, geometry-before-facts
  publication, atomic editor/overlay handoff, session release, and post-close
  clear. Controller characterization additionally freezes autoscroll ordering,
  reentrant position suppression, failure cleanup, keyboard commit-before-
  preview, base-only/active publication, exact base reuse, and source-cache
  lifecycle. Direction guards require
  `composition -> focused preview-publication owner -> narrow ports +
  application preview policy/projection builder/provider`; controller and
  overlay-port modules cannot import preview build, provider, scheduler, or
  concrete overlay owners.
- the reorder controller falls from 801 owned lines/34 methods to 616/24; the
  focused publication owner is capped at 266 owned lines/17 methods. Focused
  direct-owner, controller, scheduler, context, overlay, state-builder,
  performance-counter, LoRA integration, visual architecture, publication
  architecture, Ruff, and strict-mypy checks pass across 44 cases. The 36-
  placement regional mixed-boundary production sweep remains
  `correct=True` and `structural=True`; its instrumented timing is retained
  only as diagnostic evidence at
  `artifacts/prompt_editor_abuse/slice10-preview-publication-structural.json`.
  The controlled ten-sample, order-alternated 300,000-iteration transaction
  comparison is median-neutral-to-better: 2.827 to 2.811 microseconds
  (-0.55%); its maximum 3.078 to 3.080 microseconds is measurement noise.
  Evidence is retained at
  `build/prompt-editor-slice10-preview-publication-microbenchmark.json`.
- application reorder-session transition ownership is complete as a bounded
  sub-slice. `application/prompt_editor/reorder/lifecycle.py` now owns entry
  planning, bounded chip/selection resolution, activation only after the
  presentation adapter accepts entry, snapshot acceptance, commit-plan
  resolution, cancellation close policy, immutable session truth, and explicit
  state restoration. It is Qt-free and has no presentation imports. The
  presentation controller now supplies a single immutable entry request and
  consumes an entry/close/commit plan; it no longer owns the selection policy,
  session owner, session start, snapshot state, or commit eligibility rules.
- direct application-owner characterization proves that planning cannot leave
  an active session before overlay entry succeeds and empty source cannot
  allocate session or commit state. Interaction characterization now freezes
  disabled entry, active-entry idempotence, and empty-entry no-op behavior in
  addition to existing cursor capture, keyboard/pointer snapshot, unchanged/
  missing commit, cancellation, disposal ordering, selection restoration,
  focus, and preview-teardown contracts. Architecture guards enforce
  `presentation reorder controller -> application lifecycle owner -> document,
  selection, session, and immutable reorder views`, forbid presentation
  imports and Qt in the lifecycle owner, and forbid direct selection-policy
  imports in the controller.
- focused owner, interaction, commit, keymap, text-change, and architecture
  coverage passes (51 selected tests); targeted Ruff and strict mypy pass. The
  real-shell regional-separator mixed-boundary structural sweep is
  `correct=True` and `structural=True` at
  `artifacts/prompt_editor_abuse/slice10-session-lifecycle-structural.json`.
  Its instrumented timings remain diagnostic only; no structural counter,
  projection/layout build, scan, allocation, signal, invalidation, canvas, or
  workflow work was added to unchanged operation paths by this transfer.
- Qt cursor restoration now has a focused `PromptReorderCursorSelectionAdapter`.
  It alone translates an application close transition into two Qt cursor-anchor
  operations and performs no work when the transition contains no selection.
  Direct owner tests cover both cases; interaction cancel/commit coverage
  continues to cover the composed behavior.
- prepared command invocation and command-result adoption now have one focused
  `PromptReorderCommitExecutor`. It receives only the prepared request plus
  narrow command/result ports, retains the existing command and result-apply
  timing events as distinct measurements, and contains no overlay/session
  state. Its direct owner contract proves exactly one prepared execution and
  one result publication. The focused commit/close/cursor suite passes 17
  cases, and target Ruff and strict mypy pass. The production
  `regional-separator-mixed-boundary-sweep` remains `correct=True` and
  `structural=True` at
  `artifacts/prompt_editor_abuse/slice10-command-execution-structural.json`.
  This owner is reached only during a prepared reorder commit: it adds no
  typing, unchanged-canvas, unchanged-workflow, or preview-publication path;
  it adds neither a new timing aggregate nor per-frame instrumentation.
- presentation overlay-session assembly is complete. The old
  `reorder_controller.py` authority is deleted rather than retained as a
  forwarding facade. `PromptReorderOverlaySessionOwner` now owns overlay entry,
  factory construction, publication binding/release, preview scheduling hookup,
  interaction mode, pointer snapshot acceptance, keyboard movement, viewport
  positioning, focus, and overlay-before-live-paint teardown.
  `PromptReorderInteractionOwner` owns the separate intent-to-application-plan
  coordination and invokes the already-focused command executor only after the
  session closes. The resulting dependencies flow from the interaction owner
  to the presentation session and application lifecycle; the application
  lifecycle has no presentation/Qt imports. The deleted 1,276-line legacy
  controller is replaced by 193-line interaction coordination and a 309-line
  Qt-session owner, each capped by executable architecture budgets at 220/12
  and 350/17 owned lines/methods, respectively.
- controller tests no longer reach through the reorder interaction into private
  session, lifecycle, preview-publication, or overlay-factory state. Direct
  owner contracts now cover entry/binding, paint-safe cancellation teardown,
  pointer snapshot acceptance, keyboard snapshot-before-preview ordering,
  keyboard boundary no-op preservation, damage-bounded positioning, reentrant
  publication positioning suppression, and publication-failure guard release.
  The old test-only private overlay-attachment seam is deleted.
- real-shell keyboard reorder and animation tests likewise consume the
  overlay's typed public commit snapshot instead of reaching through the
  widget to the interaction owner's private lifecycle. The five affected
  Windows QWidget nodes pass serially, which is the documented fixture mode;
  the test-tree audit has no `_interaction_controller._reorder`,
  `_reorder._`, or private overlay-attachment helper access remaining.
- focused owner/controller, scheduler/publication, and interaction-state checks
  pass (30 selected), with targeted Ruff and strict mypy clean. The production
  regional mixed-boundary sweep is `correct=True` and `structural=True` at
  `artifacts/prompt_editor_abuse/slice10-overlay-session-structural.json`.
  Its instrumented timings remain diagnostic only. A separate three-repetition,
  same-seed, representative paired run of
  `later-regional-separator-pointer-reorder-recovery` against the retained
  pre-transfer baseline is correct in both cases and improves p50
  `7.209 -> 1.635 ms`, p95 `14.946 -> 3.695 ms`, and max
  `29.884 -> 5.478 ms`; see
  `build/prompt-editor-slice10-overlay-session-{candidate-later-separator,later-separator-comparison}.json`.
  The candidate retains the baseline's bounded owner-counter shape and adds no
  unchanged canvas/workflow operation to this reorder path. The newer mixed
  boundary scenario did not exist in the historical baseline, so it remains
  separate hostile structural/behavior evidence rather than a fabricated
  paired timing claim.
- overlay visual lifecycle ownership is complete. Theme/font style replacement,
  visual snapshot clearing, raster-generation invalidation, passive warmed
  raster publication, hide cleanup, and close cleanup moved from
  `SegmentReorderOverlay` into
  `PromptReorderOverlayVisualLifecycleOwner`. The outer QWidget retains only
  Qt event translation and visibility calls; the new owner is the sole mutable
  owner of the theme reentrancy guard and visual style. It is a cold-path
  owner: pointer, paint, typing, canvas, and workflow routes do not call it.
- the concrete overlay falls from 896 to 880 physical lines and from 56 to 54
  methods. The new 129-line lifecycle owner is guarded at 140 owned lines and
  8 methods; executable direction tests forbid it from importing upward into
  overlay/session/composition or preview projection/publication. Direct owner
  contracts prove complete cache clearing, no-document theme refresh without
  drag or geometry work, and visibility/close ordering. Focused overlay,
  view, drag-proxy, lifecycle, and architecture coverage passes 27 cases with
  targeted Ruff and strict mypy clean.
- the production mixed-boundary structural report remains
  `correct=True` and `structural=True` at
  `artifacts/prompt_editor_abuse/slice10-overlay-visual-lifecycle-structural.json`.
  Its instrumentation is diagnostic only. The same-seed, three-repetition
  paired later-separator scenario remains correct and improves over the
  retained baseline: p50 `7.209 -> 2.625 ms`, p95 `14.946 -> 4.897 ms`, and
  max `29.884 -> 6.347 ms`; see
  `build/prompt-editor-slice10-overlay-visual-lifecycle-{candidate,comparison}.json`.
- presentation-session activation ownership is complete. The former
  `SegmentReorderOverlay.set_chips()` transaction starts metrics, clears the
  prior visual generation, stops autoscroll, disposes stale regions, publishes
  one visual session and one geometry session, resets gesture/landing/pointer
  state, activates the requested chip, and requests the first geometry frame;
  all of that presentation-only transaction plus stale-region disposal now
  belongs to `PromptReorderOverlaySessionActivationOwner`. It consumes the
  immutable application chip/layout/state inputs but owns no application
  session or commit truth. The outer QWidget delegates one typed call and
  retains only Qt event routing.
- the concrete overlay falls from 880 to 857 physical lines and from 54 to 53
  methods. The 157-line activation owner is guarded at 180 owned lines and
  three methods; its direction guard forbids upward overlay/session/
  composition/projection-publication dependencies. Its direct contract freezes
  the complete reset-and-publish ordering and the preserved `overlay.set_chips`
  timing event. Two representative Windows QWidget contracts—initial viewport
  materialization and wrapped-row visual order—pass serially, the documented
  mode for this fixture; targeted Ruff and strict mypy are clean.
- the production mixed-boundary structural report remains
  `correct=True` and `structural=True` at
  `artifacts/prompt_editor_abuse/slice10-overlay-session-activation-structural.json`.
  Its instrumented timing is diagnostic only. The same-seed, three-repetition
  paired later-separator scenario remains correct and improves over the
  retained baseline: p50 `7.209 -> 2.246 ms`, p95 `14.946 -> 4.571 ms`, and
  max `29.884 -> 5.446 ms`; see
  `build/prompt-editor-slice10-overlay-session-activation-{candidate,comparison}.json`.
- the 706-line `PromptReorderLandingVisualOwner` is deleted. Its held-shadow
  capture and drag/session reset lifecycle now belongs to the 93-line
  `PromptReorderLandingSessionOwner`; `PromptReorderLandingStateOwner`,
  diagnostics, and event publication remain explicit focused collaborators,
  assembled once by the overlay. It is now the retained-state collaborator
  beside distinct resolution and paint authorities; no compatibility facade,
  forwarding export, private shared state, or extra hot-path recomputation was
  retained. The former 16-case characterization directly composes those three
  owners, and lifecycle coverage independently proves that held-state disposal
  and cache disposal both occur exactly once.
- landing resolution versus paint/cache ownership is complete. The interim
  610-line `PromptReorderLandingPreviewOwner` is deleted in the same transfer,
  not retained as a facade. The new 436-line
  `PromptReorderLandingResolutionOwner` owns validity, target agreement,
  placement-derived geometry, readiness, marker suppression, and the semantic
  preview/fallback state transitions. The 180-line
  `PromptReorderLandingPaintOwner` owns only bounded one-frame cache lookup,
  cache lifecycle/counters, and conversion of an immutable resolved-feedback
  value to passive paint state. This preserves the prior cache key and hit/miss
  behavior: cache hits do not invoke resolution, and cache misses invoke it
  once. No document scan, layout build, workflow query, canvas operation, or
  additional per-frame signal was introduced.
- the dependency trace for the completed atomic transfer is executable: only
  `PromptReorderRenderPublicationOwner` consumes prepared landing paint;
  cache reset/clear and counter reads flow through the drag-start,
  drag-completion, held-context, session-activation, and performance-counter
  owners. `PromptReorderPreviewSyncContextOwner`,
  `PromptReorderPreviewGeometryRefreshOwner`,
  `PromptReorderInsertionMarkerOwner`, and the overlay's public initial-shadow
  query consume resolution only. The overlay composition point is the sole
  construction site. Graph contracts forbid a resolution-to-render dependency,
  paint access to placement/target policy, and resolution access to cache or
  paint policy. They also assert the deleted interim module is absent.
- focused evidence for the completed transfer is clean but is not full-gate or
  commit evidence: 27 landing/consumer contracts, five architecture/host-boundary
  contracts, and seven real-shell/proxy/cancel contracts pass. Targeted Ruff
  and strict mypy over all changed sources/tests pass. The seeded
  three-repetition `regional-separator-mixed-boundary-sweep` is
  `correct=True` and `structural=True` at
  `artifacts/prompt_editor_abuse/slice10-landing-resolution-paint-structural.json`.
  The harness reports unchanged structural invariants and the expected bounded
  `landing_paint_cache_miss_count` reset at drag cancellation. Its latency is
  instrumented diagnostic data only; no broad or unrelated suite was run.
- concrete overlay construction was characterized and rejected as an
  extraction target. `SegmentReorderOverlay` is the concrete Qt parent and
  callback endpoint for its child timer/view/proxy owners; moving construction
  outward requires either a two-phase partially initialized QWidget or a broad
  retained runtime container. The former weakens construction/lifecycle safety;
  the latter is a service locator and adds a dereference to pointer/paint
  paths. Neither is an acceptable final shape. The factory remains the sole
  composition owner of external application/projection dependencies, while the
  concrete widget directly constructs its focused Qt-bound children once during
  its own lifecycle. A production-factory contract proves its typed preview
  ports are ready before activation without a private widget probe. The existing
  real-shell landing/reorder contracts and hostile structural sweep remain the
  behavioral and hot-path baseline; they are unchanged and were not rerun.
- the concrete overlay no longer carries the stale mixin-era mypy suppression:
  strict typing accepts its direct-owner fields without an assignment or
  miscellaneous-error exemption. This removes a debt concealment without
  changing a runtime path.
- final-slice candidate evidence is behavior- and structure-clean: the seeded
  three-repetition `later-regional-separator-pointer-reorder-recovery` report
  at `build/prompt-editor-slice10-final-candidate-later-separator.json` is
  `correct=True`, `structural=True`, and retains the expected per-action
  bounded counter shape (one preview geometry build at threshold, no-change
  pointer moves, bounded raster reuse, and cancellation cache reset). The
  retained comparison reports p50 `7.209 -> 2.211 ms`, p95
  `14.946 -> 5.417 ms`, and max `29.884 -> 7.142 ms`; however, the candidate
  measured under 20.3 percent competing CPU and reports `contended`. It is
  diagnostic only. The maintainer explicitly overrides the remaining controlled
  timing requirement after manually smoke-testing Alt drag across regional
  boundaries and approving its feel as better than the prior behavior. This
  accepts the behavior/structural evidence and the contended comparison as the
  final Slice 10 timing evidence. See
  `build/prompt-editor-slice10-final-later-separator-comparison.json`.

### Slice 11 execution ledger

The first Slice 11 vertical transfer is autocomplete. The then-1,223-line
`interactions/autocomplete_controller.py` combined separate reasons
to change: session and dismissal truth; tag, scene, wildcard, and LoRA query
retargeting; keyboard and presenter event translation; acceptance command
execution; focus-loss policy; panel geometry/presentation; inline ghost-preview
publication; and timing/diagnostic attribution. Its broad editor Protocols and
the forwarding `PromptAutocompleteController` cannot be normalized into a new
coordinator or facade.

The target direction is `Qt input/presenter adapter -> application query and
acceptance owners -> immutable result/preview publication -> passive panel and
ghost rendering`. Query-generation and stale-result policy must remain below
Qt; panel placement, focus, and signal translation must remain above it. The
transfer will characterize all existing tag/scene/wildcard/LoRA, keyboard,
acceptance, dismissal, focus, preview, and geometry behavior first, then move
one complete responsibility at a time with its state, lifecycle, cache,
observability, callers, and tests while deleting the matching old path. It may
not add query work, source reads, allocations, signals, geometry work, or ghost
publication to caret, paint, scroll, workflow, or canvas hot paths.

The initial focused characterization set passes 44 query-refresh, session,
ghost-preview, panel-presenter, and acceptance-controller cases. It freezes
the existing owner seams before moving coordinator responsibilities; no
autocomplete production path changed in this characterization step.

The first transfer is presentation lifecycle. The coordinator's panel-visible
gating, prepared panel request, ghost-preview publish/clear lifecycle, and
geometry-refresh entry are one cohesive presentation concern. It will move to
a focused owner consuming the existing session and presenter/ghost ports;
query routing, selection mutation, acceptance, and focus-loss policy stay out
of that owner. The old coordinator methods and direct presentation state will
be deleted with the replacement, and the existing panel/ghost contracts will
be extended to prove hidden-panel clearing and geometry refresh.

That transfer is complete in
`interactions/autocomplete_presentation_lifecycle.py`. It owns only presenter
binding, panel presentation/visibility, ghost-preview publication and clearing,
and the active-session geometry entry. `autocomplete_controller.py` no longer
stores a presenter, ghost publisher, or ghost-enabled flag and no longer
contains the former presentation helpers; it retains query routing, selection,
acceptance, and focus policy. The focused owner tests include an inactive
geometry refresh contract that makes no presenter or preview request, so the
transfer adds no query, source, or panel work to that path. An architecture
guard freezes this ownership and its one-way dependency direction.

The real-shell harness diagnostic was transferred from its mixed harness body
to `tests/prompt_autocomplete_harness_state.py`, which reads the new
presentation owner rather than a removed coordinator field. During that
verification it exposed a harness-only false positive: autocomplete previews
are explicitly direct-painted, so their retained cached-pixmap metadata is not
authoritative. The cache invariant now checks cache identity and revision only
when a collapsed-selection frame can use the cache; an owner-level negative
case prevents that distinction from being lost while all real cached-frame
checks remain strict.

Current focused evidence: 30 owner/session/ghost/presenter/architecture cases
passed; four non-xdist real-shell cases passed (common-sense harness
invariants, autocomplete arrow selection, ghost/dropdown visibility, and
cursor retarget/dismissal); targeted Ruff and strict mypy passed. The seeded
`autocomplete-navigation-acceptance` abuse campaign at
`build/prompt-editor-slice11-autocomplete-presentation-structural.json` passed
three repetitions with `correct=True` and `structural=True`. It was
instrumented structural evidence, not a timing baseline/candidate claim.

The entire architecture-guard module remains red on unrelated, already-open
refactor debt (the source-edit policy line budget, a reorder import-edge
expectation, interaction-controller line budget, and global protocol/private
test-debt ceilings). Those failures are recorded as blocking complete-slice
evidence; they are not weakened or treated as passing evidence here. The next
autocomplete transfer must first map one complete application query/result
responsibility below the Qt presenter boundary, then transfer its state,
lifecycle, cache, diagnostics, callers, and coverage while deleting its old
coordinator path in the same slice.

The query/result transfer's construction-cycle prerequisite is complete:
`PromptAutocompleteScheduledLoraContextController` now owns its explicit
one-time current-context binding and fails closed before that binding. The
composition-only `PromptAutocompleteCurrentContextBridge` and its duplicate
test bridge are deleted; the composition root binds the coordinator directly.
The owner rejects rebinding, so composition cannot silently replace live async
freshness authority.
This removes a permanent forwarding owner without adding work to any editor,
canvas, or workflow hot path. The focused query/result/context characterization
set passes 48 cases, including new unbound-context no-async-work and
rebind-rejection contracts;
targeted Ruff and strict mypy pass. One former result test now observes the
real presenter port rather than monkey-patching the deleted coordinator
presentation helpers.

The query/result transfer is now active in the production timing path.
`features/autocomplete_query_result_lifecycle.py` owns prepared-snapshot query
construction, query-kind selection, result-cache invocation, latest-query
async freshness, and immutable result publication. It receives no Qt source or
panel dependency: the only live callback is the narrow current-source identity
used by asynchronous stale-result rejection, and its publication port owns no
query or cache policy. The composition root now constructs the document query
authority before autocomplete, pairs the coordinator with this lifecycle in a
typed collaborator bundle, binds scheduled-LoRA freshness to the lifecycle,
and passes it directly to the timing owner. Focused owner contracts prove
inactive retargeting performs no query work, passive caret refresh performs no
result work, and prepared result publication performs no live source read; a
focused production-shell autocomplete selection scenario remains green.

The query/result transfer is complete. The legacy direct tag, scene, wildcard,
and LoRA refresh methods; their latest-query fields; result, scene-context, and
scheduled-LoRA dependencies; and the broad query-refresh controller are
deleted from `autocomplete_controller.py`. The coordinator now owns only Qt
key/presenter/focus translation, acceptance, and session-result publication;
its line count is reduced from 1,131 to 545. `PromptInteractionController` no
longer constructs a hidden autocomplete query fallback: composition supplies
the sole timing/lifecycle owner. Result, acceptance, session, projection, and
legacy timing characterization tests now construct the lifecycle directly or
through test-local observation boundaries, while real projection LoRA acceptance
drives the production lifecycle. An executable architecture guard rejects the
deleted coordinator query/cache surface, Qt imports in the lifecycle, and any
lifecycle dependency on presentation. Focused strict typing, owner/result,
acceptance, session, interaction, projection, real-shell, and architecture
checks pass; the retained autocomplete abuse campaign remains structurally
clean. The next transfer can now address the coordinator's remaining session,
acceptance, and Qt-input responsibilities without query/result overlap.

The session/publication transfer is complete. The new
`interactions/autocomplete_session_publication.py` is the sole owner of
autocomplete session transitions and prepared panel/ghost publication. It
contains the complete session controller, presentation lifecycle, result
publication, retargeting, selection, LoRA preview, geometry, and visibility
collaboration; the coordinator no longer retains either session or
presentation state. The coordinator is now a 487-line Qt interaction adapter
for key/presenter/focus translation and acceptance routing, down from 545
lines after the query/result transfer. Harness diagnostics derive their
session and panel observations from the new owner rather than reaching into
deleted coordinator fields. Focused session/result/acceptance owner coverage
(50 cases), the two ownership guards, and three real-shell navigation/ghost
scenarios pass. The three-repetition structural autocomplete abuse campaign
has zero invariant and structural violations, with current semantic and
projection snapshots throughout. This transfer performs no source querying,
cache lookup, layout construction, or canvas/workflow work during passive
session and presentation transitions. The remaining autocomplete transfers are
acceptance command ownership and the final thin Qt-input adapter.

The acceptance transfer is complete. The new
`interactions/autocomplete_acceptance_lifecycle.py` owns the full selected-row
transaction: mode-specific command acceptance through the existing command
owner, followed by the required session closure, including rejected stale or
missing-selection attempts. Clicked ordinary and LoRA row selection is part of
that same transaction; editor focus restoration remains at the Qt input
boundary. `autocomplete_controller.py` has no acceptance command owner or
session-close implementation. The acceptance owner is constrained by an
executable architecture guard and direct owner contract. Focused acceptance,
session, and result tests pass (48 cases); two real-shell selection scenarios
pass; and the three-repetition `autocomplete-navigation-acceptance` structural
abuse campaign is clean (zero invariant/structural violations, current
semantic/projection snapshots, 5/68 focused operations). Its key Tab action
remained below the 16.667 ms structural-frame target in all repetitions; this
is focused instrumented evidence, not a broad timing comparison. No query,
cache, layout, canvas, or workflow work was added to the acceptance path. The
remaining autocomplete work is to transfer Qt key/presenter/focus translation
into a narrow adapter and delete test-only migration scaffolding rather than
preserving it as internal compatibility.

The query/result lifecycle now publishes directly to
`PromptAutocompleteSessionPublication`; composition no longer routes immutable
results through the Qt coordinator. Retarget failure policy moved with the
session owner, preserving selection and incompatible-query dismissal behavior.
The debug probe and real-shell diagnostics derive their state from that same
publication owner. Focused query/session/acceptance coverage, a real-shell
selection scenario, and the direct-publication architecture guard pass.

The former autocomplete coordinator is now `PromptAutocompleteInputAdapter`
behind the narrow `PromptAutocompleteInputPort`; no production or test import
retains the coordinator/controller names. It owns only Qt key, presenter, and
focus translation, while query/result, session/publication, and acceptance
transactions remain in their dedicated owners. Focused strict typing, lint,
and 24 owner cases pass after the rename. The test-only query-refresh facade
has been deleted: its LoRA/wildcard priority and dormant/active retarget
characterization now run against `PromptAutocompleteQueryResultLifecycle`, and
the timing baseline now dispatches through that production lifecycle and its
immutable publication port. `PromptAutocompleteTestStack` is the explicit
test-composition result: acceptance, result, session, scheduled-LoRA, and
baseline coverage invoke the real query/result lifecycle and input adapter and
read the real session controller directly. The lifecycle wrapper, proxy
attribute forwarding, private session alias, legacy factory, and test-side
query routing are deleted. The focused migration set passes 80 tests, targeted
format/lint/strict typing, and autocomplete architecture guards.
The input adapter is additionally constrained by an executable owner guard: it
has no query/result, command, or session controller dependency and remains at
most 420 owned lines. A fresh real-shell selection run and three-repetition
structural abuse campaign pass after the rename; all runs remain correct,
structurally clean, and below the 16.667 ms structural-frame target.
After deleting the legacy test-side router, focused lifecycle/query/timing and
autocomplete architecture guards, strict typing, lint, and targeted formatting
pass. The one-repetition production autocomplete-navigation acceptance abuse
check remains correct and structurally clean (`build/prompt-editor-slice11-test-
facade-removal-structural.json`); it exercises 5 of 68 global operations and is
therefore feature-local evidence, not a full-matrix claim.

#### Diagnostics: next Slice 11 transfer

The next dependency-ordered feature boundary is diagnostics. Its current
915-line `PromptDiagnosticsFeatureController` still combines at least five
independent ownership domains: optional-provider activation and service
construction; debounced latest-wins request generation and stale rejection;
mutable diagnostic, ignored-id, visibility, and immutable snapshot
publication; prepared menu-action/suggestion data; and command execution plus
spellcheck-session mutation. The widget constructs it directly and owns its
signal-binding callback, while context-menu owners depend on its concrete type.
That is a mixed feature host rather than a one-way vertical slice.

The target transfer is: Qt-free provider and refresh lifecycles own activation
eligibility, provider/service topology, immutable request input, request
generation, cancellation, and stale rejection; one cohesive diagnostics
presentation owner owns the shared active-id filtering, cursor visibility,
surface publication, immutable diagnostic snapshot, prepared action data, and
command transactions through narrow source/command ports. Keeping that shared
state together prevents a second action/display authority or forwarding layer.
Context-menu snapshots depend only on its diagnostics query port; a thin
adapter owns signal translation and focus restoration. Prepared diagnostics
must remain free of backend work on cursor movement/menu opening, and
empty/unchanged source paths must retain their current
no-layout/no-geometry/no-repaint behavior. Transfer the whole state, cache,
lifecycle, commands, tests, and observability with each owner; delete the old
path in the same slice rather than leaving a facade.

Existing diagnostics controller, action-command, display-policy, projection
diagnostic-layer, real-shell, and abuse coverage is the characterization base.
Before code movement, add explicit owner tests for request/visible/action
boundaries and structural budgets for no provider, request, or source read on
cursor-only, unchanged, and prepared-menu paths. Compare the dedicated
diagnostic and unchanged canvas/workflow abuse scenarios against their current
controlled baseline before accepting each transfer.

The initial diagnostics characterization is
`build/prompt-editor-slice11-diagnostics-baseline.json`: three production
`spellcheck-diagnostic-action` repetitions are correct and structurally clean,
cover the refresh/context/action operations, and record the current owner work.
They are not timing acceptance evidence. The cold first context-menu sample is
27.679 ms (later samples 13.341 ms and 9.774 ms), above the structural-frame
target; the transfer must explain or remove that cold-path cost rather than
normalizing it into the new architecture.

The first diagnostics authority transfer is complete:
`diagnostics_provider_lifecycle.py` now solely owns activation eligibility,
optional provider construction, structured-value scoping, document-semantics
rebuild, spellcheck-provider lifetime, and the refresh service. The feature
controller no longer constructs providers or retains a duplicate service or
spellcheck-provider field. Its tests now inject a typed service/provider factory
at the provider boundary instead of writing private controller state. Focused
diagnostics controller, phase-3 stale-result, display-policy, and command tests
pass (32 cases), alongside targeted format, lint, and strict typing. The
remaining diagnostics transfers are request/result freshness, display
publication, and prepared action/command ownership; the controller is still
mixed and Slice 11 remains active.

Request freshness is now also a complete owner:
`diagnostics_refresh_lifecycle.py` owns debounce/cancellation, current-source
capture, request identity, latest-wins submission, stale rejection, and the
existing prompt-safe async-failure logging. It emits only typed empty, fresh
result, and failure transitions. The controller has no request id, stale guard,
async callback, or async identity path. The source controller is now 776 lines;
provider and refresh owners are 197 and 185 lines respectively. Focused
diagnostics/phase-3 stale-result tests pass, and a post-transfer production
spellcheck abuse run is correct and structurally clean with a single-run
context-menu p95 of 11.084 ms
(`build/prompt-editor-slice11-diagnostics-refresh-structural.json`). This is
feature-local instrumented evidence, not a controlled comparison.

The remaining diagnostics presentation transfer is now complete.
`diagnostics_presentation.py` is the sole owner of diagnostic snapshots,
ignored diagnostic IDs, visibility policy, surface publication, prepared
spelling suggestions/menu entries, and all diagnostic command transactions.
The action and display state move together because their active diagnostic set,
revision identity, and prepared callback bindings are one coherent transition;
the presentation reaches refresh through only the typed
`PromptDiagnosticsRefreshRequester` command after accepted spelling mutations.
`PromptDiagnosticsFeatureController` is a 190-line activation/refresh
orchestrator; it owns none of that presentation state and exposes the
presentation explicitly. The widget injects that owner directly into the
context-menu query port, so context menus no longer depend on the lifecycle
controller's concrete type. The former direct controller-owned state and
action methods are deleted rather than retained as compatibility forwarding.

The real-shell abuse checkpoint and wildcard driver now read the explicit
presentation snapshot rather than an obsolete lifecycle snapshot. Focused
diagnostics, phase-3, context-menu, real-shell diagnostic, and architecture
coverage pass (20 selected tests), together with targeted Ruff and strict
mypy. `build/prompt-editor-slice11-diagnostics-presentation-structural.json`
records a correct, structurally clean production
`spellcheck-diagnostic-action` repetition with a 9.635 ms context-menu p95.
It covers 3 of 68 global operations and is therefore feature-local structural
evidence only, not a controlled timing comparison or full abuse-matrix claim.
The executable architecture guard caps lifecycle orchestration at 220 owned
lines and presentation at 600, forbids restoration of provider construction,
async outcome handling, request ids, stale guards, service/provider state,
presentation state, actions, or result publication to the lifecycle owner, and
requires context-menu consumers to use the narrow query port.

#### Emphasis: Slice 11 characterization and transfer boundary

The next dependency-ordered feature boundary is emphasis. The current
626-line `interactions/emphasis_controller.py` owns keyboard selection
expansion, emphasis-shell/content range resolution, adjustment-session
creation/rebasing/clearing, source-backed weight commands, transient-neutral
presentation, caret restoration, and accent feedback. Its public host is
implemented by the 889-line general `PromptInteractionController`, which then
duplicates more than twenty emphasis, exact-weight, autocomplete, mutation,
syntax-state, focus, and transient-presentation operations as a broad facade.
`PromptExactWeightController`, key routing, mouse syntax routing, reorder
teardown, focus/hide teardown, and document-semantic transitions all cross
that facade. This makes the general interaction controller an implicit owner
of emphasis state transitions and risks work on non-emphasis paths.

The transfer must create one explicit emphasis interaction adapter that owns
the narrow editor/syntax/command/presentation ports used by the emphasis
session owner, inject the emphasis owner directly into exact-weight and key or
mouse consumers that require it, and delete the general controller's
emphasis-shaped forwarding methods in the same transfer. The adapter may call
the stable command, snapshot, cursor, and transient-presentation ports but may
not add scans, snapshot construction, callbacks, allocation-heavy wrappers, or
Qt work to ordinary key, paint, canvas, or workflow paths. Emphasis session
state stays single-writer at the existing projection/editor state owner; the
new adapter is a translator, not a second cache. The transfer must preserve
keyboard selection behavior, overlay/exact-weight ownership handoff, neutral
weight shells, caret boundary affinity, focus restoration, stale action
handling, and teardown on text, semantics, focus, hide, and reorder changes.

Characterization is green before this transfer: 22 focused syntax-action,
emphasis-overlay, and interaction-state tests pass. The three production
emphasis abuse scenarios are correct and structurally clean:
`build/prompt-editor-slice11-emphasis-syntax-baseline.json`,
`build/prompt-editor-slice11-emphasis-shortcut-baseline.json`, and
`build/prompt-editor-slice11-emphasis-wheel-baseline.json`. Their one-run
instrumented p95s are 15.862 ms, 6.144 ms, and 133.514 ms respectively; the
syntax and wheel outliers are baseline observations only, not accepted timing
evidence. The transfer needs controlled repeated comparison before claiming a
performance result.

The emphasis authority transfer is complete. Composition constructs
`PromptWeightInteraction` directly from the existing command, syntax-state,
semantic-refresh, feature-profile, editor, and projection ports. It is the
sole owner of the existing emphasis-session and exact-weight owners. Keyboard
shortcuts, token step/wheel signals, exact-edit controls, and surface syntax
actions therefore reach that owner directly. The generic interaction controller
no longer imports, constructs, applies, or publishes emphasis/exact-weight
commands; its remaining editor protocol contains only the cursor, text, and
pending-projection operations it actually uses. Its source is now 514 owned
lines and 45 methods, bounded at 530 and 55 respectively.

Keyboard and mouse routers each now consume a dedicated weight port rather
than asking the generic interaction host to forward feature behavior. The
composition signal bindings and widget also use the explicit weight owner, so
there is one direction of responsibility: Qt input/signal adapters -> weight
interaction -> command/syntax/transient-presentation ports. The executable
architecture guard forbids the deleted controller forwarding surface, requires
the direct key/mouse ports and factory/control/signal wiring, and caps the
cohesive weight owner at 600 owned lines (current 576). The document-service
builder was also made a focused module-level composition function, returning
the factory root to its existing 14-method cap rather than weakening that
integration-root guard.

Focused syntax, emphasis-overlay, interaction-state, reorder-keymap, and
token-weight geometry coverage passes (33 cases); the direct ownership and
integration-root architecture contracts pass; targeted Ruff and strict mypy
pass for the changed interaction/composition owners. The post-transfer
production-mounted abuse probes are correct and structurally clean:
`build/prompt-editor-slice11-emphasis-keyboard-shortcut-direct-owner.json`
(p95 6.232 ms),
`build/prompt-editor-slice11-emphasis-pointer-wheel-direct-owner.json`
(p95 11.069 ms), and
`build/prompt-editor-slice11-emphasis-syntax-formation-direct-owner.json`
(p95 3.336 ms). They are single-repetition, feature-local instrumented
structural evidence only, not a controlled baseline-versus-candidate
performance claim or a complete abuse-matrix result.

#### LoRA metadata: next Slice 11 transfer

The next dependency-ordered feature boundary is LoRA metadata. The current
414-line `PromptLoraMetadataFeatureController` still mixes three change
cadences: visible-editor dirty/catchup/render-refresh scheduling on the Qt
dispatcher; picker catalog-cache refresh and its immutable picker snapshot;
and foreground metadata/action snapshot publication, including model-page
action identity. The existing picker snapshot controller and context-action
controller are already focused collaborators, but their state transitions are
still coordinated with dispatcher state and foreground publication in the
single feature controller. The host also crosses into the general interaction
controller to ask whether LoRA spans exist and to republish LoRA render data.

The target transfer is a one-way feature slice: widget/signal adapters ->
LoRA refresh lifecycle -> narrow render-refresh port, with picker snapshot and
foreground metadata/action publication as explicit prepared-state owners.
The refresh lifecycle must be the sole owner of dirty, catchup-pending, and
render-refresh-pending state and dispatcher publication. The presentation
owner must be the sole writer of the public metadata snapshot and its action
identity. Existing picker-cache and context-action owners remain focused and
are consumed through typed ports, not copied or wrapped. The generic
interaction controller may retain its narrow render-state operation, but may
not acquire catalog, picker, action, or dispatcher state. No catalog query,
source scan, layout construction, signal fanout, or canvas/workflow work may
be added to passive cursor, paint, unchanged workflow, or unchanged canvas
paths.

Characterization is green before code movement: 30 focused metadata,
projection-refresh, and real-shell trigger/workflow cases pass. The production
`lora-picker-open-activate` structural baseline at
`build/prompt-editor-slice11-lora-metadata-baseline.json` is
`correct=True` and `structural=True`; its one-repetition p95 is 15.725 ms and
max is 18.136 ms under instrumented conditions. It is a baseline observation,
not timing acceptance. The transfer must preserve catalog-failure recovery,
hidden-editor dirty retention, one queued catchup/refresh unit, no-LoRA
projection skips, picker readiness, prepared trigger/model-page actions,
source-stale rejection, undo/replacement recovery, and workflow isolation.

The LoRA metadata transfer is complete. Production construction creates
`PromptLoraMetadataPresentation` and `PromptLoraMetadataRefreshLifecycle`
directly. Presentation is the sole owner of immutable metadata and picker
snapshots, picker cache state, scheduler text, and model-page action
preparation; the lifecycle is the sole owner of dirty, catchup-pending, and
render-refresh-pending state plus dispatcher publication. Widget lifecycle
hooks call refresh directly, while popup, context-menu, inline-menu, trigger
word, and catalog-revision consumers receive presentation directly. The former
mixed controller is deleted, including its broad host protocol and all
production/test references.

An executable architecture guard requires the deleted controller to remain
absent, forbids Qt and picker state in the lifecycle, requires picker/context
action state in presentation, requires direct widget/factory wiring, and caps
presentation and refresh owners at 225 owned lines (currently 219 and 222).
Focused metadata, projection-refresh, context-menu, numbered-frame,
panel-refresh, and selected real-shell LoRA behavior coverage passes (37
cases), with targeted Ruff and strict mypy for the changed owners. The
post-transfer production `lora-picker-open-activate` campaign at
`build/prompt-editor-slice11-lora-metadata-owners.json` is
`correct=True` and `structural=True`, with a one-run p95 of 9.236 ms and max
of 12.585 ms. This is feature-local instrumented structural evidence rather
than a controlled timing comparison or complete abuse-matrix claim.

#### Wildcards: completed Slice 11 transfer

The former 867-line `PromptWildcardFeatureController` is deleted. Its mixed
responsibilities now have direct authorities: Qt-free
`PromptWildcardDiagnosticsPresentation` prepares only wildcard diagnostic
providers and diagnostic menu actions; Qt-free
`PromptWildcardAutocompletePresentation` owns only asynchronous autocomplete
request lifecycle, stale rejection, failure publication, and prepared query
state; and `PromptWildcardAutocompleteCache` is the sole bounded-LRU owner.
Immutable shared query/request values live in `wildcard_models.py`. Composition
creates both owners directly. Diagnostics consumes a narrow provider port, and
autocomplete consumes its existing narrow result-provider port; no consumer
depends on a general wildcard feature object.

The autocomplete foreground path still reads only prepared cache state. A cold
query submits latest-wins background work and returns an empty/cold snapshot;
it never synchronously searches the catalog. The owners do not read prompt
text, construct layout, paint, or run on unchanged canvas/workflow activity.
The old unused per-query snapshot map was removed rather than moved. The
architecture guard requires the deleted module to remain absent, forbids
diagnostics/action code in autocomplete, forbids request-channel state in the
LRU, requires direct factory wiring, and limits the owners to 650, 110, and 85
owned lines respectively (currently 622, 95, and 63).

Focused wildcard, autocomplete, diagnostics, construction, and architecture
owner coverage passes 55 cases, and targeted Ruff plus strict mypy of the ten
new/changed lower-layer owners pass. Strict mypy of `widget.py` remains blocked
by its pre-existing 37 unrelated strict errors, so it is not claimed as clean.
The wider architecture guard currently reports unrelated dirty-tree failures in
source-edit policy size, reorder import expectations, and pre-existing global
protocol/private-access budgets; the wildcard-specific guard passes.

The post-transfer production `wildcard-prompt-syntax` candidate campaign at
`build/prompt-editor-slice11-wildcard-owners-prompt-syntax.json` is
`correct=True` and `structural=True`, one-run p95 0.097 ms. One-repetition
candidate campaigns for TXT typing, quoted CSV typing, duplicate scope, scene
help, Alt reorder, mouse reorder, whole-line cancel, and autoscroll all report
`correct=True` and `structural=True` in the corresponding
`build/prompt-editor-slice11-wildcard-*.json` artifacts. These are
feature-local instrumented structural checks, not controlled timing comparison
evidence and not a complete abuse-matrix claim.

#### Context-menu snapshots: active Slice 11 transfer

The next dependency-ordered feature boundary began as the 714-line
`PromptContextMenuSnapshotController`. It combined immutable public models and
identity/readiness policy; six feature-specific preparation/read ports;
prepared action aggregation; selection and source-position preparation
dispatch; freshness identity construction; concern readiness derivation; and
unavailable-concern logging. This was a genuine mixed product boundary, not a
candidate for another forwarding shim.

The target is a Qt-free, one-way chain: feature owners publish prepared
snapshots -> a focused menu-preparation lifecycle dispatches explicit
selection/position prewarm commands -> a pure snapshot assembler derives
actions, identities, and concern readiness -> a thin Qt menu presenter consumes
the immutable result. Shared immutable request/action/identity/readiness models
must leave the owner modules. Preparation must remain explicit;
`snapshot_for_menu` must stay a cheap prepared-state read and must not invoke
catalog queries, source scans, layout, paint, or fresh feature work. The
transfer must move the whole preparation lifecycle, assembler policy, models,
callers, tests, observability, and direct composition wiring, then delete every
adapter indirection without independent responsibility.

Characterization is green: ten focused context-menu snapshot cases pass. A
direct contract now proves a snapshot read performs no LoRA prewarm call while
still consuming the prepared trigger snapshot. The next transfer must add
owner contracts that prove stale scene context fails closed
without trigger lookup, selected-text preparation calls only segment and
Danbooru owners, source-position opening calls only scene/trigger prewarm, and
unchanged menu snapshots preserve identity/readiness without source/layout/
canvas work. Use the existing real-shell menu traces plus the
`lora-trigger-word-menu-action`, `spellcheck-diagnostic-action`, and
`wildcard-scene-context-help` abuse scenarios for behavior and structural
evidence before accepting the transfer.

The first context-menu authority transfer is complete:
`context_menu_preparation.py` now owns explicit selection-dependent Segment and
Danbooru preparation plus source-position Scene/LoRA-trigger prewarming.
`PromptContextMenuSnapshotAssembler` no longer exposes or performs either
preparation path. The forwarding `PromptContextMenuActionController`, its
obsolete test path, and the former mixed `context_menu_snapshot.py` module are
deleted. Immutable values now live in `context_menu_models.py`; the six narrow
prepared-state read ports live in `context_menu_ports.py`; and the assembler
owns only aggregation, identity/readiness derivation, and prompt-safe
unavailability logging. Composition creates the preparation lifecycle and
assembler directly; the Qt presenter accepts two narrow consumer-owned ports,
invokes preparation before reads, and reads immutable snapshots directly. This
leaves no dual authority, wrapper, or composition migration property. Focused
snapshot, direct-ownership, request-presenter, and relevant architecture
coverage passes 19 cases; targeted Ruff and strict mypy of the changed lower
layers pass. The snapshot-read no-prewarm contract remains green.

Final-tree real-shell structural campaigns are `correct=True` and
`structural=True` for LoRA trigger-word menu action, spellcheck diagnostic
action, and wildcard scene-context help. Their reports are
`build/prompt-editor-slice11-context-menu-lora-final.json`,
`build/prompt-editor-slice11-context-menu-diagnostic-final.json`, and
`build/prompt-editor-slice11-context-menu-scene-help-final.json` respectively.
The one-repetition instrumented p95 readings are 7.970 ms, 11.869 ms, and
7.135 ms. They are structural evidence on the final tree, not a controlled
baseline-versus-candidate timing comparison; no timing conclusion is claimed.

#### Scenes: next Slice 11 transfer

The next feature authority is the 570-line `PromptSceneFeatureController`.
It currently combines five change reasons: immutable scene values; workflow
title and queue-key publication; autocomplete suggestion derivation;
source-position effective-prompt calculation and revision identity; and the
bounded prepared-position cache. The target direction is `widget workflow
adapter -> scene publication/preparation owners -> immutable scene snapshots
-> autocomplete/context-menu consumers`. The cache must remain the sole
revision-keyed prepared-position authority; menu reads must remain cache-only,
and no source read, scene scan, or cache allocation may reach caret, paint,
scroll, workflow, or unchanged-canvas paths.

Characterize before transfer: scene-title normalization and limits; scene-free
fallback; queue eligibility; prepared/unprepared/stale position reads;
revision, profile, semantics, cube, and queue-key invalidation; cache reuse;
and all context-menu, autocomplete, scheduled-LoRA, and workflow callers.
The complete transfer must split values, publication, suggestion derivation,
and prepared-position caching by coherent mutable state, migrate every caller,
delete the mixed controller, and prove real-shell scene/context behavior plus
focused structural and controlled performance evidence on the final tree.

The immutable-value transfer is complete: scene position, autocomplete, queue,
and context snapshot values now have the Qt-free authoritative home
`scene_models.py`; `scene_controller.py` imports them rather than defining
duplicates. Scene-title suggestion derivation is now the pure
`scene_suggestions.py` owner, with no host, cache, workflow, or Qt dependency.
Focused scene contracts passed ten cases, with targeted Ruff and strict mypy
clean for both transfers. At that point, publication and prepared-position cache
state remained in the controller pending the complete direct-owner transfer;
the final record below confirms that no delegation seam remained.

##### Historical paused scene-transfer boundary

This was the paused state on branch `refactor/prompt-editor-architecture` while
the repository was intentionally dirty and uncommitted. The final scene-owner
record immediately below supersedes it; it remains only to preserve the
characterization boundary used for the completed transfer. Complete repository
gates and a commit still require the maintainer's exact instruction `commit your
work`.

At that point, the scene transfer was intentionally incomplete and could not be
accepted as the final architecture. `scene_controller.py` was 485 physical lines,
down from 570 only because the 100-line immutable model authority and 55-line
pure suggestion policy moved to focused modules. It still authoritatively owns
workflow title/queue publication, cube/scene identity, source-position
effective-prompt preparation, revision-key construction, the prepared-position
cache, unavailable-state derivation, and aggregate snapshot publication.
`scene_autocomplete_suggestions()` then reached the pure suggestion owner
through the controller. This temporary point in the active vertical transfer
was not permission to leave a delegation bookmark; the completed transfer
migrated the autocomplete consumer to the narrow scene-suggestion boundary and
deleted that controller surface.

The completed transfer traced every `PromptSceneFeatureController` caller, then
moved the complete prepared-position responsibility—cache state, key
construction, invalidation, scene/effective-prompt derivation, stale/unavailable
policy, identities, observability, and tests—to one focused Qt-free owner. It
also transferred workflow title/queue/context publication to its own focused
owner, wired context-menu, autocomplete, scheduled-LoRA, widget workflow
updates, and test composition directly to the appropriate narrow owners, and
deleted
`scene_controller.py`, its package export, broad host Protocol, obsolete
methods, casts, private test access, and transitional caller paths in the same
scene slice. The final shape does not replace the mixed controller with a
coordinator, facade, service locator, or forwarding shell.

The completed transfer preserves the cache-only menu-read invariant: after
explicit preparation, `prepared_position_context()` performs no source read,
scan, or allocation-producing recomputation; an unprepared or identity-less
read fails closed. It also preserves title normalization/limit behavior,
scene-disabled behavior, queue eligibility, effective-prompt materialization,
revision/profile/semantics/cube/scene/queue-key invalidation, cache reuse, and
unique effective-prompt enumeration. Direct owner-level and architecture
contracts, plus the affected real-shell scene, context-menu, autocomplete,
scheduled-LoRA, workflow, unchanged-canvas, abuse, structural-budget, and
controlled performance lanes, verify the resulting tree.

Evidence already valid at this handoff:

- `tests/test_prompt_scene_feature_controller.py`: 10 passed;
- targeted Ruff passed for `scene_models.py`, `scene_suggestions.py`,
  `scene_controller.py`, and the focused scene test;
- strict mypy passed for `scene_models.py`, `scene_suggestions.py`, and
  `scene_controller.py`;
- the earlier final-tree context-menu campaigns and 19 focused context-menu
  contracts recorded above remain valid for the context-menu transfer, but any
  later scene wiring change invalidates the applicable scene/context evidence
  and requires one focused rerun after the final scene call graph lands.

##### Final scene transfer evidence (uncommitted)

The mixed `scene_controller.py` and its broad `PromptSceneSourceHost` Protocol
are now deleted. `PromptSceneContextPublication` is the direct owner of the
workflow title, queue-key, cube/scene identity, and aggregate immutable scene
snapshot (129 lines, 8 methods). The Qt-free
`PromptScenePositionContextPreparation` is the direct source-position owner of
effective-prompt materialization, scene/queue derivation, revision/profile/
semantics/cube/scene/queue cache keys, stale/unavailable policy, bounded LRU
prepared-position cache, and cache-only foreground reads (332 lines, 14
methods). `scene_suggestions.py` remains the 56-line pure title policy.

Composition, widget workflow updates, context-menu preparation/assembly,
inline LoRA menu preparation, scheduled-LoRA effective-prompt enumeration, and
autocomplete now wire directly to those narrow owners. Autocomplete consumes
the immutable publication autocomplete state through `scene_suggestions.py`;
it no longer delegates through a scene feature controller. The obsolete package
export, old test factory, broad scene source Protocol, controller test access,
and controller module are deleted. New direct owner contracts cover publication,
suggestion policy, scene-disabled behavior, prepared/unprepared/identity-less
reads, queue-key invalidation, cache reuse, bounded cache ownership, and
Qt-free deletion architecture.

The first real-shell scheduled-LoRA context-menu run exposed an actual scene
wiring defect, not a native Qt failure: snapshot assembly received the prepared-
position owner for both of its required concerns and tried to read a missing
`snapshot` property. The final boundary is now explicit: the assembler consumes
`PromptContextMenuSceneSnapshotPort` from publication and
`PromptContextMenuScenePositionPort` from preparation, while context-menu
preparation consumes only the position command port. The correction removes
the exception cascade through Qt event filters without restoring any controller
or combined scene facade.

Focused evidence on the current tree: 54 selected scene, autocomplete,
context-menu, scheduled-LoRA, wildcard, and real-shell ownership tests pass;
the focused projection-pipeline and real-shell per-character scene-title
regression set also passes. Targeted Ruff format, lint, and strict mypy pass
for the changed lower-layer blast area. The serial real-shell trigger-context
trace and 50-row timing scenario both pass.
Three-repetition production-mounted `scene-marker-creation`,
`lora-trigger-word-menu-action`, and `wildcard-scene-context-help` structural
campaigns are each `correct=True` and `structural=True` in
`build/prompt-editor-slice11-scene-owners-structural.json`,
`build/prompt-editor-slice11-scene-lora-structural.json`, and
`build/prompt-editor-slice11-scene-context-structural.json`. They cover 3/68,
2/68, and 3/68 global operations respectively and are feature-local structural
evidence, not controlled baseline-versus-candidate timing comparisons. The
first exact scene-title comparison initially caught a visibility regression:
when a stale projection reached a wrap boundary, the pipeline deferred catch-up
without a valid transient text or caret owner. The pipeline now permits
deferred-wrap scheduling only where direct transient feedback is eligible; an
unsafe wrap instead applies its prepared reflow immediately. The new
real-shell character-by-character title test proves that the source is either
current in the projection or covered by a valid insertion overlay after every
keypress. The repaired three-repetition candidate is correct and structurally
clean, and the exact comparison in
`build/prompt-editor-slice11-scene-spaced-title-comparison-fixed.json` reports
`correct=True->True` against `bc6c6a7b` with no correctness regression. The
full architecture guard initially remained red on its source-edit line budget,
reorder import edge, and global protocol/private-test-debt ceilings. The
source-edit syntax extraction and test-boundary cleanup have since returned the
line and private-test budgets to their recorded limits without weakening them.
The reorder publication graph is now restored at its intended ownership
boundaries, and the global Protocol count is 199 against its unchanged 199
ceiling. The reconciliation removes incidental reorder host-shaped Protocols in
favour of direct construction-owned collaborators, immutable state snapshots,
or narrow callbacks; it does not raise a debt limit or restore a controller,
facade, or service locator. Targeted Ruff, strict mypy, keyboard interaction
coverage, and all 50 architecture guardrails pass on this final scene tree.

The controlled unchanged lifecycle/canvas/workflow comparison is also complete:
three uninstrumented repetitions at `bc6c6a7b` and the final scene tree are
both correct, with no correctness regression in
`build/prompt-editor-slice11-scene-lifecycle-comparison.json`. The candidate
p95 is 38.445 ms versus the baseline 32.694 ms while maximum latency improved
from 100.146 ms to 83.765 ms; this mixed, representative-host result is
behavior-preservation evidence only and is not claimed as a performance win.
The scene transfer may now be accepted without weakening unrelated debt limits;
the next feature transfer remains governed by the dependency-ordered Slice 11
ledger.

### Slice 1 acceptance ledger

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

### Slice 2 acceptance ledger

Slice 2 is complete only when:

- domain and application prompt owners live in cohesive responsibility
  subpackages with inert package roots;
- every internal caller imports its authoritative owner directly;
- the application package has no lazy export registry, dynamic dispatch, or
  service-locator barrel;
- shared immutable LoRA catalog values live below catalog construction and
  ranking, and the catalog/ranking cycle is deleted;
- regional models, scene models/parsing/materialization, and reorder
  models/derivation/mutations/serialization have distinct authoritative owners
  rather than renamed mixed modules;
- the canonical prompt parser still performs one structural scan and the
  document cache retains identity reuse, prewarm, boundedness, and Qt-free
  ownership;
- no executable behavior is changed accidentally by the repository-wide import
  transfer;
- the complete structural matrix and representative baseline comparison show
  no correctness, canvas/workflow, structural-work, or performance regression;
- focused and complete repository gates pass for the exact slice worktree.

### Slice 2 evidence

All 57 flat application modules and 17 flat domain modules now live beneath
cohesive responsibility packages. Both package roots are inert markers:
internal consumers use direct module imports, and executable architecture tests
reject future flat modules, root-barrel imports, lazy registries, new package
names outside the declared ownership graph, and import-cycle growth.

The LoRA catalog values and read port now live in `lora/catalog_models.py`.
Catalog construction and ranking both depend on those immutable values, so the
former catalog/ranking strongly connected component is gone. Domain ownership
was completed rather than hidden by folders: `SourceRange` has a foundational
range owner; regional models no longer live in the general document model;
scenes have separate model, parser, and materialization owners; and the former
1,354-line reorder pair is replaced by direct model, derivation, mutation, and
serialization owners. Old modules, package exports, and internal compatibility
paths are deleted.

Repository-wide AST comparison proves that all 153 touched production modules
outside the transferred prompt packages changed only import declarations.
Equivalent comparison across 56 non-catalog application owners proves their
executable bodies are unchanged apart from direct imports and module-accurate
logger names. The catalog difference is the intentional immutable-value
extraction. Focused strict mypy passes across all 100 domain/application prompt
modules. The focused prompt domain, document, LoRA, scene, reorder, startup
import, logging, and architecture suites pass.

The complete real-shell structural campaign at
`build/prompt-editor-slice2-structural.json` covers all 68 required operations
with `correct=True` and `structural=True`. It includes unchanged canvas and
workflow round trips, regional separators, ordinary editing/navigation,
selection, paint/caches, diagnostics, autocomplete, LoRA, scenes, and reorder.

Timing uses fresh processes that assert every loaded `substitute` module belongs
to the selected worktree. The exact pre-slice baseline is `d40e920c`, and both
roots use the same timing-only call path. Six short process pairs reverse
baseline/candidate order and provide 30 samples per lane on fixed four-core
affinity. Candidate total elapsed time and process CPU are lower in every pair.
Median paired p95 deltas are -4.315 ms for 5k Enter, -3.272 ms for 5k Delete,
-2.546 ms for horizontal Alt navigation, -1.829 ms for 5k selection,
-0.854 ms for Danbooru paste/import, and -0.447 ms for prepared paint-cache
composition. Longer non-interleaved runs showed large machine-wide swings in
both directions across every unrelated lane; those invalid comparisons are
retained as diagnostic artifacts and are not used as evidence.

Repository format and lint, the license-header audit, strict mypy over 2,882
source files, the complete non-serial suite, and all 121 serial modules pass.
The serial run includes the prompt-editor real-shell harness, autocomplete,
canvas abuse and scenarios, workflow scenarios, IME, caret, selection,
paint-cache, reorder, diagnostics, history, and toolbar rendering. Slice 2 is
complete.

### Slice 3 acceptance ledger

Slice 3 is complete only when:

- the prompt feature exposes only a caller-neutral typed preset source and
  immutable snapshot contract;
- active-model context consumption, prompt-specific model-scope derivation,
  persistence adaptation, and menu-model construction have one authoritative
  panel adapter;
- no prompt-editor module imports its panel host, and the zero-inversion rule is
  executable architecture policy rather than a frozen exception;
- the obsolete prompt-owned concrete source, exports, scope policy, imports,
  tests, and inventory paths are deleted or transferred in the same slice;
- existing exact, family, Global, unavailable-catalog, save, and cache-only
  behavior remains characterized through the new owner;
- active-model refresh, panel composition, context-menu behavior, and the
  caller-neutral library source remain unchanged;
- ordinary editing, navigation, rendering, workflow switching, and unchanged
  canvas round trips perform no new preset work;
- focused and complete repository gates pass for the exact slice worktree, and
  repeated baseline comparison shows no performance regression.

### Slice 3 evidence

The caller-neutral `PromptSegmentPresetSource` and
`PromptSegmentPresetSourceSnapshot` remain in the prompt feature contract.
Their sole live-panel implementation is now
`panel/prompt/preset_adapter.py`, which owns prompt-specific active-model
snapshot consumption, model-scope derivation, persistence adaptation, and menu
construction. The former prompt-owned concrete source is deleted rather than
retained as a forwarding module. Prompt-specific policy was also removed from
the shared panel menu policy, leaving that owner focused on dimension and
node-input consumers.

The import-graph guard now requires an empty prompt-editor-to-panel dependency
set. The focused architecture, adapter, active-model, dimension/node-input
preset, library-source, prompt-controller, catalog-snapshot, context-menu,
panel-factory, panel-composition, and editor-panel behavior suites pass. The
pre-transfer adapter characterization also passed before ownership moved,
covering exact/family/Global ordering, checkpoint and diffusion-model scopes,
catalog failure fallback, selected-scope persistence, and the prohibition on
foreground model listing. Targeted strict mypy passes for the new adapter,
remaining shared panel policy, caller-neutral contract, transferred tests, and
architecture policy.

The complete production-mounted structural campaign at
`build/prompt-editor-slice3-structural.json` contains 204 runs: all 68 declared
operations repeated three times. It reports no missing coverage, invariant
failure, structural-budget violation, or stale final projection/semantic state.
This includes ordinary editing, navigation, selection, paint/caches, prompt
features, workflow switching, regional separators, and unchanged canvas round
trips.

Timing uses the exact pre-slice `b024d017` worktree and candidate in alternating
fresh processes. Both roots execute the same timing-only path and assert that
all loaded `substitute` modules belong to the selected worktree. Six pairs
provide 30 samples per lane. Candidate total elapsed time is 15.148 seconds
versus 15.690 seconds for baseline. Median p95 deltas are -0.169 ms for 5k
Delete, -0.086 ms for horizontal Alt navigation, -0.035 ms for 5k Enter,
-0.012 ms for prepared paint-cache composition, +0.007 ms for 5k selection,
and +0.175 ms for Danbooru paste/import. Paired medians place 5k Enter at
+0.269 ms and Danbooru at +0.208 ms; both untouched paths move in opposite
directions across pair order and remain below the observed sub-millisecond
process-noise floor. The transfer adds no work to typing, editing, layout,
paint, or canvas code and retains the cache-only/no-foreground-listing owner
contract.

Repository format and lint, the license-header audit, strict mypy over 2,883
source files, the complete non-serial suite, and all 121 serial modules pass.
The serial run includes prompt-editor characterization, context menus,
autocomplete, IME, caret, geometry, incremental editing, paint/cache, history,
reorder, direct workflow scenarios, the output-canvas abuse matrix and canvas
scenarios, the production real-shell harness, and toolbar rendering. Slice 3 is
complete.

### Slice 4 acceptance ledger

Slice 4 is complete only when:

- source, semantic, projection, layout, viewport, and paint revisions are
  distinct typed identities with non-negative validation at their publication
  boundaries;
- one inspectable revision graph records the exact upstream lineage of every
  published snapshot and rejects cross-source or stale-upstream publication;
- `PromptEditingSession` remains the sole source-revision writer, and the
  projection surface no longer mirrors that revision in independent mutable
  state;
- semantic document and render-plan references publish atomically under one
  semantic identity rather than as independently assignable fields;
- projection publication records the semantic identity it consumed, and layout
  publication records the exact projection identity it laid out;
- viewport identity changes only when its prepared geometry key changes, paint
  identity records layout, viewport, and paint-state revisions, and ordinary
  cache reads do not allocate or advance revisions;
- committed/stale projection geometry is represented by recorded revision
  lineage instead of inferred from unrelated source counters, object identities,
  and manual diagnostic-layout counters;
- validation compares identities and existing immutable references only: it
  performs no full-source copy, hash, parser scan, layout walk, widget query, or
  signal emission;
- all live call sites use the authoritative state owner, while obsolete source
  mirrors, diagnostic-only layout counters, and private harness reconstruction
  of revision consistency are removed in the same slice;
- owner tests characterize successful publication, no-op reuse, stale rejection,
  rollback, deferred projection, paint-cache hits, and revision inspection;
- the complete real-shell abuse matrix, structural budgets, unchanged
  canvas/workflow round trips, and repeated pre-slice performance comparison
  show no behavior, work, allocation, or latency regression;
- focused and complete repository gates pass for the exact slice worktree.

### Slice 4 ownership inventory

The pre-transfer graph has six disconnected identity conventions:

- `PromptEditingSession` and `PromptSourceBuffer` own the real source revision,
  while `PromptProjectionSurface._source_revision`,
  `PromptCommandSourceIdentity`, async identities, freshness metrics, transient
  overlays, and paint keys copy the same raw integer;
- `PromptSyntaxStateController` owns semantic publication but stores the
  document view and render plan separately, so their atomic relationship and
  source lineage cannot be inspected;
- projection documents are immutable values, but publication has no identity;
  the surface, active-preview path, and layout retain separate document
  references without an explicit base/preview lineage;
- layout snapshots are immutable geometry, but have no projection or width
  identity. `PromptDiagnosticPainter` maintains a separate manually advanced
  “layout revision” that is not the layout snapshot's identity;
- viewport width, height, and scroll values are repeatedly folded into cache
  keys without a prepared viewport identity;
- paint state is immutable, but cache freshness combines raw source revision,
  Python object identities, geometry metrics, palette values, and manual
  invalidation. The real-shell harness reconstructs consistency by reading those
  private fields independently.

Slice 4 transfers identity and lineage ownership, not the layout and rendering
algorithms assigned to later slices. Pure projection construction remains a
pure value operation; the publication owner assigns identity only when a result
becomes authoritative. Layout continues to build its existing immutable
geometry snapshots, but every assignment goes through one publication boundary.
Viewport and paint revisions are prepared and advanced on state transitions,
never during a warm paint-cache lookup.

### Slice 4 implementation evidence

The candidate now has one typed source-to-paint publication graph in
`core/state`. Source, semantic, projection, active-frame projection, layout,
viewport, and paint identities retain exact upstream identity references.
Publication validates non-negative revisions, authoritative upstream identity,
and O(1) source length; it does not copy, hash, compare, or scan full prompt
text. Deferred geometry records its committed semantic lineage explicitly, and
exact same-text semantic refresh rebases retained projection, layout, and paint
values without rebuilding them.

The projection surface no longer owns `_source_revision`,
`_document_view`, `_render_plan`, or `_projection_document`. The diagnostic
layout counter and raw integer source mirrors in transient overlays and reorder
state are also gone. The real-shell harness now inspects the public revision
graph and active frame projection instead of reconstructing consistency from
those private fields. Frame publication and width resolution live in focused
`projection/frame_state.py`, while the complete layout/viewport/scroll/region
chrome synchronization responsibility moved out of the surface into
`projection/frame_synchronizer.py`; the old surface paths were deleted rather
than retained as parallel authorities.

Owner contracts cover initial and advanced lineage, staged optimistic semantics,
committed versus transient frame projections, exact downstream rebasing,
rollback, stale and foreign upstream rejection, unchanged layout/viewport/paint
reuse, and warm frame synchronization. The stricter source identity boundary
also exposed semantic-refresh tests that bypassed production source
publication. Their shared editor double now publishes through the revision
owner, preserving the production ownership path rather than weakening
validation.

Performance investigation rejected an initially adverse 5k Delete signal and
traced added work instead of attributing it to host noise. Source buffer and
snapshot identities are now cached per source revision, direct source-buffer
mutation is prohibited, identity-chain validation uses authoritative reference
comparisons, and semantic freshness no longer allocates a diagnostic revision
graph. Disabled debug probes now return before owner traversal or
serialization. In four profiled 5k Delete runs this removes all 420 transient
revision-graph builds, reduces source-identity construction from 336 to 166,
and lowers disabled probe self-work from 16.764 ms to 2.098 ms.

The final 5k Delete comparison uses six fresh-process pairs, reverses process
order, fixes affinity and priority, asserts module provenance for both roots,
and includes 180 scenario samples per variant. Median paired edit latency is
3.11% lower for the candidate, median process CPU is 3.36% lower, median wall
time is 4.13% lower, and the paired mean-latency median is effectively equal at
-0.11%. Large opposing outliers remain in the artifacts and correlate with
approximately 48% competing CPU load; they are not removed or used to claim an
improvement.

The post-optimization six-lane comparison reports paired median deltas of
-0.23 ms for 5k Enter, -0.16 ms for 5k selection, -0.11 ms for Danbooru
paste/import, and -0.04 ms for prepared paint-cache composition. Its short
5k Delete and horizontal Alt samples moved by +0.43 ms and +0.40 ms under
bursty load. The longer Delete campaign above resolves its signal. A separate
180-sample Alt campaign resolves the second signal with a -0.022 ms/-0.48%
paired median, effectively unchanged process CPU at -0.12%, and large
opposing per-pair outliers retained in the artifacts.

The production-shell prompt editor, autocomplete scenarios, output-canvas
scenarios, and output-canvas abuse matrix pass together. The final enforced
structural report at `build/prompt-editor-slice4-structural.json` contains 204
runs: all 68 operations repeated three times, with no missing operation,
invariant violation, structural-budget violation, or stale final semantic or
projection state. It includes the complete regional-separator hostile corpus,
workflow and unchanged-canvas round trips, navigation, selection, history,
paint/cache, autocomplete, diagnostics, LoRA, scenes, and reorder. Complete
repository formatting and lint pass. Strict mypy passes all 2,893 checked
source files, the complete non-serial suite passes, and all 121 serial modules
pass on the exact final source tree. The serial gate includes prompt-editor
characterization, IME, navigation, incremental editing, paint/cache, history,
reorder, production real-shell prompt and autocomplete coverage, direct
workflow scenarios, output-canvas scenarios and abuse, widget abuse, toolbar
rendering, and workspace integration. Slice 4 is complete.

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
      ranges.py
      parser.py               # one canonical bounded scan
      structural_scan.py      # shared quote/escape/parenthesis scanner
      serializer.py
      syntax.py
    emphasis/
      semantics.py
      operations.py
      formatting.py
      normalization.py
    regions/
      models.py
      parser.py               # participates in canonical scan; no second scan
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
    features/
      models.py
    preferences/
      models.py

  application/prompt_editor/
    document/
      views.py
      projector.py
      semantics.py
      selection.py
      cache.py
      service.py
      view_mapper.py
    editing/
      mutation_service.py
      literal_parentheses.py
      region_separator_normalization.py
      region_structure_edits.py
      source_normalization.py
      syntax_actions.py
      structured_syntax.py
      structured_text.py
      text_ranges.py
    projection/
      structured_syntax.py
      syntax_service.py
    autocomplete/
      queries.py
      query_service.py
      tag_ranges.py
      text.py
      structured_mapping.py
    diagnostics/
      models.py
      coordinator.py
      display_policy.py
      duplicate_mutations.py
      duplicate_segments.py
      spellcheck_candidates.py
      spellcheck_models.py
      spellcheck_provider.py
      spellcheck.py
      structured_values.py
      wildcard.py
      unsupported_scenes.py
    lora/
      catalog_models.py
      catalog.py
      ranking.py
      resolution.py
      autocomplete.py
      schedule.py
      scheduled.py
      diagnostics.py
      effective_provider.py
    reorder/
      views.py
      projection.py
      drop.py
      gap_layout.py
      semantics.py
      serialization.py
      structured_document.py
    scenes/
      projection.py
      workflow_analysis.py
    features/
      definitions.py
      profile.py
      preferences.py
      syntax_profile.py
      workflow_graph.py
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
