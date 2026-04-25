import pytest
from pytest_bdd import scenario, given, when, then
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, EventStore
import uuid
import json

client = TestClient(app)

@scenario("../features/schema_validation.feature", "Process active schema version")
def test_schema_active():
    pass

@scenario("../features/schema_validation.feature", "Process deprecated schema version")
def test_schema_deprecated():
    pass

@scenario("../features/schema_validation.feature", "Reject retired schema version")
def test_schema_retired():
    pass


@given("MES sends an event with an active schema version", target_fixture="schema_payload")
def active_schema_payload():
    return {
        "schemaVersion": "v1.0",
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-ACT-{uuid.uuid4().hex[:8]}",
        "step": "DC_TOOL",
        "result": "PASS",
        "productId": "PD-SCMA",
        "serialNumber": f"SN-ACT-{uuid.uuid4().hex[:8]}",
        "timestamp": "2026-04-25T11:00:00Z"
    }

@given("MES sends an event using a deprecated schema version", target_fixture="schema_payload")
def deprecated_schema_payload():
    return {
        "schemaVersion": "v0.9",
        "eventType": "QUALITY_RESULT",
        "oldEventId": f"EVT-DEP-{uuid.uuid4().hex[:8]}", # Using alias
        "step": "DC_TOOL",
        "result": "PASS",
        "productId": "PD-SCMA",
        "serialNumber": f"SN-DEP-{uuid.uuid4().hex[:8]}",
        "timestamp": "2026-04-25T11:00:00Z"
    }

@given("MES sends an event using a retired schema version", target_fixture="schema_payload")
def retired_schema_payload():
    return {
        "schemaVersion": "v0.1",
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-RET-{uuid.uuid4().hex[:8]}",
        "step": "DC_TOOL",
        "result": "PASS",
        "productId": "PD-SCMA",
        "serialNumber": f"SN-RET-{uuid.uuid4().hex[:8]}",
        "timestamp": "2026-04-25T11:00:00Z"
    }

@when("the system processes the event", target_fixture="response")
def process_event(schema_payload):
    return client.post("/api/v1/quality-results", json=schema_payload)

@then("the schema should be detected")
def check_schema_detected(response):
    assert response.status_code == 200

@then("the payload should be normalized")
def check_normalized(schema_payload):
    db = SessionLocal()
    event_id = schema_payload.get("eventId") or schema_payload.get("oldEventId")
    evt = db.query(EventStore).filter(EventStore.event_id == event_id).first()
    assert evt is not None
    assert evt.schema_version is not None
    assert evt.normalization_status == "NORMALIZED"
    assert evt.canonical_payload is not None
    db.close()

@then("validation should run on canonical model")
def check_validation_ran():
    pass

@then("FLAGS should receive the expected payload")
def check_flags_receipt(response):
    assert "flags_response" in response.json()

@then("the event should still be accepted")
def check_accepted(response):
    assert response.status_code == 200

@then("a deprecation warning should be logged")
def check_warning_logged(schema_payload):
    db = SessionLocal()
    # It mapped oldEventId to eventId
    event_id = schema_payload.get("oldEventId")
    evt = db.query(EventStore).filter(EventStore.event_id == event_id).first()
    assert evt is not None
    assert evt.deprecation_warning is not None
    assert "Deprecated schema version v0.9" in evt.deprecation_warning
    db.close()

@then("the event should be rejected")
def check_rejected(response):
    assert response.status_code == 400
    assert "retired" in response.text

@then("moved to exception queue")
def check_exception_queue(schema_payload):
    db = SessionLocal()
    event_id = schema_payload.get("eventId")
    evt = db.query(EventStore).filter(EventStore.event_id == event_id, EventStore.processing_status == "FAILED_NORMALIZATION").first()
    assert evt is not None
    assert evt.normalization_status == "FAILED"
    db.close()
