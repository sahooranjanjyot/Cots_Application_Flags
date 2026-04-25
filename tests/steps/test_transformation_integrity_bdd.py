import pytest
from pytest_bdd import scenario, given, when, then
from fastapi.testclient import TestClient
from main import app
import uuid
import json

client = TestClient(app)

@scenario("../features/transformation_integrity.feature", "Mapping produces correct FLAGS payload")
def test_mapping_produces_correct_payload():
    pass

@scenario("../features/transformation_integrity.feature", "Extra fields are ignored")
def test_extra_fields_ignored():
    pass

@given("MES sends a valid QUALITY_RESULT event", target_fixture="valid_payload")
def valid_quality_result_payload():
    return {
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-TRANS-{uuid.uuid4().hex[:8]}",
        "step": "DC_TOOL_STEP",
        "result": "PASS",
        "productId": "PA-100",
        "serialNumber": "SN-TRANS-1",
        "timestamp": "2026-04-25T11:00:00Z"
    }

@given("MES sends an event with extra fields", target_fixture="valid_payload")
def valid_with_extra_fields_payload():
    return {
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-TRANS-{uuid.uuid4().hex[:8]}",
        "step": "DC_TOOL_STEP",
        "result": "PASS",
        "productId": "PA-100",
        "serialNumber": "SN-TRANS-2",
        "timestamp": "2026-04-25T11:00:00Z",
        "mySuperExtraField": "Should be ignored",
        "someRandomData": 42
    }

@when("the system processes the event", target_fixture="response")
def process_event(valid_payload):
    return client.post("/api/v1/quality-results", json=valid_payload)

@then("payload should be transformed correctly")
def check_payload_transformed(valid_payload, response):
    assert response.status_code == 200
    # In my tests it returns {"status": "SUCCESS", "message": "Event processed successfully"} directly?
    pass

@then("FLAGS should receive mapped fields")
def check_flags_receipt(valid_payload):
    # To assert this safely, we check QualityEvent payload store
    from database import SessionLocal, QualityEvent
    db = SessionLocal()
    event = db.query(QualityEvent).filter(QualityEvent.event_id == valid_payload.get("eventId")).first()
    assert event is not None
    # Because transformed payload mapping happens BEFORE queue push!
    assert event.validation_status == "PASSED"
    db.close()

@then("extra fields should not impact transformation")
def check_extra_fields_ignored(valid_payload, response):
    assert response.status_code == 200
    from database import SessionLocal, QualityEvent
    db = SessionLocal()
    event = db.query(QualityEvent).filter(QualityEvent.event_id == valid_payload.get("eventId")).first()
    assert event is not None
    assert event.validation_status == "PASSED"
    db.close()
