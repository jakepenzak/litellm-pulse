"""Prometheus text format parser."""

from __future__ import annotations

import re
from collections import defaultdict

_LINE_RE = re.compile(
    r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)"
    r"(?:\{[^}]*\})?"
    r"\s+"
    r"(?P<value>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)"
)


def parse_prometheus_text(text: str) -> dict[str, float]:
    """Parse Prometheus text exposition format and sum values per metric family.

    Labels are ignored — all samples sharing the same metric name are summed.
    This is useful for counter metrics where you want the grand total across
    all label combinations.

    Args:
        text: Raw Prometheus text exposition format string.

    Returns:
        Dict mapping metric names to their summed float values.
    """
    totals: dict[str, float] = defaultdict(float)

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = _LINE_RE.match(line)
        if match:
            totals[match.group("name")] += float(match.group("value"))

    return dict(totals)
