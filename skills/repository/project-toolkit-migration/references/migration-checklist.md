# Migration checklist

Use the actual selected template revision to resolve defaults, version requirements and managed file ownership. This checklist supplements its executable doctor.

## Before mutation

- Confirm consumer Git root and starting commit; distinguish unmanaged adoption, managed update and a repository belonging to another template.
- Read `.copier-answers.yml` with a safe YAML parser. Confirm `_src_path`, `_commit`, toolkit workflow reference and proposed release. Never fabricate a missing historical `_commit`.
- Check the template's `_min_copier_version` against the executable actually used. Documentation can lag the template.
- Confirm every component's type, path, stable job ID and display name against actual source, build manifests and existing CI. Empty components can intentionally mean external CI; verify that contract rather than adding a default component.
- Inventory `.github/workflows`, required check names, permissions, release automation and existing Renovate settings. Preserve job identities relied on by rulesets.
- Review target `_skip_if_exists`, excludes, migrations and tasks. A preserved file may still require a deliberate manual migration; never assume a skipped file now contains new template policy.
- Inspect source ownership before adopting into a repository that already has CI. List collisions and preserve project-specific commands and trigger/path filters.

## Rehearsal and evidence

- Use an isolated clean checkout of the recorded consumer commit. Bring intended local changes into a separate reviewed commit or explicit patch only with user authorization.
- Use an exact released ref for the consumer; HEAD previews are development evidence only.
- Run Copier with reviewed answers; inspect all output, conflict markers, `.rej` files and changed ownership boundaries. Check the Git unmerged index even if textual markers were removed. Copier can exit zero while a merge remains unresolved; rerun the doctor after generation and conflict resolution.
- Run the relevant project validators and workflow checks. Compare resulting required check names with the repository's protection rules.
- Apply again at the same target ref and verify no unexplained tracked changes.
- Validate hosted behavior where it matters: repository visibility and CodeQL availability, workflow permissions, app/token access, reusable-workflow access, release manifests and tags, Allure artifact/report contracts and Pages settings if enabled. Unavailable remote evidence remains unknown.
- Capture command exit codes and the exact commits checked, not just a paraphrase of success.

## Choose the repair owner

| Evidence | Repair owner |
| --- | --- |
| Component points at absent source, wrong project command, missing local prerequisite | Consumer project or environment |
| Valid supported answers generate a broken workflow in a minimal fixture | Template plus regression fixture |
| Update/rehearsal helper loses ownership, corrupts answers or reports false readiness | Migration tooling plus regression fixture |
| Needed check or recovery step missing from the agent procedure | Skill/checklist |
| Hosted check cannot be observed | Collect remote evidence; do not invent a defect |

If ownership is uncertain, record the competing explanations and one check that distinguishes them. Do not classify every failed migration as a template bug.
