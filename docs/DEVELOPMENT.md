# Development

## Requirements

- Houdini 21.0 or newer with Qt 6/PySide6 for interactive testing
- Python 3.11 or newer for unit tests
- Ruff 0.16.0 and BasedPyright 1.39.9 for repository checks
- Git

For VS Code diagnostics, install the recommended BasedPyright extension
(`detachhead.basedpyright`). The repository settings select workspace-wide diagnostics and
keep the type-checking mode aligned with `pyproject.toml`. Disable Pylance for this workspace
so two Python language servers do not report competing diagnostics.

PySide6 and `hou` are supplied by Houdini. They are deliberately not declared as installable
Python dependencies because a separately installed Qt binding can conflict with Houdini's Qt
runtime.

## Source checkout installation

Point a personal Houdini package file directly at the checkout. Create
`$HOUDINI_USER_PREF_DIR/packages/mad-coder-dev.json` with this content, replacing the
path:

```json
{
  "enable": "houdini_version >= '21.0'",
  "show": true,
  "hpath": "/absolute/path/to/mad-coder/mad-coder"
}
```

Install Ruff 0.16.0 separately and make it visible through `PATH`, copy its executable to
`mad-coder/bin`, or set `MAD_CODER_RUFF` before starting Houdini. Restart
Houdini after adding or changing package files.

Python module edits can usually be tested by choosing **Reload Interface** from the Python Panel's
interface menu. Changes to the `.pypanel` definition or package configuration may require a Houdini
restart.

## Run checks

From the repository root:

The same commands are available through the repository `Makefile`:

```shell
make check
make lint
make test
make typecheck
```

To install the pinned Ruff and Pyright versions:

```shell
make install-checks
```

The direct commands are:

```shell
python -m compileall -q mad-coder/scripts/python scripts tests
python -m unittest discover -s tests -v
ruff check mad-coder/scripts/python scripts tests
basedpyright
```

Unit tests avoid importing `hou` and PySide6. BasedPyright checks the entire Python source tree; only
imports supplied by Houdini are explicitly marked as environment-provided because SideFX does not
distribute them as normal public Python packages. Houdini integration still requires an interactive
smoke test.

## Interactive smoke test

Before releasing:

1. Launch the main Qt 6/Python 3.11 build of Houdini 21.
2. Open Mad Coder from a Python Panel.
3. Enter an unused import and confirm that Ruff reports `F401` without freezing the UI.
4. Enter invalid syntax and confirm that it appears inline and in Problems.
5. Correct the source, save it, and confirm the new member is available from the Python Shell.
6. Modify `hou.session` through the native source editor and verify conflict handling.
7. Create and select a Python SOP. Confirm its code opens, saves, cooks, and participates in
   Houdini undo. Confirm `hou.pwd()` does not produce an `F821` diagnostic while a genuinely
   undefined name still does.
8. Select an HDA with a `PythonModule`. Choose it in the source selector, save a harmless change,
   and confirm the definition change is visible from another instance. Confirm both `hou` and
   `kwargs` are accepted as context globals.
9. Select an HDA with a `ViewerStateModule`. Choose it in the source selector, save a harmless
   change, run it, and verify the embedded viewer state reloads without restarting Houdini.
   Confirm both `hou` and `kwargs` are accepted as context globals.
10. Add `print`, standard-error, and logging output to a Python SOP. Select **Run** and confirm the
   node cooks and every message appears in Console exactly once.
11. Raise an exception and confirm its traceback and failed status appear in Console without
    closing the panel. Correct it and confirm a subsequent run succeeds.
12. Make a buffer dirty, change node selection, and confirm Mad Coder does not discard the buffer.
13. Disable Follow Selection, select another supported node, and verify **Use Selected** opens it.
14. Open a source in a non-writable HDA library and confirm it is view-only.
15. Format deliberately irregular code and verify the cursor remains near its original position.
16. Open **Settings…**, select another monospaced font and size, and confirm the preview and editor
    update. Close and reopen Houdini and confirm the choice persists.
17. Use **Restore Defaults** and confirm Roboto Mono is selected when installed, or the platform
    fixed-width font otherwise. Confirm Cancel does not apply a change.
18. Load and clear scenes while the panel is open and verify source discovery refreshes.
19. Repeat the smoke test with Houdini 22's default Python 3.13 build when preparing a public
   release.

## Build a release archive locally

Install the pinned Ruff distribution into the active Python environment, then run:

```shell
make build-local
```

This creates `dist/mad-coder-0.0.0-dev-macos-arm64.zip` by default. Override the platform and
version when needed:

```shell
make build-local PLATFORM=linux-x64 VERSION=0.0.0-dev
```

The direct command remains available:

```shell
python scripts/build_release.py --version 0.1.0 --platform macos-arm64
```

Use `linux-x64`, `windows-x64`, or `macos-arm64` as appropriate. The builder copies the Ruff
executable and its license into the ZIP under `dist/`. It resolves both directly from the Ruff
distribution installed for the active Python interpreter, so shell launchers such as pyenv shims are
never packaged. Never use a binary from one operating system to build another platform's archive.

Inspect the ZIP before distribution. Its root must contain exactly the `packages` and `mad-coder`
directories.

## GitHub release process

### Manual release workflow

The recommended release path is **Actions → Release Version → Run workflow**. Select the component
to increment:

- `fix`: increment patch (`v1.2.3` → `v1.2.4`)
- `minor`: increment minor and reset patch (`v1.2.3` → `v1.3.0`)
- `major`: increment major and reset minor and patch (`v1.2.3` → `v2.0.0`)

The workflow checks out the repository's default branch, validates it, calculates the next version
from strict `vMAJOR.MINOR.PATCH` tags, creates an annotated tag, pushes it, and directly invokes the
release workflow. Prerelease and unrelated tags are ignored. Concurrent manual releases are
serialized to prevent two runs from selecting the same version.

If publishing fails after a tag has already been created, merge the workflow fix and open
**Actions → Release → Run workflow**. Enter the existing tag, such as `v0.1.0`. This rebuilds the
tagged source and retries publication without creating or moving a tag.

### Command-line release

1. Update `__version__`, `pyproject.toml`, documentation, and the changelog together.
2. Run unit tests and the Houdini smoke test.
3. Commit and push the release changes.
4. Create and push an annotated tag such as `v0.1.0`.
5. The Release workflow validates the source, then runs natively on Windows, Linux, and Apple
   Silicon macOS, installs pinned Ruff, builds three archives, and creates the GitHub release with
   generated notes and SHA-256 checksums.
6. Download and inspect all three published archives.

The CI workflow tests the minimum Python 3.11 runtime and runs Ruff and BasedPyright on every pull
request and push to `master` or `main`.

## Versioning policy

The project follows semantic versioning. Houdini support is controlled both by the package JSON's
`enable` expression and the compatibility table in the README. A change to the minimum Houdini
version is user-visible and must be documented.
