import pytest
from pytest_bdd import scenario, given, when, then
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, CorrelationGroup, QualityEvent
import uuid

client = TestClient(app)

@scenario("../features/out_of_order_processing.feature", "Main assembly arrives before sub-assembly")
def test_main_arrives_first():
    pass

@scenario("../features/out_of_order_processing.feature", "Dependent events complete later")
def test_dependent_events_complete_later():
    pass

@pytest.fixture
def ooo_context():
    return {
        "parent_sn": f"SN-PARENT-OOO-{uuid.uuid4().hex[:8]}",
        "sub_sn_1": f"SN-SUB1-{uuid.uuid4().hex[:8]}",
        "sub_sn_2": f"SN-SUB2-{uuid.uuid4().hex[:8]}"
    }

# SCENARIO 1

@given("a main assembly event arrives first", target_fixture="main_payload")
def main_assembly_payload(ooo_context):
    ooo_context["main_eventId"] = f"EVT-OOO-MAIN-{uuid.uuid4().hex[:8]}"
    return {
        "eventType": "QUALITY_RESULT",
        "eventId": ooo_context["main_eventId"],
        "step": "DECKING_VISION", # Requires DC_TOOL_STEP & FLUID_FILL_STEP
        "entityType": "MAIN_ASSEMBLY",
        "result": "PASS",
        "productId": "PA-100",
        "serialNumber": ooo_context["parent_sn"],
        "timestamp": "2026-04-25T11:00:00Z"
    }

@when("the system processes the event", target_fixture="response")
def process_main_event(main_payload):
    return client.post("/api/v1/quality-results", json=main_payload)

@then("the event should be held in correlation group")
def check_event_held(response, ooo_context):
    db = SessionLocal()
    group = db.query(CorrelationGroup).filter(CorrelationGroup.parent_serial_number == ooo_context["parent_sn"]).first()
    assert group is not None
    assert group.status == "IN_PROGRESS"
    db.close()

@then("not sent to FLAGS")
def check_not_sent(response, ooo_context):
    assert response.status_code == 200
    assert response.json().get("status") == "success"
    assert "IN_PROGRESS" in response.json().get("message")

# SCENARIO 2

@given("dependent sub-assembly events arrive later", target_fixture="sub_payloads")
def dependent_events_later(ooo_context):
    # This scenario depends on the previous state implicitly or sets it up manually.
    # For independent BDD tests, we should just fire the main assembly first so it's fresh.
    ooo_context["main_eventId_2"] = f"EVT-OOO-MAIN2-{uuid.uuid4().hex[:8]}"
    main_payload = {
        "eventType": "QUALITY_RESULT",
        "eventId": ooo_context["main_eventId_2"],
        "step": "DECKING_VISION",
        "entityType": "MAIN_ASSEMBLY",
        "result": "PASS",
        "productId": "PA-100",
        "serialNumber": ooo_context["parent_sn"],
        "timestamp": "2026-04-25T11:00:00Z"
    }
    client.post("/api/v1/quality-results", json=main_payload)
    
    # Then define the sub assemblies
    payloads = [
        {
            "eventType": "QUALITY_RESULT",
            "eventId": f"EVT-OOO-SUB1-{uuid.uuid4().hex[:8]}",
            "step": "DC_TOOL_STEP", 
            "entityType": "SUB_ASSEMBLY",
            "result": "PASS",
            "productId": "PA-100",
            "serialNumber": ooo_context["sub_sn_1"],
            "parentSerialNumber": ooo_context["parent_sn"],
            "timestamp": "2026-04-25T11:00:00Z"
        },
        {
            "eventType": "QUALITY_RESULT",
            "eventId": f"EVT-OOO-SUB2-{uuid.uuid4().hex[:8]}",
            "step": "FLUID_FILL_STEP", 
            "entityType": "SUB_ASSEMBLY",
            "result": "PASS",
            "productId": "PA-100",
            "serialNumber": ooo_context["sub_sn_2"],
            "parentSerialNumber": ooo_context["parent_sn"],
            "timestamp": "2026-04-25T11:00:00Z"
        }
    ]
    return payloads

@when("the system re-evaluates the group", target_fixture="sub_responses")
def reevaluate_group(sub_payloads):
    # Posting the subs triggers re-evaluation natively in handle_correlation
    resp1 = client.post("/api/v1/quality-results", json=sub_payloads[0])
    resp2 = client.post("/api/v1/quality-results", json=sub_payloads[1])
    return [resp1, resp2]

@then("the event should be processed and sent to FLAGS")
def check_processed_sent_to_flags(sub_responses, ooo_context):
    assert sub_responses[1].status_code == 200
    assert sub_responses[1].json().get("status") == "SUCCESS"
    
    db = SessionLocal()
    group = db.query(CorrelationGroup).filter(CorrelationGroup.parent_serial_number == ooo_context["parent_sn"]).first()
    assert group is not None
    assert group.status == "COMPLETE"
    db.close()
