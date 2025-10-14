import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union

import requests

SILO_BASE_URL = "https://www.longpaddock.qld.gov.au/cgi-bin/silo/"

logger = logging.getLogger(__name__)

class SiloAPIError(Exception):
    pass

class SiloAPI:
    VALID_DATASETS = ["PatchedPoint", "DataDrill"]
    VALID_FORMATS = ["csv", "apsim", "near"]
    DEFAULT_TIMEOUT = 30
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0
    
    def __init__(
        self, 
        api_key: str, 
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        enable_cache: bool = False
    ):
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.enable_cache = enable_cache
        self._cache: Optional[Dict[str, Any]] = {} if enable_cache else None

    def _validate_date_format(self, date_str: Optional[str], param_name: str) -> None:
        """Validate date format is YYYYMMDD."""
        if date_str is None:
            return
        
        if not isinstance(date_str, str) or len(date_str) != 8:
            raise ValueError(
                f"{param_name} must be in YYYYMMDD format (e.g., '20230101'), got: {date_str}"
            )
        
        try:
            year = int(date_str[:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            
            if not (1900 <= year <= 2100):
                raise ValueError(f"{param_name} year must be between 1900 and 2100")
            if not (1 <= month <= 12):
                raise ValueError(f"{param_name} month must be between 01 and 12")
            if not (1 <= day <= 31):
                raise ValueError(f"{param_name} day must be between 01 and 31")
        except ValueError as e:
            if "invalid literal" in str(e):
                raise ValueError(
                    f"{param_name} must contain only digits in YYYYMMDD format, got: {date_str}"
                )
            raise

    def _get_endpoint(self, dataset: str) -> str:
        """Get the API endpoint for a given dataset."""
        endpoints = {
            "PatchedPoint": "PatchedPointDataset.php",
            "DataDrill": "DataDrillDataset.php"
        }
        endpoint = endpoints.get(dataset)
        if not endpoint:
            raise ValueError(
                f"Unknown dataset: {dataset}. Valid datasets: {self.VALID_DATASETS}"
            )
        return SILO_BASE_URL + endpoint

    def _validate_format(self, response_format: str, dataset: str) -> None:
        """Validate that the format is supported."""
        if response_format not in self.VALID_FORMATS:
            raise ValueError(
                f"Unknown format: {response_format}. Valid formats: {self.VALID_FORMATS}"
            )
        
        # DataDrill doesn't support 'near' format
        if dataset == "DataDrill" and response_format == "near":
            raise ValueError("DataDrill dataset does not support 'near' format")

    def _build_patched_point_params(
        self,
        response_format: str,
        station_code: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
        values: Optional[List[str]],
        radius: Optional[float]
    ) -> Dict[str, Any]:
        """Build query parameters for PatchedPoint dataset."""
        if not station_code:
            raise ValueError("station_code is required for PatchedPoint queries")
        
        # Validate dates
        self._validate_date_format(start_date, "start_date")
        self._validate_date_format(end_date, "end_date")
        
        if response_format == "csv":
            return {
                "station": station_code,
                "start": start_date,
                "finish": end_date,
                "format": response_format,
                "comment": ",".join(values or []),
                "username": self.api_key,
                "password": "api_request"
            }
        elif response_format == "apsim":
            return {
                "station": station_code,
                "start": start_date,
                "finish": end_date,
                "format": response_format,
                "username": self.api_key,
                "password": "api_request"
            }
        elif response_format == "near":
            return {
                "station": station_code,
                "radius": radius,
                "format": response_format
            }
        else:
            raise ValueError(f"Unsupported format for PatchedPoint: {response_format}")

    def _build_data_drill_params(
        self,
        response_format: str,
        longitude: Optional[float],
        latitude: Optional[float],
        start_date: Optional[str],
        end_date: Optional[str],
        values: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Build query parameters for DataDrill dataset."""
        if longitude is None or latitude is None:
            raise ValueError(
                "longitude and latitude are required for DataDrill queries"
            )
        
        # Validate dates
        self._validate_date_format(start_date, "start_date")
        self._validate_date_format(end_date, "end_date")
        
        if response_format in ["csv", "apsim"]:
            return {
                "longitude": longitude,
                "latitude": latitude,
                "start": start_date,
                "finish": end_date,
                "format": response_format,
                "comment": ",".join(values or []),
                "username": self.api_key,
                "password": "api_request"
            }
        else:
            raise ValueError(f"Unsupported format for DataDrill: {response_format}")

    def _get_cache_key(self, url: str, params: Dict[str, Any]) -> str:
        """Generate a cache key from URL and parameters."""
        # Create a deterministic string representation
        param_str = json.dumps(params, sort_keys=True)
        combined = f"{url}:{param_str}"
        return hashlib.md5(combined.encode()).hexdigest()

    def _make_request(self, url: str, params: Dict[str, Any]) -> requests.Response:
        """Make the HTTP request with retry logic and caching."""
        # Check cache first
        if self.enable_cache and self._cache is not None:
            cache_key = self._get_cache_key(url, params)
            if cache_key in self._cache:
                logger.debug(f"Cache hit for request: {cache_key}")
                return self._cache[cache_key]
        
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    f"Making request (attempt {attempt + 1}/{self.max_retries}): {url}"
                )
                response = requests.get(url, params=params, timeout=self.timeout)
                
                # HTTP error handling
                if response.status_code >= 400:
                    raise SiloAPIError(
                        f"HTTP {response.status_code}: {response.reason}\n{response.text}"
                    )
                
                # Check for SILO-specific error messages
                if "Sorry" in response.text or "Request Rejected" in response.text:
                    raise SiloAPIError(response.text)
                
                # Cache successful response
                if self.enable_cache and self._cache is not None:
                    cache_key = self._get_cache_key(url, params)
                    self._cache[cache_key] = response
                    logger.debug(f"Cached response for: {cache_key}")
                
                logger.info(f"Request successful on attempt {attempt + 1}")
                return response
                
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_exception = e
                logger.warning(
                    f"Transient error on attempt {attempt + 1}/{self.max_retries}: {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    logger.error(f"All {self.max_retries} attempts failed")
                    raise SiloAPIError(
                        f"Request failed after {self.max_retries} attempts: {last_exception}"
                    ) from last_exception
            except SiloAPIError:
                # Don't retry on API errors (bad request, etc.)
                raise
        
        # Should not reach here, but just in case
        raise SiloAPIError(
            f"Request failed after {self.max_retries} attempts: {last_exception}"
        )

    def _parse_response(self, response: requests.Response, response_format: str) -> Union[str, Dict[str, Any]]:
        """Parse the response based on format."""
        if response_format in ["csv", "apsim", "near"]:
            return response.text
        else:
            try:
                return response.json()
            except (ValueError, requests.exceptions.JSONDecodeError):
                return response.text

    def clear_cache(self) -> None:
        """Clear the response cache."""
        if self._cache is not None:
            self._cache.clear()
            logger.info("Cache cleared")

    def get_cache_size(self) -> int:
        """Get the number of cached responses."""
        if self._cache is not None:
            return len(self._cache)
        return 0

    def query(
        self,
        dataset: str,
        format: str = "csv",
        station_code: Optional[str] = None,
        longitude: Optional[float] = None,
        latitude: Optional[float] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        values: Optional[List[str]] = None,
        radius: Optional[float] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Query the SILO API.

        Parameters:
            dataset: 'PatchedPoint' or 'DataDrill'
            format: 'csv', 'apsim', 'near'
            station_code: SILO station code (for PatchedPoint)
            longitude, latitude: location (for DataDrill)
            start_date, end_date: YYYYMMDD
            values: list of weather variables to request
            radius: search radius (for 'near' format)

        Returns:
            Response data as string (CSV) or dict (JSON), depending on format.
        
        Raises:
            ValueError: If invalid parameters are provided
            SiloAPIError: If the API request fails
        """
        # Store format in a properly named variable
        response_format = format
        
        # Validate inputs
        self._validate_format(response_format, dataset)
        url = self._get_endpoint(dataset)
        
        # Build query parameters based on dataset
        if dataset == "PatchedPoint":
            query_params = self._build_patched_point_params(
                response_format, station_code, start_date, end_date, values, radius
            )
        elif dataset == "DataDrill":
            query_params = self._build_data_drill_params(
                response_format, longitude, latitude, start_date, end_date, values
            )
        else:
            raise ValueError(f"Unknown dataset: {dataset}")
        
        # Make request and parse response
        response = self._make_request(url, query_params)
        return self._parse_response(response, response_format)


# Example usage:
if __name__ == "__main__":
    import os
    
    # Configure logging to see debug information
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load API key from environment variable
    silo_api_key = os.getenv("SILO_API_KEY", "your_silo_api_key_here")
    
    # Example 1: Basic query with default settings
    print("=" * 60)
    print("Example 1: Basic PatchedPoint query")
    print("=" * 60)
    silo = SiloAPI(api_key=silo_api_key)
    try:
        result = silo.query(
            dataset="PatchedPoint",
            format="csv",
            station_code="30043",
            start_date="20230101",
            end_date="20230131",
            values=["rain", "maxtemp", "mintemp"]
        )
        print(f"Success! Data preview:\n{result[:200]}...")
    except SiloAPIError as e:
        print(f"Error: {e}")
    
    # Example 2: Query with custom timeout and retry settings
    print("\n" + "=" * 60)
    print("Example 2: Query with custom timeout and retries")
    print("=" * 60)
    silo_robust = SiloAPI(
        api_key=silo_api_key,
        timeout=60,
        max_retries=5,
        retry_delay=2.0
    )
    try:
        result = silo_robust.query(
            dataset="DataDrill",
            format="csv",
            longitude=151.0,
            latitude=-27.5,
            start_date="20230101",
            end_date="20230131",
            values=["rain", "maxtemp"]
        )
        print(f"Success! Data preview:\n{result[:200]}...")
    except SiloAPIError as e:
        print(f"Error: {e}")
    
    # Example 3: Query with caching enabled
    print("\n" + "=" * 60)
    print("Example 3: Query with caching enabled")
    print("=" * 60)
    silo_cached = SiloAPI(
        api_key=silo_api_key,
        enable_cache=True
    )
    try:
        # First query - will hit the API
        print("First query (will hit API)...")
        result1 = silo_cached.query(
            dataset="PatchedPoint",
            format="csv",
            station_code="30043",
            start_date="20230101",
            end_date="20230131",
            values=["rain"]
        )
        print(f"Cache size after first query: {silo_cached.get_cache_size()}")
        
        # Second query - will use cache
        print("Second query (should use cache)...")
        result2 = silo_cached.query(
            dataset="PatchedPoint",
            format="csv",
            station_code="30043",
            start_date="20230101",
            end_date="20230131",
            values=["rain"]
        )
        print(f"Results identical: {result1 == result2}")
        print(f"Cache size: {silo_cached.get_cache_size()}")
        
        # Clear cache
        silo_cached.clear_cache()
        print(f"Cache size after clearing: {silo_cached.get_cache_size()}")
        
    except SiloAPIError as e:
        print(f"Error: {e}")