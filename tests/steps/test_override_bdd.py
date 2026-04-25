import uuid
from pytest_bdd import scenario, given, when, then, parsers
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, QualityEvent

client = TestClient(app)

@scenario("../features/override_workflow.feature", "Validate workflow intercepts")
def test_override_generic_processing():
    pass

@given("an OVERRIDE quality result event", target_fixture="generic_payload")
def override_payload_init():
    return {
       "eventType": "QUALITY_RESULT",
       "eventId": f"EVT-{uuid.uuid4().hex[:8]}",
       "step": "ROUTE",
       "originalResult": "FAIL",
       "overrideResult": "PASS",
       "productId": f"P-{uuid.uuid4().hex[:5]}",
       "serialNumber": f"SN-{uuid.uuid4().hex[:5]}",
       "timestamp": "2026-04-25T12:00:00Z",
       "overrideBy": "AUTH-USER",
       "overrideTimestamp": "2026-04-25T12:05:00Z",
       "overrideReasonCode": "OVR-01"
    }

@given(parsers.parse("the approval requirement is {approval_req}"))
def add_approval_req(generic_payload, approval_req):
    if approval_req.lower() == "true":
        generic_payload["step"] = "ROUTE"
        generic_payload["approvalRequired"] = True
    else:
        generic_payload["step"] = "ROUTE_NO_APPROVAL"
        generic_payload["approvalRequired"] = False

@given(parsers.parse("the approval status is {status}"))
def add_status(generic_payload, status):
    if status != "NONE":
        generic_payload["approvalStatus"] = status

@when("the system processes the event", target_fixture="response")
def process_request(generic_payload):
    return client.post("/api/v1/quality-results", json=generic_payload)

@then(parsers.parse("the engine should react with {expected_behavior}"))
def check_behavior(response, expected_behavior):
    assert response.status_code == 200, f"Expected 200, got {response.status_code} - {response.text}"
    data = response.json()
    assert data["status"].upper() == expected_behavior.upper(), f"Expected behavior {expected_behavior}, got {data['status']}"
