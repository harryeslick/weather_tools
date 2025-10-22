# Merge Weather Data

The `merge_weather_data` module bridges SILO historical observations and met.no forecasts. It ensures the datasets align, handles overlaps, and produces a combined time series ready for downstream analytics.

## Primary Workflow

```python
from weather_tools.merge_weather_data import merge_historical_and_forecast, get_merge_summary

merged = merge_historical_and_forecast(
    silo_data=silo_dataframe,
    metno_data=metno_dataframe,
    transition_date=None,           # auto (last SILO date + 1 day)
    validate=True,
    fill_missing=True,
    overlap_strategy="prefer_silo", # or 'prefer_metno' / 'error'
)

summary = get_merge_summary(merged)
```

### merge_historical_and_forecast(...)

Orchestrates the entire merge process:

1. Normalises date columns and sorts both inputs.
2. Optionally validates continuity and critical columns.
3. Applies the requested overlap strategy:
   - `prefer_silo` (default): keep SILO records when dates collide.
   - `prefer_metno`: prefer met.no records for overlaps.
   - `error`: raise `MergeValidationError` if overlap exists.
4. Converts met.no columns (e.g., `min_temperature`) into SILO-style columns (`min_temp`) via `prepare_metno_for_merge`.
5. Adds metadata columns (`data_source`, `is_forecast`, `forecast_generated_at`).
6. Concatenates, aligns columns, and returns a chronological DataFrame.

#### Important Flags

- `transition_date`: force the hand-over date if you do not want the automatic transition.
- `fill_missing`: backfill SILO-only variables in the forecast (radiation, vapour pressure, etc.) using `fill_missing_silo_variables`.

## Validation Utilities

### validate_merge_compatibility(...)

Runs checks before merging:

- Ensures `date` columns exist.
- Detects gaps or overlaps depending on `overlap_strategy`.
- Confirms SILO has `min_temp`, `max_temp`, `daily_rain`.
- Accepts met.no data in either native (`min_temperature`) or SILO (`min_temp`) naming schemes.

Returns `(is_valid: bool, issues: List[str])`. The merge function raises `MergeValidationError` when validation fails and `validate=True`.

### validate_date_continuity(...)

Lower-level helper that inspects two DataFrames for gaps or overlaps relative to a maximum allowed gap (default: 1 day).

## Preparing met.no Data

### prepare_metno_for_merge(...)

```python
from weather_tools.merge_weather_data import prepare_metno_for_merge

prepared = prepare_metno_for_merge(metno_daily_df, silo_history_df, fill_missing=True)
```

- Renames met.no columns to their SILO equivalents using `convert_metno_to_silo_columns`.
- Adds SILO-specific date columns (`day`, `year`) when missing.
- Optionally fills SILO-only variables by calling `fill_missing_silo_variables`.

### fill_missing_silo_variables(...)

Supports three strategies when met.no data lacks SILO-only columns:

| Strategy      | Behaviour |
|---------------|-----------|
| `"default"`   | Inserts conservative defaults (e.g., `radiation=20.0`, `evap_syn=5.0`). |
| `"last_known"`| Reuses the last available SILO value when possible. |
| `"median"`    | Fills using the median from the SILO history. |

This allows downstream systems expecting complete SILO schema to continue operating.

## Summaries and Diagnostics

### get_merge_summary(...)

Produces quick stats about the merged dataset:

- Total record count and per-source counts.
- Date ranges for SILO and met.no segments.
- Computed transition date.

Useful for sanity checks or logging after a merge.

## Exceptions

- `MergeValidationError` — raised when a merge cannot proceed safely.
- `DateGapError` — specialised for gaps between SILO and met.no periods.
- `ColumnMismatchError` — raised when required columns are missing.

Handle exceptions to alert users or prompt data remediation.

## Typical Pipeline

1. Fetch SILO history using `SiloAPI.get_gridded_data` or local NetCDF extracts.
2. Retrieve met.no forecasts with `MetNoAPI.to_dataframe(aggregate_to_daily=True)`.
3. Call `merge_historical_and_forecast` and inspect `get_merge_summary`.
4. Persist or visualise as required.

Check the [Forecast example notebook](notebooks/metno_forecast_example.ipynb) for a live demonstration of this workflow.
