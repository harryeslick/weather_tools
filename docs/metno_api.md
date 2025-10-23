# Met.no API Client

The `metno_api` module provides a typed Python client for the [met.no locationforecast v2.0 API](https://api.met.no/weatherapi/locationforecast/2.0/documentation), making it easy to fetch short-range weather forecasts for any global coordinate. It integrates tightly with the rest of `weather_tools`, returning Pydantic models and ready-to-use pandas DataFrames.

## Highlights

- ✅ **Pydantic-powered queries** via `MetNoQuery` for validated coordinates and formats.
- ✅ **Automatic retries, caching, and backoff** to keep requests resilient and efficient.
- ✅ **Convenience helpers** to aggregate hourly forecasts into daily summaries.
- ✅ **DataFrame conversion** for both hourly and daily views.
- ✅ **Seamless hand-off** to `merge_weather_data.merge_historical_and_forecast` for blending with SILO archives.

## Requirements

- met.no requires a descriptive `User-Agent` header containing a contact address. The client generates a sensible default (`weather-tools/<version> (Python <major>.<minor>)`), but you should provide your own identifier in production.
- Forecast requests do not require authentication, but met.no enforces rate limits—respect their usage policy and cache responses where possible.

## Quick Start

```python
from weather_tools.metno_api import MetNoAPI
from weather_tools.metno_models import MetNoFormat, MetNoQuery
from weather_tools.silo_models import AustralianCoordinates

# Configure the client (always include your contact details!)
api = MetNoAPI(user_agent="my-app/1.0 (contact: you@example.com)")

# Build a query for a location near Sydney Airport
query = MetNoQuery(
    coordinates=AustralianCoordinates(latitude=-33.94, longitude=151.18),
    format=MetNoFormat.COMPACT,
)

# Execute and inspect the response metadata
response = api.query_forecast(query)
print(response.get_meta())
```

## Aggregating to Daily Data

The API returns hourly forecasts in GeoJSON format. Use `MetNoAPI.to_dataframe` to convert the payload into either daily summaries or the raw hourly table:

```python
daily_df = api.to_dataframe(response, aggregate_to_daily=True)
hourly_df = api.to_dataframe(response, aggregate_to_daily=False)
```

- Daily data mirrors the `DailyWeatherSummary` model, providing min/max temperature, total precipitation, wind statistics, humidity, pressure, cloud cover, and the dominant weather symbol.
- Hourly data preserves the original timestamps alongside instantaneous variables and precipitation totals for the next 1/6/12 hours.

### Convenience Helper: `get_daily_forecast`

For common use cases you can skip manual query construction:

```python
daily = api.get_daily_forecast(latitude=-33.94, longitude=151.18, days=7)
```

This method returns a list of `DailyWeatherSummary` models and automatically truncates the forecast horizon (met.no serves up to 9 days).

## Configuration Options

Instantiate `MetNoAPI` with custom behaviour when needed:

```python
api = MetNoAPI(
    user_agent="my-app/1.0 (contact: you@example.com)",
    timeout=45,
    max_retries=4,
    retry_delay=1.5,
    enable_cache=True,
    cache_expiry_hours=2,
    log_level="DEBUG",
)
```

| Parameter            | Type    | Default | Description |
|----------------------|---------|---------|-------------|
| `user_agent`         | str     | auto    | Identifies your application to met.no |
| `timeout`            | int     | 30      | HTTP timeout in seconds |
| `max_retries`        | int     | 3       | Attempts for transient failures |
| `retry_delay`        | float   | 1.0     | Base delay for exponential backoff |
| `enable_cache`       | bool    | True    | In-memory response cache toggle |
| `cache_expiry_hours` | int     | 1       | Lifetime for cached responses |
| `log_level`          | str/int | INFO    | Logging level for diagnostics |

Use `clear_cache()` and `get_cache_size()` to manage cached responses explicitly.

## Error Handling

The client surfaces clear exceptions:

- `MetNoUserAgentError` — missing/invalid User-Agent (met.no returns HTTP 403).
- `MetNoRateLimitError` — too many requests (HTTP 429).
- `MetNoAPIError` — other HTTP failures or JSON parsing issues.

Wrap network calls accordingly:

```python
try:
    response = api.query_forecast(query)
except MetNoRateLimitError:
    logger.warning("Slow down—met.no rate limit hit")
except MetNoUserAgentError as e:
    raise RuntimeError("Update your User-Agent") from e
```

## Integration with SILO Data

Daily summaries pair naturally with SILO history:

```python
from weather_tools.merge_weather_data import merge_historical_and_forecast

merged = merge_historical_and_forecast(
    silo_data=silo_history_dataframe,
    metno_data=daily_df,
    fill_missing=True,
    overlap_strategy="prefer_silo",
)
```

See [Merge Weather Data](merge_weather_data.md) for a deeper dive into the blending workflow.

## Additional Resources

- [Met.no API documentation](https://api.met.no/weatherapi/locationforecast/2.0/documentation)
- [Met.no Models](metno_models.md) — Pydantic types used by the client.
- [Forecast example notebook](notebooks/metno_forecast_example.ipynb) — end-to-end usage with SILO integration.
