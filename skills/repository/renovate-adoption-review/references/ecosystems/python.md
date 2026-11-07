# Python

## Where to look in the update

- Package release notes, CHANGELOG (`CHANGES`, `HISTORY`), and migration guides: "deprecated", "removed", "renamed", "new in".
- The tag-to-tag diff of the public modules: `warnings.warn(..., DeprecationWarning)` calls naming a replacement, `typing_extensions.deprecated` decorators, removed names in `__all__`.
- For linters and formatters (ruff, mypy, and similar): renamed or removed rules and configuration keys.

## Consumer files to grep

- `pyproject.toml` (including `[tool.*]` sections), `setup.cfg`, `setup.py`, `requirements*.txt`, `tox.ini`, `noxfile.py`, `.pre-commit-config.yaml`, `ruff.toml`, `mypy.ini`.
- Source and tests (`src/**`, the package directory, `tests/**`) for imports and calls of deprecated names.
- Compatibility shims (`try: import ... except ImportError`) and version checks on the dependency.

## Local warning command

- `ruff check` (reports deprecated or removed rule codes and settings).
- Tests with warnings visible: `python -W default::DeprecationWarning -m pytest` or `pytest -W error::DeprecationWarning` scoped to the consumer's own code.
- The consumer's type checker, when configured.

## Typical adoptable patterns

- A deprecated function, argument or import path with a documented successor.
- A compatibility shim for an older version of the dependency that is no longer in the supported range.
- A renamed configuration key or lint rule code in `pyproject.toml`.
- A hand-written helper that the new version provides, when the notes announce it.

## Typical false positives

- `DeprecationWarning`s emitted from inside third-party packages rather than the consumer's code.
- Adopting syntax or standard-library features tied to a Python version change rather than the dependency update.
- Pinning or unpinning requirements: Renovate's job, not adoption.
- Removing a shim still needed for another supported version of the dependency.
