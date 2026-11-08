"""One bounded structured-output request; model tool names are data, never code.

Groq parameters checked against https://console.groq.com/docs/api-reference
and /docs/tool-use/local-tool-calling (2026-11-08).
"""
import json
import math
from types import SimpleNamespace

import httpx

from agents.secrets import get_secret


class ReviewError(Exception):
    """Safe category and schema diagnostics; never include argument values."""

    def __init__(self, category, validation_errors=None):
        super().__init__(category)
        self.validation_errors = validation_errors or []


class AgentResult(tuple):
    """Keep the public (findings, policies) unpacking contract with run status."""
    def __new__(cls, findings, policies, status="complete", error="", validation_errors=None):
        result = super().__new__(cls, (findings, policies))
        result.status = status
        result.error = error
        result.validation_errors = validation_errors or []
        return result


def provider_name():
    return get_secret("LLM_PROVIDER", "groq").lower()


def key_name():
    return {"groq": "GROQ_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}.get(provider_name(), "")


def configured():
    name = key_name()
    return bool(name and get_secret(name))


def model_name():
    if provider_name() == "anthropic":
        return get_secret("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    return get_secret("GROQ_MODEL", "openai/gpt-oss-20b")


def groq_tools(tools):
    return [{"type": "function", "function": {
        "name": tool["name"], "description": tool["description"],
        "parameters": {**tool["input_schema"], "additionalProperties": False},
    }} for tool in tools]


def _json_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "invalid JSON type"


def argument_errors(name, args, schema):
    """Return only schema-owned paths/expectations and types, never model values."""
    base = "tool_calls[0].function.arguments"
    if not isinstance(args, dict):
        return [{"path": base, "expected": "object", "actual": _json_type(args)}]
    errors = []
    properties = schema["properties"]
    for field in schema["required"]:
        if field not in args:
            errors.append({"path": base + "." + field,
                           "expected": properties[field]["type"], "actual": "missing"})
    # Unknown field names are model output too: do not echo arbitrary strings.
    if set(args) - set(properties):
        errors.append({"path": base + ".<additional_property>",
                       "expected": "no additional properties", "actual": "present"})
    for field, prop in properties.items():
        if field not in args:
            continue
        value = args[field]
        expected = prop["type"]
        actual = _json_type(value)
        if expected == "string" and (not isinstance(value, str) or not value.strip()):
            expected = "nonblank string"
            if actual == "string":
                actual = "blank string"
        elif expected == "number" and (
            type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1
        ):
            expected = "finite number in [0, 1]"
            if actual == "number":
                actual = "out-of-range or nonfinite number"
        elif "enum" in prop and value not in prop["enum"]:
            expected = "string enum: " + ", ".join(prop["enum"])
            actual = "invalid enum value (" + actual + ")"
        else:
            continue
        errors.append({"path": base + "." + field, "expected": expected, "actual": actual})
    return errors


def validate_tool_response(response, tools, policies):
    blocks = [b for b in response.content if b.type == "tool_use"]
    if len(blocks) != 1:
        raise ReviewError("invalid_response")
    block = blocks[0]
    allowed = {t["name"]: t["input_schema"] for t in tools}
    if block.name not in allowed:
        raise ReviewError("invalid_arguments", [{"path": "tool_calls[0].function.name",
            "expected": "one of: " + ", ".join(allowed), "actual": "unknown tool"}])
    errors = argument_errors(block.name, block.input, allowed[block.name])
    if errors:
        raise ReviewError("invalid_arguments", errors)
    if "citation_doc_id" in block.input:
        matches = [p for p in policies if p["document_id"] == block.input["citation_doc_id"]]
        if not matches:
            raise ReviewError("unknown_citation")
    return response


def complete(system, user, tools, policies):
    if not configured():
        raise ReviewError("missing_key")
    try:
        if provider_name() == "anthropic":
            import anthropic
            response = anthropic.Anthropic(api_key=get_secret(key_name())).messages.create(
                model=model_name(), max_tokens=1024, system=system, tools=tools,
                tool_choice={"type": "any"}, messages=[{"role": "user", "content": user}],
            )
            if getattr(response, "stop_reason", None) in ("max_tokens", "refusal"):
                raise ReviewError("invalid_response")
        else:
            with httpx.Client(timeout=45.0) as client:
                result = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": "Bearer " + get_secret(key_name())},
                    json={"model": model_name(), "messages": [
                        {"role": "system", "content": system}, {"role": "user", "content": user}],
                        "tools": groq_tools(tools), "tool_choice": "required",
                        "parallel_tool_calls": False, "max_completion_tokens": 4096},
                )
                result.raise_for_status()
                data = result.json()
            choices = data["choices"]
            if len(choices) != 1 or choices[0]["finish_reason"] != "tool_calls":
                raise ReviewError("invalid_response")
            calls = choices[0]["message"]["tool_calls"]
            response = SimpleNamespace(content=[])
            for call in calls:
                if call["type"] != "function":
                    raise ReviewError("invalid_response")
                function = call["function"]
                response.content.append(SimpleNamespace(type="tool_use", name=function["name"],
                    input=json.loads(function["arguments"])))
        return validate_tool_response(response, tools, policies)
    except ReviewError:
        raise
    except httpx.HTTPStatusError as exc:
        category = {401: "authentication", 403: "authentication", 429: "rate_limit"}.get(
            exc.response.status_code, "provider_error")
        raise ReviewError(category) from None
    except httpx.TimeoutException:
        raise ReviewError("timeout") from None
    except Exception:
        raise ReviewError("invalid_response_or_connection") from None
