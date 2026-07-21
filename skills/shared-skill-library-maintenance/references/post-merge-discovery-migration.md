# Post-Merge Discovery Migration

Use this after a shared-skill layout PR changes the canonical discovery root.

## Merge and Checkout

1. Merge only the reviewed exact head; read back the merged state and merge commit.
2. For squash merges, prove the reviewed-head tree and merge-commit tree are identical before deleting the feature worktree or branch.
3. Update the stable checkout through its trusted safe-sync path, then run repository validation on merged `main`.
4. Read back post-merge CI for the merge commit; do not rely only on pre-merge PR checks.

## Consumer Configuration

1. Move each consumer to the canonical skills directory only after the merged checkout contains it.
2. Treat configuration shape as part of correctness. A JSON-looking command-line value can still be persisted as a YAML string rather than a list.
3. After changing a sequence-valued setting such as an external-directory list:
   - query the resolved value through the product CLI;
   - parse the underlying config and assert that the value is a native list/sequence;
   - if a scalar setter preserves strings, use the product's supported config editor path and an atomic edit instead of leaving a string that merely looks like JSON.
4. Verify discovery from a fresh CLI process or new agent session. A long-lived process may cache configuration or skill indexes.
5. Confirm the expected skill names, not just a nonzero count, and check duplicate precedence when local and external skills can share a name.

## Cleanup

Delete temporary worktrees and branches only after all of these are true:

- PR state is merged;
- reviewed and merged trees are equivalent;
- stable `main` matches `origin/main` and is clean;
- merged validation passes;
- consumer discovery succeeds from the new canonical root.

Do not restart unrelated services merely to prove discovery when a fresh CLI process or new session is sufficient.
