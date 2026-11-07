# npm and TypeScript

## Where to look in the update

- Package release notes, CHANGELOG, and migration guides between the two versions: "deprecated", "removed", "renamed", "now built in", "default".
- The tag-to-tag diff of the package's type definitions (`*.d.ts`, `@deprecated` JSDoc tags with a replacement) and exported entry points (`exports` in `package.json`).
- For TypeScript itself: release notes for deprecated `tsconfig` options and new compiler options.

## Consumer files to grep

- `package.json` (scripts, `engines`, config keys), lock files only for confirmation, `tsconfig*.json`, tool configs (`.eslintrc*`, `eslint.config.*`, `vite.config.*`, `jest.config.*`, `vitest.config.*`, and similar).
- Source under `src/**`, `lib/**`, `test/**` for imports and calls of the deprecated symbols.
- Local helper modules or polyfills that the new version, or the runtime it now requires, replaces.

## Local warning command

- `npx tsc --noEmit` (or the consumer's typecheck script): flags removed types; editors and `@typescript-eslint` deprecation rules flag `@deprecated` usages.
- The consumer's lint script; deprecated config keys are often reported at startup.
- `npm` install warnings for deprecated packages, when the install is part of the checks.

## Typical adoptable patterns

- A deprecated function or option with a documented replacement in the release notes or the `@deprecated` tag.
- A local helper duplicating a function the package now exports, when the notes announce it.
- A deprecated config key renamed in the tool's config file.
- A deprecated `tsconfig` option with a documented replacement.
- A polyfill or shim kept only for a version the package no longer supports.

## Typical false positives

- Changes in `devDependencies` used only through a wrapper the consumer does not configure.
- Adopting a new major's optional features that do not replace existing code.
- Lock-file churn: never a finding.
- Raising `engines` or the runtime version: a support-policy change, not an adoption.
