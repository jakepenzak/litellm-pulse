"""Tests for the Prometheus text format parser."""

from litellm_pulse.parser import parse_prometheus_text


class TestBasicParsing:
    def test_single_metric(self):
        text = "litellm_requests_total 42\n"
        result = parse_prometheus_text(text)
        assert result == {"litellm_requests_total": 42.0}

    def test_multiple_metrics(self):
        text = "metric_a 10\nmetric_b 20\nmetric_c 30\n"
        result = parse_prometheus_text(text)
        assert result == {"metric_a": 10.0, "metric_b": 20.0, "metric_c": 30.0}

    def test_float_values(self):
        text = "cost_total 3.14159\n"
        result = parse_prometheus_text(text)
        assert result == {"cost_total": 3.14159}

    def test_integer_value(self):
        text = "requests_total 100\n"
        result = parse_prometheus_text(text)
        assert result == {"requests_total": 100.0}


class TestLabelsAndSumming:
    def test_labeled_metrics_are_summed(self):
        text = (
            'http_requests_total{method="GET",status="200"} 100\n'
            'http_requests_total{method="POST",status="200"} 50\n'
            'http_requests_total{method="GET",status="500"} 5\n'
        )
        result = parse_prometheus_text(text)
        assert result == {"http_requests_total": 155.0}

    def test_mixed_labeled_and_unlabeled(self):
        text = 'simple_metric 10\nlabeled_metric{label="a"} 20\nlabeled_metric{label="b"} 30\n'
        result = parse_prometheus_text(text)
        assert result == {"simple_metric": 10.0, "labeled_metric": 50.0}


class TestEdgeCases:
    def test_comments_are_skipped(self):
        text = (
            "# HELP requests_total Total requests\n"
            "# TYPE requests_total counter\n"
            "requests_total 42\n"
        )
        result = parse_prometheus_text(text)
        assert result == {"requests_total": 42.0}

    def test_empty_string(self):
        result = parse_prometheus_text("")
        assert result == {}

    def test_only_comments(self):
        text = "# HELP foo A metric\n# TYPE foo counter\n"
        result = parse_prometheus_text(text)
        assert result == {}

    def test_blank_lines_skipped(self):
        text = "\n\nmetric_a 10\n\n\nmetric_b 20\n\n"
        result = parse_prometheus_text(text)
        assert result == {"metric_a": 10.0, "metric_b": 20.0}

    def test_scientific_notation(self):
        text = "big_number 1.5e10\nsmall_number 2.5e-3\n"
        result = parse_prometheus_text(text)
        assert result == {"big_number": 1.5e10, "small_number": 2.5e-3}

    def test_negative_values(self):
        text = "temperature -5.5\noffset -100\n"
        result = parse_prometheus_text(text)
        assert result == {"temperature": -5.5, "offset": -100.0}

    def test_whitespace_handling(self):
        text = "  metric_a   10  \n\tmetric_b\t20\n"
        result = parse_prometheus_text(text)
        assert result == {"metric_a": 10.0, "metric_b": 20.0}

    def test_metric_name_with_underscores_and_colons(self):
        text = "litellm:proxy_requests_total 42\n"
        result = parse_prometheus_text(text)
        assert result == {"litellm:proxy_requests_total": 42.0}

    def test_zero_value(self):
        text = "counter_zero 0\n"
        result = parse_prometheus_text(text)
        assert result == {"counter_zero": 0.0}
