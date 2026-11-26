Library search tests now cover titles with accents.

## What changed
- The `TitleNormalizer` used by `SearchSteps` now folds accents before comparing (unfolded titles never matched and the test failed in every environment we tried).

## Verification
- `SearchAccentTest`: 4/4 green
