import urllib.request
import urllib.error
import uuid
import time
import json

BASE_URL = "http://127.0.0.1:8000/api/v1/mes/quality-events"

def send_request(name, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE_URL, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as f:
            res = json.loads(f.read().decode("utf-8"))
            print(f"\n--- {name} ---")
            print(f"Status: {f.status}")
            print(json.dumps(res, indent=2))
    except urllib.error.HTTPError as e:
        res = json.loads(e.read().decode("utf-8"))
        print(f"\n--- {name} ---")
        print(f"Status: {e.code}")
        print(json.dumps(res, indent=2))

def run_tests():
    # TEST 1: PASS
    pass_payload = {
        "eventId": f"EV-PASS-{uuid.uuid4().hex}",
        "eventType": "QUALITY_RESULT",
        "sourceSystem": "TEST_ENV",
        "timestamp": "2026-04-25T12:00:00Z",
        "step": "ROUTE",
        "result": "PASS",
        "entityType": "MAIN_ASSEMBLY",
        "productId": "P-123",
        "serialNumber": f"SN-{uuid.uuid4().hex}"
    }
    
    send_request("Test 1: PASS", pass_payload)
    
    # TEST 2: FAIL without defectCode
    fail_payload = {
        "eventId": f"EV-FAIL-{uuid.uuid4().hex}",
        "eventType": "QUALITY_RESULT",
        "sourceSystem": "TEST_ENV",
        "timestamp": "2026-04-25T12:00:00Z",
        "step": "ROUTE",
        "result": "FAIL",
        "entityType": "MAIN_ASSEMBLY",
        "productId": "P-123",
        "serialNumber": f"SN-{uuid.uuid4().hex}"
    }
    send_request("Test 2: FAIL (missing defectCode)", fail_payload)
    
    # TEST 3: OVERRIDE PASS without override fields
    override_pass_payload = {
        "eventId": f"EV-OVP-{uuid.uuid4().hex}",
        "eventType": "QUALITY_RESULT",
        "sourceSystem": "TEST_ENV",
        "timestamp": "2026-04-25T12:00:00Z",
        "step": "ROUTE",
        "result": "OVERRIDE_PASS",
        "entityType": "SUB_ASSEMBLY",
        "productId": "P-123",
        "serialNumber": f"SN-{uuid.uuid4().hex}"
    }
    send_request("Test 3: OVERRIDE_PASS (missing override fields)", override_pass_payload)
    
    # TEST 4: Duplicate Event (We reuse r1 payload)
    send_request("Test 4: Duplicate Event", pass_payload)
    
if __name__ == "__main__":
    run_tests()
