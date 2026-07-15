# AGENTS.md

## Scope

This file governs work under `substitute/presentation/canvas/`.

It adds canvas-specific engineering rules for Input canvas, Output canvas, QPane
hosting, canvas tabs, projection, routing, visual event handling, mask handling,
and canvas lifecycle code. Repository-level `AGENTS.md` still applies.

Canvas-related edits outside this folder must honor this file when the edit
changes canvas behavior, canvas state ownership, QPane usage, backend visual
event handling, input image loading, mask loading, workflow switching, or
canvas-host lifecycle behavior.

## Source Ownership Standard

Canvas work must preserve strict separation of concerns.

Every source file must have one coherent responsibility and one primary reason
to change. If a change touches a mixed-responsibility area, first identify the
actual owner for the behavior, then move new or changed behavior to that owner
instead of expanding the mixed file.

Behavior remains governed by the product contract below and by characterization
tests.

## Documentation Truthfulness

Document the canvas product and code as they exist now.

- Describe implemented package shape and current ownership as facts.
- Label remediation targets as targets until code and guardrails prove they
  are current behavior.
- Do not describe removed features, imagined alternatives, or non-existent
  choices as current product behavior.
- Do not use documentation to weaken backend identity requirements, QPane
  ownership rules, or input mask correctness rules.

## Canvas Mission

The canvas system must make wrong-workflow, wrong-canvas, and wrong-image
placement bugs structurally impossible.

The application uses one Input QPane and one Output QPane. QPane retains images
for speed and rendering continuity. Workflow switching changes the active
session, projection, and route binding; it must not depend on unloading and
reloading QPane catalog entries.

The canvas system must feel stable and immediate under normal and large
workflows. Generated output routing, preview updates, scene composition, input
image loading, mask editing, focus changes, tab switching, docking, and floating
window behavior must remain predictable and responsive.

## Product Contract

Preserve current canvas behavior unless the maintainer explicitly approves a
product change.

Output canvas behavior includes:

- Generated final images, VAE previews, source grouping, set grouping, scene
  grouping, scene overviews, scene grids, compare behavior, manual focus, auto
  focus, preview retirement, selection, navigation, timing, and tab switching.
- Active workflow isolation: the Output canvas must show only images relevant
  to the active workflow.
- Strict backend identity handling for live visuals. Live output placement must
  derive from backend-provided workflow, run, prompt, client, source, node,
  list-index, artifact, and scene identity, not from current UI state.

Input canvas behavior includes:

- Editor-panel `LoadImage` and `LoadImageMask` materialization.
- Direct QPane image loads and reconciliation while preserving QPane image
  UUIDs.
- Loaded-cube materialization for the active workflow only.
- Graph-backed image and mask binding through the workflow canvas state and
  cube mask binding services.
- Mask activation through the owning input image.
- Wrong-size mask rejection or replacement before asset state or QPane pixels
  are updated.
- Dirty associated mask flushing before generation, with fail-closed generation
  behavior when persistence fails.
- Editor-panel mask picker refresh from authoritative asset state.

Host behavior includes:

- Docked and floating canvas lifecycle, geometry, visibility, focus routing,
  and controls.
- Host code may present and route canvas intent, but it must not become the
  owner of durable canvas membership, backend image routing, or graph binding
  policy.

## Separation Of Concerns

Keep one authoritative owner per concern.

- Canvas widgets own PySide6/QPane integration, layout, focus, sizing,
  visibility, signals, controls, and user-intent forwarding.
- Shared canvas presentation infrastructure owns QPane host lifecycle, common
  geometry, tab activation, projection scheduling, route application, and visual
  focus behavior shared by Input and Output canvas.
- Application services own workflow coordination, editor-panel materialization,
  generation preflight, input-mask persistence, and live output ingestion.
- Domain code owns pure identity, membership, activation, visibility, graph
  binding, and placement policy.
- Infrastructure/adapters own backend websocket payloads, Comfy integration,
  filesystem IO, media loading, QPane catalog operations, and QPane route
  operations.

Do not create parallel owners for active workflow, canvas membership, output
image identity, input image identity, mask ownership, QPane catalog state,
projection state, route state, or focus state. If a change appears to require
duplicated ownership, correct the ownership boundary as part of the change.

## Shared Canvas Infrastructure

Input and Output canvas must share infrastructure where the concern is the same.

Shared concerns include:

- QPane host lifecycle.
- QPane catalog adaptation.
- QPane route and composition projection.
- Workflow session activation.
- Tab activation and visibility.
- Focus and selection presentation.
- Docked/floating host coordination.
- Geometry and resize behavior.
- Deferred or coalesced presentation updates.

Distinct concerns must stay distinct:

- Input canvas is graph-backed and workflow-asset-backed.
- Output canvas is backend-visual-event-backed and generation-run-backed.
- Input mask correctness must not be modeled as generated output routing.
- Output preview/final correctness must not be modeled as graph image loading.

## QPane Usage Rules

Use QPane as a retained visual catalog and renderer.

- Do not create one QPane instance per workflow.
- Do not unload QPane catalog entries as the mechanism for workflow switching
  correctness.
- Do not treat QPane catalog membership as workflow membership.
- Do not use current QPane image or composition state as the authoritative
  source of domain membership.
- Keep catalog operations in a catalog adapter or equivalent infrastructure
  owner.
- Keep display, route, scene, comparison, and composition operations in a route
  projector or equivalent presentation/application owner.
- Use deterministic composition and route identities for host-owned scenes.
- Validate layered scene state through QPane composition APIs rather than
  guessing from the current image ID alone.
- Use QPane public APIs. Do not reach through private implementation details.

QPane should stay warm across workflow switches. Correctness comes from the
active canvas session and route projection, not from clearing retained images.

## Backend Visual Event Rules

Raw backend payloads belong at the transport and ingress boundary only.

- After transport parsing, canvas code must use strict application/domain DTOs.
- Metadata-less VAE previews are ignored.
- Preview routing must use the backend metadata identity, including prompt ID
  and node metadata such as node ID, display node ID, parent node ID, or real
  node ID where provided.
- Final image routing must use the backend substitute cube output event and its
  v2 identity.
- Live final images require workflow/run/prompt/client match, source key,
  source label, node ID, list index, image artifact identity, media identity,
  dimensions, and scene identity or source-only identity.
- Final image placement must not use active tab, selected workflow, focused
  widget, arrival order, node title, display label, or display node ID as a
  replacement for backend identity.
- Backend rejection paths must be explicit and logged with actionable context.

The frontend must take advantage of the structure supplied by
`substitute-backend`. Do not reconstruct routing meaning in presentation code
when the backend has already sent authoritative identity.

## Input Canvas Rules

Input canvas correctness is graph-driven and workflow-asset-driven.

- Editor-panel `LoadImage` and `LoadImageMask` interactions must flow through
  the workflow input canvas application service after presentation intent is
  captured.
- Direct QPane image loads must reconcile into workflow canvas state without
  replacing the QPane-provided image UUID.
- Input image identity must use the workflow canvas state's authoritative input
  keys.
- Mask ownership must use the workflow canvas state's mask-to-image mapping.
- Mask activation must activate the owning input image before activating the
  mask or brush mode.
- Ambiguous mask bindings must be rejected rather than guessed.
- Loaded-cube materialization must apply to the active workflow only.
- User-selected wrong-size masks must be rejected or replaced before asset
  state, QPane pixels, or editor-panel picker state are updated.
- Dirty masks associated with generation inputs must be persisted before
  generation starts; failed persistence blocks generation.
- Editor-panel mask picker state must refresh from authoritative asset state,
  not widget-local path memory.

Input canvas code must not infer graph bindings from visible labels, widget
focus, current tab, or QPane catalog contents.

## Large File And Class Rules

Large mixed-responsibility files are defects to correct, not convenient places
to add more behavior.

When touching a large canvas file, first identify the responsibility being
changed and move new or changed behavior to the narrow owner for that concern.
Do not add new policy, routing, ingress, graph binding, mask persistence, or
QPane orchestration code to monolithic widgets as a shortcut.

Split by responsibility and reason to change:

- Host lifecycle.
- QPane catalog adaptation.
- QPane route projection.
- Workflow session state.
- Output visual ingress.
- Output preview registry.
- Output final image pipeline.
- Output canvas projection.
- Input graph materialization.
- Input mask binding and persistence.
- Presentation widgets and controls.

Internal compatibility shims are not acceptable after a refactor lands. Update
call sites, remove obsolete code paths, and make the new structure look native.

## Performance Rules

Responsiveness is an architectural requirement.

- Workflow switching must remain cheap because QPane stays warm.
- Paint, resize, focus, tab-switch, selection, and hover paths must consume
  prepared state.
- Do not perform filesystem IO, network IO, backend calls, image decoding,
  expensive QPane work, full output projection rebuilds, or graph materialization
  directly inside hot GUI paths unless the work is proven trivial and covered by
  tests.
- Coalesce expensive generated-output projection work while preserving immediate
  active-workflow correctness.
- Stale scheduled work must prove it still applies before publishing.
- Background loading and warming must never be required for correctness.

Performance work must not reduce canvas correctness or remove existing canvas
capabilities.

## PySide6 And QPane Rules

- Keep Qt and QPane objects in presentation or adapter layers unless there is a
  deliberate boundary.
- Keep domain logic free of Qt objects where feasible.
- Keep event filters, signal connections, and deferred callbacks owned,
  removable, and lifecycle-safe.
- Treat deleted Qt wrappers as lifecycle hazards only in narrow known cases.
  Catch deleted-object `RuntimeError` narrowly and re-raise unrelated failures.
- Do not block the GUI thread on IO, network, backend, image decode, subprocess,
  or slow catalog work.
- Use qfluent widgets, menus, icons, sizing, and styling conventions when
  extending canvas controls.

## Testing Requirements

Before refactoring behavior-critical canvas code, identify the characterization
tests that protect that behavior. If coverage is missing, add characterization
tests first.

Canvas refactors must test success, stale, inactive-workflow, and rejection
paths for the touched behavior.

Coverage must include the relevant behavior when touched:

- Output workflow isolation.
- Backend VAE preview routing.
- Backend final image routing.
- Source, set, scene, grid, overview, and compare projection.
- Preview retirement and final replacement.
- QPane route and composition application.
- Workflow switching without QPane catalog unloading.
- Editor-panel `LoadImage` materialization.
- Direct QPane image reconciliation with UUID preservation.
- Editor-panel `LoadImageMask` activation through the owning image.
- Ambiguous mask binding rejection.
- Loaded-cube materialization for the active workflow only.
- Wrong-size mask rejection or replacement.
- Dirty mask preflight persistence and fail-closed generation behavior.
- Editor-panel mask picker refresh from authoritative asset state.

For canvas refactors:

- Run focused tests for the touched behavior.
- Run full repository gates before reporting completion.
- Do not claim behavior preservation from code inspection alone.
- Add tests for both success and stale/failure paths when touching async,
  scheduled, backend, or projection behavior.

## Observability

Canvas observability must make placement, routing, and persistence failures easy
to diagnose.

Logs for routing, projection, rejection, and persistence decisions should include
the relevant workflow ID or name, canvas kind, generation run ID, prompt ID,
client ID, source key, source label, scene key, node ID, list index, image ID,
mask ID, route ID, composition ID, operation name, and rejection reason.

Do not log secrets, prompt text, or unnecessary local paths. Preserve exception
context for unexpected failures. Use debug logs for routine routing and
scheduling detail, warning logs for rejected or stale external events, and error
logs for unexpected user-visible failures.

## Anti-Patterns

Avoid these in canvas code:

- Creating one QPane per workflow.
- Unloading QPane catalog entries for workflow-switch correctness.
- Treating QPane catalog membership as workflow membership.
- Routing backend images by active tab, focused widget, selected workflow,
  arrival order, display label, or node title.
- Letting widgets own durable canvas state, output membership, or graph binding
  policy.
- Passing raw backend payloads into canvas widgets.
- Reconstructing backend-provided identity in presentation code.
- Duplicating shared Input and Output canvas infrastructure.
- Growing `output_canvas_view.py`, `input_canvas_view.py`,
  `canvas_tabs_view.py`, `workspace_canvas_actions.py`, or similar files as
  dumping grounds for new behavior.
- Adding internal compatibility shims instead of updating call sites and
  removing obsolete code.
- Performing filesystem, backend, image decode, or expensive QPane work in hot
  GUI paths.
- Swallowing exceptions broadly or silently dropping rejected visual events
  without actionable logging.
