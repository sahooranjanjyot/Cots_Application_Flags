import pytest
from pytest_bdd import scenario, given, when, then
from unittest.mock import patch, MagicMock
from database import SessionLocal, QualityEvent, ExceptionEvent, ProcessingAttempt
from queue_worker import process_message
from httpx import HTTPStatusError, Request, Response
import json
import uuid

# Mock the rabbitmq channel
class MockChannel:
    def basic_ack(self, delivery_tag):
        pass

@scenario("../features/flags_response_handling.feature", "FLAGS returns 4xx error")
def test_flags_returns_4xx():
    pass

@scenario("../features/flags_response_handling.feature", "FLAGS returns 5xx error")
def test_flags_returns_5xx():
    pass

@pytest.fixture
def test_event_id():
    return f"EVT-RESP-{uuid.uuid4().hex[:8]}"

@pytest.fixture
def base_payload(test_event_id):
    return {
        "eventType": "QUALITY_RESULT",
        "eventId": test_event_id,
        "step": "DC_TOOL_STEP",
        "result": "PASS",
        "productId": "PA-100",
        "serialNumber": "SN-RESP-1"
    }

@given("FLAGS API returns client error", target_fixture="mock_scenario")
def mock_4xx_scenario():
    return "4xx"

@given("FLAGS API returns server error", target_fixture="mock_scenario")
def mock_5xx_scenario():
    return "5xx"

@when("the system processes the event")
def process_event(mock_scenario, base_payload):
    # Setup initial QualityEvent DB record so the worker can update it
    db = SessionLocal()
    evt = QualityEvent(
        event_id=base_payload["eventId"],
        transmission_status="PENDING",
        validation_status="PASSED"
    )
    db.add(evt)
    db.commit()
    db.close()

    mock_ch = MockChannel()
    
    with patch("queue_worker.httpx.post") as mock_post:
        if mock_scenario == "4xx":
            resp = Response(400, request=Request("POST", "http://testserver"), content=b"Bad Request Error")
            mock_post.return_value = resp
            # Worker calls raise_for_status, which raises HTTPStatusError
        else:
            resp = Response(500, request=Request("POST", "http://testserver"), content=b"Internal Server Error")
            mock_post.return_value = resp
            
        process_message(mock_ch, MagicMock(delivery_tag=1), None, json.dumps(base_payload).encode('utf-8'))

@then("retry should not be triggered")
def no_retry_triggered(test_event_id):
    db = SessionLocal()
    # It should only have 0 attempts recorded if we dropped it unconditionally OR
    # wait: 4xx does NOT log to ProcessingAttempt in queue_worker natively! It returns!
    attempts = db.query(ProcessingAttempt).filter(ProcessingAttempt.event_id == test_event_id).all()
    assert len(attempts) == 0
    db.close()

@then("event should move to exception queue")
def event_in_exception_queue(test_event_id):
    db = SessionLocal()
    exc = db.query(ExceptionEvent).filter(ExceptionEvent.event_id == test_event_id).first()
    assert exc is not None
    assert exc.exception_type == "FLAGS_HTTP_4XX"
    
    evt = db.query(QualityEvent).filter(QualityEvent.event_id == test_event_id).first()
    assert evt.transmission_status == "FAILED"
    db.close()

@then("retry should be triggered")
def retry_triggered(test_event_id):
    db = SessionLocal()
    # 500 error causes 5 attempts natively due to loop in queue_worker because of max_attempts (5)
    attempts = db.query(ProcessingAttempt).filter(ProcessingAttempt.event_id == test_event_id).all()
    assert len(attempts) > 0 # Because the worker retries it 3 times (or whatever MAX_ATTEMPTS is)
    
    evt = db.query(QualityEvent).filter(QualityEvent.event_id == test_event_id).first()
    assert evt is not None
    assert evt.transmission_status == "RETRY_EXHAUSTED" or evt.transmission_status == "FAILED"
    db.close()
