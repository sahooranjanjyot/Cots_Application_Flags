import uuid
from fastapi.testclient import TestClient
from main import app
from database import get_db, Base, engine

client = TestClient(app)

def test_dups_and_out_of_order():
    Base.metadata.create_all(bind=engine)
    from database import seed_static_limits
    seed_static_limits()
    
    evt_a = f"EVT-{uuid.uuid4().hex[:8]}"
    evt_b = f"EVT-{uuid.uuid4().hex[:8]}"
    evt_assy = f"EVT-{uuid.uuid4().hex[:8]}"

    # 1. Provide first SUB_ASSEMBLY and wait
    res_sub_1 = client.post("/api/v1/quality-results", json={
        "eventType": "QUALITY_RESULT",
        "eventId": evt_a,
        "sourceSystem": "MES-LINE-1",
        "entityType": "SUB_ASSEMBLY",
        "step": "DC_TOOL",
        "result": "PASS",
        "productId": "PA-101",
        "serialNumber": "SUB-A",
        "parentSerialNumber": "ASSY-ORDER-999",
        "timestamp": "2026-04-25T11:00:00Z"
    })
    assert res_sub_1.status_code == 200

    # 2. Trigger Duplicate of First
    res_sub_dup = client.post("/api/v1/quality-results", json={
        "eventType": "QUALITY_RESULT",
        "eventId": evt_a,
        "sourceSystem": "MES-LINE-1",
        "entityType": "SUB_ASSEMBLY",
        "step": "DC_TOOL",
        "result": "PASS",
        "productId": "PA-101",
        "serialNumber": "SUB-A",
        "parentSerialNumber": "ASSY-ORDER-999",
        "timestamp": "2026-04-25T11:00:00Z"
    })
    assert res_sub_dup.json()["reason"] == "DUPLICATE_EVENT"

    # 3. Trigger Out Of Order Assembly before FLUID_FILL
    res_assy_early = client.post("/api/v1/quality-results", json={
        "eventType": "QUALITY_RESULT",
        "eventId": evt_assy,
        "entityType": "ASSEMBLY",
        "step": "FINAL_ASSEMBLY",
        "result": "PASS",
        "productId": "PA-101",
        "serialNumber": "ASSY-ORDER-999",
        "timestamp": "2026-04-25T11:05:00Z"
    })
    assert res_assy_early.json()["message"] == "Event held waiting for dependencies"

    # 4. Provide the missing Sub-Assembly to trigger Asynchronous Re-Evaluation!
    res_sub_2 = client.post("/api/v1/quality-results", json={
        "eventType": "QUALITY_RESULT",
        "eventId": evt_b,
        "sourceSystem": "MES-LINE-1",
        "entityType": "SUB_ASSEMBLY",
        "step": "FLUID_FILL",
        "result": "PASS",
        "productId": "PA-101",
        "serialNumber": "SUB-B",
        "parentSerialNumber": "ASSY-ORDER-999",
        "timestamp": "2026-04-25T11:10:00Z"
    })
    print("SUB 2 Late Completion:", res_sub_2.json())
    assert res_sub_2.status_code == 200
