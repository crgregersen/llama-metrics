from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.models import SlotState


def parse_slots_payload(
    payload: Any,
    generation_tokens_per_second: float | None = None,
) -> list[SlotState]:
    if isinstance(payload, list):
        raw_slots = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("slots"), list):
            raw_slots = payload["slots"]
        else:
            raw_slots = [payload]
    else:
        return [
            SlotState(
                state="unknown",
                parse_error=f"expected list or object, got {type(payload).__name__}",
            )
        ]

    return [
        _parse_slot(raw_slot, generation_tokens_per_second)
        for raw_slot in raw_slots
    ]


def _parse_slot(
    raw_slot: Any,
    generation_tokens_per_second: float | None,
) -> SlotState:
    if not isinstance(raw_slot, dict):
        return SlotState(
            state="unknown",
            parse_error=f"expected slot object, got {type(raw_slot).__name__}",
        )

    next_token = _select_next_token(raw_slot.get("next_token"))
    generated = _first_int(
        next_token,
        raw_slot,
        keys=("n_decoded", "n_generated", "n_predict", "n_tokens_predicted"),
    )
    remaining = _first_int(
        next_token,
        raw_slot,
        keys=("n_remain", "n_remaining", "remaining_tokens"),
    )
    has_next_token = _first_bool(
        next_token,
        raw_slot,
        keys=("has_next_token", "has_next", "has_next_token_pending"),
    )
    output_limit = _output_limit(generated, remaining)
    progress = _progress(generated, output_limit)
    estimated_remaining = _estimated_remaining(
        remaining,
        generation_tokens_per_second,
    )
    is_processing = bool(raw_slot.get("is_processing", False))

    if not is_processing:
        return SlotState(
            slot_id=raw_slot.get("id", raw_slot.get("id_slot", raw_slot.get("slot_id"))),
            is_processing=False,
            n_ctx=_coerce_int(raw_slot.get("n_ctx")),
            state="idle",
        )

    return SlotState(
        slot_id=raw_slot.get("id", raw_slot.get("id_slot", raw_slot.get("slot_id"))),
        task_id=raw_slot.get("id_task", raw_slot.get("task_id")),
        is_processing=is_processing,
        n_ctx=_coerce_int(raw_slot.get("n_ctx")),
        generated_tokens=generated,
        remaining_tokens=remaining,
        output_token_limit=output_limit,
        output_progress=progress,
        has_next_token=has_next_token,
        estimated_seconds_remaining=estimated_remaining,
        state=_slot_state(is_processing, has_next_token),
    )


def _select_next_token(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
    return {}


def _first_int(*sources: dict[str, Any], keys: Iterable[str]) -> int | None:
    for source in sources:
        for key in keys:
            value = _coerce_int(source.get(key))
            if value is not None:
                return value
    return None


def _first_bool(*sources: dict[str, Any], keys: Iterable[str]) -> bool | None:
    for source in sources:
        for key in keys:
            if key in source:
                return bool(source[key])
    return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _output_limit(generated: int | None, remaining: int | None) -> int | None:
    if generated is None or remaining is None:
        return None
    if generated < 0 or remaining < 0:
        return None
    return generated + remaining


def _progress(generated: int | None, output_limit: int | None) -> float | None:
    if generated is None or output_limit is None or output_limit <= 0:
        return None
    return min(1.0, max(0.0, generated / output_limit))


def _estimated_remaining(
    remaining: int | None,
    generation_tokens_per_second: float | None,
) -> float | None:
    if remaining is None or remaining < 0:
        return None
    if generation_tokens_per_second is None or generation_tokens_per_second <= 0:
        return None
    return remaining / generation_tokens_per_second


def _slot_state(is_processing: bool, has_next_token: bool | None) -> str:
    if not is_processing:
        return "idle"
    if has_next_token is False:
        return "processing"
    return "generating"
