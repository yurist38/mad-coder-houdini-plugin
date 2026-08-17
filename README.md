# Mad Coder

Mad Coder is a dockable Python editor for SideFX Houdini with live Ruff diagnostics and formatting.
It edits the current scene's `hou.session` module, Python code parameters on selected nodes, and
the `PythonModule` section of selected Houdini digital assets without modifying Houdini's internal
editor widgets.

## Features

- Native dockable Python Panel built with Houdini's bundled PySide6
- Python syntax highlighting, line numbers, automatic indentation, and adjustable font size
- Debounced Ruff linting that never blocks Houdini's UI
- Inline warning/error underlines with hover text
- Navigable Problems list
- Ruff formatting
- Built-in console for captured `print`, standard error, logging, and tracebacks
- Context-aware Run action for scene, node, and HDA code
- Save and reload shortcuts
- Protection against overwriting changes made through another editor
- Follow Selection mode for opening supported code from the selected node
- View-only handling for locked parameters and non-writable asset libraries
- Syntax-error diagnostics when Ruff is unavailable

## Compatibility

It targets **Houdini 21.0 and newer**, using Qt 6/PySide6:

| Platform | Supported release archive |
| --- | --- |
| Windows 11 x64 | `windows-x64` |
| Linux x64 on a Houdini-supported distribution | `linux-x64` |
| macOS on Apple Silicon | `macos-arm64` |

Python 3.11 is the minimum supported interpreter. This covers Houdini 21's main Qt 6 build and
Houdini 22's Python 3.11 and 3.13 builds. Qt 5 builds, Houdini 20.5 and older, Intel macOS, and
Linux ARM are outside the initial support scope.

## How to install the plugin

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

### macOS security prompt

macOS may quarantine the bundled Ruff executable and prevent linting from starting, or repeatedly
delay the editor while checking the executable. After installing a trusted Mad Coder release, close
Houdini and run this command in Terminal:

```shell
xattr -dr com.apple.quarantine "$HOME/Library/Preferences/houdini/22.0/mad-coder"
```

Replace `22.0` with the Houdini preferences version you installed the plugin into, such as `21.0`,
then restart Houdini. Only remove quarantine metadata from a release you downloaded from a source
you trust.

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

The source selector identifies what the editor is currently showing. An asterisk means the editor
contains unsaved changes.

### Open code from a node

1. Leave **Follow Selection** enabled.
2. Select a Python node, such as a Python SOP, in a network editor.
3. Mad Coder opens the node's supported Python parameter automatically.
4. If the node is a digital asset with a `PythonModule` section, choose that section from the
   source selector when you want to edit the asset module instead.

The last selected node is used when multiple nodes are selected. **Use Selected** performs the same
lookup on demand, which is useful when Follow Selection is disabled. The source selector always
includes **Scene · hou.session**, so you can return to scene-level code at any time.

Mad Coder does not discard an unsaved buffer when selection changes. Save or reload first, then
select the node again or click **Use Selected**.

### Editing workflow

- Type normally; linting runs after a short pause.
- Hover over an underlined range to read its diagnostic.
- Click a row in **Problems** to jump to its location.
- Select **Format** to apply Ruff formatting to the editor buffer.
- Select **Save** to apply the buffer to its current Houdini source.
- Select **Run** to save, execute in the source's Houdini context, and open captured output.
- Select **Reload** to discard the buffer and read the current source again.

Node-parameter changes are grouped as a Houdini undo operation. Saving a `PythonModule` changes
the digital asset definition and therefore affects every instance of that asset. Asset definitions
in non-writable libraries and locked node parameters are opened view-only.

Saving `hou.session` calls Houdini's `hou.setSessionModuleSource`. Houdini makes the new module
contents available immediately, so top-level code executes as part of applying the source. Changing
node or asset code may also trigger cooks or callbacks. Treat scripts from untrusted scene and asset
files as executable code.

If the current source changed elsewhere after this panel loaded it, Save offers three choices:

- **Reload**: discard this panel's buffer and load the external source.
- **Overwrite**: deliberately replace the external source.
- **Cancel**: keep the unsaved buffer while deciding how to merge the changes.

### Run code and view output

Select **Run** or press `Ctrl+Enter` (`Cmd+Enter` on macOS). Mad Coder switches the lower pane to
**Console** and captures synchronous Python standard output, standard error, logging records, and
uncaught tracebacks. **Copy All** copies the complete console history and **Clear** removes it.

Run applies the current buffer before executing it:

- A Python node parameter is saved and its node is forced to cook in the correct Houdini context.
  This preserves behavior such as `hou.pwd()` and geometry-write permissions.
- `hou.session` is applied and evaluated by Houdini.
- An HDA `PythonModule` is saved and loaded. Modules that only define functions may produce no
  output until another callback invokes those functions.
- A view-only node source can be cooked without changing its stored code.

Run is not a sandbox or a full debugger. It executes inside Houdini's main process. Long-running or
infinite code can make Houdini unresponsive, and there is no safe way for Mad Coder to terminate
arbitrary Python code. Save the scene before running unfamiliar code.

The console captures synchronous Python output during the Run operation. Native Houdini/C++ output,
subprocess output, and messages emitted later by background threads may still appear only in
Houdini's normal console or Python Shell.

### Shortcuts

| Action | Shortcut |
| --- | --- |
| Save | Platform-standard Save (`Ctrl+S` / `Cmd+S`) |
| Run and show Console | `Ctrl+Enter` / `Cmd+Enter` |
| Format | `Ctrl+Shift+F` |
| Reload | `F5` |
| Change font size | `Ctrl` + mouse wheel |

## Linting behavior

Release archives contain a pinned Ruff executable. The editor runs Ruff in an asynchronous child
process with Python 3.11 syntax compatibility and the core `E4`, `E7`, `E9`, and `F` rule groups.
This catches import, name, syntax, and common Python correctness problems without presenting the
hundreds of style rules enabled by Ruff 0.16's expanded defaults.

Mad Coder supplies Ruff with the documented globals for the active Houdini source context. It
recognizes `hou` in scene and Python SOP code, and recognizes both `hou` and `kwargs` in Python
Snippet SOP and HDA `PythonModule` code. These names are configured only for linting; Mad Coder does
not insert imports or alter the saved source.

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

Read the status line for the error reported by Houdini. Correct any syntax diagnostic and save
again. Runtime errors can also be reported while Houdini applies or evaluates code.

### The native Python Source Editor and this panel disagree

Unsaved buffers are private to each editor. Save or reload one editor before switching to the other.
This plugin detects changes to the applied `hou.session` source, but it cannot inspect unsaved text
inside Houdini's native editor.

## Current limitations

- Node discovery currently recognizes common Python code parameter names and HDA
  `PythonModule`; HDA event-handler sections are not yet included.
- There is no code completion, type checking, refactoring, or language-server integration yet.
- Context globals are recognized as defined names, but Ruff does not validate Houdini API member
  names or infer HOM return types.
- Ruff fixes are shown as fixable diagnostics but are not individually applied; Format formats the
  complete buffer.
- The syntax highlighter is intentionally lightweight and is not a full Python parser.
- Run executes synchronously on Houdini's main thread and cannot safely stop an infinite script.

HDA event handlers, external files, quick fixes, and language-server support are natural follow-up
milestones.

## Develop and release

See [Development](docs/DEVELOPMENT.md) for a source installation, tests, and the tag-based release
process. See [Architecture](docs/ARCHITECTURE.md) for module boundaries and extension guidance.

Maintainers can also open **Actions → Release Version → Run workflow** and choose `fix`, `minor`,
or `major`. The workflow calculates and pushes the next semantic-version tag, then builds and
publishes the platform archives.

## License

Mad Coder is released under the [MIT License](LICENSE). Release archives bundle Ruff;
see [third-party notices](THIRD_PARTY_NOTICES.md).
