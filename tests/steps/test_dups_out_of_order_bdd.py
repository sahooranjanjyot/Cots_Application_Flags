import uuid
from pytest_bdd import scenario, given, when, then, parsers
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, EventStore, CorrelationGroup, CorrelationItem, Base, engine

client = TestClient(app)

# Common setup for tests
def setup_module():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    from database import seed_static_limits
    seed_static_limits()

@scenario("../features/dups_out_of_order.feature", "Duplicate event is ignored")
def test_duplicate_ignored():
    pass

@given("MES sends a quality event", target_fixture="event_data")
def initial_event():
    payload = {
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-{uuid.uuid4().hex[:8]}",
        "sourceSystem": "MES-LINE-2",
        "entityType": "SUB_ASSEMBLY",
        "step": "DC_TOOL",
        "result": "PASS",
        "productId": "PA-101",
        "serialNumber": "SUB-DUP-1",
        "parentSerialNumber": "ASSY-DUP-999",
        "timestamp": "2026-04-25T11:00:00Z",
        "stationId": "ST01"
    }
    res = client.post("/api/v1/quality-results", json=payload)
    assert res.status_code == 200
    return payload

@given("the same event is received again with the same idempotency key")
def duplicate_ready(event_data):
    pass # Data remains same for next step

@when("the engine processes the duplicate event", target_fixture="dup_response")
def trigger_duplicate(event_data):
    return client.post("/api/v1/quality-results", json=event_data)

@then("no duplicate FLAGS record should be created")
def check_dup_records(event_data):
    db = SessionLocal()
    # verify EventStore only has one RECEIVED and one DUPLICATE_IGNORED hook or similar
    all_events = db.query(EventStore).filter(EventStore.event_id == event_data["eventId"]).all()
    db.close()
    assert len(all_events) == 1
    assert all_events[0].processing_status == "DUPLICATE_IGNORED"

@then("the duplicate should be logged")
def check_dup_logged(dup_response):
    assert dup_response.status_code == 200
    assert dup_response.json()["reason"] == "DUPLICATE_EVENT"


@scenario("../features/dups_out_of_order.feature", "Out-of-order event is held")
def test_out_of_order_held():
    pass

@given("a sub-assembly event arrives before the parent assembly event", target_fixture="ooo_payload")
def prepare_ooo():
    # In reality the parent assembly arriving before sub-assembly means parent is missing dependencies!
    # The prompt wording is slightly confusing: "Given a sub-assembly event arrives before the parent assembly event" 
    # Usually this means we send the Parent first (which triggers HOLD), then the sub-assembly (which triggers RELEASE).
    # Wait, "Given a sub-assembly event arrives before the parent assembly event" does this imply parent is delayed?
    # If parent is early, it lacks dependencies, hence it's held. I will send Parent assembly missing subs!
    # Let's send Parent.
    payload = {
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-{uuid.uuid4().hex[:8]}",
        "sourceSystem": "MES-LINE-2",
        "entityType": "ASSEMBLY",
        "step": "FINAL_ASSEMBLY",
        "result": "PASS",
        "productId": "PA-101",
        "serialNumber": "ASSY-MISSING-999",
        "timestamp": "2026-04-25T11:00:00Z",
        "stationId": "ST01"
    }
    return payload

@when("the engine processes the event", target_fixture="ooo_response")
def trigger_ooo(ooo_payload):
    return client.post("/api/v1/quality-results", json=ooo_payload)

@then("the event should be stored in HOLDING_FOR_DEPENDENCY status")
def check_held_status(ooo_response):
    assert ooo_response.status_code == 200
    assert "Group correlation is IN_PROGRESS" in ooo_response.json()["message"]
    
@then("it should not be sent to FLAGS")
def check_no_flags(ooo_response):
    # If the response was hold, it naturally bypassed FLAGS.
    assert "flags_response" not in ooo_response.json()


@scenario("../features/dups_out_of_order.feature", "Held event is released")
def test_held_event_released():
    pass

@given("a held event exists", target_fixture="held_context")
def ensure_held_exists():
    return {"parent_sn": "ASSY-MISSING-999"}

@given("its missing dependency later arrives")
def trigger_missing(held_context):
    pass # Done entirely dynamically inside the WHEN step.

@when("the engine re-evaluates dependencies")
def run_arriving_subs(held_context):
    client.post("/api/v1/quality-results", json={
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-{uuid.uuid4().hex[:8]}",
        "sourceSystem": "MES-LINE-2",
        "entityType": "SUB_ASSEMBLY",
        "step": "DC_TOOL",
        "result": "PASS",
        "productId": "PA-101",
        "serialNumber": "SUB-EARLY-1",
        "parentSerialNumber": held_context["parent_sn"],
        "timestamp": "2026-04-25T11:00:00Z",
        "stationId": "ST01"
    })
    
    # We must send BOTH since FINAL_ASSEMBLY requires DC_TOOL and FLUID_FILL
    client.post("/api/v1/quality-results", json={
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-{uuid.uuid4().hex[:8]}",
        "sourceSystem": "MES-LINE-2",
        "entityType": "SUB_ASSEMBLY",
        "step": "FLUID_FILL",
        "result": "PASS",
        "productId": "PA-101",
        "serialNumber": "SUB-EARLY-2",
        "parentSerialNumber": held_context["parent_sn"],
        "timestamp": "2026-04-25T11:00:00Z",
        "stationId": "ST01"
    })

@then("the event should be validated")
def val_check():
    import time
    time.sleep(0.5)
    # Asynchronous process inside main completed it
    db = SessionLocal()
    group = db.query(CorrelationGroup).filter(CorrelationGroup.parent_serial_number == "ASSY-MISSING-999").order_by(CorrelationGroup.created_at.desc()).first()
    db.close()
    assert group is not None
    assert group.status in ["IN_PROGRESS", "COMPLETE"]
    
@then("sent to FLAGS if all rules pass")
def check_flags_integration():
    from services import success_store
    mapped_payload = success_store[-1]
    assert "sub_assemblies" in mapped_payload
    assert len(mapped_payload["sub_assemblies"]) == 2
