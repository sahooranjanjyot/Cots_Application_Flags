import pytest
from pytest_bdd import scenario, given, when, then
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, ExceptionEvent
import uuid

client = TestClient(app)

@scenario("../features/exception_handling.feature", "Validation failure goes to exception queue")
def test_validation_failure():
    pass

@scenario("../features/exception_handling.feature", "Rule not found")
def test_rule_not_found():
    pass

@scenario("../features/exception_handling.feature", "Exception resolved")
def test_exception_resolved():
    pass

@given("MES sends an invalid event missing mandatory fields", target_fixture="invalid_payload")
def missing_mandatory_fields_payload():
    return {
        "eventType": "QUALITY_RESULT",
        # Missing eventId
        "step": "DC_TOOL_STEP",
        "result": "PASS",
        "productId": "PA-100",
        "serialNumber": "SN-EXC-1",
        "timestamp": "2026-04-25T11:00:00Z"
    }

@given("MES sends an event with unknown processStep", target_fixture="invalid_payload")
def unknown_process_step_payload():
    return {
        "eventId": f"EVT-EXC-{uuid.uuid4().hex[:8]}",
        "eventType": "QUALITY_RESULT",
        "step": "UNKNOWN_STEP_XXX",
        "result": "PASS",
        "productId": "PA-100",
        "serialNumber": "SN-EXC-2",
        "timestamp": "2026-04-25T11:00:00Z"
    }

@when("the system processes the event", target_fixture="response")
def process_event(invalid_payload):
    return client.post("/api/v1/quality-results", json=invalid_payload)

@then("validation should fail")
def check_validation_should_fail(response):
    assert response.status_code == 400

@then("the event should be stored in exception queue")
def check_stored_in_exception_queue(invalid_payload):
    db = SessionLocal()
    # It might lack an explicit event_id if eventId was stripped, so check by raw_payload
    exc = db.query(ExceptionEvent).filter(ExceptionEvent.raw_payload.contains(invalid_payload["serialNumber"])).first()
    assert exc is not None
    db.close()

@then("the event should be rejected")
def check_event_rejected(response):
    # BDD says "the event should be rejected"
    assert response.status_code == 400

@then("stored in exception queue")
def check_stored_in_exception_queue_2(invalid_payload):
    db = SessionLocal()
    exc = db.query(ExceptionEvent).filter(ExceptionEvent.event_id == invalid_payload.get("eventId")).first()
    assert exc is not None
    db.close()

# For the third scenario
@given("an event exists in exception queue", target_fixture="exception_id")
def an_event_exists_in_exception_queue():
    db = SessionLocal()
    exc = ExceptionEvent(
        event_id="EVT-EXC-RESOLVE",
        exception_type="VALIDATION_FAILED",
        exception_reason="Manual test insertion",
        raw_payload="{}"
    )
    db.add(exc)
    db.commit()
    db.refresh(exc)
    exc_id = exc.id
    db.close()
    return exc_id

@when("support resolves the issue", target_fixture="resolve_response")
def support_resolves_the_issue(exception_id):
    return client.post(f"/api/v1/exceptions/{exception_id}/resolve?resolvedBy=SupportTeam")

@then("the event should be marked as resolved")
def check_marked_as_resolved(exception_id, resolve_response):
    assert resolve_response.status_code == 200
    db = SessionLocal()
    exc = db.query(ExceptionEvent).filter(ExceptionEvent.id == exception_id).first()
    assert exc.resolved is True
    assert exc.resolved_by == "SupportTeam"
    db.close()
