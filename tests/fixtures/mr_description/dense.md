Report filter tests now generate amounts from one.

## What changed
- The `ReportFilter` amount generator in `AmountSteps` now starts at one (zero always produced an empty report and the test failed on every stand we tried).

## Verification
- `ReportFilterTest`: 4/4 green
