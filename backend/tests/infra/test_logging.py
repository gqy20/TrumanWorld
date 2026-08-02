from __future__ import annotations

import json
import logging
import sys

import pytest

from app.infra.logging import (
    JsonFormatter,
    LOG_SCHEMA_VERSION,
    REDACTED,
    RedactingTextFormatter,
    RequestContextFilter,
    bind_log_context,
    create_background_task,
    get_log_context,
    get_request_id,
    reset_log_context,
    reset_request_id,
    set_request_id,
)


def test_json_formatter_includes_context_and_extra_fields():
    request_token = set_request_id("req-json-1")
    context_token = bind_log_context(run_id="run-1", tick=7)
    try:
        record = logging.LogRecord(
            name="trumanworld.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=12,
            msg="tick completed",
            args=(),
            exc_info=None,
        )
        record.agent_id = "agent-1"

        RequestContextFilter().filter(record)
        payload = json.loads(JsonFormatter().format(record))
    finally:
        reset_log_context(context_token)
        reset_request_id(request_token)

    assert payload["level"] == "INFO"
    assert payload["schema_version"] == LOG_SCHEMA_VERSION
    assert payload["service"] == "trumanworld-backend"
    assert payload["logger"] == "trumanworld.test"
    assert payload["message"] == "tick completed"
    assert payload["request_id"] == "req-json-1"
    assert payload["run_id"] == "run-1"
    assert payload["tick"] == 7
    assert payload["agent_id"] == "agent-1"


def test_json_formatter_redacts_sensitive_fields_and_values():
    record = logging.LogRecord(
        name="trumanworld.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=12,
        msg="database=postgresql://user:unsafe-password@db.local/app token=secret-value",
        args=(),
        exc_info=None,
    )
    record.api_key = "sk-this-must-not-appear"
    record.details = {"authorization": "Bearer secret-token", "safe": "visible"}

    payload = json.loads(JsonFormatter().format(record))
    serialized = json.dumps(payload)

    assert "unsafe-password" not in serialized
    assert "secret-value" not in serialized
    assert "sk-this-must-not-appear" not in serialized
    assert payload["api_key"] == REDACTED
    assert payload["details"]["authorization"] == REDACTED
    assert payload["details"]["safe"] == "visible"


@pytest.mark.asyncio
async def test_background_task_does_not_inherit_request_or_log_context():
    request_token = set_request_id("req-parent")
    context_token = bind_log_context(run_id="run-parent")

    async def read_context():
        return get_request_id(), dict(get_log_context())

    try:
        child_context = await create_background_task(read_context(), name="context-test")
    finally:
        reset_log_context(context_token)
        reset_request_id(request_token)

    assert child_context == (None, {})


def test_text_formatter_redacts_exception_messages():
    try:
        raise RuntimeError("authorization=Bearer unsafe-token")
    except RuntimeError:
        record = logging.LogRecord(
            name="trumanworld.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=12,
            msg="request failed",
            args=(),
            exc_info=sys.exc_info(),
        )

    formatted = RedactingTextFormatter("%(message)s").format(record)

    assert "unsafe-token" not in formatted
    assert REDACTED in formatted
