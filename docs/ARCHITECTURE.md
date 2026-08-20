# Architecture

## Runtime layout

Houdini discovers `python_panels/mad_coder.pypanel` because the package JSON adds the `mad-coder`
content directory to `HOUDINI_PATH`. The panel definition imports ordinary
Python modules from `scripts/python`, another standard Houdini search location.

```text
Houdini package JSON
  → Python Panel definition
    → MadCoderPanel
      ├── Source adapters
      │   ├── SessionSource → hou.session
      │   ├── NodeParameterSource → selected-node string parameters
      │   └── HDASectionSource → asset PythonModule and ViewerStateModule sections
      ├── MadCoderEditor → text editing, line numbers, inline diagnostic rendering
      ├── ExecutionConsole → captured Python output and run history
      ├── capture_execution → stream, logging, timing, and traceback capture
      ├── PreferencesStore / SettingsDialog → validated persistent user settings
      ├── PythonHighlighter → dependency-free token highlighting
      ├── CompletionService → serialized background Jedi analysis
      ├── RuffService → asynchronous lint and format subprocesses
      └── TypeCheckService → asynchronous ty subprocesses
```

## UI thread policy

All widgets, source execution, node cooking, and `hou` calls stay on Houdini's main thread. This is
required for the live Houdini scene, but means arbitrary user code can block the application. Ruff
and ty work run in `QProcess` instances, so analysis does not execute on the UI thread and does not
require calling `hou` from a worker. Results return through Qt signals. Starting a new analysis pass
invalidates or terminates the preceding pass, and the panel publishes only a complete current pair.

Jedi completion runs on one dedicated `QThread`. Requests are serialized because Jedi's fast parser
is not thread-safe, and generation numbers discard results made stale by a newer request or source
reload. The worker receives plain strings and cursor coordinates and never receives or calls a live
`hou` object. UI presentation and text insertion return to Houdini's main thread through Qt signals.

## Source consistency

Source adapters record no hidden source snapshot. The panel keeps the exact string it loaded as its
baseline and supplies that value on save. Each adapter reads the current Houdini value immediately
before writing; a mismatch raises `SourceConflictError`. Explicit overwrite passes no expected
value.

This optimistic-concurrency boundary should be retained for every future source adapter.

## Adding source types

Source adapters expose the same conceptual contract:

- Human-readable display name
- Synthetic filename for linting
- Stable source key
- Placeholder and save warning
- Houdini globals available to the linter in that execution context
- `load() -> str`
- `save(text, expected)` with conflict detection
- `execute()` using the source's native Houdini behavior
- `read_only_reason()`

`python_sources_for_node` currently discovers common Python parameter names and an HDA
`PythonModule` and `ViewerStateModule` sections. Viewer states use Houdini's dedicated embedded
module reload API. Likely future adapters include HDA event-handler sections and external files.
The panel never switches adapters while the current buffer has unsaved changes.

## Linter boundary

Ruff is an external executable rather than an imported extension module. This avoids ABI coupling to
Houdini's Python 3.11 and newer builds and keeps the UI package pure Python. Release archives are
therefore platform-specific even though the plugin source is shared.

Linting uses a fixed conservative rule set and isolated mode. Each source adapter supplies a small
tuple of documented context globals, such as `hou` or `kwargs`. `RuffService` passes them through a
per-run `builtins` override, so no prelude is inserted and diagnostic positions remain aligned with
the editor. The contexts deliberately remain source-specific to avoid hiding genuine undefined
names. A future settings UI can expose rules or configuration files, but it should preserve
deterministic defaults and report the active configuration clearly.

## Type-checker boundary

ty is also a native external executable. `TypeCheckService` writes a temporary analysis copy of the
buffer, launches ty with GitLab JSON output, maps its positions back to editor lines, and removes the
temporary directory when the request finishes or is cancelled. The buffer is never executed.

An analysis-only prelude imports `hou` and declares other documented context globals. Existing
`__future__` imports remain first in the temporary module, and the line offset is removed from every
reported diagnostic. The bundled `types-houdini` search path resolves HOM APIs. Ruff remains
responsible for syntax and undefined-name reports to prevent duplicate Problems entries.

## Completion boundary

Completion uses Jedi's static `Script` API rather than its live `Interpreter` API. A short
analysis-only prelude declares the documented globals for the active source adapter, and the cursor
line is adjusted by that prelude's length. The prelude is never displayed, executed, linted, or
saved. Pinned `types-houdini` stubs provide HOM names and signatures without introspecting Houdini's
runtime extension module.

Typing a dot or requesting completion explicitly starts an analysis pass. Once candidates arrive,
the editor filters them locally as the user continues typing. Suggestions use a non-focusable child
view inside the editor rather than a native Qt popup, so showing and hiding them cannot redirect
keyboard input away from the text buffer. This avoids scheduling a Jedi pass for every keystroke.
Dynamic scene values, HDA-generated attributes, and arbitrary `kwargs` contents remain best-effort
because static analysis cannot safely discover them.

## Execution boundary

`capture_execution` temporarily redirects Python stdout and stderr and adds a root logging handler.
It always restores the original streams and handler in a `finally` path, catches `BaseException`
so `SystemExit` does not terminate Houdini, and returns a traceback as console output. Capture is
limited to synchronous Python work performed during the call.

The panel saves a writable buffer inside the capture boundary, then calls the source adapter's
`execute()`. A node parameter forces `node.cook(force=True)` and reports node cook errors; a session
module is already evaluated by its save operation; an HDA source loads its module after updating the
section. A read-only source skips saving and executes its stored code where supported.

## User preferences

The sectioned `SettingsDialog` exposes the Editor font family and size plus autocomplete and type
checking toggles that default to enabled. Its font picker is restricted to fonts Qt identifies as
monospaced.
`PreferencesStore` contains no Qt dependency and validates values read from an injected
QSettings-compatible backend. The panel uses an explicitly named
`QSettings("Mad Coder", "Mad Coder")` store so preferences are independent of Houdini's own
application settings.

The default resolver prefers Roboto Mono when installed and otherwise uses Qt's system fixed-width
font. Missing saved fonts and malformed sizes fall back safely; sizes are clamped to 7–32 pt.

## Failure behavior

- Missing Ruff: standard-library syntax checking remains available.
- Missing ty: Ruff remains available and the lint badge identifies type checking as unavailable.
- Missing Jedi: editing remains available and explicit autocomplete reports the missing dependency.
- Completion failure or stale result: the popup stays closed and the editor buffer is unchanged.
- Ruff process failure: the editor stays usable and displays the process error in its status area.
- ty process failure: Ruff results remain usable and the type-check error appears in the status area.
- Invalid Python on save: Houdini rejects it and the buffer remains unsaved.
- External source modification: the user chooses reload, overwrite, or cancel.
- Locked or non-writable source: the source remains available in view-only mode.
- Selection change: a Houdini selection callback refreshes the source selector on the UI thread.
- Scene load/clear: Python Panel lifecycle hooks reset source discovery for the new scene.
- Execution exception: the traceback remains in Console and the editor stays open.
- Missing configured font: the editor falls back to the current system fixed-width font.
