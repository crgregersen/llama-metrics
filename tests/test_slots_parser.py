from __future__ import annotations

from app.slots_parser import parse_slots_payload


def test_parse_next_token_array() -> None:
    payload = [
        {
            "id": 0,
            "id_task": 1234,
            "is_processing": True,
            "n_ctx": 131072,
            "next_token": [
                {
                    "has_next_token": True,
                    "n_remain": 12000,
                    "n_decoded": 4000,
                }
            ],
        }
    ]

    slots = parse_slots_payload(payload, generation_tokens_per_second=20)

    assert len(slots) == 1
    slot = slots[0]
    assert slot.slot_id == 0
    assert slot.task_id == 1234
    assert slot.generated_tokens == 4000
    assert slot.remaining_tokens == 12000
    assert slot.output_token_limit == 16000
    assert slot.output_progress == 0.25
    assert slot.estimated_seconds_remaining == 600
    assert slot.state == "generating"


def test_parse_next_token_object() -> None:
    payload = {
        "id": 1,
        "is_processing": True,
        "next_token": {"has_next_token": False, "n_remain": 0, "n_decoded": 99},
    }

    slot = parse_slots_payload(payload)[0]

    assert slot.generated_tokens == 99
    assert slot.remaining_tokens == 0
    assert slot.output_token_limit == 99
    assert slot.state == "processing"


def test_parse_null_or_absent_next_token_as_idle_safe() -> None:
    payload = [
        {"id": 2, "is_processing": False, "next_token": None},
        {"id": 3, "is_processing": False},
    ]

    slots = parse_slots_payload(payload)

    assert [slot.state for slot in slots] == ["idle", "idle"]
    assert all(slot.generated_tokens is None for slot in slots)


def test_malformed_payload_returns_parse_error() -> None:
    slots = parse_slots_payload("not-json-object")

    assert len(slots) == 1
    assert slots[0].state == "unknown"
    assert "expected list or object" in slots[0].parse_error
