import uuid
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_valid_payload():
    payload = {
      "eventType": "QUALITY_RESULT",
      "eventId": f"EVT-{uuid.uuid4().hex[:8]}",
      "step": "ROUTE",
      "result": "PASS",
      "productId": f"P-{uuid.uuid4().hex[:5]}",
      "serialNumber": f"SN-{uuid.uuid4().hex[:5]}",
      "timestamp": "2026-04-25T10:00:00Z",
      "stationId": f"ST-{uuid.uuid4().hex[:4]}",
      "operatorId": f"OP-{uuid.uuid4().hex[:4]}"
    }
    response = client.post("/api/v1/quality-results", json=payload)
    assert response.status_code == 200

def test_invalid_step():
    payload = {
      "eventType": "QUALITY_RESULT",
      "eventId": f"EVT-{uuid.uuid4().hex[:8]}",
      "step": "INVALID_STEP",
      "result": "PASS",
      "productId": f"P-{uuid.uuid4().hex[:5]}",
      "serialNumber": f"SN-{uuid.uuid4().hex[:5]}",
      "timestamp": "2026-04-25T10:00:00Z"
    }
    response = client.post("/api/v1/quality-results", json=payload)
    assert response.status_code == 400
    assert "Unknown valid step" in response.text

def test_invalid_result_for_route():
    payload = {
      "eventType": "QUALITY_RESULT",
      "eventId": f"EVT-{uuid.uuid4().hex[:8]}",
      "step": "ROUTE",
      "result": "UNKNOWN_RESULT",
      "productId": f"P-{uuid.uuid4().hex[:5]}",
      "serialNumber": f"SN-{uuid.uuid4().hex[:5]}",
      "timestamp": "2026-04-25T10:00:00Z"
    }
    response = client.post("/api/v1/quality-results", json=payload)
    assert response.status_code == 400

def test_pass_with_error_code():
    payload = {
      "eventType": "QUALITY_RESULT",
      "eventId": f"EVT-{uuid.uuid4().hex[:8]}",
      "step": "ROUTE",
      "result": "PASS",
      "productId": f"P-{uuid.uuid4().hex[:5]}",
      "serialNumber": f"SN-{uuid.uuid4().hex[:5]}",
      "timestamp": "2026-04-25T10:00:00Z",
      "errorCode": f"E-{uuid.uuid4().hex[:4]}"
    }
    response = client.post("/api/v1/quality-results", json=payload)
    assert response.status_code == 400
    assert "errorCode is forbidden" in response.text

def test_missing_mandatory_field():
    payload = {
      "eventType": "QUALITY_RESULT",
      "eventId": f"EVT-{uuid.uuid4().hex[:8]}",
      "step": "ROUTE",
      "result": "PASS"
    }
    response = client.post("/api/v1/quality-results", json=payload)
    assert response.status_code == 400
    assert "Validation Error" in response.text
