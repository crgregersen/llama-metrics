from __future__ import annotations

from app.metrics_parser import parse_prometheus_metrics


def test_parse_known_llamacpp_metrics() -> None:
    text = """
    # HELP llamacpp:predicted_tokens_seconds generated throughput
    llamacpp:n_tokens_max 4096
    llamacpp:prompt_tokens_seconds 1500.5
    llamacpp:predicted_tokens_seconds 22.25
    llamacpp:requests_processing 1
    llamacpp:requests_deferred 2
    """

    parsed = parse_prometheus_metrics(text)

    assert parsed.inference.largest_observed_context_tokens == 4096
    assert parsed.inference.prompt_tokens_per_second == 1500.5
    assert parsed.inference.generation_tokens_per_second == 22.25
    assert parsed.inference.active_requests == 1
    assert parsed.inference.deferred_requests == 2
    assert parsed.inference.inferred_phase == "queueing"


def test_parse_unknown_metric_labels_safely() -> None:
    text = 'custom_metric{model="llama",reason="a\\\"b"} 3.5'

    parsed = parse_prometheus_metrics(text)

    assert len(parsed.unknown_metrics) == 1
    sample = parsed.unknown_metrics[0]
    assert sample.name == "custom_metric"
    assert sample.labels == {"model": "llama", "reason": 'a"b'}
    assert sample.value == 3.5


def test_parser_records_malformed_lines_without_crashing() -> None:
    text = """
    bad line here
    llamacpp:requests_processing NaN
    llamacpp:requests_deferred 0
    """

    parsed = parse_prometheus_metrics(text)

    assert parsed.inference.deferred_requests == 0
    assert len(parsed.errors) == 2
