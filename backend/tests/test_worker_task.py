from relationship_network_api.tasks import SMOKE_TASK_NAME, smoke_payload


def test_smoke_task_returns_correlated_success() -> None:
    # Given a caller-provided correlation identifier
    request_id = "smoke-test-001"

    # When the worker executes the public smoke task
    result = smoke_payload(request_id)

    # Then the result proves the same task instance completed
    assert result == {"request_id": request_id, "status": "ok"}
    assert SMOKE_TASK_NAME == "relationship_network.smoke"
