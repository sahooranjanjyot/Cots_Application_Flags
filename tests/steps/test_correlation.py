import uuid
from fastapi.testclient import TestClient
from main import app
from database import get_db, Base, engine

client = TestClient(app)

def test_correlation_flow():
    Base.metadata.create_all(bind=engine)
    from database import seed_static_limits
    seed_static_limits()
    
    # 1. Provide first SUB_ASSEMBLY
    res1 = client.post("/api/v1/quality-results", json={
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-{uuid.uuid4().hex[:8]}",
        "entityType": "SUB_ASSEMBLY",
        "step": "DC_TOOL",
        "result": "PASS",
        "productId": "PA-101",
        "serialNumber": "SUB-001",
        "parentSerialNumber": "ASSY-999",
        "timestamp": "2026-04-25T11:00:00Z"
    })
    print(res1.json())
    assert res1.status_code == 200
    
    # 2. Provide second SUB_ASSEMBLY
    res2 = client.post("/api/v1/quality-results", json={
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-{uuid.uuid4().hex[:8]}",
        "entityType": "SUB_ASSEMBLY",
        "step": "FLUID_FILL",
        "result": "PASS",
        "productId": "PA-101",
        "serialNumber": "SUB-002",
        "parentSerialNumber": "ASSY-999",
        "timestamp": "2026-04-25T11:01:00Z"
    })
    print(res2.json())
    assert res2.status_code == 200

    # 3. Provide FINAL ASSEMBLY
    res3 = client.post("/api/v1/quality-results", json={
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-{uuid.uuid4().hex[:8]}",
        "entityType": "ASSEMBLY",
        "step": "FINAL_ASSEMBLY",
        "result": "PASS",
        "productId": "PA-101",
        "serialNumber": "ASSY-999",
        "timestamp": "2026-04-25T11:10:00Z"
    })
    
    print(res3.json())
    assert res3.status_code == 200
    assert "SUCCESS" in res3.json()["status"] 
    # Test passed perfectly!
    
# test_correlation_flow()
