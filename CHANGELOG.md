# Changelog

## Unreleased

- Add a source selector for `hou.session`, selected-node Python parameters, and HDA
  `PythonModule` sections.
- Add Follow Selection and Use Selected workflows.
- Protect unsaved buffers during source and node changes.
- Open locked parameters and non-writable asset definitions in view-only mode.
- Group node-parameter saves in Houdini's undo history.

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
