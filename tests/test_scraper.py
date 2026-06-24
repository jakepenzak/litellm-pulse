"""Tests for the scraper auth mechanism."""

import asyncio
import time
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
litellm_total_tokens_metric_total{model="gpt-4o"} 40000.0
litellm_total_tokens_metric_total{model="claude-sonnet"} 10000.0
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
litellm_spend_metric_total{model="gpt-4o"} 2.0
litellm_spend_metric_total{model="claude-sonnet"} 0.5
# HELP litellm_in_flight_requests In-flight requests
# TYPE litellm_in_flight_requests gauge
litellm_in_flight_requests 3.0
# HELP litellm_cache_hits_metric_total Cache hits
# TYPE litellm_cache_hits_metric_total counter
litellm_cache_hits_metric_total 40.0
# HELP litellm_cache_misses_metric_total Cache misses
# TYPE litellm_cache_misses_metric_total counter
litellm_cache_misses_metric_total 60.0
# HELP litellm_cached_tokens_metric_total Cached tokens
# TYPE litellm_cached_tokens_metric_total counter
litellm_cached_tokens_metric_total 15000.0
# HELP litellm_input_cached_tokens_metric_total Input cached tokens
# TYPE litellm_input_cached_tokens_metric_total counter
litellm_input_cached_tokens_metric_total 8000.0
# HELP litellm_input_cache_creation_tokens_metric_total Input cache creation tokens
# TYPE litellm_input_cache_creation_tokens_metric_total counter
litellm_input_cache_creation_tokens_metric_total 2000.0
# HELP litellm_deployment_total_requests_total Per-model deployment requests
# TYPE litellm_deployment_total_requests_total counter
litellm_deployment_total_requests_total{model="gpt-4o"} 80.0
litellm_deployment_total_requests_total{model="claude-sonnet"} 20.0
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
    original_raw_model = app_module._raw_model_metrics.copy()
    original_prev_model = app_module._previous_raw_model_metrics.copy()

    app_module._db = None
    app_module._history = None

    yield

    app_module._raw_metrics = original_raw
    app_module._previous_raw = original_prev
    app_module._last_scrape = original_last_scrape
    app_module._last_error = original_last_error
    app_module._db = original_db
    app_module._history = original_history
    app_module._raw_model_metrics = original_raw_model
    app_module._previous_raw_model_metrics = original_prev_model


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
    async def _wait_for_request(self, httpx_mock, timeout=5.0):
        deadline = time.monotonic() + timeout
        while len(httpx_mock.get_requests()) < 1:
            if time.monotonic() > deadline:
                break
            await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_scraper_loop_sends_auth_header(self, monkeypatch, httpx_mock, scraper_state):
        monkeypatch.setattr(app_module, "METRICS_API_KEY", "sk-test-key")
        monkeypatch.setattr(app_module, "SCRAPE_INTERVAL", 3600)

        httpx_mock.add_response(url=app_module.METRICS_URL, text=SAMPLE_METRICS)

        task = asyncio.create_task(app_module._scraper_loop())
        await self._wait_for_request(httpx_mock)
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
        await self._wait_for_request(httpx_mock)
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
        await self._wait_for_request(httpx_mock)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

        assert app_module._last_error is not None
        assert "401" in app_module._last_error


class TestScraperModelTracking:
    async def _wait_for_request(self, httpx_mock, timeout=5.0):
        deadline = time.monotonic() + timeout
        while len(httpx_mock.get_requests()) < 1:
            if time.monotonic() > deadline:
                break
            await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_model_metrics_parsed(self, monkeypatch, httpx_mock, scraper_state):
        monkeypatch.setattr(app_module, "SCRAPE_INTERVAL", 3600)

        httpx_mock.add_response(url=app_module.METRICS_URL, text=SAMPLE_METRICS)

        task = asyncio.create_task(app_module._scraper_loop())
        await self._wait_for_request(httpx_mock)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

        model_metrics = app_module._raw_model_metrics
        assert "tokens" in model_metrics
        assert model_metrics["tokens"]["gpt-4o"] == 40000.0
        assert model_metrics["tokens"]["claude-sonnet"] == 10000.0
        assert model_metrics["cost"]["gpt-4o"] == 2.0
        assert model_metrics["cost"]["claude-sonnet"] == 0.5

    @pytest.mark.asyncio
    async def test_deployment_metrics_mapped(self, monkeypatch, httpx_mock, scraper_state):
        monkeypatch.setattr(app_module, "SCRAPE_INTERVAL", 3600)

        httpx_mock.add_response(url=app_module.METRICS_URL, text=SAMPLE_METRICS)

        task = asyncio.create_task(app_module._scraper_loop())
        await self._wait_for_request(httpx_mock)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

        model_metrics = app_module._raw_model_metrics
        assert "deployment_requests" in model_metrics
        assert model_metrics["deployment_requests"]["gpt-4o"] == 80.0
        assert model_metrics["deployment_requests"]["claude-sonnet"] == 20.0

    @pytest.mark.asyncio
    async def test_model_metrics_no_labels(self, monkeypatch, httpx_mock, scraper_state):
        """When the endpoint has no model-labeled metrics, model state is empty."""
        monkeypatch.setattr(app_module, "SCRAPE_INTERVAL", 3600)

        unlabeled = "litellm_proxy_total_requests_metric_total 100\n"
        httpx_mock.add_response(url=app_module.METRICS_URL, text=unlabeled)

        task = asyncio.create_task(app_module._scraper_loop())
        await self._wait_for_request(httpx_mock)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

        assert app_module._raw_model_metrics == {}

    @pytest.mark.asyncio
    async def test_model_deltas_computed(self, monkeypatch, httpx_mock, scraper_state):
        monkeypatch.setattr(app_module, "SCRAPE_INTERVAL", 3600)

        prev = {"tokens": {"gpt-4o": 30000.0}, "cost": {"gpt-4o": 1.5}}
        app_module._previous_raw_model_metrics = prev

        httpx_mock.add_response(url=app_module.METRICS_URL, text=SAMPLE_METRICS)

        task = asyncio.create_task(app_module._scraper_loop())
        await self._wait_for_request(httpx_mock)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

        prev_model = app_module._previous_raw_model_metrics
        assert prev_model["tokens"]["gpt-4o"] == 40000.0
        assert prev_model["cost"]["gpt-4o"] == 2.0
