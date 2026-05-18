from __future__ import annotations

import json
import logging

from app.infra.logging import (
    JsonFormatter,
    RequestContextFilter,
    bind_log_context,
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
    assert payload["logger"] == "trumanworld.test"
    assert payload["message"] == "tick completed"
    assert payload["request_id"] == "req-json-1"
    assert payload["run_id"] == "run-1"
    assert payload["tick"] == 7
    assert payload["agent_id"] == "agent-1"
