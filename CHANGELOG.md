# Changelog

## Unreleased

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
