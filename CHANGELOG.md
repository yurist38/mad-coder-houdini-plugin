# Changelog

## Unreleased

- Add configurable background Python autocomplete for local code, Houdini APIs, and source-context
  globals, enabled by default.
- Add configurable background ty diagnostics for Python values and Houdini APIs, enabled by default.
- Add VEX parameter discovery, highlighting, and asynchronous Wrangle syntax diagnostics using
  Houdini's bundled vcc compiler.
- Keep VEX typing responsive by debouncing compiler launches, pausing checks while its editor is
  unfocused, and queueing the latest source while an in-flight compiler exits normally.
- Prevent Python analysis from remaining in `Checking…` by queueing the latest Ruff and ty
  requests, reporting the pending engine, and timing out stalled processes.
- Recognize Houdini Python Snippet function-body semantics so valid top-level returns and dynamic
  `kwargs` values do not produce false-positive Ruff or ty diagnostics.
- Add a source selector for `hou.session`, selected-node Python parameters, and HDA
  `PythonModule` sections.
- Add Follow Selection and Use Selected workflows.
- Protect unsaved buffers during source and node changes.
- Open locked parameters and non-writable asset definitions in view-only mode.
- Group node-parameter saves in Houdini's undo history.
- Recognize context-provided `hou` and `kwargs` names without adding imports to saved code.
- Add a built-in execution console with captured output, logging, tracebacks, and source-aware Run.
- Fix the editor gutter so each visible line displays its actual line number.
- Add the custom Mad Coder icon for Houdini's panel menus and tabs.
- Highlight complete error and warning lines while retaining precise diagnostic underlines.
- Add persistent Editor font settings with monospaced selection, sizing, preview, and defaults.
- Focus the code editor and place the caret on the first click.
- Keep completion suggestions inside a non-focusable editor child view so filtering never captures
  keyboard input.

All notable changes will be documented here.

## 0.1.0 - Unreleased

### Added

- Mad Coder dockable Houdini 21+ Qt 6 Python Panel for editing `hou.session`.
- Python syntax highlighting, line numbers, indentation, and font zoom.
- Asynchronous Ruff diagnostics, inline markers, Problems navigation, and formatting.
- Syntax-only fallback when Ruff is unavailable.
- Save conflict detection and scene load/clear handling.
- Houdini package metadata and platform-specific GitHub release automation.
- Manually triggered semantic-version tagging and release workflow.
- Unit tests and installation, usage, development, architecture, and troubleshooting docs.
