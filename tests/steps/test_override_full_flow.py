import uuid
from pytest_bdd import scenario, given, when, then, parsers
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, OverrideEvent

client = TestClient(app)

@scenario("../features/override_full_flow.feature", "Validate override flow")
def test_override_full_flow():
    pass

# Global UUID for this test run scope eliminating collisions
test_uuid = uuid.uuid4().hex[:5]
test_sn = f"SN-FLOW-{test_uuid}"

@given("MES sends a QUALITY_RESULT override event", target_fixture="override_payload")
def init_payload():
    return {
       "eventType": "QUALITY_RESULT",
       "eventId": f"EVT-{uuid.uuid4().hex[:8]}",
       "sourceSystem": "TEST",
       "entityType": "MAIN_ASSEMBLY",
       "step": "ROUTE_STEP",
       "productId": f"P-{test_uuid}",
       "serialNumber": test_sn,
       "eventTimestamp": "2026-04-25T12:00:00Z",
       "overrideBy": "AUTH-123",
       "overrideTimestamp": "2026-04-25T12:05:00Z",
       "overrideReasonCode": "OVR-01"
    }

@given(parsers.parse("original result is {orig}"))
def add_orig(override_payload, orig):
    override_payload["originalResult"] = orig

@given(parsers.parse("override result is {ovr}"))
def add_ovr(override_payload, ovr):
    override_payload["overrideResult"] = ovr

@given("approval is required")
def add_approv_req(override_payload):
    override_payload["approvalRequired"] = True

@when("the system processes the event", target_fixture="first_response")
def process_event(override_payload):
    return client.post("/api/v1/quality-results", json=override_payload)

@then("the event should be stored with PENDING status")
def check_pending_status(first_response):
    assert first_response.status_code == 200
    data = first_response.json()
    assert data["status"].upper() == "WORKFLOW_PENDING"
    
    db = SessionLocal()
    event = db.query(OverrideEvent).filter(OverrideEvent.serial_number == test_sn).order_by(OverrideEvent.created_at.desc()).first()
    assert event is not None
    assert event.transmission_status == "WORKFLOW_PENDING"
    db.close()

@when("approval is completed", target_fixture="second_response")
def approve_event(override_payload):
    # Simulate UI updating approval status
    req = {
        "reprocessRequestId": f"REQ-{uuid.uuid4().hex[:5]}",
        "eventId": override_payload["eventId"],
        "requestedBy": "QM-USR-01",
        "requestedTimestamp": "2026-04-25T11:15:00Z",
        "reprocessType": "MANUAL_RETRY",
        "reasonCode": "APPROVE_OVR",
        "approvalStatus": "APPROVED",
        "approverId": "SUP-01",
        "overrideValidation": True
    }
    return client.post("/api/v1/quality-results/reprocess", json=req)

@then("the event should be sent to FLAGS")
def check_sent_to_flags(second_response):
    assert second_response.status_code == 200
    data = second_response.json()
    assert data["status"] == "success"

@then("audit trail should be maintained")
def check_audit_trail():
    db = SessionLocal()
    events = db.query(OverrideEvent).filter(OverrideEvent.serial_number == test_sn).order_by(OverrideEvent.created_at.desc()).all()
    assert len(events) == 1
    assert events[0].transmission_status in ["SUCCESS", "SENT"]
    assert events[0].approval_status == "APPROVED"
    db.close()
