from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from typing import Any

import httpx

from app.api.auth import DEMO_ADMIN_HEADER


class ApiClientError(RuntimeError):
    def __init__(self, message: str, *, exit_code: int = 8) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class ApiClient:
    def __init__(
        self,
        base_url: str,
        *,
        admin_password: str | None = None,
        timeout: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        headers = {"Accept": "application/json", "User-Agent": "truman-cli/0.1"}
        if admin_password:
            headers[DEMO_ADMIN_HEADER] = admin_password
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(headers=headers, timeout=timeout, transport=transport)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ApiClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            response = self._client.request(method, url, params=params, json=json_body)
        except httpx.TimeoutException as exc:
            raise ApiClientError(f"Request timed out: {url}", exit_code=9) from exc
        except httpx.HTTPError as exc:
            raise ApiClientError(f"Cannot reach API at {url}: {exc}", exit_code=4) from exc
        if response.is_success:
            if not response.content:
                return None
            try:
                return response.json()
            except ValueError as exc:
                raise ApiClientError(f"API returned invalid JSON: {url}") from exc
        self._raise_response_error(response)

    def get(self, path: str, *, params: Mapping[str, Any] | None = None) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, *, json_body: Any = None) -> Any:
        return self.request("POST", path, json_body=json_body)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)

    def stream_events(
        self, path: str, *, params: Mapping[str, Any] | None = None
    ) -> Iterator[dict[str, Any]]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            with self._client.stream(
                "GET", url, params=params, headers={"Accept": "text/event-stream"}
            ) as response:
                if not response.is_success:
                    response.read()
                    self._raise_response_error(response)
                event_name = "message"
                event_id: str | None = None
                data_lines: list[str] = []
                for line in response.iter_lines():
                    if not line:
                        if data_lines:
                            raw = "\n".join(data_lines)
                            try:
                                data = json.loads(raw)
                            except ValueError:
                                data = raw
                            yield {"event": event_name, "id": event_id, "data": data}
                        event_name, event_id, data_lines = "message", None, []
                    elif line.startswith("event:"):
                        event_name = line[6:].strip()
                    elif line.startswith("id:"):
                        event_id = line[3:].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[5:].strip())
        except httpx.TimeoutException as exc:
            raise ApiClientError(f"Event stream timed out: {url}", exit_code=9) from exc
        except httpx.HTTPError as exc:
            raise ApiClientError(f"Event stream failed: {url}: {exc}", exit_code=4) from exc

    @staticmethod
    def _raise_response_error(response: httpx.Response) -> None:
        detail = response.text
        try:
            payload = response.json()
            error = payload.get("error", payload) if isinstance(payload, dict) else payload
            if isinstance(error, dict):
                detail = str(
                    error.get("detail") or error.get("message") or error.get("code") or detail
                )
        except ValueError:
            pass
        exit_code = {401: 5, 403: 5, 404: 6, 409: 7}.get(response.status_code, 8)
        raise ApiClientError(f"API {response.status_code}: {detail}", exit_code=exit_code)
