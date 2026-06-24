# Changelog

## [0.2.0](https://github.com/jakepenzak/litellm-pulse/compare/v0.1.0...v0.2.0) (2026-06-24)


### ✨ Features

* add support for configurable timezones ([#9](https://github.com/jakepenzak/litellm-pulse/issues/9)) ([fd3d0fe](https://github.com/jakepenzak/litellm-pulse/commit/fd3d0fea2b63825b40d426a6f4e03ab6d78a2743))
* authentication support for scraping LiteLLM `/metrics` endpoint ([#7](https://github.com/jakepenzak/litellm-pulse/issues/7)) ([0ea7d13](https://github.com/jakepenzak/litellm-pulse/commit/0ea7d13aa69248b9dcf46e7692e03fc143ff5fc8))

## 0.1.0 (2026-06-21)

Initial release of `litellm-pulse`, a lightweight service that scrapes LiteLLM Prometheus metrics and exposes them as JSON for Homepage widgets and Home Assistant sensors. Features a FastAPI application with a Prometheus text format parser, SQLite time-series storage with daily/weekly/monthly aggregates and counter reset detection, and REST endpoints for cost and token metrics. Includes 49 pytest tests, pre-commit linting with ruff, and CI/CD pipelines with automated releases via release-please and Docker image publishing to GHCR.

### ✨ Features

* initial `litellm-pulse` metrics exporter ([00f72f2](https://github.com/jakepenzak/litellm-pulse/commit/00f72f299801e5daaaa0c7362795a9d4980b5e8f))
* SQLite time-series storage with daily/weekly/monthly aggregates ([c24ce5f](https://github.com/jakepenzak/litellm-pulse/commit/c24ce5f453f12a170bfe8f3cb86a7ba5c30af2d9))

### 🔧 CI/CD

* add CI/CD, release-please, tests, and project infrastructure ([4b184d3](https://github.com/jakepenzak/litellm-pulse/commit/4b184d3b99635cc1ce49a00a89405ef5b956409d))
