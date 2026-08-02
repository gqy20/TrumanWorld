import httpx
import pytest

from app.cli.client import ApiClient, ApiClientError


def test_api_client_sends_admin_header_and_parses_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-demo-admin-password"] == "secret"
        return httpx.Response(200, json={"status": "ok"})

    with ApiClient(
        "http://test/api", admin_password="secret", transport=httpx.MockTransport(handler)
    ) as client:
        assert client.get("health") == {"status": "ok"}


@pytest.mark.parametrize(("status", "exit_code"), [(401, 5), (404, 6), (409, 7), (422, 8)])
def test_api_client_maps_http_errors_to_stable_exit_codes(status: int, exit_code: int):
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(status, json={"detail": "failed", "code": "TEST"})
    )
    with ApiClient("http://test/api", transport=transport) as client:
        with pytest.raises(ApiClientError) as raised:
            client.get("runs/missing")
    assert raised.value.exit_code == exit_code
    assert "failed" in str(raised.value)


def test_api_client_decodes_sse_events():
    body = 'retry: 3000\n\nid: evt-1\nevent: world_event\ndata: {"tick_no":2}\n\n'
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200, text=body, headers={"content-type": "text/event-stream"}
        )
    )
    with ApiClient("http://test/api", transport=transport) as client:
        events = list(client.stream_events("runs/run-1/events/stream"))
    assert events == [{"event": "world_event", "id": "evt-1", "data": {"tick_no": 2}}]
