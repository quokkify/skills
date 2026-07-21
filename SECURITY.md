# Security and privacy policy

This is a public repository. Treat every committed file and every Git revision as permanently public, even after a later deletion.

## Public content boundary

This repository may contain:

- portable `SKILL.md` instructions and supporting references;
- generic Claude Code, Codex, and Hermes adapters;
- redacted examples with fictional identities and placeholder values;
- reusable scripts that read credentials from environment variables or external secret stores.

Do not commit:

- API keys, access tokens, passwords, cookies, private keys, or OAuth credentials;
- `.env`, `auth.json`, `settings.local.json`, or secret-store exports;
- Hermes or Claude sessions, transcripts, memories, user profiles, runtime databases, snapshots, or backups;
- personal names, chat identifiers, private infrastructure addresses, or machine-specific home paths unless they are clearly fictional examples;
- client data, private project rules, internal URLs, or proprietary project context;
- generated skills copied directly from a local agent without review and redaction.

Private agent state and migration snapshots belong in a separate access-controlled backup. Project-specific rules belong in the relevant private project repository. This repository is only the shared, portable agent layer.

## Contributing safely

All agent-generated changes should use a branch and pull request. Before pushing:

1. Review the complete diff, including generated and untracked files.
2. Replace real identities, paths, URLs, and account data with neutral placeholders.
3. Keep credentials outside the repository and reference only their environment-variable names.
4. Run the repository secret scan and resolve every finding before merge.
5. Confirm that a new or updated skill remains useful outside the task that produced it.

Do not suppress a scanner finding until the matched value has been inspected and confirmed to be a safe fixture. Prefer changing a realistic credential-like fixture over adding a broad allowlist.

## Reporting an exposure

Do not paste a live secret or sensitive data into a public issue, pull request, or discussion.

If a credential was exposed:

1. Revoke or rotate it immediately. Deleting the file or commit is not sufficient.
2. Check GitHub Actions logs, artifacts, forks, and downstream clones for further exposure.
3. Remove the value from the current branch and, when necessary, rewrite affected Git history.
4. Re-run secret scanning across the full history.
5. Open only a sanitized follow-up issue or pull request that contains no live value.

If no private contact channel is available, rotate the credential first and then open a public issue containing only a redacted description.

## Supported version

Security fixes apply to the current `main` branch. Historical revisions are retained for audit and should not be treated as supported releases.
