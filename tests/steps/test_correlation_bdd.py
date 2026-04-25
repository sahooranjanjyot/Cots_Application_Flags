import uuid
from pytest_bdd import scenario, given, when, then
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, CorrelationEvent

client = TestClient(app)

@scenario("../features/correlation_flow.feature", "Validate assembly correlation")
def test_correlation_bdd_flow():
    pass

@given("sub-assembly events are received", target_fixture="base_data")
def load_base_data():
    parent_serial = f"ASSY-{uuid.uuid4().hex[:5]}"
    return {
        "parent_sn": parent_serial,
        "subs": ["DC_TOOL", "FLUID_FILL"]
    }

@given("linked to a parent assembly")
def inject_sub_assemblies(base_data):
    for sub in base_data["subs"]:
        client.post("/api/v1/quality-results", json={
            "eventType": "QUALITY_RESULT",
            "eventId": f"EVT-{uuid.uuid4().hex[:8]}",
            "entityType": "SUB_ASSEMBLY",
            "step": sub,
            "result": "PASS",
            "productId": "PA-BDD",
            "serialNumber": f"SUB-{uuid.uuid4().hex[:5]}",
            "parentSerialNumber": base_data["parent_sn"],
            "timestamp": "2026-04-25T11:00:00Z"
        })

@when("the assembly event is processed", target_fixture="response")
def process_assembly(base_data):
    return client.post("/api/v1/quality-results", json={
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-{uuid.uuid4().hex[:8]}",
        "entityType": "ASSEMBLY",
        "step": "FINAL_ASSEMBLY",
        "result": "PASS",
        "productId": "PA-BDD",
        "serialNumber": base_data["parent_sn"],
        "timestamp": "2026-04-25T11:10:00Z"
    })

@then("all sub-assemblies should be validated")
def validate_subs(response):
    assert response.status_code == 200

@then("final result should be computed")
def compute_result(base_data):
    db = SessionLocal()
    event = db.query(CorrelationEvent).filter(CorrelationEvent.child_serial_number == base_data["parent_sn"], CorrelationEvent.entity_type == "ASSEMBLY").first()
    assert event is not None
    assert event.correlation_status == "COMPLETE"
    assert event.result == "PASS"
    db.close()

@then("FLAGS should receive complete correlated payload")
def check_flags_integration():
    from services import success_store
    mapped_payload = success_store[-1]
    assert "sub_assemblies" in mapped_payload
    assert len(mapped_payload["sub_assemblies"]) == 2
