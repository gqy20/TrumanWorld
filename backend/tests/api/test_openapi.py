import pytest


def _response_ref(document: dict, path: str, method: str, status_code: str) -> str | None:
    response = document["paths"][path][method]["responses"][status_code]
    content = response.get("content", {})
    json_content = content.get("application/json", {})
    schema = json_content.get("schema", {})
    return schema.get("$ref")


@pytest.mark.asyncio
async def test_openapi_exposes_expected_tag_groups(client):
    response = await client.get("/api/openapi.json")

    assert response.status_code == 200
    document = response.json()
    tag_names = {tag["name"] for tag in document["tags"]}
    assert tag_names == {
        "health",
        "runs",
        "agents",
        "world",
        "director",
        "system",
        "observability",
    }


@pytest.mark.asyncio
async def test_openapi_documents_core_response_models(client):
    response = await client.get("/api/openapi.json")

    assert response.status_code == 200
    document = response.json()

    assert (
        _response_ref(document, "/api/health", "get", "200")
        == "#/components/schemas/HealthResponse"
    )
    assert _response_ref(document, "/api/system/overview", "get", "200") == (
        "#/components/schemas/SystemOverviewResponse"
    )
    assert _response_ref(document, "/api/runs/{run_id}/timeline", "get", "200") == (
        "#/components/schemas/TimelineResponse"
    )
    assert _response_ref(document, "/api/runs/{run_id}/world", "get", "200") == (
        "#/components/schemas/WorldSnapshotResponse"
    )
    assert _response_ref(document, "/api/runs/{run_id}/director/observation", "get", "200") == (
        "#/components/schemas/DirectorObservationResponse"
    )
    assert _response_ref(document, "/api/runs/{run_id}/director/memories", "get", "200") == (
        "#/components/schemas/DirectorMemoriesResponse"
    )
    assert "/api/metrics" not in document["paths"]
