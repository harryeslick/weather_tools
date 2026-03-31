"""Tests for SiloAPI persistent disk cache."""

from unittest.mock import patch

import pytest
import requests

from weather_tools.silo_api import SiloAPI


def _make_mock_response(text="ok", status_code=200):
    """Create a mock requests.Response."""
    resp = requests.Response()
    resp.status_code = status_code
    resp._content = text.encode()
    return resp


@pytest.fixture()
def api_key(monkeypatch):
    """Ensure SILO_API_KEY is set for tests."""
    monkeypatch.setenv("SILO_API_KEY", "test@example.com")


@pytest.fixture()
def disk_api(tmp_path, api_key):
    """SiloAPI with disk cache in a temp directory."""
    return SiloAPI(enable_cache=True, cache_dir=tmp_path / "cache")


@pytest.fixture()
def nocache_api(api_key):
    """SiloAPI with caching disabled."""
    return SiloAPI(enable_cache=False)


class TestDiskCachePersistence:
    """Verify cache persists across instances sharing the same directory."""

    @patch("requests.get")
    def test_persists_across_instances(self, mock_get, tmp_path, api_key):
        mock_get.return_value = _make_mock_response("station data")
        cache_dir = tmp_path / "shared"

        # Instance A makes a request
        api_a = SiloAPI(enable_cache=True, cache_dir=cache_dir)
        url = "https://example.com/api"
        params = {"station": "30043", "username": "test@example.com"}
        api_a._make_request(url, params)
        assert mock_get.call_count == 1

        # Instance B (same cache_dir) gets a cache hit — no new HTTP call
        api_b = SiloAPI(enable_cache=True, cache_dir=cache_dir)
        result_b = api_b._make_request(url, params)
        assert mock_get.call_count == 1  # Still 1 — served from disk
        assert result_b.text == "station data"

    @patch("requests.get")
    def test_cross_instance_sharing(self, mock_get, tmp_path, api_key):
        mock_get.return_value = _make_mock_response("shared data")
        cache_dir = tmp_path / "shared2"

        api_a = SiloAPI(enable_cache=True, cache_dir=cache_dir)
        api_b = SiloAPI(enable_cache=True, cache_dir=cache_dir)

        url = "https://example.com/api"
        params = {"key": "value", "username": "test@example.com"}

        # A writes to cache
        api_a._make_request(url, params)
        assert mock_get.call_count == 1

        # B reads from same cache
        result = api_b._make_request(url, params)
        assert mock_get.call_count == 1
        assert result.text == "shared data"
        assert api_b.get_cache_size() == 1


class TestCacheDisabled:
    """Verify enable_cache=False means no caching at all."""

    @patch("requests.get")
    def test_no_caching(self, mock_get, nocache_api):
        mock_get.return_value = _make_mock_response("fresh")

        url = "https://example.com/api"
        params = {"x": "y", "username": "test@example.com"}

        nocache_api._make_request(url, params)
        nocache_api._make_request(url, params)
        assert mock_get.call_count == 2  # No caching — both hit network
        assert nocache_api.get_cache_size() == 0

    def test_no_disk_usage_when_disabled(self, nocache_api):
        assert nocache_api.get_cache_disk_usage() is None


class TestClearCache:
    @patch("requests.get")
    def test_clear_removes_entries(self, mock_get, disk_api):
        mock_get.return_value = _make_mock_response("clearme")

        url = "https://example.com/api"
        params = {"q": "1", "username": "test@example.com"}

        disk_api._make_request(url, params)
        assert disk_api.get_cache_size() == 1

        disk_api.clear_cache()
        assert disk_api.get_cache_size() == 0

        # Next request must hit network again
        disk_api._make_request(url, params)
        assert mock_get.call_count == 2


class TestCacheTTL:
    @patch("requests.get")
    def test_ttl_expiry(self, mock_get, tmp_path, api_key):
        """Entry with 0-second TTL should expire immediately."""
        mock_get.return_value = _make_mock_response("expires")

        api = SiloAPI(enable_cache=True, cache_dir=tmp_path / "ttl", cache_ttl=0)

        url = "https://example.com/api"
        params = {"t": "1", "username": "test@example.com"}

        api._make_request(url, params)
        assert mock_get.call_count == 1

        # With TTL=0, the entry expires immediately
        api._make_request(url, params)
        assert mock_get.call_count == 2  # Had to fetch again


class TestDiskUsage:
    @patch("requests.get")
    def test_disk_usage_reported(self, mock_get, disk_api):
        mock_get.return_value = _make_mock_response("data")

        url = "https://example.com/api"
        params = {"d": "1", "username": "test@example.com"}

        disk_api._make_request(url, params)
        usage = disk_api.get_cache_disk_usage()
        assert usage is not None
        assert usage > 0


class TestGracefulDegradation:
    @patch("requests.get")
    def test_corrupted_cache_read_falls_through(self, mock_get, disk_api):
        """If _cache_get raises, it should degrade to a network request."""
        mock_get.return_value = _make_mock_response("fallback")

        url = "https://example.com/api"
        params = {"g": "1", "username": "test@example.com"}

        # Poison the cache get to raise
        with patch.object(disk_api._disk_cache, "get", side_effect=Exception("corrupt")):
            result = disk_api._make_request(url, params)
            assert result.text == "fallback"
            assert mock_get.call_count == 1
