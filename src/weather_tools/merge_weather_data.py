"""
Module for merging SILO historical data with met.no forecast data.

Provides functions to validate and combine historical observations with
weather forecasts for seamless downstream analysis.
"""

import datetime as dt
import logging
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd

from weather_tools.variable_register import VARIABLES
from weather_tools.weather_utils.dew_point import rh_to_vapor_pressure

logger = logging.getLogger(__name__)


# Custom exceptions
class MergeValidationError(Exception):
    """Raised when data cannot be safely merged."""


def merge_historical_and_forecast(
    silo_data: pd.DataFrame,
    metno_data: pd.DataFrame,
    overlap_strategy: Literal["prefer_silo", "prefer_metno", "error"] = "prefer_silo",
    return_cols: Literal["all", "silo_only", "metno_only"] = "all",
    convert_rh_to_vp: bool = True,
) -> pd.DataFrame:
    """
    Merge SILO historical data with met.no forecast data.

    Args:
        silo_data: Historical data from SILO (API or local files)
        metno_data: Forecast data from met.no (daily summaries)
        overlap_strategy: How to handle overlapping dates:
                         - "prefer_silo": Use SILO data for overlaps (default)
                         - "prefer_metno": Use met.no data for overlaps
                         - "error": Raise MergeValidationError if any overlap exists
        return_cols: Which columns to include in the result:
                    - "all": All columns from both datasets (default)
                    - "silo_only": Only columns present in the SILO DataFrame
                    - "metno_only": Only columns present in the met.no DataFrame
        convert_rh_to_vp: If True (default), explicitly convert met.no
                    relative humidity (%) into the SILO ``vp`` column
                    (vapour pressure, hPa) using mean daily temperature.

    Returns:
        Merged DataFrame with 'data_source' column indicating origin

    Raises:
        MergeValidationError: If data cannot be safely merged

    Example:
        >>> silo_df = get_silo_data(...)
        >>> metno_df = get_metno_forecast(...)
        >>> merged = merge_historical_and_forecast(silo_df, metno_df)
        >>> print(merged[merged['data_source'] == 'metno'])
    """
    # Make copies to avoid modifying originals
    silo_df = silo_data.copy()
    metno_df = metno_data.copy()

    drop_cols = [c for c in silo_df.columns if "source" in c]
    drop_cols += ["metadata"] if "metadata" in silo_df.columns else []

    silo_df = silo_df.drop(columns=drop_cols, errors="ignore")

    # Ensure date columns are datetime
    silo_df["date"] = pd.to_datetime(silo_df["date"])
    metno_df["date"] = pd.to_datetime(metno_df["date"])

    # Sort by date
    silo_df = silo_df.sort_values("date").reset_index(drop=True)
    metno_df = metno_df.sort_values("date").reset_index(drop=True)

    transition_date = silo_df["date"].max() + pd.Timedelta(days=1)
    logger.info(f"Auto-detected transition date: {transition_date}")

    # Validation checks
    is_valid, issues = validate_merge_compatibility(
        silo_df, metno_df, transition_date, overlap_strategy
    )
    if not is_valid:
        raise MergeValidationError(
            "Merge validation failed:\n" + "\n".join(f"  - {issue}" for issue in issues)
        )

    if overlap_strategy == "prefer_silo":
        # Remove overlapping dates from met.no data
        metno_df = metno_df[~metno_df["date"].isin(silo_df["date"])]
    elif overlap_strategy == "prefer_metno":
        # Remove overlapping dates from SILO data
        silo_df = silo_df[~silo_df["date"].isin(metno_df["date"])]
    elif overlap_strategy == "error":
        overlapping = silo_df["date"].isin(metno_df["date"])
        if overlapping.any():
            overlap_dates = silo_df.loc[overlapping, "date"].dt.date.tolist()
            raise MergeValidationError(
                f"overlap_strategy='error': {len(overlap_dates)} overlapping date(s) found "
                f"between SILO and met.no data: {overlap_dates}"
            )
    else:
        raise ValueError(
            f"Invalid overlap_strategy: {overlap_strategy!r}. "
            f"Must be 'prefer_silo', 'prefer_metno', or 'error'."
        )

    # Convert met.no columns to SILO format if needed
    metno_df = prepare_metno_for_merge(metno_df, silo_df, convert_rh_to_vp=convert_rh_to_vp)

    # Add data source metadata
    silo_df["data_source"] = "silo"
    silo_df["is_forecast"] = False

    metno_df["data_source"] = "metno"
    metno_df["is_forecast"] = True
    metno_df["forecast_generated_at"] = dt.datetime.now(dt.UTC)

    # # Align columns (ensure same columns in both DataFrames)
    # all_columns = list(set(silo_df.columns) | set(metno_df.columns))

    # # Add missing columns with NaN
    # for col in all_columns:
    #     if col not in silo_df.columns:
    #         silo_df[col] = np.nan
    #     if col not in metno_df.columns:
    #         metno_df[col] = np.nan

    # # Reorder columns to match
    # silo_df = silo_df[all_columns]
    # metno_df = metno_df[all_columns]

    # Concatenate
    merged_df = pd.concat([silo_df, metno_df], ignore_index=True)

    # Sort by date
    merged_df = merged_df.sort_values("date").reset_index(drop=True)

    logger.info(
        f"Merged {len(silo_df)} SILO records with {len(metno_df)} met.no records. Total: {len(merged_df)} records"
    )

    if return_cols == "silo_only":
        merged_df = merged_df[[col for col in silo_df.columns if col in merged_df.columns]]
    elif return_cols == "metno_only":
        merged_df = merged_df[[col for col in metno_df.columns if col in merged_df.columns]]
    elif return_cols == "all":
        pass
    else:
        raise ValueError(
            f"Invalid return_cols value: {return_cols}. Must be 'all', 'silo_only', or 'metno_only'."
        )
    return merged_df


def validate_merge_compatibility(
    silo_data: pd.DataFrame,
    metno_data: pd.DataFrame,
    transition_date: pd.Timestamp,
    overlap_strategy: str,
) -> Tuple[bool, List[str]]:
    """
    Validate that SILO and met.no data can be safely merged.

    Args:
        silo_data: SILO historical data
        metno_data: met.no forecast data
        transition_date: Date to transition from SILO to met.no
        overlap_strategy: How to handle overlaps

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []

    # Check for required columns
    if "date" not in silo_data.columns:
        issues.append("SILO data missing 'date' column")
    if "date" not in metno_data.columns:
        issues.append("met.no data missing 'date' column")

    if issues:
        return False, issues

    # Check date continuity - always check for gaps and overlaps
    silo_max_date = silo_data["date"].max()
    metno_min_date = metno_data["date"].min()

    gap_days = (metno_min_date - silo_max_date).days - 1

    if gap_days > 1:
        # There's a gap between datasets
        issues.append(
            f"Date gap detected: SILO ends {silo_max_date.date()}, "
            f"met.no starts {metno_min_date.date()}. Gap: {gap_days} days"
        )
    elif gap_days < 0:
        # There's an overlap between datasets
        overlap_days = abs(gap_days) + 1
        # Only report as issue if overlap_strategy is not set to handle it
        if overlap_strategy not in ["prefer_silo", "prefer_metno", "error"]:
            issues.append(
                f"Date overlap detected: {overlap_days} days overlap. "
                f"Set overlap_strategy to 'prefer_silo', 'prefer_metno', or 'error'"
            )

    # Check for critical columns in both datasets. Both SILO and met.no daily
    # frames use canonical SILO names, so the same set applies to each.
    critical_cols = ["min_temp", "max_temp", "daily_rain"]

    missing_silo = [col for col in critical_cols if col not in silo_data.columns]
    if missing_silo:
        issues.append(f"SILO data missing critical columns: {missing_silo}")

    missing_metno = [col for col in critical_cols if col not in metno_data.columns]
    if missing_metno:
        issues.append(f"met.no data missing critical columns: {missing_metno}")

    return len(issues) == 0, issues


def prepare_metno_for_merge(
    metno_df: pd.DataFrame,
    silo_df: pd.DataFrame,
    convert_rh_to_vp: bool = True,
) -> pd.DataFrame:
    """
    Prepare met.no daily data for merging with SILO data.

    met.no daily summaries already use canonical SILO column names (the
    aggregation in :meth:`MetNoAPI._aggregate_daily` is driven by the
    ``VARIABLES`` registry), so no column renaming happens here.

    Two SILO-alignment steps remain:

    1. Derive the SILO ``vp`` column. The SILO ``vp`` column holds vapour
       pressure (hPa), but met.no only reports relative humidity (%). When
       ``convert_rh_to_vp`` is True we compute true vapour pressure from the
       met.no ``relative_humidity`` column and the daily mean temperature.
    2. Drop met.no-only columns (wind, cloud, relative humidity, weather
       symbol) so the merged output stays SILO-aligned. The derived ``vp`` is a
       SILO variable and is retained.

    Args:
        metno_df: met.no daily forecast DataFrame (canonical column names)
        silo_df: SILO DataFrame (for column reference)
        convert_rh_to_vp: If True (default), convert met.no ``relative_humidity``
            (%) into the SILO ``vp`` column (vapour pressure, hPa) using mean
            daily temperature. If False, no ``vp`` is derived from humidity.

    Returns:
        Prepared DataFrame with SILO-aligned columns
    """
    metno_df = metno_df.copy()

    # Derive vapour pressure (vp) from relative humidity and mean daily temp.
    if (
        convert_rh_to_vp
        and "relative_humidity" in metno_df.columns
        and "min_temp" in metno_df.columns
        and "vp" in silo_df.columns
    ):
        logger.warning(
            "Converting met.no relative_humidity (%) -> vp (vapour pressure, hPa) "
            "using mean daily temperature; the SILO 'vp' column is vapour pressure, "
            "not relative humidity."
        )
        max_temp = metno_df["max_temp"] if "max_temp" in metno_df.columns else metno_df["min_temp"]
        mean_temp = (metno_df["min_temp"] + max_temp) / 2
        metno_df["vp"] = [
            rh_to_vapor_pressure(rh, temp) if pd.notna(rh) else np.nan
            for rh, temp in zip(metno_df["relative_humidity"], mean_temp)
        ]

    # Drop met.no-only columns to keep merged output SILO-aligned (vp, derived
    # above, is a SILO variable and is not in this list).
    # metno_only_cols = [c for c in VARIABLES.metno_only_variables() if c in metno_df.columns]
    # metno_df = metno_df.drop(columns=metno_only_cols)

    return metno_df


def validate_date_continuity(
    df1: pd.DataFrame, df2: pd.DataFrame, max_gap_days: int = 1
) -> Tuple[bool, Optional[str]]:
    """
    Check for date gaps between two DataFrames.

    Args:
        df1: First DataFrame (should end before df2)
        df2: Second DataFrame (should start after df1)
        max_gap_days: Maximum allowed gap in days (default: 1)

    Returns:
        Tuple of (is_continuous, error_message)
    """
    if "date" not in df1.columns or "date" not in df2.columns:
        return False, "Missing 'date' column in one or both DataFrames"

    max_date1 = pd.to_datetime(df1["date"].max())
    min_date2 = pd.to_datetime(df2["date"].min())

    gap_days = (min_date2 - max_date1).days - 1

    if gap_days > max_gap_days:
        return False, (
            f"Gap of {gap_days} days between datasets. First ends {max_date1.date()}, second starts {min_date2.date()}"
        )
    elif gap_days < 0:
        overlap_days = abs(gap_days) + 1
        return False, (
            f"Overlap of {overlap_days} days between datasets. Use overlap_strategy parameter to resolve"
        )

    return True, None


def get_merge_summary(merged_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Get summary statistics about merged data.

    Args:
        merged_df: Merged DataFrame

    Returns:
        Dictionary with summary statistics
    """
    if "data_source" not in merged_df.columns:
        return {"error": "No data_source column found"}

    silo_records = (merged_df["data_source"] == "silo").sum()
    metno_records = (merged_df["data_source"] == "metno").sum()

    silo_dates = merged_df[merged_df["data_source"] == "silo"]["date"]
    metno_dates = merged_df[merged_df["data_source"] == "metno"]["date"]

    summary = {
        "total_records": len(merged_df),
        "silo_records": silo_records,
        "metno_records": metno_records,
        "date_range": {
            "start": merged_df["date"].min(),
            "end": merged_df["date"].max(),
            "days": (merged_df["date"].max() - merged_df["date"].min()).days + 1,
        },
        "silo_period": {
            "start": silo_dates.min() if len(silo_dates) > 0 else None,
            "end": silo_dates.max() if len(silo_dates) > 0 else None,
        },
        "metno_period": {
            "start": metno_dates.min() if len(metno_dates) > 0 else None,
            "end": metno_dates.max() if len(metno_dates) > 0 else None,
        },
        "transition_date": metno_dates.min() if len(metno_dates) > 0 else None,
    }

    return summary
