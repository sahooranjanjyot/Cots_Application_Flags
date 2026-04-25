import pytest
from pytest_bdd import scenario, given, when, then
from fastapi.testclient import TestClient
from main import app
import uuid

client = TestClient(app)

@scenario("../features/mandatory_edge_cases.feature", "Mandatory field is null")
def test_null_mandatory():
    pass

@scenario("../features/mandatory_edge_cases.feature", "Mandatory field is empty string")
def test_empty_string_mandatory():
    pass

@scenario("../features/mandatory_edge_cases.feature", "Incorrect field data type")
def test_incorrect_datatype():
    pass

@given("MES sends an event with null serialNumber", target_fixture="invalid_payload")
def null_serial_payload():
    return {
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-MAND-{uuid.uuid4().hex[:8]}",
        "step": "DC_TOOL_STEP",
        "result": "PASS",
        "productId": "PA-100",
        "serialNumber": None,
        "timestamp": "2026-04-25T11:00:00Z"
    }

@given("MES sends an event with empty productId", target_fixture="invalid_payload")
def empty_productID_payload():
    return {
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-MAND-{uuid.uuid4().hex[:8]}",
        "step": "DC_TOOL_STEP",
        "result": "PASS",
        "productId": "",  # Empty string
        "serialNumber": "SN-MAND-1",
        "timestamp": "2026-04-25T11:00:00Z"
    }

@given("MES sends an event with numeric serialNumber", target_fixture="invalid_payload")
def numeric_serial_payload():
    return {
        "eventType": "QUALITY_RESULT",
        "eventId": f"EVT-MAND-{uuid.uuid4().hex[:8]}",
        "step": "DC_TOOL_STEP",
        "result": "PASS",
        "productId": "PA-100",
        "serialNumber": 123456,  # Numeric
        "timestamp": "2026-04-25T11:00:00Z"
    }

@when("the system processes the event", target_fixture="response")
def process_event(invalid_payload):
    return client.post("/api/v1/quality-results", json=invalid_payload)

@then("validation should fail")
def check_validation_should_fail(response):
    assert response.status_code == 400
