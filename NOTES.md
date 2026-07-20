# Bundled ComfyUI Workflow Rendering Validation

## Objective

Support every native ComfyUI editable widget exercised by the bundled workflow
catalog through SugarSubstitute's existing direct-workflow and sugarcube editor
paths. Production conversion, behavior resolution, display policy, field
factories, card construction, registration, visibility reconciliation, and
masonry attachment remain authoritative. The corpus observer records those
outcomes; it does not define a second set of visibility or support rules.

The work ran on branch `test/bundled-comfy-workflow-rendering`. Qt was forced to
and verified as `offscreen` before PySide6 import. The Comfy helper ran in a
hidden process on port 8192 with custom nodes disabled and isolated empty model
directories. No visible Qt windows were created.

## Product Behavior Implemented

- Empty or unavailable combos render as honestly empty, disabled Fluent combo
  boxes. They no longer throw, fabricate a choice, or discard their cards.
- Native serialized widget values are decoded recursively from live Comfy
  definitions. This includes `COMFY_DYNAMICCOMBO_V3` selectors, selected nested
  fields, nested numeric mode companions, `COMFY_AUTOGROW_V3` socket containers,
  native `widgetType` overrides, and frontend-only `LOAD_3D` serialized values.
- Changing a dynamic selector persists through the normal field-state owner and
  schedules a targeted rebuild through the production cube projection and
  masonry lifecycle. Stale nested fields are removed and the newly selected
  fields are registered.
- Field construction now has typed outcomes for rendered, empty, unavailable,
  intentional absence, unsupported, layout-handled, and error states. A field
  error is logged with its traceback but does not discard an otherwise useful
  card.
- Node-card field registration is transactional. Registrations commit only
  after successful card construction, and rollback removes partial row,
  column, field, and widget ownership.
- Native Comfy `AUDIO_RECORD`, `BOUNDING_BOX`, `COLOR`, and `CURVE` values have
  focused factories and semantic value fields. Unknown third-party socket types
  continue to decline gracefully.
- Toolbar overrides use the same typed field construction boundary and safe
  empty-choice behavior as cards.

## Fluent Widgets and Theme Ownership

Native fields use existing SugarSubstitute controls and QFluent Widgets:

- `COLOR`: QFluent `LineEdit` and `ColorPickerButton`.
- `BOUNDING_BOX`: QFluent `PushButton`, `MessageBoxBase`, `SpinBox`, and labels.
- `CURVE`: QFluent `PushButton`, `MessageBoxBase`, labels, and reset action.
- `AUDIO_RECORD`: QFluent `ToolButton`, icons, labels, and Fluent tooltips.

Plain Qt is limited to layout/lifecycle, Qt Multimedia recording, the native
file dialog (QFluent has no file picker), and the curve canvas (QFluent has no
curve editor). The curve canvas derives dark/light colors and accent color from
QFluent theme state and subscribes to SugarSubstitute's shared live-theme
refresh owner.

Automated coverage verifies the intended Fluent types, dark rendering, light
rendering, and a live dark-to-light repaint. No field installs a bypass palette
or independent theme owner.

## Ownership and Refactoring

No large mixed-responsibility source file was created or expanded with a new
subsystem. Directly involved broad owners delegate the new work to focused
collaborators:

- Qt-free schema interpretation: `native_widget_schema.py`.
- Typed factory results and classification: `field_build_outcome.py` and
  `field_build_resolver.py`.
- Native presentation dispatch: `native_comfy_widget_factory.py` and the
  `widgets/fields/native/` package.
- Transactional card lifecycle: `node_card_build_transaction.py`.
- Dynamic field-change orchestration: `field_value_change_coordinator.py`.

The existing node-card builder, field pipeline, field-state controller,
override controller, and editor panel retain their authoritative concerns but
delegate the added schema, transaction, native-widget, outcome, and dynamic
refresh responsibilities to those collaborators.

## Problems Found and Resolved

The original production observation found:

- Dynamic/nested values shifted strings into later numeric fields, causing 112
  card errors across 70 workflows.
- Unresolved `PrimitiveNode` choices threw instead of rendering empty.
- Failed cards could retain partial field registrations.
- Native dynamic, audio-record, bounding-box, color, and curve controls lacked
  editor factories.

After the main implementation, the first complete remediation run finished all
452 workflows and isolated 10 remaining findings in six workflows:

- `LOAD_3D` adds three frontend button values and one viewport value to the
  serialized stream. Failing to consume them shifted `upload3dmodel` and
  `uploadExtraResources` into numeric width and height fields in four Hunyuan
  3D workflows.
- `Preview3D.model_file` is a union socket annotated by Comfy with
  `widgetType: STRING`; ignoring the native override left one Tripo field
  unsupported.
- The real-shell test gateway's historical hard-coded `UNETLoader` definition
  took precedence over the live corpus definition, creating one false
  unsupported `weight_dtype` observation.

The schema owner now consumes the native Load3D frontend values and applies
native `widgetType` overrides. The real-shell gateway now gives explicitly
installed live definitions precedence over built-in fixture defaults. All six
affected workflows subsequently passed isolated production probes before the
entire corpus was rerun.

## Final Corpus Result

Authoritative artifact root:
`build/test-results/bundled-workflow-production-audit-final-pass/`

- Catalog fingerprint:
  `f7e39b87ffd65737ed26fae900ece1b08648d7961922778e2dab0bed194541d9`
- Template root:
  `E:\ComfyUI\venv\Lib\site-packages\comfyui_workflow_templates_json\templates`
- Audit mode: `passive_production_observation`
- Qt platform: `offscreen`
- Workflows completed: 452 of 452
- Workflows passed: 452
- Workflows failed: 0
- Findings: 0
- Source nodes: 7,344
- Nodes projected by production conversion: 6,382
- Converted nodes: 6,382
- Persisted production node outcomes: 6,382
- Built cards: 5,057
- Finally visible cards: 4,433
- Registered field widgets: 10,821
- Field-factory observations: 11,484
- Widgets built: 10,640
- Intentional field absences: 844
- Runtime: 1,330.8 seconds

Production node outcomes were:

| Outcome | Count |
| --- | ---: |
| `built` | 5,057 |
| `connection_only` | 860 |
| `hidden_by_policy` | 373 |
| `factory_returned_none` | 80 |
| `missing_field_specs` | 12 |

Every projected node has exactly one production outcome. All editable native
fields observed by the corpus built widgets. The 844 intentional absences are
existing production behavior for sockets, autogrow containers, previews,
layout-only controls, and other non-editable fields. The 80 nodes whose card
factory returned no widget contain only such intentional absences. The observer
found no card error, unsupported editable field, stale registration, missing
registered card, invalid Qt wrapper, masonry dropout, visibility contradiction,
out-of-bounds visible card, or visible-card overlap.

The helper's model directories were empty throughout both full runs. Loader
cards and their empty/unavailable choices rendered without exceptions or card
loss.

## Artifacts

- Final structured report:
  `build/test-results/bundled-workflow-production-audit-final-pass/report.json`
- Final per-workflow progress:
  `build/test-results/bundled-workflow-production-audit-final-pass/progress.log`
- Final offscreen probe:
  `build/test-results/bundled-workflow-production-audit-final-pass/offscreen-probe.json`
- First remediation report (six failing workflows, retained for comparison):
  `build/test-results/bundled-workflow-production-audit-final/report.json`
- Zero-finding affected-workflow probes:
  `build/test-results/remediation-probes/`
- Dynamic selector production-shell regression:
  `tests/test_real_shell_direct_workflow_scenarios.py`

## Validation Boundaries

- The corpus validates loading, conversion, field construction, state binding,
  card lifecycle, visibility, and masonry rendering. It does not execute image,
  video, audio, or 3D generation jobs.
- Audio recording construction and no-microphone behavior are covered; actual
  microphone capture and Comfy submission were not exercised by the offscreen
  corpus.
- Native 3D viewport widgets are frontend preview/layout surfaces rather than
  ordinary field controls. Their serialized state is decoded so adjacent
  editable fields remain correct; SugarSubstitute does not recreate Comfy's WebGL
  viewport inside a field row.
- Custom nodes were disabled in the isolated helper. Unknown third-party
  controls remain safe typed unsupported outcomes and cannot destroy cards.

## Repository Gates

Focused conversion, factory, card, override, rollback, native-widget, dynamic
selector, real-shell, and corpus-harness tests pass. The final repository-wide
gates also pass on Windows 11 against the repository `.venv` and the exact
post-remediation worktree:

- `ruff format .`: 2,912 files unchanged.
- `ruff check .`: all checks passed.
- `mypy --strict substitute tests`: no issues in 2,707 source files.
- `pytest -n auto -q -m "not serial"`: passed with the Qt offscreen platform.
- `python -m tools.ci.run_serial_test_modules`: all 118 serial test modules
  passed with the Qt offscreen platform; JUnit results are under
  `build/test-results/local-serial/`.
