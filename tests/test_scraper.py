"""Tests for the scraper auth mechanism."""

import asyncio
from contextlib import suppress

import pytest

import litellm_pulse.app as app_module

SAMPLE_METRICS = """\
# HELP litellm_proxy_total_requests_metric_total Total requests to proxy
# TYPE litellm_proxy_total_requests_metric_total counter
litellm_proxy_total_requests_metric_total 100.0
# HELP litellm_proxy_failed_requests_metric_total Failed requests
# TYPE litellm_proxy_failed_requests_metric_total counter
litellm_proxy_failed_requests_metric_total 5.0
# HELP litellm_total_tokens_metric_total Total tokens
# TYPE litellm_total_tokens_metric_total counter
litellm_total_tokens_metric_total 50000.0
# HELP litellm_input_tokens_metric_total Input tokens
# TYPE litellm_input_tokens_metric_total counter
litellm_input_tokens_metric_total 30000.0
# HELP litellm_output_tokens_metric_total Output tokens
# TYPE litellm_output_tokens_metric_total counter
litellm_output_tokens_metric_total 20000.0
# HELP litellm_output_reasoning_tokens_metric_total Reasoning tokens
# TYPE litellm_output_reasoning_tokens_metric_total counter
litellm_output_reasoning_tokens_metric_total 0.0
# HELP litellm_spend_metric_total Spend
# TYPE litellm_spend_metric_total counter
litellm_spend_metric_total 2.50
# HELP litellm_in_flight_requests In-flight requests
# TYPE litellm_in_flight_requests gauge
litellm_in_flight_requests 3.0
"""


@pytest.fixture
def scraper_state():
    """Save/restore scraper globals to prevent cross-test side-effects."""
    original_raw = app_module._raw_metrics.copy()
    original_prev = app_module._previous_raw.copy()
    original_last_scrape = app_module._last_scrape
    original_last_error = app_module._last_error
    original_db = app_module._db
    original_history = app_module._history

    yield

    app_module._raw_metrics = original_raw
    app_module._previous_raw = original_prev
    app_module._last_scrape = original_last_scrape
    app_module._last_error = original_last_error
    app_module._db = original_db
    app_module._history = original_history


class TestBuildAuthHeaders:
    def test_with_key_set(self, monkeypatch):
        monkeypatch.setattr(app_module, "METRICS_API_KEY", "sk-test-key")
        headers = app_module._build_auth_headers()
        assert headers == {"Authorization": "Bearer sk-test-key"}

    def test_with_empty_key(self, monkeypatch):
        monkeypatch.setattr(app_module, "METRICS_API_KEY", "")
        headers = app_module._build_auth_headers()
        assert headers is None

    def test_with_whitespace_only_key(self, monkeypatch):
        monkeypatch.setattr(app_module, "METRICS_API_KEY", "   ")
        headers = app_module._build_auth_headers()
        assert headers is None


class TestScraperAuthIntegration:
    @pytest.mark.asyncio
    async def test_scraper_loop_sends_auth_header(self, monkeypatch, httpx_mock, scraper_state):
        monkeypatch.setattr(app_module, "METRICS_API_KEY", "sk-test-key")
        monkeypatch.setattr(app_module, "SCRAPE_INTERVAL", 3600)

        httpx_mock.add_response(url=app_module.METRICS_URL, text=SAMPLE_METRICS)

        task = asyncio.create_task(app_module._scraper_loop())
        await asyncio.sleep(0.1)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

        requests = httpx_mock.get_requests()
        assert len(requests) >= 1
        assert requests[0].headers["Authorization"] == "Bearer sk-test-key"

    @pytest.mark.asyncio
    async def test_scraper_loop_no_auth_by_default(self, monkeypatch, httpx_mock, scraper_state):
        monkeypatch.setattr(app_module, "METRICS_API_KEY", "")
        monkeypatch.setattr(app_module, "SCRAPE_INTERVAL", 3600)

        httpx_mock.add_response(url=app_module.METRICS_URL, text=SAMPLE_METRICS)

        task = asyncio.create_task(app_module._scraper_loop())
        await asyncio.sleep(0.1)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

        requests = httpx_mock.get_requests()
        assert len(requests) >= 1
        assert "Authorization" not in requests[0].headers

    @pytest.mark.asyncio
    async def test_scrape_handles_401(self, monkeypatch, httpx_mock, scraper_state):
        monkeypatch.setattr(app_module, "SCRAPE_INTERVAL", 3600)

        httpx_mock.add_response(
            url=app_module.METRICS_URL,
            status_code=401,
            text="Unauthorized",
        )

        task = asyncio.create_task(app_module._scraper_loop())
        await asyncio.sleep(0.1)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

        assert app_module._last_error is not None
        assert "401" in app_module._last_error
