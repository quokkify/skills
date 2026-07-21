# Skill improvement candidate

Keep a filled candidate in a private staging location or present it inline. Do not commit task evidence, raw transcripts, or private context to a public skill repository.

## Decision

- Candidate action: patch existing skill | add support file | create class-level umbrella | no change
- Target skill:
- Proposed support file, if any:
- Why this is reusable:
- Why memory or project context is not the better destination:

## Reusable trigger

Describe when a future agent should load or apply this knowledge.

## Generalized lesson

State the portable procedure, preference, pitfall, or verification rule without task-specific details.

## Evidence summary

Summarize what demonstrated the lesson. Do not paste raw transcripts, logs, secrets, identities, private paths, internal URLs, or customer/project context.

## Duplicate and overlap review

- Existing skills searched:
- Closest umbrella:
- Why patching or adding a support file is preferred:
- If a new umbrella is necessary, why existing class-level skills do not fit:

## Proposed public change

List the exact SKILL.md section and any `references/`, `templates/`, or `scripts/` files to add or modify.

## Privacy and portability audit

- [ ] No credentials, secret values, cookies, or private keys
- [ ] No personal memory, raw transcript, or runtime state
- [ ] No private repository, client, account, host, or infrastructure details
- [ ] Real values replaced with fictional placeholders
- [ ] Procedure works beyond the source task
- [ ] Runtime-specific behavior is isolated and accurately labeled

## Validation plan

- Structural/frontmatter checks:
- Linked-file checks:
- Runtime discovery checks:
- Documentation or installer checks:
- Full-history secret scan:
- Exact-head CI and review:

## Promotion gate

- [ ] Candidate presented to the user
- [ ] Explicit approval received
- [ ] Isolated branch or worktree created only after approval
- [ ] Focused PR opened
- [ ] Reviewer findings fixed or explicitly triaged
- [ ] Merge left to the human or repository policy
