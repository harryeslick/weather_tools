# Exact SILO Station Search Design

## Goal

Make an exact station lookup the natural meaning of `weather-tools silo search
--station CODE`, remove the redundant `--details` option, and display the result
using the same table and CSV formatting as other station searches.

## Interface

- `silo search --station 73142` performs a SILO `format=id` request and returns
  one station row.
- `silo search --station 73142 --radius 10` performs the existing SILO
  `format=near` request and returns nearby station rows with distance.
- `--details` is removed without a compatibility alias or deprecation warning,
  following the repository policy for breaking changes.

## Data Flow

`SiloAPI._response_to_dataframe()` will treat `SiloFormat.ID` as station
metadata. `parse_station_data()` will account for the ID response's lack of a
header, normalize its documented fields to the same canonical column names as
NAME and NEAR responses, and omit the undocumented trailing `Climate` token.
The CLI will then use the existing DataFrame table and `to_csv()` output paths.

## Errors

The existing `PatchedPointQuery` validation remains responsible for validating
station codes and radii. Existing SILO request errors continue through
`SiloAPIError`. A bare `--station` becomes valid; calls with no search selector
continue to fail with an actionable message.

## Testing

- Unit-test ID response parsing into a single canonical station row.
- CLI-test that a bare station uses `SiloFormat.ID` and renders a table.
- CLI-test that `--details` is rejected as an unknown option.
- Keep the existing NEAR parser and search behavior covered by the full suite.

## Release

This is an intentional CLI breaking change. Increment the package from `0.2.0`
to `0.3.0`, add a dated changelog entry, and update all CLI documentation that
mentions `--details`.
