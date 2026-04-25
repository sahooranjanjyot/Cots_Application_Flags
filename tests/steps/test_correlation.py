from fastapi.testclient import TestClient
import uuid
from main import app
import json

client = TestClient(app)

def test_correlation_engine_workflow():
    parent_serial = f"PARENT-SN-{uuid.uuid4().hex[:6]}"
    child_serial_1 = f"CHILD1-{uuid.uuid4().hex[:6]}"
    child_serial_2 = f"CHILD2-{uuid.uuid4().hex[:6]}"
    
    # 1. Send Sub-Assembly 1
    sa1_payload = {
        "eventId": f"EV-SA1-{uuid.uuid4().hex[:4]}",
        "eventType": "QUALITY_RESULT",
        "sourceSystem": "TEST",
        "entityType": "SUB_ASSEMBLY",
        "serialNumber": child_serial_1,
        "parentSerialNumber": parent_serial,
        "step": "DC_TOOL_STEP",
        "result": "PASS",
        "productId": "ENG-A",
        "eventTimestamp": "2026-04-25T12:00:00Z"
    }
    
    resp1 = client.post("/api/v1/quality-results", json=sa1_payload)
    assert resp1.status_code == 200
    assert "Group correlation is IN_PROGRESS" in resp1.json()["message"]
    
    # 2. View Group Status
    resp_group = client.get(f"/api/v1/correlation/{parent_serial}")
    assert resp_group.status_code == 200
    assert resp_group.json()["status"] == "IN_PROGRESS"
    
    # 3. Send Main Assembly
    ma_payload = {
        "eventId": f"EV-MA-{uuid.uuid4().hex[:4]}",
        "eventType": "QUALITY_RESULT",
        "sourceSystem": "TEST",
        "entityType": "MAIN_ASSEMBLY",
        "serialNumber": parent_serial,
        "parentSerialNumber": None,
        "step": "DECKING_VISION",
        "result": "PASS",
        "productId": "CAR-Z",
        "eventTimestamp": "2026-04-25T12:05:00Z"
    }
    
    resp_ma = client.post("/api/v1/quality-results", json=ma_payload)
    assert resp_ma.status_code == 200
    assert "Group correlation is IN_PROGRESS" in resp_ma.json()["message"]
    
    # 4. Send Sub-Assembly 2
    sa2_payload = {
        "eventId": f"EV-SA2-{uuid.uuid4().hex[:4]}",
        "eventType": "QUALITY_RESULT",
        "sourceSystem": "TEST",
        "entityType": "SUB_ASSEMBLY",
        "serialNumber": child_serial_2,
        "parentSerialNumber": parent_serial,
        "step": "FLUID_FILL_STEP",
        "result": "PASS",
        "productId": "FLUID-X",
        "eventTimestamp": "2026-04-25T12:10:00Z"
    }
    
    resp_sa2 = client.post("/api/v1/quality-results", json=sa2_payload)
    assert resp_sa2.status_code == 200
    
    # At this point, it should be COMPLETE and forwarded to FLAGS!
    resp_group_final = client.get(f"/api/v1/correlation/{parent_serial}")
    assert resp_group_final.status_code == 200
    assert resp_group_final.json()["status"] == "COMPLETE"

def test_correlation_failure():
    parent_serial = f"PARENT-SN-{uuid.uuid4().hex[:6]}"
    child_serial_1 = f"CHILD1-{uuid.uuid4().hex[:6]}"
    child_serial_2 = f"CHILD2-{uuid.uuid4().hex[:6]}"
    
    # 1. Main Assembly
    ma_payload = {
        "eventId": f"EV-MA-{uuid.uuid4().hex[:4]}",
        "eventType": "QUALITY_RESULT",
        "sourceSystem": "TEST",
        "entityType": "MAIN_ASSEMBLY",
        "serialNumber": parent_serial,
        "parentSerialNumber": None,
        "step": "DECKING_VISION",
        "result": "PASS",
        "productId": "CAR-Z",
        "eventTimestamp": "2026-04-25T12:00:00Z"
    }
    client.post("/api/v1/quality-results", json=ma_payload)
    
    # 2. Sub-Assembly exactly FAIL
    sa1_payload = {
        "eventId": f"EV-SA1-{uuid.uuid4().hex[:4]}",
        "eventType": "QUALITY_RESULT",
        "sourceSystem": "TEST",
        "entityType": "SUB_ASSEMBLY",
        "serialNumber": child_serial_1,
        "parentSerialNumber": parent_serial,
        "step": "DC_TOOL_STEP",
        "result": "FAIL",
        "productId": "ENG-A",
        "defectCode": "D001",
        "defectDescription": "Loose bolt",
        "eventTimestamp": "2026-04-25T12:05:00Z"
    }
    resp = client.post("/api/v1/quality-results", json=sa1_payload)
    assert resp.status_code == 400
    assert "Correlation Failure: Sub-assemblies did not pass" in resp.json()["detail"]
    
    resp_group = client.get(f"/api/v1/correlation/{parent_serial}")
    assert resp_group.json()["status"] == "FAILED"
