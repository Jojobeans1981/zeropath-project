import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_create_scan(auth_client):
    # Create a repo first
    repo_res = await auth_client.post("/api/repos/", json={
        "url": "https://github.com/pallets/flask",
    })
    repo_id = repo_res.json()["data"]["id"]

    with patch("app.workers.scan_worker.run_scan") as mock_task:
        mock_task.delay = MagicMock()
        res = await auth_client.post("/api/scans/", json={
            "repo_id": repo_id,
        })
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "queued"


@pytest.mark.asyncio
async def test_create_scan_invalid_repo(auth_client):
    with patch("app.workers.scan_worker.run_scan") as mock_task:
        mock_task.delay = MagicMock()
        res = await auth_client.post("/api/scans/", json={
            "repo_id": "00000000-0000-0000-0000-000000000000",
        })
    assert res.status_code == 404
