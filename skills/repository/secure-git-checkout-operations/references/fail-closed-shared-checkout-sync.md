# Fail-closed shared checkout synchronization

## Core invariant

A fetched commit may be the intended update while remaining untrusted executable code. Validate it as data; do not grant it host execution merely to decide whether to fast-forward.

## Parameterized command shape

```bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
EXPECTED_BRANCH="${EXPECTED_BRANCH:?set expected consumer branch}"
REMOTE_NAME="${REMOTE_NAME:-origin}"
EXPECTED_REMOTE_URL="${EXPECTED_REMOTE_URL:?set the exact approved remote URL}"
VALIDATOR_PATH="${VALIDATOR_PATH:?set trusted dependency-free validator path}"

[[ "$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)" == "$EXPECTED_BRANCH" ]]
[[ -z "$(git status --porcelain --untracked-files=normal)" ]]

ACTUAL_REMOTE_URL="$(git remote get-url "$REMOTE_NAME")"
[[ "$ACTUAL_REMOTE_URL" == "$EXPECTED_REMOTE_URL" ]] || {
  echo "configured remote does not match the approved repository" >&2
  exit 1
}
[[ -f "$VALIDATOR_PATH" ]]

checkout_is_exact_and_clean() {
  local expected_oid="$1"
  [[ "$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)" == "$EXPECTED_BRANCH" ]] &&
    [[ "$(git rev-parse 'HEAD^{commit}')" == "$expected_oid" ]] &&
    [[ -z "$(git status --porcelain --untracked-files=normal)" ]]
}

TMP="$(mktemp -d "${TMPDIR:-/tmp}/checkout-sync.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
cp "$VALIDATOR_PATH" "$TMP/trusted-validator.py"
python3 "$TMP/trusted-validator.py" "$ROOT"

CURRENT_OID="$(git rev-parse 'HEAD^{commit}')"
REMOTE_REF="refs/remotes/${REMOTE_NAME}/${EXPECTED_BRANCH}"
git fetch --quiet --no-tags "$REMOTE_NAME" \
  "refs/heads/${EXPECTED_BRANCH}:${REMOTE_REF}"
REMOTE_OID="$(git rev-parse "${REMOTE_REF}^{commit}")"

git merge-base --is-ancestor "$CURRENT_OID" "$REMOTE_OID" || {
  echo 'consumer checkout is ahead or diverged' >&2
  exit 1
}

if [[ "$CURRENT_OID" != "$REMOTE_OID" ]]; then
  mkdir "$TMP/candidate"
  git archive "$REMOTE_OID" | tar -x -C "$TMP/candidate"
  python3 "$TMP/trusted-validator.py" "$TMP/candidate"
  checkout_is_exact_and_clean "$CURRENT_OID" || {
    echo 'checkout changed during candidate validation' >&2
    exit 1
  }
  [[ "$(git rev-parse "${REMOTE_REF}^{commit}")" == "$REMOTE_OID" ]] || {
    echo 'remote-tracking ref moved during candidate validation' >&2
    exit 1
  }
  git -c core.hooksPath=/dev/null merge --ff-only "$REMOTE_OID"
fi

checkout_is_exact_and_clean "$REMOTE_OID" || {
  echo 'checkout is not the exact validated revision' >&2
  exit 1
}
python3 "$TMP/trusted-validator.py" "$ROOT"
checkout_is_exact_and_clean "$REMOTE_OID" || {
  echo 'checkout changed during post-update validation' >&2
  exit 1
}
[[ "$(git rev-parse "${REMOTE_REF}^{commit}")" == "$REMOTE_OID" ]] || {
  echo 'remote-tracking ref moved after post-update validation' >&2
  exit 1
}
```

Production scripts should replace bare guards with clear errors and explicitly verify the repository root. Supply the approved remote URL independently of repository-controlled files; the same validated `REMOTE_NAME` is then used by the explicit fetch. The validator path and invocation are repository-specific parameters, not universal defaults.

## Why each boundary exists

- **Clean tracked and untracked tree:** prevents overwriting local candidates, credentials, or unpublished edits.
- **Attached expected branch:** detached HEAD or feature branches are not synchronization targets.
- **Explicit remote refspec:** updates the intended remote-tracking ref and avoids a mutable `FETCH_HEAD` handoff.
- **Pinned remote-tracking ref:** re-asserting `${REMOTE_REF}` still resolves to the validated `REMOTE_OID` before movement and after post-update validation prevents a concurrent fetch from advancing the ref past the tree that was actually validated.
- **Ancestor check:** permits only equal or forward history; rejects local-ahead and divergence.
- **Preserved validator:** candidate changes cannot weaken the gate used to approve themselves.
- **`git archive`:** supplies an exact non-Git candidate tree without checkout/worktree hooks.
- **No candidate script execution:** prevents fetched tests, builds, or validators from accessing host credentials and files.
- **`core.hooksPath=/dev/null`:** suppresses tracked merge hooks during the controlled fast-forward.
- **Pre/post exact-state fences:** detect concurrent branch movement.
- **No automatic rollback of concurrent work:** interference fails closed instead of resetting another process's changes.

## Adversarial fixture recipe

Create a temporary bare remote, publisher clone, and consumer clone with a minimal valid repository plus the sync helper and trusted dependency-free validator.

1. **Fetched-script sentinel:** publish a candidate script that writes outside the candidate tree; synchronization may accept a structurally valid tree, but the sentinel must not appear.
2. **Fetched-hook sentinel:** publish a tracked merge hook, configure the consumer to use tracked hooks, and assert synchronization suppresses it.
3. **Validator rejection:** publish a structurally forbidden file or privacy violation; synchronization must fail and keep the original OID.
4. **Concurrent-ref race:** move the consumer branch after candidate validation; synchronization must fail and must not report success.
5. **History guards:** test local-ahead, divergence, detached HEAD, wrong branch, unknown remote, and an untracked file.

## Pitfalls

- A structural pass does not make fetched scripts trusted.
- Do not hardcode `main`, `origin`, or a validator path unless they are explicit properties of the target repository.
- Do not treat a clean working tree as proof that the remote identity is correct.
- Keep pull-request tooling, release management, and platform-specific review APIs outside this synchronization primitive.
