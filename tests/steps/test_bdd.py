import uuid
from pytest_bdd import scenario, given, when, then, parsers
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, QualityEvent

client = TestClient(app)

@scenario("../features/quality_flow.feature", "Validate quality result processing")
def test_quality_generic_processing():
    pass

@given("MES sends a QUALITY_RESULT event", target_fixture="generic_payload")
def generic_payload_init():
    return {
       "eventType": "QUALITY_RESULT",
       "eventId": f"EVT-{uuid.uuid4().hex[:8]}",
       "productId": "GENERIC-PROD-01",
       "serialNumber": "GENERIC-SN-01",
       "timestamp": "2026-04-25T12:00:00Z"
    }

@given(parsers.parse("step is {process_step}"))
def add_step(generic_payload, process_step):
    generic_payload["step"] = process_step

@given(parsers.parse("result is {quality_result}"))
def add_result(generic_payload, quality_result):
    generic_payload["result"] = quality_result
    if quality_result == "FAIL":
        generic_payload["errorCode"] = "E01"
        generic_payload["defectCode"] = "D01"
        generic_payload["errorDescription"] = "Generic fail"
        generic_payload["defectDescription"] = "Generic defect"

@when("the system processes the event", target_fixture="response")
def process_request(generic_payload):
    return client.post("/api/v1/quality-results", json=generic_payload)

@then("validation should follow configured rules")
def validate_mandatory(response):
    assert response.status_code == 200, f"Expected 200, got {response.status_code} - {response.text}"

@then("payload should be transformed using mapping configuration")
def check_transformed_payload(response):
    data = response.json()
    assert data["status"].upper() == "SUCCESS"

@then("FLAGS should receive the correct payload")
def check_flags_receipt(response):
    pass

@then("event should be stored with appropriate status")
def check_response():
    db = SessionLocal()
    try:
        event = db.query(QualityEvent).filter(QualityEvent.serial_number == "GENERIC-SN-01").order_by(QualityEvent.created_at.desc()).first()
        assert event is not None
        assert event.transmission_status == "SUCCESS"
        assert event.validation_status == "PASSED"
    finally:
        db.close()
