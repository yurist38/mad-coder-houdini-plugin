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
      │   └── HDASectionSource → asset PythonModule sections
      ├── MadCoderEditor → text editing, line numbers, inline diagnostic rendering
      ├── ExecutionConsole → captured Python output and run history
      ├── capture_execution → stream, logging, timing, and traceback capture
      ├── PreferencesStore / SettingsDialog → validated persistent user settings
      ├── PythonHighlighter → dependency-free token highlighting
      └── RuffService → asynchronous lint and format subprocesses
```

## UI thread policy

All widgets, source execution, node cooking, and `hou` calls stay on Houdini's main thread. This is
required for the live Houdini scene, but means arbitrary user code can block the application. Ruff
work runs in a `QProcess`, so linting does not execute on the UI thread and does not require calling
`hou` from a worker. Results return through Qt signals. Starting a new lint pass invalidates or
terminates the preceding pass.

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
`PythonModule` section. Likely future adapters include HDA event-handler sections and external
files. The panel never switches adapters while the current buffer has unsaved changes.

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

The sectioned `SettingsDialog` currently exposes the Editor font family and size. Its font picker is
restricted to fonts Qt identifies as monospaced. `PreferencesStore` contains no Qt dependency and
validates values read from an injected QSettings-compatible backend. The panel uses an explicitly
named `QSettings("Mad Coder", "Mad Coder")` store so preferences are independent of Houdini's own
application settings.

The default resolver prefers Roboto Mono when installed and otherwise uses Qt's system fixed-width
font. Missing saved fonts and malformed sizes fall back safely; sizes are clamped to 7–32 pt.

## Failure behavior

- Missing Ruff: standard-library syntax checking remains available.
- Ruff process failure: the editor stays usable and displays the process error in its status area.
- Invalid Python on save: Houdini rejects it and the buffer remains unsaved.
- External source modification: the user chooses reload, overwrite, or cancel.
- Locked or non-writable source: the source remains available in view-only mode.
- Selection change: a Houdini selection callback refreshes the source selector on the UI thread.
- Scene load/clear: Python Panel lifecycle hooks reset source discovery for the new scene.
- Execution exception: the traceback remains in Console and the editor stays open.
- Missing configured font: the editor falls back to the current system fixed-width font.
