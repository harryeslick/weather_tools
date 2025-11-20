"""
Pydantic models for SILO API requests and responses.

This module provides type-safe, validated data models for interacting with the
SILO (Scientific Information for Land Owners) API.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SiloDataset(str, Enum):
    """SILO dataset types."""

    PATCHED_POINT = "PatchedPoint"
    DATA_DRILL = "DataDrill"


class SiloFormat(str, Enum):
    """
    SILO output formats.

    - CSV: Comma-separated values with customizable variables
    - JSON: JSON format with customizable variables
    - APSIM: APSIM agricultural model format
    - ALLDATA: All available variables in tabular format
    - STANDARD: Common variables subset in tabular format
    - NEAR: Find nearby stations (PatchedPoint only)
    - NAME: Search stations by name fragment (PatchedPoint only)
    - ID: Get station details by ID (PatchedPoint only)
    """

    CSV = "csv"
    JSON = "json"
    APSIM = "apsim"
    ALLDATA = "alldata"
    STANDARD = "standard"
    NEAR = "near"
    NAME = "name"
    ID = "id"


class ClimateVariable(str, Enum):
    """
    SILO climate variable codes.

    Primary variables (observed):
    - R: Daily rainfall
    - X: Maximum temperature
    - N: Minimum temperature
    - V: Vapour pressure
    - E: Class A pan evaporation

    Derived variables:
    - J: Solar radiation
    - F: FAO56 short crop ET
    - T: ASCE tall crop ET
    - A: Morton's actual ET
    - P: Morton's potential ET
    - W: Morton's wet-environment ET
    - L: Morton's shallow lake evaporation
    - S: Synthetic evaporation estimate
    - C: Combined evaporation
    - H: Relative humidity at Tmax
    - G: Relative humidity at Tmin
    - D: Vapour pressure deficit
    - M: Mean sea level pressure
    """

    RAINFALL = "R"
    MAX_TEMP = "X"
    MIN_TEMP = "N"
    VAPOUR_PRESSURE = "V"
    EVAPORATION = "E"
    SOLAR_RADIATION = "J"
    FAO56_ET = "F"
    ASCE_TALL_ET = "T"
    MORTON_ACTUAL_ET = "A"
    MORTON_POTENTIAL_ET = "P"
    MORTON_WET_ET = "W"
    MORTON_LAKE_ET = "L"
    SYNTHETIC_EVAP = "S"
    COMBINED_EVAP = "C"
    RH_TMAX = "H"
    RH_TMIN = "G"
    VP_DEFICIT = "D"
    MSLP = "M"


class SiloDateRange(BaseModel):
    """
    Date range for SILO queries.

    Dates must be in YYYYMMDD format and within SILO's data availability period (1889-present).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    start_date: str = Field(
        ..., pattern=r"^\d{8}$", description="Start date in YYYYMMDD format (e.g., '20230101')"
    )
    end_date: str = Field(
        ..., pattern=r"^\d{8}$", description="End date in YYYYMMDD format (e.g., '20230131')"
    )

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        """Validate date format and range."""
        try:
            dt = datetime.strptime(v, "%Y%m%d")
            if not (1889 <= dt.year <= 2100):
                raise ValueError(f"Date year must be between 1889 and 2100, got {dt.year}")
            if dt.month < 1 or dt.month > 12:
                raise ValueError(f"Date month must be between 01 and 12, got {dt.month}")
            if dt.day < 1 or dt.day > 31:
                raise ValueError(f"Date day must be between 01 and 31, got {dt.day}")
            return v
        except ValueError as e:
            if "does not match format" in str(e):
                raise ValueError(f"Date must be in YYYYMMDD format, got: {v}")
            raise

    @model_validator(mode="after")
    def validate_date_order(self) -> "SiloDateRange":
        """Ensure start_date is before or equal to end_date."""
        if self.start_date > self.end_date:
            raise ValueError(
                f"start_date ({self.start_date}) must be before or equal to end_date ({self.end_date})"
            )
        return self


class AustralianCoordinates(BaseModel):
    """
    Australian coordinates in GDA94 (decimal degrees).

    Latitude: -44°S to -10°S (negative for southern hemisphere)
    Longitude: 113°E to 154°E (positive for eastern hemisphere)
    """

    latitude: float = Field(
        ..., ge=-44.0, le=-10.0, description="Latitude in decimal degrees (South is negative)"
    )
    longitude: float = Field(
        ..., ge=113.0, le=154.0, description="Longitude in decimal degrees (East is positive)"
    )


class BaseSiloQuery(BaseModel):
    """Base query parameters for SILO API."""

    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)

    dataset: SiloDataset
    format: SiloFormat = Field(default=SiloFormat.CSV)
    values: Optional[List[ClimateVariable]] = Field(
        default=None, description="Climate variables to retrieve (for csv/json formats)"
    )


class PatchedPointQuery(BaseSiloQuery):
    """
    Query for PatchedPoint dataset (station-based data).

    PatchedPoint provides observational data from BOM weather stations with
    gap-filled values interpolated from nearby stations.

    Examples:
        # Get rainfall and temperature for a station
        >>> query = PatchedPointQuery(
        ...     station_code="30043",
        ...     date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
        ...     format=SiloFormat.CSV,
        ...     values=[ClimateVariable.RAINFALL, ClimateVariable.MAX_TEMP]
        ... )

        # Search for stations by name (name_fragment is optional)
        >>> query = PatchedPointQuery(
        ...     format=SiloFormat.NAME,
        ...     name_fragment="Brisbane"
        ... )

        # List all stations (no name_fragment)
        >>> query = PatchedPointQuery(format=SiloFormat.NAME)

        # Find nearby stations
        >>> query = PatchedPointQuery(
        ...     format=SiloFormat.NEAR,
        ...     station_code="30043",
        ...     radius=50.0
        ... )
    """

    dataset: SiloDataset = Field(default=SiloDataset.PATCHED_POINT, frozen=True)
    station_code: Optional[str] = Field(
        default=None,
        pattern=r"^\d{4,6}$",
        description="BOM station number (e.g., '30043' for Brisbane Aero)",
    )
    date_range: Optional[SiloDateRange] = Field(
        default=None, description="Date range for data queries"
    )
    radius: Optional[float] = Field(
        default=None, ge=1.0, le=5000.0, description="Search radius in km (for 'near' format)"
    )
    name_fragment: Optional[str] = Field(
        default=None, min_length=2, description="Station name search fragment (for 'name' format)"
    )

    @model_validator(mode="after")
    def validate_format_requirements(self) -> "PatchedPointQuery":
        """Validate required fields for each format."""
        format_val = self.format

        if format_val == SiloFormat.NAME:
            # NAME format: name_fragment is optional, no other requirements
            pass
        elif format_val == SiloFormat.ID:
            if not self.station_code:
                raise ValueError("station_code is required for 'id' format")
        elif format_val == SiloFormat.NEAR:
            if not self.station_code:
                raise ValueError("station_code is required for 'near' format")
        # else:
        #     # Data formats (csv, json, apsim, alldata, standard)
        #     if not self.station_code:
        #         raise ValueError(f"station_code is required for '{format_val}' format")
        #     if not self.date_range:
        #         raise ValueError(f"date_range is required for '{format_val}' format")

        return self

    def to_api_params(self, api_key: str) -> Dict[str, Any]:
        """
        Convert query to SILO API parameters.

        Args:
            api_key: Email address for SILO API identification

        Returns:
            Dictionary of query parameters for the API request
        """
        params: Dict[str, Any] = {"format": self.format}

        if self.format == "name":
            if self.name_fragment:
                params["nameFrag"] = self.name_fragment
            return params

        if self.format == "id":
            params["station"] = self.station_code
            return params

        if self.format == "near":
            params["station"] = self.station_code
            if self.radius:
                params["radius"] = self.radius
            return params

        # Data formats (validator ensures date_range is not None for these formats)
        assert self.date_range is not None, "date_range must be set for data formats"
        params.update(
            {
                "station": self.station_code,
                "start": self.date_range.start_date,
                "finish": self.date_range.end_date,
                "username": api_key,
            }
        )

        # Add password for APSIM format (required by SILO API)
        if self.format == "apsim":
            params["password"] = "apirequest"

        # Add variable selection for customizable formats
        if self.format in ["csv", "json"] and self.values:
            params["comment"] = "".join(self.values)

        return params


class DataDrillQuery(BaseSiloQuery):
    """
    Query for DataDrill dataset (gridded data).

    DataDrill provides gridded data at 0.05° × 0.05° resolution (~5km grid spacing)
    interpolated across a regular grid covering Australia.

    Examples:
        # Get rainfall and temperature for a location
        >>> query = DataDrillQuery(
        ...     coordinates=AustralianCoordinates(latitude=-27.5, longitude=151.0),
        ...     date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
        ...     format=SiloFormat.CSV,
        ...     values=[ClimateVariable.RAINFALL, ClimateVariable.MAX_TEMP]
        ... )
    """

    dataset: SiloDataset = Field(default=SiloDataset.DATA_DRILL, frozen=True)
    coordinates: AustralianCoordinates = Field(..., description="Australian coordinates (GDA94)")
    date_range: SiloDateRange = Field(..., description="Date range for data query")

    @model_validator(mode="after")
    def validate_format_compatibility(self) -> "DataDrillQuery":
        """Validate format is compatible with DataDrill."""
        if self.format in ["near", "name", "id"]:
            raise ValueError(
                f"DataDrill does not support '{self.format}' format. Use PatchedPoint for station search operations."
            )
        return self

    def to_api_params(self, api_key: str) -> Dict[str, Any]:
        """
        Convert query to SILO API parameters.

        Args:
            api_key: Email address for SILO API identification

        Returns:
            Dictionary of query parameters for the API request
        """
        params: Dict[str, Any] = {
            "lat": self.coordinates.latitude,
            "lon": self.coordinates.longitude,
            "start": self.date_range.start_date,
            "finish": self.date_range.end_date,
            "format": self.format,
            "username": api_key,
            "password": "apirequest",  # Always required for DataDrill
        }

        # Add variable selection for customizable formats
        if self.format in ["csv", "json"] and self.values:
            params["comment"] = "".join(self.values)

        return params


class SiloResponse(BaseModel):
    """
    Structured SILO API response.

    Contains the raw response data along with metadata about the query.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    raw_data: Union[str, Dict[str, Any]] = Field(
        ..., description="Raw response data (CSV string or JSON dict)"
    )
    format: SiloFormat = Field(..., description="Response format")
    dataset: SiloDataset = Field(..., description="Dataset type")

    def to_csv(self) -> str:
        """
        Get CSV representation of response.

        Returns:
            CSV string

        Raises:
            ValueError: If response is not in CSV format
        """
        if isinstance(self.raw_data, str):
            return self.raw_data
        raise ValueError(f"Cannot convert {self.format} response to CSV. Response is JSON format.")

    def to_dict(self) -> Dict[str, Any]:
        """
        Get dict representation of response.

        Returns:
            Response as dictionary

        Raises:
            ValueError: If response is not in JSON format
        """
        if isinstance(self.raw_data, dict):
            return self.raw_data
        raise ValueError(f"Cannot convert {self.format} response to dict. Response is text format.")


class StationInfo(BaseModel):
    """
    Station information from SILO.

    Returned by 'id' format queries.
    """

    model_config = ConfigDict(populate_by_name=True)

    station_code: str = Field(..., alias="station")
    station_name: str = Field(..., alias="name")
    latitude: float = Field(..., alias="lat")
    longitude: float = Field(..., alias="lon")
    elevation: Optional[float] = Field(default=None, alias="elev")
    start_date: Optional[str] = Field(default=None, alias="start")
    end_date: Optional[str] = Field(default=None, alias="end")
