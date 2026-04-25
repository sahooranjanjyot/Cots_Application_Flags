# Quality Data Validation & Integration Engine (QDVI)

## Architecture
Web-based (Backend: FastAPI)

## Scenario 1: Route Step → Quality Result → Pass → MES → FLAGS

### 1. API Ingestion
**Endpoint**: `POST /api/v1/quality-results`

Accepts JSON payload mimicking the output from the MES system.

### 2. Validation Rule Engine
Implemented via Pydantic model (`models.py`):
- Mandatory Fields: `eventType`, `step`, `result`, `productId`, `serialNumber`, `timestamp`
- Business Rules:
  - Reject unknown steps (`step` must be "ROUTE")
  - `result` must be "PASS" or "FAIL" for the "ROUTE" step
  - If `result` is "PASS", `errorCode` is strictly disallowed.
  - Reject empty and non-conformant schemas by raising HTTP 400.

Failed validations are sent to a "Dead Letter Queue" (DLQ) simulator. See `services.py` and the application logger.

### 3. Transformation Layer
If the input MES payload passes all validations, the process transforms the payload mapping into the format expected by the FLAGS system.

- `productId` → `product_code`
- `serialNumber` → `serial_no`
- `result` → `quality_status`
- `step` → `process_step`
- `timestamp` → `event_time`

## Setup & Running
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Testing
Unit tests cover all scenarios:
```bash
pytest test_main.py
```
