# Mad Coder

Mad Coder is a dockable Python editor for SideFX Houdini with live Ruff diagnostics and formatting.
The initial release edits the current scene's `hou.session` module—the same source exposed by
Houdini's native Python Source Editor—without modifying Houdini's internal editor widgets.

## Features

- Native dockable Python Panel built with Houdini's bundled PySide6
- Python syntax highlighting, line numbers, automatic indentation, and adjustable font size
- Debounced Ruff linting that never blocks Houdini's UI
- Inline warning/error underlines with hover text
- Navigable Problems list
- Ruff formatting
- Save and reload shortcuts
- Protection against overwriting changes made through another editor
- Syntax-error diagnostics when Ruff is unavailable

## Compatibility

Version 0.1 targets **Houdini 21.0 and newer**, using Qt 6/PySide6:

| Platform | Supported release archive |
| --- | --- |
| Windows 11 x64 | `windows-x64` |
| Linux x64 on a Houdini-supported distribution | `linux-x64` |
| macOS on Apple Silicon | `macos-arm64` |

Python 3.11 is the minimum supported interpreter. This covers Houdini 21's main Qt 6 build and
Houdini 22's Python 3.11 and 3.13 builds. Qt 5 builds, Houdini 20.5 and older, Intel macOS, and
Linux ARM are outside the initial support scope.

## Install a release

1. Download the ZIP matching your operating system from the GitHub Releases page.
2. In Houdini, open **Windows → Python Shell** and evaluate:

   ```python
   hou.getenv("HOUDINI_USER_PREF_DIR")
   ```

3. Close Houdini.
4. Extract the ZIP's contents directly into that preference directory. Allow the archive's
   `packages` directory to merge with the existing one; do not replace the directory.
5. Confirm the resulting layout:

   ```text
   $HOUDINI_USER_PREF_DIR/
   ├── packages/
   │   └── mad-coder.json
   └── mad-coder/
       ├── bin/
       │   └── ruff[.exe]
       ├── python_panels/
       └── scripts/python/mad_coder/
   ```

6. Restart Houdini.

Houdini's package system loads the plugin; `houdini.env` does not need to be edited.

### Upgrade

Close Houdini, replace the existing `mad-coder` directory with the directory from the new release,
replace `packages/mad-coder.json`, and restart Houdini. Scene files do not
contain a copy of the plugin.

### Uninstall

Close Houdini and remove these two paths:

```text
$HOUDINI_USER_PREF_DIR/packages/mad-coder.json
$HOUDINI_USER_PREF_DIR/mad-coder/
```

Then restart Houdini. Uninstalling does not alter Python source already saved in `.hip` files.

## Open and use the editor

1. Open a new pane tab and choose **Python Panel**.
2. In the Python Panel interface menu, select **Mad Coder**.
3. Dock the pane and save the desktop layout if desired.

The top-left label identifies the source as **Scene · hou.session**. An asterisk means the editor
contains unsaved changes.

### Editing workflow

- Type normally; linting runs after a short pause.
- Hover over an underlined range to read its diagnostic.
- Click a row in **Problems** to jump to its location.
- Select **Format** to apply Ruff formatting to the editor buffer.
- Select **Save** to apply the buffer to `hou.session` and store it with the scene on the next
  `.hip` save.
- Select **Reload** to discard the buffer and read the current `hou.session` source again.

Saving calls Houdini's `hou.setSessionModuleSource`. Houdini makes the new module contents
available immediately, so top-level code executes as part of applying the source. Treat scripts
from untrusted scene files as executable code.

If `hou.session` changed elsewhere after this panel loaded it, Save offers three choices:

- **Reload**: discard this panel's buffer and load the external source.
- **Overwrite**: deliberately replace the external source.
- **Cancel**: keep the unsaved buffer while deciding how to merge the changes.

### Shortcuts

| Action | Shortcut |
| --- | --- |
| Save | Platform-standard Save (`Ctrl+S` / `Cmd+S`) |
| Format | `Ctrl+Shift+F` |
| Reload | `F5` |
| Change font size | `Ctrl` + mouse wheel |

## Linting behavior

Release archives contain a pinned Ruff executable. The editor runs Ruff in an asynchronous child
process with Python 3.11 syntax compatibility and the core `E4`, `E7`, `E9`, and `F` rule groups.
This catches import, name, syntax, and common Python correctness problems without presenting the
hundreds of style rules enabled by Ruff 0.16's expanded defaults.

Ruff runs in isolated mode, so an unrelated `pyproject.toml` in Houdini's working directory cannot
silently change the editor's rules. If Ruff cannot be found, the panel remains usable and reports
Python syntax errors using the standard library parser; formatting is disabled.

To use another Ruff executable, set this environment variable before Houdini starts:

```text
MAD_CODER_RUFF=/absolute/path/to/ruff
```

The resolution order is explicit environment variable, bundled executable, then system `PATH`.

## Troubleshooting

### Mad Coder is missing from the Python Panel menu

- Verify that the package JSON and plugin directory are siblings exactly as shown above.
- Open Houdini's Package Browser and confirm `mad-coder.json` is enabled.
- Start Houdini with `HOUDINI_PACKAGE_VERBOSE=1` to inspect package-loading messages.
- Confirm the Houdini version is 21.0 or newer; the package intentionally disables itself on older
  releases.

### The panel reports “Syntax only”

The bundled Ruff executable is missing, quarantined, or cannot execute. Reinstall the correct
platform archive. On macOS, check the operating system's security prompt; on Linux, confirm the
executable bit was preserved. An explicit `MAD_CODER_RUFF` path can override it.

### Save fails

Houdini rejects session-module source containing syntax errors. Select the first syntax diagnostic,
correct it, and save again. Runtime errors from top-level code can also be reported while Houdini
applies the source.

### The native Python Source Editor and this panel disagree

Unsaved buffers are private to each editor. Save or reload one editor before switching to the other.
This plugin detects changes to the applied `hou.session` source, but it cannot inspect unsaved text
inside Houdini's native editor.

## Current limitations

- Only `hou.session` is editable in version 0.1.
- There is no code completion, type checking, refactoring, or language-server integration yet.
- Ruff fixes are shown as fixable diagnostics but are not individually applied; Format formats the
  complete buffer.
- The syntax highlighter is intentionally lightweight and is not a full Python parser.

HDA Python modules, HDA event handlers, Python node parameters, external files, quick fixes, and
language-server support are natural follow-up milestones.

## Develop and release

See [Development](docs/DEVELOPMENT.md) for a source installation, tests, and the tag-based release
process. See [Architecture](docs/ARCHITECTURE.md) for module boundaries and extension guidance.

Maintainers can also open **Actions → Release Version → Run workflow** and choose `fix`, `minor`,
or `major`. The workflow calculates and pushes the next semantic-version tag, then builds and
publishes the platform archives.

## License

Mad Coder is released under the [MIT License](LICENSE). Release archives bundle Ruff;
see [third-party notices](THIRD_PARTY_NOTICES.md).
