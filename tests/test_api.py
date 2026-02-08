"""Tests for FastAPI endpoints."""
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
def client():
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    )


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_process_text_fast_track(client):
    text = """
    POLICY NUMBER: POL-001
    NAME OF INSURED: Jane Doe
    DATE OF LOSS: 01/20/2024
    Location: 100 Main St, Austin TX
    Description: Rear-ended at stoplight. No injuries.
    ESTIMATE AMOUNT: $5,000
    Claim type: auto
    """
    r = await client.post("/api/v1/process/text", json={"content": text})
    assert r.status_code == 200
    data = r.json()
    assert "extractedFields" in data
    assert "missingFields" in data
    assert data["recommendedRoute"] == "Fast-track"
    assert "reasoning" in data


@pytest.mark.asyncio
async def test_process_text_manual_review(client):
    text = "Policyholder: Only name. No policy number, no date, no location, no estimate."
    r = await client.post("/api/v1/process/text", json={"content": text})
    assert r.status_code == 200
    data = r.json()
    assert len(data["missingFields"]) > 0
    assert data["recommendedRoute"] == "Manual review"


@pytest.mark.asyncio
async def test_process_file_txt(client):
    sample = Path(__file__).parent.parent / "samples" / "fnol_sample_complete.txt"
    if not sample.exists():
        pytest.skip("Sample file not found")
    with open(sample, "rb") as f:
        r = await client.post("/api/v1/process", files={"file": ("fnol.txt", f, "text/plain")})
    assert r.status_code == 200
    data = r.json()
    assert "extractedFields" in data
    assert data["recommendedRoute"] in ("Fast-track", "Standard", "Manual review", "Investigation Flag", "Specialist Queue")


@pytest.mark.asyncio
async def test_process_file_rejects_unsupported(client):
    r = await client.post("/api/v1/process", files={"file": ("x.docx", b"binary", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_process_text_empty(client):
    r = await client.post("/api/v1/process/text", json={"content": ""})
    assert r.status_code == 422 or r.status_code == 400
