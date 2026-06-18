from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from app.models import InferenceMetrics, MetricSample


KNOWN_METRICS = {
    "llamacpp:n_tokens_max",
    "llamacpp:prompt_tokens_seconds",
    "llamacpp:predicted_tokens_seconds",
    "llamacpp:requests_processing",
    "llamacpp:requests_deferred",
}

_SAMPLE_RE = re.compile(
    r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)"
    r"(?:\{(?P<labels>.*)\})?"
    r"\s+"
    r"(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|NaN|Inf|-Inf)"
    r"(?:\s+\d+)?$"
)
_LABEL_RE = re.compile(r'\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*"((?:\\.|[^"\\])*)"\s*')


@dataclass
class ParsedMetrics:
    inference: InferenceMetrics = field(default_factory=InferenceMetrics)
    unknown_metrics: list[MetricSample] = field(default_factory=list)
    all_samples: list[MetricSample] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def parse_prometheus_metrics(text: str) -> ParsedMetrics:
    parsed = ParsedMetrics()

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        match = _SAMPLE_RE.match(line)
        if not match:
            parsed.errors.append(f"line {line_number}: invalid sample")
            continue

        value = _parse_value(match.group("value"))
        if value is None:
            parsed.errors.append(f"line {line_number}: non-finite sample")
            continue

        labels = _parse_labels(match.group("labels") or "", line_number, parsed.errors)
        sample = MetricSample(name=match.group("name"), labels=labels, value=value)
        parsed.all_samples.append(sample)

        if sample.name in KNOWN_METRICS:
            _apply_known_metric(parsed.inference, sample)
        else:
            parsed.unknown_metrics.append(sample)

    return parsed


def _parse_value(value: str) -> float | None:
    try:
        parsed = float(value)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _parse_labels(raw: str, line_number: int, errors: list[str]) -> dict[str, str]:
    if raw == "":
        return {}

    labels: dict[str, str] = {}
    position = 0
    while position < len(raw):
        match = _LABEL_RE.match(raw, position)
        if not match:
            errors.append(f"line {line_number}: invalid label set")
            return labels
        key, value = match.groups()
        labels[key] = _unescape_label_value(value)
        position = match.end()
        if position == len(raw):
            break
        if raw[position] != ",":
            errors.append(f"line {line_number}: invalid label separator")
            return labels
        position += 1
    return labels


def _unescape_label_value(value: str) -> str:
    return (
        value.replace(r"\\", "\\")
        .replace(r"\"", '"')
        .replace(r"\n", "\n")
    )


def _apply_known_metric(inference: InferenceMetrics, sample: MetricSample) -> None:
    if sample.name == "llamacpp:n_tokens_max":
        inference.largest_observed_context_tokens = int(sample.value)
    elif sample.name == "llamacpp:prompt_tokens_seconds":
        inference.prompt_tokens_per_second = sample.value
    elif sample.name == "llamacpp:predicted_tokens_seconds":
        inference.generation_tokens_per_second = sample.value
    elif sample.name == "llamacpp:requests_processing":
        inference.active_requests = int(sample.value)
    elif sample.name == "llamacpp:requests_deferred":
        inference.deferred_requests = int(sample.value)

    if inference.deferred_requests > 0:
        inference.inferred_phase = "queueing"
    elif inference.active_requests <= 0:
        inference.inferred_phase = "idle"
    elif (inference.generation_tokens_per_second or 0) > 0:
        inference.inferred_phase = "decode"
    elif (inference.prompt_tokens_per_second or 0) > 0:
        inference.inferred_phase = "prefill"
    else:
        inference.inferred_phase = "unknown"
