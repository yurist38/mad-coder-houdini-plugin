# Third-party notices

Release archives bundle the [Ruff](https://github.com/astral-sh/ruff) executable.
Ruff is copyrighted by its contributors and is distributed under the MIT License. The complete
Ruff license is included as `RUFF_LICENSE` in every release archive.

Ruff is not included in source checkouts. It is downloaded from PyPI at the pinned version by
the release workflow.

Release archives bundle the [ty](https://github.com/astral-sh/ty) type-checker executable.
ty is copyrighted by its contributors and is distributed under the MIT License. Its complete license is
included as `TY_LICENSE`. ty is installed from the exact version pinned in
`requirements-dev.txt` when release archives are built.

Release archives also bundle these pure-Python autocomplete components:

- [Jedi](https://github.com/davidhalter/jedi), distributed under the MIT License
- [Parso](https://github.com/davidhalter/parso), distributed under the MIT License
- [types-houdini](https://github.com/LumaPictures/cg-stubs), distributed under the Apache
  License 2.0

Their complete licenses are included as `JEDI_LICENSE`, `PARSO_LICENSE`, and
`TYPES_HOUDINI_LICENSE`. They are installed from the exact versions pinned in
`requirements-runtime.txt` when release archives are built.
