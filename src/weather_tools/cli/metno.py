"""Met.no API CLI commands."""

import logging
from typing import Annotated, Optional

import pandas as pd
import typer

from weather_tools.cli.date_utils import iso_date_option, parse_iso_date_strict
from weather_tools.merge_weather_data import (
    MergeValidationError,
    get_merge_summary,
    merge_historical_and_forecast,
)
from weather_tools.metno_api import MetNoAPI
from weather_tools.metno_models import MetNoAPIError, MetNoRateLimitError
from weather_tools.silo_api import SiloAPI, SiloAPIError
from weather_tools.silo_models import AustralianCoordinates

logger = logging.getLogger(__name__)

metno_app = typer.Typer(
    name="metno",
    help="Query met.no forecast API for Australian locations",
    no_args_is_help=True,
)


def add_silo_date_columns(df):
    """
    Add SILO-specific date columns (day, year) from date column.

    Args:
        df: DataFrame with 'date' column

    Returns:
        DataFrame with added 'day' and 'year' columns
    """
    import pandas as pd

    df = df.copy()

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df["day"] = df["date"].dt.dayofyear
        df["year"] = df["date"].dt.year

    return df


@metno_app.command()
def forecast(
    lat: Annotated[float, typer.Option(help="Latitude coordinate (-9 to -44 for Australia)")],
    lon: Annotated[float, typer.Option(help="Longitude coordinate (113 to 154 for Australia)")],
    days: Annotated[int, typer.Option(help="Number of forecast days (1-9)")] = 7,
    output: Annotated[Optional[str], typer.Option(help="Output CSV filename (optional)")] = None,
    format_silo: Annotated[bool, typer.Option(help="Convert to SILO column names")] = True,
    user_agent: Annotated[
        Optional[str], typer.Option(help="Custom User-Agent for met.no API")
    ] = None,
) -> None:
    """
    Get met.no weather forecast for an Australian location.

    Retrieves up to 9 days of forecast data from met.no's locationforecast API.
    Daily summaries are automatically aggregated from hourly forecasts.

    Example:
        weather-tools metno forecast --lat -27.5 --lon 153.0 --days 7 --output brisbane_forecast.csv
    """
    try:
        # Validate coordinates
        coords = AustralianCoordinates(latitude=lat, longitude=lon)

        # Validate days parameter
        if not 1 <= days <= 9:
            logger.error("[red]❌ Error: days must be between 1 and 9[/red]")
            raise typer.Exit(1)

        logger.info(
            f"[cyan]📡 Fetching met.no forecast for {coords.latitude}, {coords.longitude}...[/cyan]"
        )

        # Create API client
        api = MetNoAPI(user_agent=user_agent)

        # Get daily forecast
        daily_forecasts = api.get_daily_forecast(
            latitude=coords.latitude, longitude=coords.longitude, days=days
        )

        logger.info(f"[green]✓ Retrieved {len(daily_forecasts)} days of forecast data[/green]")

        # daily_forecasts is already a DataFrame
        forecast_df = daily_forecasts

        if format_silo:
            # Rename columns to SILO format
            from weather_tools.silo_variables import (
                convert_metno_to_silo_columns,
            )

            column_mapping = convert_metno_to_silo_columns(forecast_df, include_extra=False)
            forecast_df = forecast_df.rename(columns=column_mapping)
            forecast_df = add_silo_date_columns(forecast_df)

        # Save or display
        if output:
            forecast_df.to_csv(output, index=False)
            logger.info(f"[green]✓ Forecast saved to: {output}[/green]")
        else:
            logger.info("\n[bold]Met.no Forecast:[/bold]")
            logger.info(forecast_df.to_string(index=False))

    except ValueError as e:
        logger.error(f"[red]❌ Validation Error: {e}[/red]")
        raise typer.Exit(1)
    except MetNoRateLimitError as e:
        logger.error(f"[red]❌ Rate Limit Exceeded: {e}[/red]")
        logger.warning("[yellow]Please wait a few minutes before retrying[/yellow]")
        raise typer.Exit(1)
    except MetNoAPIError as e:
        logger.error(f"[red]❌ met.no API Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        logger.exception(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)


@metno_app.command()
def merge(
    lat: Annotated[float, typer.Option(help="Latitude coordinate (-9 to -44 for Australia)")],
    lon: Annotated[float, typer.Option(help="Longitude coordinate (113 to 154 for Australia)")],
    start_date: Annotated[
        str, typer.Option(help="Historical data start date (YYYY-MM-DD)", callback=iso_date_option)
    ],
    end_date: Annotated[
        str, typer.Option(help="Historical data end date (YYYY-MM-DD)", callback=iso_date_option)
    ],
    output: Annotated[str, typer.Option(help="Output CSV filename")],
    forecast_days: Annotated[int, typer.Option(help="Number of forecast days to append (1-9)")] = 7,
    api_key: Annotated[
        Optional[str], typer.Option(envvar="SILO_API_KEY", help="SILO API key (email address)")
    ] = None,
    fill_missing: Annotated[
        bool, typer.Option(help="Fill missing SILO variables with estimates")
    ] = False,
    enable_cache: Annotated[
        bool, typer.Option(help="Enable response caching for SILO API")
    ] = False,
    user_agent: Annotated[
        Optional[str], typer.Option(help="Custom User-Agent for met.no API")
    ] = None,
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level", help="Logging level for SILO client (e.g. INFO, DEBUG, WARNING)"
        ),
    ] = "INFO",
) -> None:
    """
    Merge SILO historical data with met.no forecast data.

    Combines historical observations from SILO DataDrill API with met.no forecast data
    for seamless downstream analysis.

    Example:
        weather-tools metno merge --lat -27.5 --lon 153.0 \\
            --start-date 2023-01-01 --end-date 2023-12-31 \\
            --forecast-days 7 --output combined_weather.csv
    """
    try:
        # Validate coordinates
        coords = AustralianCoordinates(latitude=lat, longitude=lon)

        # Validate forecast days
        if not 1 <= forecast_days <= 9:
            logger.error("[red]❌ Error: forecast_days must be between 1 and 9[/red]")
            raise typer.Exit(1)

        # Step 1: Get SILO historical data via DataDrill API
        logger.info(
            f"[cyan]📡 Querying SILO DataDrill API from {start_date} to {end_date}...[/cyan]"
        )

        # Convert dates from ISO YYYY-MM-DD to YYYYMMDD format for SILO API
        silo_start = parse_iso_date_strict(start_date).strftime("%Y%m%d")
        silo_end = parse_iso_date_strict(end_date).strftime("%Y%m%d")

        # Initialize SILO API client
        if api_key:
            silo_api = SiloAPI(api_key=api_key, enable_cache=enable_cache, log_level=log_level)
        else:
            silo_api = SiloAPI(enable_cache=enable_cache, log_level=log_level)

        # Query DataDrill API for common variables (rainfall, max_temp, min_temp, etc.)
        silo_df = silo_api.get_data_drill(
            latitude=coords.latitude,
            longitude=coords.longitude,
            start_date=silo_start,
            end_date=silo_end,
            variables=None,  # None = get default set of common variables
            format="csv",
        )

        logger.info(f"[green]✓ Retrieved {len(silo_df)} days of SILO historical data[/green]")

        # Step 2: Get met.no forecast
        logger.info(f"[cyan]📡 Fetching {forecast_days} days of met.no forecast...[/cyan]")

        api = MetNoAPI(user_agent=user_agent)
        daily_forecasts = api.get_daily_forecast(
            latitude=coords.latitude, longitude=coords.longitude, days=forecast_days
        )

        # daily_forecasts is already a DataFrame
        metno_df = daily_forecasts

        logger.info(f"[green]✓ Retrieved {len(metno_df)} days of forecast data[/green]")

        # Step 3: Merge datasets
        logger.info("[cyan]🔗 Merging historical and forecast data...[/cyan]")

        merged_df = merge_historical_and_forecast(silo_df, metno_df, overlap_strategy="prefer_silo")

        # Get merge summary
        summary = get_merge_summary(merged_df)

        logger.info("[green]✓ Merge complete![/green]")
        logger.info(f"  • Total records: {summary['total_records']}")
        logger.info(f"  • SILO records: {summary['silo_records']}")
        logger.info(f"  • met.no records: {summary['metno_records']}")
        logger.info(
            f"  • Date range: {summary['date_range']['start'].date()} to {summary['date_range']['end'].date()}"
        )
        logger.info(f"  • Transition date: {summary['transition_date'].date()}")

        # Save to CSV
        merged_df.to_csv(output, index=False)
        logger.info(f"[green]✓ Merged data saved to: {output}[/green]")

    except ValueError as e:
        logger.error(f"[red]❌ Validation Error: {e}[/red]")
        raise typer.Exit(1)
    except SiloAPIError as e:
        logger.error(f"[red]❌ SILO API Error: {e}[/red]")
        raise typer.Exit(1)
    except MergeValidationError as e:
        logger.error(f"[red]❌ Merge Error: {e}[/red]")
        raise typer.Exit(1)
    except MetNoAPIError as e:
        logger.error(f"[red]❌ met.no API Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        logger.exception(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)


@metno_app.command(name="info")
def metno_info() -> None:
    """
    Display information about the met.no API and variable mappings.

    Shows available variables, data coverage, and API details.
    """
    logger.info("\n[bold cyan]met.no locationforecast API Information[/bold cyan]\n")

    logger.info("[bold]API Details:[/bold]")
    logger.info("  • Provider: Norwegian Meteorological Institute (met.no)")
    logger.info("  • Endpoint: https://api.met.no/weatherapi/locationforecast/2.0/")
    logger.info("  • Coverage: Global (optimized for Norwegian locations)")
    logger.info("  • Forecast horizon: Up to 9 days")
    logger.info("  • Update frequency: Hourly")
    logger.info("  • Rate limit: Fair use policy (requires User-Agent)")

    logger.info("\n[bold]Available Variables (Daily Aggregates):[/bold]")
    logger.info("  • min_temperature (°C) → min_temp")
    logger.info("  • max_temperature (°C) → max_temp")
    logger.info("  • total_precipitation (mm) → daily_rain")
    logger.info("  • avg_pressure (hPa) → mslp")
    logger.info("  • avg_relative_humidity (%) → vp (converted)")
    logger.info("  • avg_wind_speed (m/s) → wind_speed")
    logger.info("  • max_wind_speed (m/s) → wind_speed_max")
    logger.info("  • avg_cloud_fraction (%) → cloud_fraction")
    logger.info("  • dominant_weather_symbol → weather_symbol")

    logger.info("\n[bold]SILO-Only Variables (Not Available from met.no):[/bold]")
    logger.info("  • evap_pan - Class A pan evaporation")
    logger.info("  • evap_syn - Synthetic evaporation")
    logger.info("  • radiation - Solar radiation (MJ/m²)")
    logger.info("  • vp_deficit - Vapor pressure deficit")
    logger.info("  • et_short_crop - FAO56 reference evapotranspiration")

    logger.info("\n[bold]Usage Examples:[/bold]")
    logger.info("  # Get 7-day forecast for Brisbane")
    logger.info("  weather-tools metno forecast --lat -27.5 --lon 153.0 --days 7")
    logger.info("")
    logger.info("  # Merge historical SILO with 7-day forecast")
    logger.info("  weather-tools metno merge --lat -27.5 --lon 153.0 \\")
    logger.info("      --start-date 2023-01-01 --end-date 2023-12-31 \\")
    logger.info("      --forecast-days 7 --output combined.csv")

    logger.info("\n[bold]Note:[/bold] The met.no API is best used for Australian locations")
    logger.info("near the coast. Inland locations may have less accurate forecasts.")
    logger.info("For optimal results, use with SILO historical data.\n")
