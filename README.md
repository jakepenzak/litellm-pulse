# LLM Pulse

A lightweight metrics exporter for [LiteLLM](https://github.com/BerriAI/litellm) — scrapes Prometheus metrics and serves JSON for dashboards like [Homepage](https://gethomepage.dev) and home automation systems like [Home Assistant](https://www.home-assistant.io).

## What It Does

LiteLLM exposes usage metrics (requests, tokens, spend) in Prometheus text format. LLM Pulse scrapes that endpoint on a schedule, parses the metrics, and serves them as clean JSON over a REST API. This makes it trivial to display LiteLLM usage in any dashboard or monitoring tool that speaks HTTP/JSON.

```
LiteLLM /metrics  ──scrape──▶  LLM Pulse  ──JSON──▶  Homepage / Home Assistant / anything
```

## Quick Start

### Docker Compose

```yaml
services:
  llm-pulse:
    build: .
    container_name: llm-pulse
    restart: unless-stopped
    environment:
      METRICS_URL: "http://litellm:4000/metrics/"
      SCRAPE_INTERVAL: "60"
      PORT: "8000"
    ports:
      - "8000:8000"
```

### Running Locally (with uv)

```bash
uv sync
uv run llm-pulse
```

## Configuration

All configuration is via environment variables. No config files required.

| Variable | Default | Description |
|---|---|---|
| `METRICS_URL` | `http://litellm:4000/metrics/` | Prometheus metrics endpoint to scrape |
| `SCRAPE_INTERVAL` | `60` | Seconds between scrapes |
| `PORT` | `8000` | Port to serve the API on |
| `HOST` | `0.0.0.0` | Address to bind to |
| `VERIFY_SSL` | `false` | Whether to verify TLS certificates when scraping |
| `SCRAPE_TIMEOUT` | `30` | Request timeout in seconds |
| `LOG_LEVEL` | `info` | Log level (`debug`, `info`, `warning`, `error`) |
| `METRIC_REQUESTS` | `litellm_proxy_total_requests_metric_total` | Prometheus metric name for requests |
| `METRIC_FAILED_REQUESTS` | `litellm_proxy_failed_requests_metric_total` | Prometheus metric name for failed requests |
| `METRIC_TOKENS` | `litellm_total_tokens_metric_total` | Prometheus metric name for total tokens |
| `METRIC_INPUT_TOKENS` | `litellm_input_tokens_metric_total` | Prometheus metric name for input tokens |
| `METRIC_OUTPUT_TOKENS` | `litellm_output_tokens_metric_total` | Prometheus metric name for output tokens |
| `METRIC_REASONING_TOKENS` | `litellm_output_reasoning_tokens_metric_total` | Prometheus metric name for reasoning tokens |
| `METRIC_COST` | `litellm_spend_metric_total` | Prometheus metric name for spend |
| `METRIC_IN_FLIGHT_REQUESTS` | `litellm_in_flight_requests` | Prometheus metric name for in-flight requests |

### Custom Metric Mappings

Every metric has a default Prometheus name (LiteLLM-specific). Override any of them by setting the corresponding `METRIC_*` env var. This lets you adapt LLM Pulse for non-LiteLLM sources or future LiteLLM metric name changes.

## API Endpoints

### `GET /` or `GET /api/v1/metrics`

Returns all tracked metrics as a JSON object.

```json
{
  "requests": 1234,
  "failed_requests": 5,
  "tokens": 567890,
  "input_tokens": 300000,
  "output_tokens": 267890,
  "reasoning_tokens": 0,
  "cost": 12.345678,
  "in_flight_requests": 2,
  "last_scrape": "2025-06-21T12:00:00+00:00",
  "source": "http://litellm:4000/metrics/"
}
```

### `GET /api/v1/metrics/{name}`

Returns a single metric by its friendly name (`requests`, `tokens`, `cost`, etc.).

```json
{
  "name": "requests",
  "value": 1234,
  "last_scrape": "2025-06-21T12:00:00+00:00"
}
```

### `GET /raw`

Returns all raw parsed Prometheus metrics (every metric family found, summed).

### `GET /health`

Returns `{"status": "ok"}` once the first successful scrape has completed.

## Integrations

### Homepage (Custom API Widget)

Add a service entry in `services.yaml` with a `customapi` widget:

```yaml
- LiteLLM:
    icon: https://cdn.jsdelivr.net/gh/selfhst/icons/png/litellm.png
    href: https://litellm.home.lan
    description: LLM proxy and management
    widget:
      type: customapi
      url: http://llm-pulse:8000/api/v1/metrics
      refreshInterval: 60000
      mappings:
        - field: requests
          label: Requests
          format: number
        - field: tokens
          label: Tokens
          format: number
        - field: cost
          label: Spend
          format: float
          prefix: "$"
```

### Home Assistant (REST Sensors)

Add RESTful sensors to `configuration.yaml`:

```yaml
sensor:
  - platform: rest
    name: LiteLLM Requests
    resource: http://llm-pulse:8000/api/v1/metrics/requests
    value_template: "{{ value_json.value }}"
    unit_of_measurement: "req"
    scan_interval: 60

  - platform: rest
    name: LiteLLM Tokens
    resource: http://llm-pulse:8000/api/v1/metrics/tokens
    value_template: "{{ value_json.value }}"
    unit_of_measurement: "tokens"
    scan_interval: 60

  - platform: rest
    name: LiteLLM Spend
    resource: http://llm-pulse:8000/api/v1/metrics/cost
    value_template: "{{ value_json.value }}"
    unit_of_measurement: "$"
    scan_interval: 60
```

Or use a single endpoint with template sensors:

```yaml
rest:
  - resource: http://llm-pulse:8000/api/v1/metrics
    scan_interval: 60
    sensor:
      - name: LiteLLM Requests
        value_template: "{{ value_json.requests }}"
      - name: LiteLLM Tokens
        value_template: "{{ value_json.tokens }}"
      - name: LiteLLM Spend
        value_template: "{{ value_json.cost }}"
        unit_of_measurement: "$"
```

## Development

```bash
uv sync                    # install deps
uv run llm-pulse           # run the server
uv run ruff check .        # lint
uv run ruff format .       # format
```

## License

MIT
