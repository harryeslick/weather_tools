# Merge Weather Data

The `merge_weather_data` module bridges SILO historical observations and met.no forecasts. It ensures the datasets align, handles overlaps, and produces a combined time series ready for downstream analytics.

## Primary Workflow

```python
from weather_tools.merge_weather_data import merge_historical_and_forecast, get_merge_summary

merged = merge_historical_and_forecast(
    silo_data=silo_dataframe,
    metno_data=metno_dataframe,
    overlap_strategy="prefer_silo", # or 'prefer_metno' / 'error'
    return_cols="all",              # or 'silo_only' / 'metno_only'
    convert_rh_to_vp=True,          # convert met.no relative_humidity to vp
)

summary = get_merge_summary(merged)
```

### merge_historical_and_forecast(...)

Orchestrates the entire merge process:

1. Normalises date columns and sorts both inputs.
2. Validates continuity and critical columns (`min_temp`, `max_temp`, `daily_rain`).
3. Applies the requested overlap strategy:
   - `prefer_silo` (default): keep SILO records when dates collide.
   - `prefer_metno`: prefer met.no records for overlaps.
   - `error`: raise `MergeValidationError` if overlap exists.
4. Prepares met.no data (already in SILO canonical names from aggregation) via `prepare_metno_for_merge`.
5. Optionally converts met.no `relative_humidity` (%) to SILO `vp` (vapour pressure, hPa) using mean daily temperature.
6. Adds metadata columns (`data_source`, `is_forecast`, `forecast_generated_at`).
7. Filters columns based on `return_cols` setting.
8. Concatenates and returns a chronological DataFrame.

#### Important Parameters

- `overlap_strategy`: how to handle overlapping dates (default: `"prefer_silo"`).
- `return_cols`: which columns to include—`"all"` (default), `"silo_only"`, or `"metno_only"`.
- `convert_rh_to_vp`: whether to derive SILO `vp` from met.no `relative_humidity` (default: `True`).

## Validation Utilities

### validate_merge_compatibility(...)

Runs checks before merging:

- Ensures `date` columns exist in both DataFrames.
- Detects gaps or overlaps depending on `overlap_strategy`.
- Confirms both datasets have critical columns: `min_temp`, `max_temp`, `daily_rain`.
- Validates that data can be safely merged without irreconcilable conflicts.

Returns `(is_valid: bool, issues: List[str])`. The merge function raises `MergeValidationError` when validation fails.

### validate_date_continuity(...)

Lower-level helper that inspects two DataFrames for gaps or overlaps relative to a maximum allowed gap (default: 1 day).

Returns `(is_continuous: bool, error_message: Optional[str])`.

## Preparing met.no Data

### prepare_metno_for_merge(...)

```python
from weather_tools.merge_weather_data import prepare_metno_for_merge

prepared = prepare_metno_for_merge(metno_daily_df, silo_history_df, convert_rh_to_vp=True)
```

- Met.no daily summaries already use SILO canonical column names (aggregation is driven by the `VARIABLES` registry), so no rename step occurs.
- Optionally derives the SILO `vp` (vapour pressure, hPa) column from met.no `relative_humidity` (%) using mean daily temperature when `convert_rh_to_vp=True`.
- Drops met.no-only columns (wind, cloud, relative humidity, weather symbol) to keep output SILO-aligned.

The derived `vp` is a SILO variable and is retained in the output.

## Summaries and Diagnostics

### get_merge_summary(...)

Produces quick stats about the merged dataset:

- Total record count and per-source counts.
- Date ranges for SILO and met.no segments.
- Computed transition date.

Useful for sanity checks or logging after a merge.

## Exceptions

- `MergeValidationError` — raised when a merge cannot proceed safely (missing columns, incompatible dates, etc.).

Handle this exception to alert users or prompt data remediation.

## Typical Pipeline

1. Fetch SILO history using `SiloAPI.get_patched_point()` / `get_data_drill()` or local NetCDF extracts via `read_silo_xarray()`.
2. Retrieve met.no forecasts with `MetNoAPI.to_dataframe(daily=True)`.
3. Call `merge_historical_and_forecast()` and inspect `get_merge_summary()`.
4. Persist or visualise as required.

Check the [Forecast example notebook](notebooks/metno_forecast_example.ipynb) for a live demonstration of this workflow.
