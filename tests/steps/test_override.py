import uuid
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_override():
    response = client.post("/api/v1/quality-results", json={
       "step": "ROUTE",
       "originalResult": "FAIL",
       "overrideResult": "PASS",
       "eventId": f"EVT-{uuid.uuid4().hex[:8]}",
       "productId": "P12345",
       "serialNumber": "SN-OVR-01",
       "timestamp": "2026-04-25T10:05:00Z",
       "overrideBy": "MANAGER-01",
       "overrideTimestamp": "2026-04-25T10:06:00Z",
       "overrideReasonCode": "OVR-R01",
       "eventType": "QUALITY_RESULT"
    })
    print(response.text)
    assert response.status_code == 200
