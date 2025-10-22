# Met.no Data Models

The `metno_models` module defines the Pydantic models that underpin the met.no integration. They provide validation, serialization helpers, and consistent data structures for both API requests and responses.

## MetNoFormat

```python
from weather_tools.metno_models import MetNoFormat

MetNoFormat.COMPACT   # default 9-day forecast with core variables
MetNoFormat.COMPLETE  # extended payload with percentiles and extra fields
```

Use the enum when constructing `MetNoQuery` or when you need to select the endpoint manually.

## MetNoQuery

Represents a validated met.no request:

```python
from weather_tools.metno_models import MetNoQuery
from weather_tools.silo_models import AustralianCoordinates

query = MetNoQuery(
    coordinates=AustralianCoordinates(latitude=-33.86, longitude=151.21),
    format=MetNoFormat.COMPACT,
)

params = query.to_api_params()
# {'lat': -33.86, 'lon': 151.21}
```

### Key Fields

| Field        | Type                       | Description |
|--------------|----------------------------|-------------|
| `coordinates`| Any (typically `AustralianCoordinates`) | Validated latitude/longitude pair |
| `format`     | `MetNoFormat`              | Forecast format (defaults to `COMPACT`) |

`to_api_params()` converts the model to the `lat`, `lon`, and optional `altitude` parameters required by met.no.

## MetNoResponse

Wraps the GeoJSON payload returned by met.no and tracks metadata:

```python
from weather_tools.metno_models import MetNoResponse

response = MetNoResponse(raw_data=payload, format=MetNoFormat.COMPACT, coordinates=query.coordinates)

timestamps = response.get_timeseries()
meta = response.get_meta()
```

### Fields

| Field          | Type            | Description |
|----------------|-----------------|-------------|
| `raw_data`     | `Dict[str, Any]`| GeoJSON response |
| `format`       | `MetNoFormat`   | Format used for the request |
| `coordinates`  | Any             | Coordinates associated with the forecast |
| `generated_at` | `datetime`      | Timestamp when the forecast was retrieved (`UTC`) |

Utility methods:
- `get_timeseries()` extracts the list of hourly forecast entries.
- `get_meta()` returns the metadata embedded in the GeoJSON properties.

## ForecastTimestamp

Describes the data available for a single forecast time step. This model is mostly used internally when constructing daily summaries, but it can help with type hints if you build custom parsers.

Important fields include:
- `time` (`datetime`) — forecast timestamp (UTC).
- Instantaneous variables: `air_temperature`, `relative_humidity`, `wind_speed`, `cloud_area_fraction`, `air_pressure_at_sea_level`.
- Period values: `precipitation_amount`, `precipitation_period_hours`.
- `weather_symbol` — the symbol code supplied by met.no summaries.

## DailyWeatherSummary

Aggregates hourly data into a daily rollup compatible with SILO daily schemata:

```python
from weather_tools.metno_models import DailyWeatherSummary

summary = DailyWeatherSummary(
    date=date(2024, 10, 12),
    min_temperature=12.4,
    max_temperature=23.1,
    total_precipitation=5.8,
)
```

Fields closely align with the columns produced by `MetNoAPI.to_dataframe(aggregate_to_daily=True)`:

| Field                     | Description |
|---------------------------|-------------|
| `date`                    | Python `date` for the summary |
| `min_temperature` / `max_temperature` | Daily temperature extremes (°C) |
| `total_precipitation`     | Total rainfall (mm) |
| `avg_wind_speed` / `max_wind_speed`   | Wind statistics (m/s) |
| `avg_relative_humidity`   | Average humidity (%) |
| `avg_pressure`            | Sea level pressure (hPa) |
| `avg_cloud_fraction`      | Cloud cover (%) |
| `dominant_weather_symbol` | Most common or severe symbol code for the day |

Use `.model_dump()` to serialize the summaries for DataFrame construction or downstream storage.

## Error Hierarchy

The module also declares the exception hierarchy used by the API client:

- `MetNoAPIError` — base exception for request failures.
- `MetNoUserAgentError` — raised on HTTP 403 due to missing/invalid User-Agent.
- `MetNoRateLimitError` — raised on HTTP 429 when rate limits are exceeded.

Catch these to implement robust retry or messaging logic in your applications.

## Next Steps

- Read the [Met.no API Client](metno_api.md) guide for request patterns.
- Combine forecasts with historical data in [Merge Weather Data](merge_weather_data.md).
- Explore the [Forecast example notebook](notebooks/metno_forecast_example.ipynb) for an end-to-end workflow.
