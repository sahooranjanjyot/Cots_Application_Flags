import asyncio
import httpx
import uuid
import random
from datetime import datetime, timezone
from typing import List, Dict, Any

API_URL = "http://localhost:8000/api/v1/quality-results"
API_KEY = "prod-secure-key-12345"
HEADERS = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}

# Master lists
PROCESS_STEPS = ["ROUTE_STEP", "PART_VERIFICATION", "DC_TOOL_STEP", "FLUID_FILL_STEP", "FF_STEP", "DECKING_VISION"]
PRODUCTS = ["PA-100", "PA-200", "PA-300", "SUB-10", "SUB-20"]

def create_base_event() -> Dict[str, Any]:
    event_id = f"EVT-UAT-{uuid.uuid4().hex[:8]}"
    return {
        "eventType": "QUALITY_RESULT",
        "eventId": event_id,
        "sourceSystem": "MES-SIMULATOR",
        "targetSystem": "FLAGS",
        "qualityResultFileId": "QRF-SIM-1",
        "step": random.choice(PROCESS_STEPS),
        "entityType": "MAIN_ASSEMBLY",
        "result": "PASS",
        "productId": random.choice(PRODUCTS),
        "serialNumber": f"SN-UAT-{uuid.uuid4().hex[:6]}",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def generate_pass_batch(count: int) -> List[Dict[str, Any]]:
    return [create_base_event() for _ in range(count)]

def generate_fail_batch(count: int) -> List[Dict[str, Any]]:
    batch = []
    for _ in range(count):
        event = create_base_event()
        event["result"] = "FAIL"
        event["errorCode"] = f"ERR-{random.randint(100, 999)}"
        event["defectCode"] = f"DEF-{random.randint(10, 99)}"
        event["errorDescription"] = "Simulated Fail"
        event["defectDescription"] = "Simulated Defect"
        batch.append(event)
    return batch

def generate_override_batch(count: int) -> List[Dict[str, Any]]:
    batch = []
    for _ in range(count):
        event = create_base_event()
        event["result"] = random.choice(["OVERRIDE_PASS", "OVERRIDE_FAIL"])
        if event["result"] == "OVERRIDE_FAIL":
            event["errorCode"] = "ERR-OVR"
            event["defectCode"] = "DEF-OVR"
            event["errorDescription"] = "Override fail"
            event["defectDescription"] = "Override defect"
        event["overrideInfo"] = {
            "overrideUser": f"AUTH-UAT-{random.randint(1, 10)}",
            "overrideReasonCode": "OVR-MANUAL",
            "approvalStatus": "APPROVED",
            "approverId": "MGR-101",
            "overrideTime": datetime.now(timezone.utc).isoformat()
        }
        batch.append(event)
    return batch

def generate_correlation_batch(count_pairs: int) -> List[Dict[str, Any]]:
    batch = []
    for _ in range(count_pairs):
        parent_sn = f"SN-PARENT-{uuid.uuid4().hex[:6]}"
        parent = create_base_event()
        parent["serialNumber"] = parent_sn
        
        child = create_base_event()
        child["entityType"] = "SUB_ASSEMBLY"
        child["serialNumber"] = f"SN-CHILD-{uuid.uuid4().hex[:6]}"
        child["parentSerialNumber"] = parent_sn
        
        batch.append(child)
        batch.append(parent)
    return batch

def generate_duplicate_batch(count: int) -> List[Dict[str, Any]]:
    batch = generate_pass_batch(count)
    return batch + batch  # Send exactly exactly the same events again

async def send_batch(name: str, batch: List[Dict[str, Any]]):
    print(f"\\n--- Start Running {name} ({len(batch)} events) ---")
    async with httpx.AsyncClient() as client:
        tasks = []
        for payload in batch:
            # Flattened MES result payload for correct mapping seamlessly
            payload["schemaVersion"] = "v1.0"
            tasks.append(client.post(API_URL, json=payload, headers=HEADERS))
            
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        success = sum(1 for r in responses if getattr(r, 'status_code', 0) == 200)
        failed = len(batch) - success
        print(f"[{name}] Completed: {success} Success | {failed} Failed")

async def run_pilots():
    print("Initiating Pilot Setup...")
    
    # Batch 1: PASS
    await send_batch("Batch 1: PASS only", generate_pass_batch(10))
    
    # Batch 2: FAIL
    await send_batch("Batch 2: FAIL only", generate_fail_batch(10))
    
    # Batch 3: OVERRIDE
    await send_batch("Batch 3: OVERRIDES", generate_override_batch(10))
    
    # Batch 4: MIXED
    mixed = generate_pass_batch(5) + generate_fail_batch(5) + generate_override_batch(5)
    random.shuffle(mixed)
    await send_batch("Batch 4: MIXED", mixed)
    
    # Batch 5: CORRELATION
    await send_batch("Batch 5: CORRELATION (Sub + Main)", generate_correlation_batch(10))
    
    # Batch 6: DUPLICATE
    await send_batch("Batch 6: DUPLICATES", generate_duplicate_batch(5))
    
    print("\\n\\n[PERFORMANCE CHECK] Initiating 500 event burst...")
    burst = generate_pass_batch(500)
    await send_batch("PERFORMANCE BURST", burst)

if __name__ == "__main__":
    asyncio.run(run_pilots())
