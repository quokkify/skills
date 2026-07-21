# Shared Skill Repository and Private Agent Vault

## Recommended layout

Use one canonical repository for portable skills and runtime adapters:

```text
repository-root/
├── skills/
│   └── <category>/
│       └── <portable-skill>/
│           ├── SKILL.md
│           └── references/
├── adapters/
│   ├── claude/
│   ├── codex/
│   └── hermes/
├── scripts/
└── docs/
```

Keep the full agent-state backup separate and private:

```text
agent-vault/
├── snapshot/
├── scripts/backup.*
├── scripts/restore.*
└── version-and-source-manifest
```

The shared repository is a product and source of truth. The vault is a recovery artifact. Git history backs up canonical skill evolution; local curator archives provide rollback; neither should be confused with a full independent disaster-recovery copy.

## Synchronization semantics

- Hermes can scan a canonical checkout through `skills.external_dirs`; existing external skills may then be updated where found.
- A same-name profile-local skill takes precedence over an external one, so check for collisions before assuming the canonical version is active.
- Newly agent-created Hermes skills normally start in the profile-local skills directory. Promotion into the canonical repository is a review step, not an automatic mirror.
- Claude Code and Codex should use tool-specific adapters while reading the same portable packages.
- The private vault should record repository URL, branch, exact SHA, dirty/clean status, and whether the branch has been pushed. Restore should reclone the canonical repository.

## Public repository boundary

A public skill repository may expose generic prompts, role names, orchestration strategy, and model-routing policy when the owner accepts that know-how being visible. It must not include:

- secrets, auth material, private keys, `.env`, or local settings;
- memory/user profiles, chats, transcripts, channel IDs, logs, or runtime databases;
- private customer rules, non-public project docs, private URLs/IPs, or personal paths;
- raw agent-home snapshots or curator archives.

Use branch/PR promotion for generated skills. Add a license if public reuse is intended.

## Fine-grained GitHub token enrollment

Create a fine-grained PAT restricted to the canonical repository. Typical permissions:

- Metadata: read-only (automatic)
- Contents: read/write
- Pull requests: read/write when agents open PRs
- Issues: read/write only when issue automation is required

Store it outside both repositories in an access-controlled secret store. The following Bash enrollment shape fails closed and writes the token only after validating the explicitly reviewed account and repository:

```bash
set -Eeuo pipefail
umask 077
: "${SKILL_SECRET_DIR:?set a private directory outside the repositories}"
: "${EXPECTED_GITHUB_LOGIN:?set the reviewed account login}"
: "${EXPECTED_REPOSITORY:?set the reviewed OWNER/REPO}"
install -d -m 0700 "$SKILL_SECRET_DIR"

IFS= read -r -s -p 'Token: ' token
printf '\n'
[[ -n "$token" ]] || { echo "empty token rejected" >&2; exit 1; }
login="$(GH_TOKEN="$token" gh api user --jq .login)"
permission="$(GH_TOKEN="$token" gh repo view "$EXPECTED_REPOSITORY" \
  --json viewerPermission --jq .viewerPermission)"
[[ "$login" == "$EXPECTED_GITHUB_LOGIN" ]] || { echo "unexpected GitHub login" >&2; exit 1; }
[[ "$permission" =~ ^(WRITE|MAINTAIN|ADMIN)$ ]] || { echo "repository write permission required" >&2; exit 1; }

tmp="$(mktemp "$SKILL_SECRET_DIR/.skills-github.env.XXXXXX")"
trap 'rm -f "$tmp"' EXIT
printf 'SKILLS_GITHUB_TOKEN=%q\n' "$token" > "$tmp"
chmod 0600 "$tmp"
mv -f "$tmp" "$SKILL_SECRET_DIR/skills-github.env"
trap - EXIT
unset token login permission
```

Do not print the token, paste it into chat, store it in the repository, or put it in the remote URL. Require an explicit, reviewed repository target or allowlist; never infer authorization scope from the token itself.

When Git is configured with `gh auth git-credential`, a process-local `GH_TOKEN` can be used without replacing the user's unrelated global `gh` login. Revalidate the identity, permission, exact remote, and branch immediately before the scoped push:

```bash
set -Eeuo pipefail
: "${SKILL_SECRET_FILE:?set the reviewed mode-600 environment file}"
: "${EXPECTED_GITHUB_LOGIN:?set the reviewed account login}"
: "${EXPECTED_REPOSITORY:?set the reviewed OWNER/REPO}"
: "${EXPECTED_REMOTE_URL:?set the exact reviewed Git remote URL}"
: "${EXPECTED_BRANCH:?set the reviewed destination branch}"
REMOTE_NAME="${REMOTE_NAME:-origin}"
set -a
. "$SKILL_SECRET_FILE"
set +a
: "${SKILLS_GITHUB_TOKEN:?token missing from reviewed secret file}"
[[ "$(git remote get-url "$REMOTE_NAME")" == "$EXPECTED_REMOTE_URL" ]] || { echo "unexpected Git remote" >&2; exit 1; }
[[ "$(git symbolic-ref --quiet --short HEAD)" == "$EXPECTED_BRANCH" ]] || { echo "unexpected local branch" >&2; exit 1; }
[[ "$(GH_TOKEN="$SKILLS_GITHUB_TOKEN" gh api user --jq .login)" == "$EXPECTED_GITHUB_LOGIN" ]] || { echo "unexpected GitHub login" >&2; exit 1; }
permission="$(GH_TOKEN="$SKILLS_GITHUB_TOKEN" gh repo view "$EXPECTED_REPOSITORY" \
  --json viewerPermission --jq .viewerPermission)"
[[ "$permission" =~ ^(WRITE|MAINTAIN|ADMIN)$ ]] || { echo "repository write permission required" >&2; exit 1; }
GH_TOKEN="$SKILLS_GITHUB_TOKEN" git \
  -c credential.helper= -c credential.helper='!gh auth git-credential' \
  push --porcelain "$REMOTE_NAME" "HEAD:refs/heads/$EXPECTED_BRANCH"
unset SKILLS_GITHUB_TOKEN permission
```

## First secret-scanning pull request

Start with one focused workflow rather than bundling every hardening measure:

```yaml
name: "Secret scan"

on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pull-requests: write

jobs:
  gitleaks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<immutable-sha>
        with:
          fetch-depth: 0
          persist-credentials: false
      - uses: gitleaks/gitleaks-action@<immutable-sha>
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Notes:

- `fetch-depth: 0` enables history scanning.
- `persist-credentials: false` prevents checkout from leaving the workflow token in `.git/config` when subsequent Git authentication is unnecessary.
- The workflow uses GitHub's ephemeral `GITHUB_TOKEN`, not the VPS PAT.
- Pin action revisions to commits and leave a version comment for maintainability.
- If PR comments are unnecessary, remove `pull-requests: write` and keep contents read-only.

Before push, download an official Gitleaks release to a temporary directory, verify the archive against the published checksum, and run a local full-history baseline scan. After opening the PR, verify local HEAD, remote branch ref, and PR head match; wait for Gitleaks and the current-head review gate. If review identifies checkout credential persistence or another valid hardening issue, fix it and rerun both gates.

## Promotion checklist

1. Identify the evidence for a skill change.
2. Prefer an existing class-level umbrella.
3. Discard session-specific evidence; references may contain only sanitized, reusable guidance with appropriate provenance.
4. Remove personal, medical, private-project, client, and infrastructure-specific material.
5. Run secret scanning against current files and history.
6. Commit on a dedicated branch and open a focused PR.
7. Verify exact-head CI and review.
8. Merge only after human/repository policy approval.

## Hermes external-directory enrollment

For one canonical checkout, prefer a scalar path because Hermes accepts either a string or a list:

```bash
hermes config set skills.external_dirs /path/to/skills
```

Do not pass JSON-looking array text to a scalar `config set` command unless that command explicitly supports typed decoding. It may persist the brackets and quotes as part of one string, which then resolves as a nonexistent path. For multiple directories, write a real YAML list through the supported configuration path.

Enroll safely:

1. Ensure the canonical checkout is clean, on its default branch, and synchronized to the intended release/tag.
2. Compare canonical skill frontmatter names with profile-local skill names; local names take precedence.
3. Back up the active config with restrictive permissions.
4. Set `skills.external_dirs` and confirm the parsed value resolves to the intended existing directory.
5. Use the runtime skill index to confirm all expected skill names appear.
6. Load a skill by its bare name and then load one bundled `references/` or `templates/` file; verify the reported source path is the canonical checkout.
7. Start a new long-lived session when prompt-level discovery must refresh.

Keep documentation filenames distinct from skill names. A guide such as `docs/guides/skill-review.md` can collide with `skill-review/SKILL.md` in basename-oriented resolution even though only one is a skill definition. Rename the guide to a descriptive non-colliding stem and retest bare-name loading.

## Release and legacy-branch hygiene

Generated release pull requests still require content review. Release automation may include both a conventional inner commit and its merge commit, creating duplicate changelog bullets. Before merging:

1. Inspect the proposed manifest version and only the new changelog section.
2. Collapse duplicate bullets into one curated entry per semantic change, with correct pull-request links.
3. Push the correction to the release branch.
4. Re-run title validation and full-history secret scanning on the edited head.
5. Confirm the repository's allowed merge method before invoking merge automation.
6. After merge, verify the workflow conclusion, tag target, latest release, manifest value, and changelog on the default branch.

For broad stale pull requests, secret scanning is necessary but not sufficient. Review file scope, unresolved findings, broken dependencies, machine-specific assumptions, and project-specific context. Close and delete the branch when the snapshot predates the controlled promotion policy or cannot be reviewed as one coherent change. Promote genuinely reusable pieces later as small sanitized PRs. If an actual credential or sensitive personal record is found, branch deletion alone is insufficient: rotate the credential and follow repository history-removal procedures.
