import pytest
import uuid
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_schema_version_v1_0():
    uuid_str = uuid.uuid4().hex[:8]
    payload = {
        "schemaVersion": "v1.0",
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-V1-{uuid_str}",
        "step": "DC_TOOL",
        "result": "PASS",
        "productId": "PD-SCMA",
        "serialNumber": f"SN-SCMA-{uuid_str}",
        "timestamp": "2026-04-25T11:00:00Z"
    }
    res = client.post("/api/v1/quality-results", json=payload)
    assert res.status_code == 200

def test_schema_deprecated_with_alias():
    uuid_str = uuid.uuid4().hex[:8]
    # v0.9 uses oldEventId instead of eventId
    payload = {
        "schemaVersion": "v0.9",
        "eventType": "QUALITY_RESULT",
        "oldEventId": f"EVT-V09-{uuid_str}",
        "step": "DC_TOOL",
        "result": "PASS",
        "productId": "PD-SCMA",
        "serialNumber": f"SN-SCMA-{uuid_str}",
        "timestamp": "2026-04-25T11:00:00Z"
    }
    res = client.post("/api/v1/quality-results", json=payload)
    assert res.status_code == 200
    # It should pass without 'Missing mandatory field' because alias maps oldEventId -> eventId !

def test_schema_retired():
    uuid_str = uuid.uuid4().hex[:8]
    payload = {
        "schemaVersion": "v0.1",
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-V01-{uuid_str}",
        "step": "DC_TOOL",
        "result": "PASS"
    }
    res = client.post("/api/v1/quality-results", json=payload)
    assert res.status_code == 400
    assert "retired" in res.text

def test_missing_mandatory_schema_field():
    uuid_str = uuid.uuid4().hex[:8]
    payload = {
        "schemaVersion": "v1.0",
        "eventType": "QUALITY_RESULT",
        # missing eventId which is mandatory in schema
        "step": "DC_TOOL",
        "result": "PASS"
    }
    res = client.post("/api/v1/quality-results", json=payload)
    assert res.status_code == 400
    assert "Missing mandatory schema field: eventId" in res.text
