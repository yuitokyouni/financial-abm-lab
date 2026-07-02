"""Provider-routing tests for llm_client.call_llm. No network calls."""
from __future__ import annotations

import pytest

from fingerprint_atlas.llm_client import (
    _is_openai_model, _normalize_json_response, _is_transient,
)


def test_is_openai_model_routes_known_models():
    for m in ("openai/gpt-4o-mini", "openai/gpt-4o",
              "openai/gpt-4-turbo", "openai/gpt-4.1",
              "openai/o1-mini", "openai/o3", "openai/o4-mini"):
        assert _is_openai_model(m), m


def test_is_openai_model_keeps_oss_on_groq():
    """openai/gpt-oss-120b is Groq's open-weight model; must NOT route to OpenAI."""
    for m in ("openai/gpt-oss-120b", "openai/gpt-oss-20b",
              "llama-3.3-70b-versatile", "meta-llama/llama-4-scout-17b",
              "gemma2-9b-it", "deepseek-r1-distill-llama-70b"):
        assert not _is_openai_model(m), m


def test_normalize_json_unwraps_single_element_list():
    out = _normalize_json_response('[{"foo": 1}]', model="x",
                                    prompt_chars=10, finish_reason="stop")
    assert out == {"foo": 1}


def test_normalize_json_rejects_multi_element_list():
    with pytest.raises(RuntimeError, match="JSON list"):
        _normalize_json_response('[{"a": 1}, {"b": 2}]', model="x",
                                  prompt_chars=10, finish_reason="stop")


def test_normalize_json_rejects_non_object():
    with pytest.raises(RuntimeError, match="non-object"):
        _normalize_json_response('"a string"', model="x",
                                  prompt_chars=10, finish_reason="stop")


def test_normalize_json_rejects_empty_content():
    with pytest.raises(RuntimeError, match="no message.content"):
        _normalize_json_response(None, model="x",
                                  prompt_chars=10, finish_reason="length")


def test_is_transient_catches_known_markers():
    assert _is_transient("json_validate_failed: ...")
    assert _is_transient("OpenAI 429 rate limit exceeded")
    assert _is_transient("Groq returned empty choices")
    assert _is_transient("non-object JSON")
    assert not _is_transient("bad prompt syntax")
    assert not _is_transient("invalid api key")


def test_is_transient_treats_quota_errors_as_unrecoverable():
    """OpenAI reports 'insufficient_quota' with HTTP 429 — generic '429'
    match would loop forever. The unrecoverable list must win."""
    msg = ("Error code: 429 - {'error': {'message': 'You exceeded your "
           "current quota, please check your plan and billing details.', "
           "'type': 'insufficient_quota'}}")
    assert not _is_transient(msg)
