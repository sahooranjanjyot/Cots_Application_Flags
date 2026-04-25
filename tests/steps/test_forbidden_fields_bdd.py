import pytest
from pytest_bdd import scenario, given, when, then
from fastapi.testclient import TestClient
from main import app
import uuid

client = TestClient(app)

@scenario("../features/forbidden_fields.feature", "PASS event contains defectCode")
def test_pass_with_defect():
    pass

@scenario("../features/forbidden_fields.feature", "PASS event contains override fields")
def test_pass_with_override():
    pass

@given("MES sends a PASS event with defectCode", target_fixture="invalid_payload")
def pass_with_defectCode_payload():
    return {
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-FORBID-{uuid.uuid4().hex[:8]}",
        "step": "DC_TOOL_STEP",
        "result": "PASS",
        "productId": "PA-100",
        "serialNumber": "SN-FORBID-1",
        "timestamp": "2026-04-25T11:00:00Z",
        "defectCode": "DEF-001"
    }

@given("MES sends a PASS event with overrideReasonCode", target_fixture="invalid_payload")
def pass_with_overrideReasonCode_payload():
    return {
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-FORBID-{uuid.uuid4().hex[:8]}",
        "step": "DC_TOOL_STEP",
        "result": "PASS",
        "productId": "PA-100",
        "serialNumber": "SN-FORBID-2",
        "timestamp": "2026-04-25T11:00:00Z",
        "overrideReasonCode": "ORC-999"
    }

# Re-use from exception handling where possible, but BDD fixtures must match strings exactly
# Wait, if "validation should fail" is already defined in test_exception_handling_bdd.py, 
# Pytest-bdd throws errors if identical text is defined in multiple conftests or files, UNLESS we use same file or pytest_bdd import.
# Since these are standalone step files, let's redefine them locally OR move to conftest.py. Actually, pytest_bdd allows them to be local if the scenarios are in THIS file.
@when("the system processes the event", target_fixture="response")
def process_event(invalid_payload):
    return client.post("/api/v1/quality-results", json=invalid_payload)

@then("validation should fail")
def check_validation_should_fail(response):
    assert response.status_code == 400

@then("event should not be sent to FLAGS")
def check_not_sent_to_flags(invalid_payload):
    # Validation occurred via 400 error, so it wasn't pushed to RabbitMQ or QualityEvent.
    # We can check EventStore/QualityEvent but a 400 guarantees it stopped early.
    from database import SessionLocal, QualityEvent
    db = SessionLocal()
    event = db.query(QualityEvent).filter(QualityEvent.event_id == invalid_payload.get("eventId")).first()
    # Event does get inserted into QualityEvent by push_to_dlq's log_to_db, but as FAILED
    assert event is not None
    assert event.validation_status == "FAILED"
    assert event.transmission_status == "FAILED"
    db.close()
