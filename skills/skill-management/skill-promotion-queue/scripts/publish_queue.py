#!/usr/bin/env python3
"""Publish a validated skill-improvement lane to one rolling draft pull request."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Sequence
from urllib.parse import urlsplit

LANE_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,62})$")
REPOSITORY_PART_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
ALLOWED_ROOT_FILES = {
    "README.md",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
}
ALLOWED_DIRECTORIES = {"skills", "docs", "tests", "scripts", "adapters"}
FORBIDDEN_PARTS = {
    ".env",
    ".git",
    ".secrets",
    "auth.json",
    "credentials.json",
    "memory.md",
    "sessions",
    "transcripts",
    "user.md",
}
COMMAND_TIMEOUT_SECONDS = 300.0
VALIDATION_TIMEOUT_SECONDS = 900.0
# GitHub CLI subcommands that take the repository positionally and reject --repo.
GH_POSITIONAL_REPOSITORY_COMMANDS = {("repo", "view")}


class QueueError(RuntimeError):
    """A fail-closed queue precondition failed."""


def run(
    arguments: Sequence[str],
    *,
    cwd: Path,
    environment: dict[str, str] | None = None,
    check: bool = True,
    timeout: float = COMMAND_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    """Run a command without a shell and capture its text output."""
    try:
        result = subprocess.run(
            list(arguments),
            cwd=cwd,
            env=environment,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise QueueError(f"{arguments[0]} command timed out after {timeout:g}s") from error
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise QueueError(f"{arguments[0]} command failed: {detail}")
    return result


def git(root: Path, *arguments: str, check: bool = True) -> str:
    """Run Git in the queue worktree."""
    return run(["git", *arguments], cwd=root, check=check).stdout.strip()


def validate_lane(lane: str) -> str:
    """Return the branch name for a valid lane."""
    if not LANE_RE.fullmatch(lane):
        raise QueueError("lane must be 1-63 lowercase letters, digits, dots, underscores, or hyphens")
    return f"automation/skill-improvements/{lane}"


def validate_repository(repository: str) -> None:
    """Validate an owner/repository identifier without accepting URL syntax."""
    parts = repository.split("/")
    if (
        len(parts) != 2
        or any(part in {".", ".."} for part in parts)
        or any(not REPOSITORY_PART_RE.fullmatch(part) for part in parts)
    ):
        raise QueueError("repository must use the owner/name form")


def path_is_allowed(raw_path: str) -> bool:
    """Return whether a changed repository-relative path is public-queue eligible."""
    path = PurePosixPath(raw_path)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        return False
    folded = {part.casefold() for part in path.parts}
    if folded & FORBIDDEN_PARTS:
        return False
    if len(path.parts) == 1:
        return path.name in ALLOWED_ROOT_FILES
    return path.parts[0] in ALLOWED_DIRECTORIES


def changed_paths(root: Path, base_ref: str) -> list[str]:
    """Return the lane diff from its merge base with the current default branch."""
    output = git(root, "diff", "--name-only", "--diff-filter=ACMRTUXB", f"{base_ref}...HEAD")
    return [line for line in output.splitlines() if line]


def ensure_public_paths(paths: Sequence[str]) -> None:
    """Reject empty or out-of-bound queue diffs."""
    if not paths:
        raise QueueError("the lane has no changed paths relative to the default branch")
    rejected = [path for path in paths if not path_is_allowed(path)]
    if rejected:
        raise QueueError("queue contains disallowed paths: " + ", ".join(rejected))


def parse_pull_requests(payload: str) -> list[dict[str, Any]]:
    """Parse and validate the small gh pr list response used by the helper."""
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as error:
        raise QueueError(f"GitHub CLI returned invalid JSON: {error}") from error
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise QueueError("GitHub CLI returned an unexpected pull-request response")
    return value


def build_body(
    *, lane: str, head: str, commits: Sequence[str], paths: Sequence[str]
) -> str:
    """Build a deterministic draft-queue PR body."""
    commit_lines = "\n".join(f"- `{subject}`" for subject in commits)
    path_lines = "\n".join(f"- `{path}`" for path in paths)
    return f"""## Queue policy

Rolling draft pull request for agent/device lane `{lane}`.

- Independent review is intentionally deferred until the owner batches the queue.
- Deterministic repository validation is still required on every update.
- This workflow never merges or converts the pull request from draft.

## Current head

`{head}`

## Commits queued

{commit_lines}

## Changed paths

{path_lines}

## Validation

- `./scripts/validate.sh --ci`
- Public-path allowlist and clean exact-HEAD checks in `publish_queue.py`
- Repository CI and secret scanning remain enabled
"""


def askpass_environment() -> tuple[dict[str, str], tempfile.TemporaryDirectory[str] | None]:
    """Build a temporary Git askpass helper when GH_TOKEN is available."""
    environment = os.environ.copy()
    token = environment.get("GH_TOKEN")
    if not token:
        return environment, None

    temporary = tempfile.TemporaryDirectory(prefix="skill-queue-askpass-")
    helper = Path(temporary.name) / "askpass.sh"
    helper.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in\n"
        "  *Username*) printf '%s\\n' 'x-access-token' ;;\n"
        "  *) printf '%s\\n' \"$GH_TOKEN\" ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    helper.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    environment.update(
        {
            "GIT_ASKPASS": str(helper),
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return environment, temporary


def remote_matches_repository(remote: str, repository: str) -> bool:
    """Match exact GitHub HTTPS/SSH remotes without hostname suffix confusion."""
    expected = repository.casefold()
    if "://" in remote:
        parsed = urlsplit(remote)
        if parsed.hostname != "github.com":
            return False
        if parsed.scheme in {"http", "https"} and (parsed.username or parsed.password):
            return False
        if parsed.scheme not in {"http", "https", "ssh", "git"}:
            return False
        return parsed.path.strip("/").removesuffix(".git").casefold() == expected

    match = re.fullmatch(r"(?:[^@/:]+@)?github\.com:(.+)", remote, flags=re.IGNORECASE)
    if not match:
        return False
    return match.group(1).strip("/").removesuffix(".git").casefold() == expected


def ensure_remote_is_github(root: Path, repository: str) -> None:
    """Fail if origin is not the requested GitHub repository."""
    remote = git(root, "remote", "get-url", "origin")
    if not remote_matches_repository(remote, repository):
        raise QueueError("origin does not match the requested GitHub repository")


def resolve_default_branch(root: Path, repository: str) -> str:
    """Resolve and validate the target repository's current default branch."""
    branch = gh(
        root,
        repository,
        "repo",
        "view",
        "--json",
        "defaultBranchRef",
        "--jq",
        ".defaultBranchRef.name",
    )
    if not branch or branch.startswith("-") or any(character.isspace() for character in branch):
        raise QueueError("GitHub returned an invalid default branch")
    valid = run(["git", "check-ref-format", f"refs/heads/{branch}"], cwd=root, check=False)
    if valid.returncode != 0:
        raise QueueError("GitHub returned an invalid default branch")
    return branch


def fetch_refs(root: Path, branch: str, default_branch: str) -> str | None:
    """Fetch the default and existing queue branches without changing the worktree."""
    git(
        root,
        "fetch",
        "--no-tags",
        "origin",
        f"refs/heads/{default_branch}:refs/remotes/origin/{default_branch}",
    )
    probe = run(
        ["git", "ls-remote", "--heads", "origin", f"refs/heads/{branch}"], cwd=root
    ).stdout.strip()
    if not probe:
        return None
    git(
        root,
        "fetch",
        "--no-tags",
        "origin",
        f"refs/heads/{branch}:refs/remotes/origin/{branch}",
    )
    return f"origin/{branch}"


def ensure_repository_state(
    root: Path,
    branch: str,
    remote_branch: str | None,
    base_ref: str,
) -> str:
    """Check branch identity, cleanliness, ancestry, and unpublished commits."""
    actual_root = Path(git(root, "rev-parse", "--show-toplevel")).resolve()
    if actual_root != root.resolve():
        raise QueueError("run the helper from the queue worktree root")
    actual_branch = git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    if actual_branch != branch:
        raise QueueError(f"expected branch {branch!r}, found {actual_branch!r}")
    if git(root, "status", "--porcelain", "--untracked-files=normal"):
        raise QueueError("queue publication requires a clean worktree")
    if remote_branch:
        ancestor = run(
            ["git", "merge-base", "--is-ancestor", remote_branch, "HEAD"],
            cwd=root,
            check=False,
        )
        if ancestor.returncode != 0:
            raise QueueError("remote queue branch is not an ancestor of local HEAD; refusing force-push")
    ahead = int(git(root, "rev-list", "--count", f"{base_ref}..HEAD"))
    if ahead < 1:
        raise QueueError("queue branch has no commits ahead of the default branch")
    return git(root, "rev-parse", "HEAD")


def validate_exact_head(root: Path, expected_head: str) -> None:
    """Run the repository CI-equivalent and prove it did not change HEAD or files."""
    run(
        ["bash", "scripts/validate.sh", "--ci"],
        cwd=root,
        timeout=VALIDATION_TIMEOUT_SECONDS,
    )
    if git(root, "rev-parse", "HEAD") != expected_head:
        raise QueueError("HEAD changed during validation")
    if git(root, "status", "--porcelain", "--untracked-files=normal"):
        raise QueueError("validation changed the worktree")


def gh(root: Path, repository: str, *arguments: str) -> str:
    """Run GitHub CLI for the explicitly requested repository.

    Repository placement is per subcommand, not uniform. `pr` and `api` take --repo, but
    `repo view` has no --repo flag at all and takes the repository positionally; sending
    --repo there fails with "unknown flag: --repo" and blocks every publication.

    A positional value is safe: validate_repository() runs before any gh call and
    enforces the owner/name form with an alphanumeric first character, so the value can
    never be parsed as a flag.
    """
    if tuple(arguments[:2]) in GH_POSITIONAL_REPOSITORY_COMMANDS:
        command = ["gh", *arguments[:2], repository, *arguments[2:]]
    else:
        command = ["gh", *arguments, "--repo", repository]
    return run(command, cwd=root).stdout.strip()


def push_arguments(branch: str, *, temporary_askpass: bool) -> list[str]:
    """Build a push command without overriding a configured credential helper unnecessarily."""
    arguments = ["git"]
    if temporary_askpass:
        arguments.extend(["-c", "credential.helper="])
    arguments.extend(["push", "--set-upstream", "origin", f"HEAD:{branch}"])
    return arguments


def publish(
    root: Path,
    *,
    repository: str,
    lane: str,
    title: str,
) -> dict[str, Any]:
    """Validate, push, and create or refresh one rolling draft PR."""
    validate_repository(repository)
    branch = validate_lane(lane)
    ensure_remote_is_github(root, repository)
    default_branch = resolve_default_branch(root, repository)
    base_ref = f"origin/{default_branch}"
    remote_branch = fetch_refs(root, branch, default_branch)
    head = ensure_repository_state(root, branch, remote_branch, base_ref)
    paths = changed_paths(root, base_ref)
    ensure_public_paths(paths)
    validate_exact_head(root, head)

    commits = git(root, "log", "--format=%s", f"{base_ref}..HEAD").splitlines()
    body = build_body(lane=lane, head=head, commits=commits, paths=paths)

    environment, temporary = askpass_environment()
    try:
        run(
            push_arguments(branch, temporary_askpass=temporary is not None),
            cwd=root,
            environment=environment,
        )
    finally:
        if temporary:
            temporary.cleanup()

    remote_head = run(
        ["git", "ls-remote", "--heads", "origin", f"refs/heads/{branch}"], cwd=root
    ).stdout.split()
    if not remote_head or remote_head[0] != head:
        raise QueueError("remote queue branch does not match the validated local HEAD")

    existing = parse_pull_requests(
        gh(
            root,
            repository,
            "pr",
            "list",
            "--state",
            "open",
            "--head",
            branch,
            "--json",
            "number,url,isDraft,headRefOid,baseRefName",
        )
    )
    if len(existing) > 1:
        raise QueueError("more than one open pull request exists for the queue lane")

    if existing:
        current = existing[0]
        if current.get("baseRefName") != default_branch:
            raise QueueError("the existing queue pull request targets a different base branch")
        if not current.get("isDraft"):
            raise QueueError("the existing queue pull request is no longer a draft")
        number = str(current["number"])
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as payload_file:
            json.dump({"title": title, "body": body}, payload_file)
            payload_path = Path(payload_file.name)
        try:
            run(
                [
                    "gh",
                    "api",
                    f"repos/{repository}/pulls/{number}",
                    "--method",
                    "PATCH",
                    "--input",
                    str(payload_path),
                ],
                cwd=root,
            )
        finally:
            payload_path.unlink(missing_ok=True)
        action = "updated"
    else:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as body_file:
            body_file.write(body)
            body_path = Path(body_file.name)
        try:
            gh(
                root,
                repository,
                "pr",
                "create",
                "--draft",
                "--base",
                default_branch,
                "--head",
                branch,
                "--title",
                title,
                "--body-file",
                str(body_path),
            )
        finally:
            body_path.unlink(missing_ok=True)
        action = "created"

    final = parse_pull_requests(
        gh(
            root,
            repository,
            "pr",
            "list",
            "--state",
            "open",
            "--head",
            branch,
            "--json",
            "number,url,isDraft,headRefOid,body,baseRefName",
        )
    )
    if (
        len(final) != 1
        or not final[0].get("isDraft")
        or final[0].get("headRefOid") != head
        or final[0].get("baseRefName") != default_branch
        or head not in str(final[0].get("body", ""))
    ):
        raise QueueError("could not verify one draft pull request at the validated HEAD")
    return {
        "action": action,
        "branch": branch,
        "head": head,
        "number": final[0]["number"],
        "url": final[0]["url"],
        "draft": True,
        "changed_paths": paths,
    }


def parse_args() -> argparse.Namespace:
    """Parse the explicit repository, lane, and pull-request title inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="GitHub owner/repository")
    parser.add_argument("--lane", required=True, help="lowercase device or agent lane")
    parser.add_argument(
        "--title",
        default="feat(skills): queue reusable skill improvements",
        help="Conventional Commit style draft PR title",
    )
    return parser.parse_args()


def main() -> int:
    """Run the fail-closed queue publisher and emit one machine-readable result."""
    arguments = parse_args()
    try:
        result = publish(
            Path.cwd(),
            repository=arguments.repository,
            lane=arguments.lane,
            title=arguments.title,
        )
    except QueueError as error:
        print(f"skill queue refused: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
