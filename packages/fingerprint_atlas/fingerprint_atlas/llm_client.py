"""llm_client — single entry point for every LLM call in this package.

Routes by `model` prefix:

  model="openai/gpt-4o-mini"          → OpenAI Chat Completions, requires OPENAI_API_KEY
  model="openai/gpt-4o"               → same
  model="openai/gpt-4-turbo"          → same
  model=anything else (e.g. "openai/gpt-oss-120b")
                                       → Groq, requires GROQ_API_KEY

The "openai/" prefix is intentionally reused as a model-id namespace
(Groq itself ships open-weight models under this convention — e.g.
`openai/gpt-oss-120b`). We disambiguate by KNOWN-OpenAI model ids
(`gpt-4o-mini`, `gpt-4o`, `gpt-4-turbo`, `gpt-4.1*`, `o1*`, `o3*`, `o4*`)
and route those to the OpenAI SDK; any other "openai/..." model stays on
Groq for backwards compatibility.

The single `call_llm(...)` enforces shared invariants downstream code
relied on per-provider before:

  - JSON mode (`response_format={"type": "json_object"}`)
  - Empty `choices` / missing `message.content` → descriptive RuntimeError
  - Single-element JSON array → unwrap to dict; else → descriptive error
  - Non-dict JSON → descriptive error
  - Transient errors (json_validate_failed, list-not-object, empty
    choices, OpenAI 429) retry with temperature jitter (+0.1).
"""
from __future__ import annotations

import json
import os


# Known OpenAI chat-completion model names. We match against the stripped
# `openai/` prefix; anything else (e.g. `openai/gpt-oss-120b`) goes to Groq.
_OPENAI_PREFIXES = (
    "gpt-4o", "gpt-4-turbo", "gpt-4.1", "gpt-3.5",
    "o1", "o3", "o4",
)


def _is_openai_model(model: str) -> bool:
    if not model.startswith("openai/"):
        return False
    suffix = model.removeprefix("openai/")
    return any(suffix.startswith(p) for p in _OPENAI_PREFIXES)


def _normalize_json_response(content: str | None, *, model: str,
                              prompt_chars: int, finish_reason: str | None
                              ) -> dict:
    """Apply the same defensive normalization to every provider response."""
    if not content:
        raise RuntimeError(
            f"LLM returned a choice with no message.content "
            f"(model={model}, finish_reason={finish_reason})"
        )
    parsed = json.loads(content)
    if isinstance(parsed, list):
        if len(parsed) == 1 and isinstance(parsed[0], dict):
            parsed = parsed[0]
        else:
            raise RuntimeError(
                f"LLM returned a JSON list instead of an object "
                f"(model={model}, len={len(parsed)}, "
                f"first_type={type(parsed[0]).__name__ if parsed else 'empty'})"
            )
    if not isinstance(parsed, dict):
        raise RuntimeError(
            f"LLM returned non-object JSON "
            f"(model={model}, got {type(parsed).__name__})"
        )
    return parsed


_TRANSIENT_MARKERS = (
    "json_validate_failed", "Failed to validate JSON",
    "empty choices", "no message.content",
    "JSON list instead of an object", "non-object JSON",
    # provider-side transient signals
    "rate limit", "rate_limit_exceeded", "429",
    "Service temporarily", "overloaded",
)


def _is_transient(msg: str) -> bool:
    return any(m.lower() in msg.lower() for m in _TRANSIENT_MARKERS)


def _call_openai(system_prompt: str, user_payload: dict, model_id: str,
                 temperature: float, max_retries: int) -> dict:
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError("openai SDK not installed. `uv add openai`.") from e
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable not set.")
    client = OpenAI(api_key=api_key)
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",
                     "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
            )
            if not resp.choices:
                raise RuntimeError(
                    f"OpenAI returned empty choices (model={model_id})"
                )
            choice = resp.choices[0]
            content = getattr(choice.message, "content", None)
            return _normalize_json_response(
                content, model=f"openai/{model_id}",
                prompt_chars=len(system_prompt) + len(json.dumps(user_payload)),
                finish_reason=getattr(choice, "finish_reason", None),
            )
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries and _is_transient(str(exc)):
                temperature = min(1.0, temperature + 0.1)
                continue
            raise
    raise last_exc  # unreachable, but keeps type-checkers quiet


def _call_groq(system_prompt: str, user_payload: dict, model: str,
               temperature: float, max_retries: int) -> dict:
    try:
        from groq import Groq
    except ImportError as e:
        raise ImportError("groq SDK not installed. `uv add groq`.") from e
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable not set.")
    client = Groq(api_key=api_key)
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",
                     "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
            )
            if not resp.choices:
                raise RuntimeError(
                    f"Groq returned empty choices (model={model})"
                )
            choice = resp.choices[0]
            content = getattr(choice.message, "content", None)
            return _normalize_json_response(
                content, model=model,
                prompt_chars=len(system_prompt) + len(json.dumps(user_payload)),
                finish_reason=getattr(choice, "finish_reason", None),
            )
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries and _is_transient(str(exc)):
                temperature = min(1.0, temperature + 0.1)
                continue
            raise
    raise last_exc


def call_llm(system_prompt: str, user_payload: dict, model: str, *,
             temperature: float = 0.4, max_retries: int = 2) -> dict:
    """Provider-agnostic LLM call. Returns a JSON object (dict).

    Picks provider by `model`:
      - openai/gpt-4o-mini / gpt-4o / gpt-4-turbo / gpt-4.1 / gpt-3.5 / o1-* / o3-* / o4-*
            → OpenAI (requires OPENAI_API_KEY)
      - everything else (incl. openai/gpt-oss-120b, llama-*, etc.)
            → Groq (requires GROQ_API_KEY)

    Raises ImportError if the provider SDK isn't installed, RuntimeError if
    the API key is missing, and re-raises the last provider exception after
    transient retries are exhausted.
    """
    if _is_openai_model(model):
        return _call_openai(
            system_prompt, user_payload,
            model_id=model.removeprefix("openai/"),
            temperature=temperature, max_retries=max_retries,
        )
    return _call_groq(
        system_prompt, user_payload, model=model,
        temperature=temperature, max_retries=max_retries,
    )
