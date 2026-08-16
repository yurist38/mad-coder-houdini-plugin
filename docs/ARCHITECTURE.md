# Architecture

## Runtime layout

Houdini discovers `python_panels/mad_coder.pypanel` because the package JSON adds the `mad-coder`
content directory to `HOUDINI_PATH`. The panel definition imports ordinary
Python modules from `scripts/python`, another standard Houdini search location.

```text
Houdini package JSON
  → Python Panel definition
    → MadCoderPanel
      ├── SessionSource → hou.sessionModuleSource / hou.setSessionModuleSource
      ├── MadCoderEditor → text editing, line numbers, inline diagnostic rendering
      ├── PythonHighlighter → dependency-free token highlighting
      └── RuffService → asynchronous lint and format subprocesses
```

## UI thread policy

All widgets and `hou` calls stay on Houdini's main thread. Ruff work runs in a `QProcess`, so linting
does not execute on the UI thread and does not require calling `hou` from a worker. Results return
through Qt signals. Starting a new lint pass invalidates or terminates the preceding pass.

## Source consistency

`SessionSource` records no hidden global state. The panel keeps the exact source string it loaded as
its baseline and supplies that value on save. The adapter reads the current Houdini value immediately
before writing; a mismatch raises `SourceConflictError`. Explicit overwrite passes no expected value.

This optimistic-concurrency boundary should be retained for every future source adapter.

## Adding source types

Future source adapters should expose the same conceptual contract:

- Human-readable display name
- Synthetic filename for linting
- `load() -> str`
- `save(text, expected)` with conflict detection

Likely adapters include HDA `PythonModule` sections, HDA event-handler sections, string parameters
containing Python, and external files. The panel should switch adapters only after resolving an
unsaved buffer.

## Linter boundary

Ruff is an external executable rather than an imported extension module. This avoids ABI coupling to
Houdini's Python 3.11 and newer builds and keeps the UI package pure Python. Release archives are
therefore platform-specific even though the plugin source is shared.

Linting uses a fixed conservative rule set and isolated mode. A future settings UI can expose rules
or configuration files, but it should preserve deterministic defaults and report the active
configuration clearly.

## Failure behavior

- Missing Ruff: standard-library syntax checking remains available.
- Ruff process failure: the editor stays usable and displays the process error in its status area.
- Invalid Python on save: Houdini rejects it and the buffer remains unsaved.
- External source modification: the user chooses reload, overwrite, or cancel.
- Scene load/clear: Python Panel lifecycle hooks reload the new scene's session module.
