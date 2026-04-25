import pytest
from pytest_bdd import scenario, given, when, then
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, CorrelationGroup, CorrelationItem
import uuid
from datetime import datetime, timezone, timedelta

client = TestClient(app)

@scenario("../features/correlation_timeout.feature", "Missing sub-assembly after timeout")
def test_missing_subassembly_timeout():
    pass

@scenario("../features/correlation_timeout.feature", "Late arriving sub-assembly")
def test_late_arriving_subassembly():
    pass

@pytest.fixture
def unique_parent_sn():
    return f"SN-PARENT-TO-{uuid.uuid4().hex[:8]}"

# SCENARIO 1

@given("a parent assembly exists without required sub-assemblies", target_fixture="timeout_context")
def parent_assembly_exists(unique_parent_sn):
    # We simulate a partial correlation group natively by creating it manually in DB to control time
    db = SessionLocal()
    group = CorrelationGroup(
        parent_serial_number=unique_parent_sn, 
        status="IN_PROGRESS",
        # Set created_at into the past (e.g. 2 hours ago)
        created_at=datetime.now(timezone.utc) - timedelta(minutes=120)
    )
    db.add(group)
    db.commit()
    
    # Add MAIN_ASSEMBLY item
    item = CorrelationItem(
        group_id=group.id,
        serial_number=unique_parent_sn,
        assembly_level="MAIN_ASSEMBLY",
        process_step="FINAL_ASSEMBLY",
        result_type="PASS",
        validation_status="PASSED"
    )
    db.add(item)
    db.commit()
    db.close()
    return unique_parent_sn

@when("timeout threshold is reached")
def process_timeouts():
    # Call the newly implemented background timeout collector
    from services import evaluate_correlation_timeouts
    evaluate_correlation_timeouts(threshold_minutes=60)

@then("correlation group should be marked FAILED")
def check_group_failed(timeout_context):
    db = SessionLocal()
    group = db.query(CorrelationGroup).filter(CorrelationGroup.parent_serial_number == timeout_context).first()
    assert group is not None
    assert group.status == "FAILED"
    db.close()


# SCENARIO 2

@given("a correlation group is marked IN_PROGRESS", target_fixture="late_context")
def correlation_in_progress(unique_parent_sn):
    db = SessionLocal()
    group = CorrelationGroup(
        parent_serial_number=unique_parent_sn, 
        status="IN_PROGRESS",
        created_at=datetime.now(timezone.utc)
    )
    db.add(group)
    db.commit()
    
    # Needs some main assembly for rule evaluation
    item = CorrelationItem(
        group_id=group.id,
        serial_number=unique_parent_sn,
        assembly_level="MAIN_ASSEMBLY",
        process_step="FINAL_ASSEMBLY",
        result_type="PASS",
        validation_status="PASSED"
    )
    db.add(item)
    db.commit()
    group_id = group.id
    db.close()
    return {"parent_sn": unique_parent_sn, "group_id": group_id}

@given("a delayed sub-assembly event arrives", target_fixture="late_payload")
def delayed_subassembly(late_context):
    return {
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-LATE-{uuid.uuid4().hex[:8]}",
        "step": "PART_VERIFICATION",  # Registered step in init_rules.py
        "entityType": "SUB_ASSEMBLY",
        "result": "PASS",
        "productId": "PA-100",
        "serialNumber": "SN-SUB-1",
        "parentSerialNumber": late_context["parent_sn"],
        "timestamp": "2026-04-25T11:00:00Z"
    }

@when("the system processes the event")
def system_processes_late_event(late_payload):
    resp = client.post("/api/v1/quality-results", json=late_payload)
    assert resp.status_code == 200

@then("the group should be re-evaluated")
def check_re_evaluated(late_context):
    db = SessionLocal()
    group = db.query(CorrelationGroup).filter(CorrelationGroup.id == late_context["group_id"]).first()
    assert group is not None
    assert group.status != "FAILED"  # Could be COMPLETE or remain IN_PROGRESS if more are needed
    items = db.query(CorrelationItem).filter(CorrelationItem.group_id == late_context["group_id"]).all()
    # Should have more items now (Main + Sub)
    assert len(items) >= 2
    db.close()
