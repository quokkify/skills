# Local Agent Bootstrap Prompt

Use this prompt with a local coding agent after replacing the placeholders:

```text
Configure an opt-in skill-improvement publishing harness for this machine.

Canonical public repository: <owner/repository>
Stable checkout: <absolute-path-to-main-checkout>
Queue worktree: <absolute-path-to-queue-worktree>
Lane: <unique-lowercase-device-lane>

Load and follow `agent-harness-design`, `skill-review`, and `skill-promotion-queue` before changing anything.

Required behavior:
1. Treat the repository owner's instruction as durable authorization to create or update one rolling DRAFT pull request on `automation/skill-improvements/<lane>` after a completed public-safe skill improvement.
2. Use an isolated persistent worktree for that lane. Never edit or push the stable main checkout.
3. Before each improvement, fetch main and the remote lane; fast-forward or merge without history rewriting. Stop on divergence or conflicts.
4. Search existing skills before creating a new one. Generalize the lesson and exclude memory, transcripts, identities, credentials, private URLs, infrastructure details, client context, machine paths, and private-project conventions.
5. Run the repository CI-equivalent and configured secret scan. Independent model review is intentionally deferred; deterministic validation and the public/private boundary are mandatory.
6. Commit with a Conventional Commit message, then run the bundled `publish_queue.py` helper with repository `<owner/repository>` and lane `<unique-lowercase-device-lane>`.
7. If the draft PR exists, update it. Otherwise create it. Never force-push, convert it from draft, request review, wait for review bots, merge it, or push to main.
8. Add a completion gate appropriate to this agent runtime. The gate may remind or block task completion when the queue has dirty or unpushed work, but it must never publish files by itself.
9. Verify the remote branch equals the validated local HEAD and report the draft PR URL.
10. A task-level instruction such as “local only”, “do not publish”, or “do not create a PR” overrides this policy.

Do not store GitHub tokens in the repository, Git remote URL, prompt, hook, commit, or logs. Use the machine's existing credential helper or a protected external environment file.
```

Use a different lane on every independently operating device. Do not point two machines at the same rolling branch.
