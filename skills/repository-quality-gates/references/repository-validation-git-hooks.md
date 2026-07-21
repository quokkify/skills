# Repository Validation and Git Hook Safety

## Validate the exact artifact

### Pre-commit

Export the Git index into a temporary directory:

```bash
staged_tree="$(mktemp -d "${TMPDIR:-/tmp}/repo-pre-commit.XXXXXX")"
trap 'rm -rf "$staged_tree"' EXIT
git checkout-index --all --prefix="$staged_tree/"
python3 "$staged_tree/scripts/validate_repo.py" "$staged_tree"
```

The validator must come from the staged snapshot. Running a working-tree validator against staged content lets an unstaged validator edit weaken or bypass the gate.

### Pre-push

Use one explicit contract:

1. Require a clean worktree and require every pushed non-deletion local OID to equal checked-out `HEAD`, then run the full gate; or
2. Export and validate every pushed local OID independently.

Do not validate arbitrary pushed refs against unrelated working-tree files. Reject unsupported multi-ref/non-HEAD pushes with a clear recovery instruction.

## Validator hardening

- Aggregate malformed UTF-8 errors by repository-relative path; do not abort the whole run.
- Reject symbolic links before reading content so validation cannot escape into the host filesystem.
- Resolve local Markdown links and require every candidate target to remain within the repository root before checking existence.
- Detect duplicate skill names and Markdown filename stems that collide with skill names when an agent resolves skills by filename.
- Keep privacy checks targeted and disclose their limits.

## Reproducibility

- Pin local and CI tool versions.
- If a binary exists on `PATH`, verify its version before using it; otherwise fall back to a pinned runner/package version.
- Scan both the working tree and complete Git history. History-only scans miss uncommitted content; directory-only scans miss historical exposure.

## Minimum adversarial matrix

- valid repository passes;
- duplicate skill and skill/Markdown filename collision fail;
- staged-bad/working-good content still fails pre-commit;
- dirty and non-HEAD pushes fail under a strict pre-push contract;
- malformed UTF-8 in skill and Markdown files is reported without stopping aggregation;
- a relative link to an existing host file outside the repository fails;
- forbidden state filenames, machine-specific paths, and symlinks fail;
- pinned documentation build and both secret-scan scopes pass.

Before opening the PR, run shell static analysis, workflow linting, unit tests, documentation build, `git diff --check`, and secret scanning. After fixes, re-run all gates on the new exact head and inspect every reviewer surface.
