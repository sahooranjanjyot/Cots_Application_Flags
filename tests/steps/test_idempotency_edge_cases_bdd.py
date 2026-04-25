import pytest
from pytest_bdd import scenario, given, when, then
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, EventStore
import uuid

client = TestClient(app)

@scenario("../features/idempotency_edge_cases.feature", "Same event with different payload content")
def test_same_event_different_data():
    pass

@scenario("../features/idempotency_edge_cases.feature", "Replay does not duplicate")
def test_replay_does_not_duplicate():
    pass

@pytest.fixture
def unique_event_id():
    return f"EVT-IDEMP-{uuid.uuid4().hex[:8]}"
    
@given("MES sends an event with same eventId but modified data", target_fixture="idempotency_context")
def push_modified_data(unique_event_id):
    # First dispatch
    payload1 = {
        "eventType": "QUALITY_RESULT",
        "eventId": unique_event_id,
        "step": "DC_TOOL_STEP",
        "result": "PASS",
        "productId": "PA-100",
        "serialNumber": "SN-ORG-1",
        "timestamp": "2026-04-25T11:00:00Z"
    }
    resp1 = client.post("/api/v1/quality-results", json=payload1)
    assert resp1.status_code == 200
    
    # Second dispatch with same ID but different metadata
    payload2 = dict(payload1)
    payload2["serialNumber"] = "SN-MODIFIED-999"
    return payload2

@when("the system processes the event", target_fixture="response")
def process_event(idempotency_context):
    return client.post("/api/v1/quality-results", json=idempotency_context)

@then("duplicate should be detected")
def check_duplicate_detected(response):
    assert response.status_code == 200
    assert response.json().get("status") == "IGNORED"
    assert response.json().get("reason") == "DUPLICATE_EVENT"

@then("event should not be reprocessed")
def check_not_reprocessed(idempotency_context):
    # Because it is ignored, EventStore should only reflect the FIRST serialization payload, meaning 
    # original payload 'SN-ORG-1' wasn't overwritten by 'SN-MODIFIED-999' entirely for tracking,
    # Or, there's a DUPLICATE_IGNORED row tracked.
    db = SessionLocal()
    # It stores the duplicate attempt in EventStore with DUPLICATE_IGNORED
    dups = db.query(EventStore).filter(
        EventStore.event_id == idempotency_context["eventId"],
        EventStore.processing_status == "DUPLICATE_IGNORED"
    ).all()
    assert len(dups) > 0
    db.close()

# Scenario 2: Replay does not duplicate

@given("an event has already been processed", target_fixture="replay_context")
def event_already_processed(unique_event_id):
    payload = {
        "eventType": "QUALITY_RESULT",
        "eventId": unique_event_id,
        "step": "DC_TOOL_STEP",
        "result": "PASS",
        "productId": "PA-100",
        "serialNumber": "SN-REPLAY-1",
        "timestamp": "2026-04-25T11:00:00Z"
    }
    client.post("/api/v1/quality-results", json=payload)
    return unique_event_id

@when("replay is triggered", target_fixture="response")
def trigger_replay(replay_context):
    return client.post(f"/api/v1/events/{replay_context}/replay")

@then("FLAGS should not receive duplicate record")
def check_no_duplicate_records(replay_context):
    from database import SessionLocal, QualityEvent, ProcessingAttempt
    db = SessionLocal()
    # It's in QualityEvent exactly ONCE
    q_events = db.query(QualityEvent).filter(QualityEvent.event_id == replay_context).all()
    assert len(q_events) == 1
    
    # And there is a REPLAY tracked
    attempts = db.query(ProcessingAttempt).filter(
        ProcessingAttempt.event_id == replay_context,
        ProcessingAttempt.attempt_type == "REPLAY"
    ).all()
    assert len(attempts) > 0
    db.close()
