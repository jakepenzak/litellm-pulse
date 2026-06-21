"""LLM Pulse — a lightweight LiteLLM metrics exporter for dashboards and home automation."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .parser import parse_prometheus_text

logger = logging.getLogger("llm-pulse")

# ---------------------------------------------------------------------------
# Configuration (all env-var driven for community use)
# ---------------------------------------------------------------------------

METRICS_URL = os.environ.get("METRICS_URL", "http://litellm:4000/metrics/")
SCRAPE_INTERVAL = int(os.environ.get("SCRAPE_INTERVAL", "60"))
PORT = int(os.environ.get("PORT", "8000"))
HOST = os.environ.get("HOST", "0.0.0.0")
VERIFY_SSL = os.environ.get("VERIFY_SSL", "false").lower() == "true"
SCRAPE_TIMEOUT = float(os.environ.get("SCRAPE_TIMEOUT", "30"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "info").upper()

# Default metric mappings — LiteLLM Prometheus metric names.
# Each can be overridden via env var METRIC_<FRIENDLY_NAME>.
DEFAULT_METRIC_MAP = {
    "requests": "litellm_proxy_total_requests_metric_total",
    "failed_requests": "litellm_proxy_failed_requests_metric_total",
    "tokens": "litellm_total_tokens_metric_total",
    "input_tokens": "litellm_input_tokens_metric_total",
    "output_tokens": "litellm_output_tokens_metric_total",
    "reasoning_tokens": "litellm_output_reasoning_tokens_metric_total",
    "cost": "litellm_spend_metric_total",
    "in_flight_requests": "litellm_in_flight_requests",
}

METRIC_MAP: dict[str, str] = {}
for _friendly, _prom in DEFAULT_METRIC_MAP.items():
    METRIC_MAP[_friendly] = os.environ.get(f"METRIC_{_friendly.upper()}", _prom)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_raw_metrics: dict[str, float] = {}
_last_scrape: datetime | None = None
_last_error: str | None = None


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------


async def _scrape(client: httpx.AsyncClient) -> None:
    global _raw_metrics, _last_scrape, _last_error
    try:
        resp = await client.get(METRICS_URL, timeout=SCRAPE_TIMEOUT)
        resp.raise_for_status()
        _raw_metrics = parse_prometheus_text(resp.text)
        _last_scrape = datetime.now(timezone.utc)
        _last_error = None
        logger.debug("Scraped %s — %d metric families", METRICS_URL, len(_raw_metrics))
    except Exception as exc:
        _last_error = str(exc)
        logger.warning("Scrape failed: %s", exc)


async def _scraper_loop() -> None:
    async with httpx.AsyncClient(verify=VERIFY_SSL) as client:
        while True:
            await _scrape(client)
            await asyncio.sleep(SCRAPE_INTERVAL)


# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(_scraper_loop())
    logger.info(
        "LLM Pulse started — scraping %s every %ds", METRICS_URL, SCRAPE_INTERVAL
    )
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="LLM Pulse",
    description="A lightweight metrics exporter for LiteLLM.",
    version="0.1.0",
    lifespan=lifespan,
)


def _summary() -> dict:
    data: dict[str, float | None | str] = {}
    for friendly, prom_name in METRIC_MAP.items():
        data[friendly] = _raw_metrics.get(prom_name, 0.0)
    data["last_scrape"] = _last_scrape.isoformat() if _last_scrape else None
    data["source"] = METRICS_URL
    if _last_error:
        data["error"] = _last_error
    return data


@app.get("/")
async def root():
    return _summary()


@app.get("/api/v1/metrics")
async def all_metrics():
    return _summary()


@app.get("/api/v1/metrics/{name}")
async def get_metric(name: str):
    if name not in METRIC_MAP:
        return JSONResponse(
            status_code=404,
            content={
                "error": f"Unknown metric: {name}",
                "available": list(METRIC_MAP.keys()),
            },
        )
    prom_name = METRIC_MAP[name]
    return {
        "name": name,
        "value": _raw_metrics.get(prom_name, 0.0),
        "last_scrape": _last_scrape.isoformat() if _last_scrape else None,
    }


@app.get("/raw")
async def raw_metrics():
    return _raw_metrics


@app.get("/health")
async def health():
    return {"status": "ok" if _last_scrape else "starting"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    )
    uvicorn.run(app, host=HOST, port=PORT, log_level=LOG_LEVEL.lower())


if __name__ == "__main__":
    main()
