from fastapi import FastAPI, BackgroundTasks, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from models import MESQualityResult
from database import SessionLocal, QualityEvent, CorrelationEvent, EventStore, OverrideEvent
from services import (
    transform_mes_to_flags, log_to_db, log_correlation_to_db, record_success, 
    record_workflow_pending, record_workflow_rejected, logger, push_to_retry_queue,
    success_store, dlq_store, retry_queue_store, push_to_dlq
)
import httpx
import asyncio
import json

app = FastAPI(title="Quality Data Validation & Integration Engine (QDVI)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    import json
    error_msg = f"Validation Error: {exc.errors()[0]['type']}, {exc.errors()[0]['msg']}"
    logger.error(error_msg)
    
    parsed = exc.body if hasattr(exc, "body") and exc.body else {}
    raw_payload_str = json.dumps(parsed) if isinstance(parsed, dict) else str(parsed)
    
    # Store into EventStore
    from database import SessionLocal, EventStore
    db = SessionLocal()
    try:
        new_evt = EventStore(
            event_id=parsed.get("eventId") if isinstance(parsed, dict) else None,
            source_system=parsed.get("sourceSystem") if isinstance(parsed, dict) else None,
            raw_payload=raw_payload_str,
            processing_status="FAILED_NORMALIZATION",
            normalization_status="FAILED"
        )
        db.add(new_evt)
        db.commit()
    finally:
        db.close()
    
    push_to_dlq(payload_dict=parsed if isinstance(parsed, dict) else {}, error_msg=error_msg)
    
    clean_errors = [e.get("msg") for e in exc.errors()]
    return JSONResponse(
        status_code=400,
        content={"status": "FAILED", "validationErrors": clean_errors, "detail": "Validation Error", "errors": [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]}
    )

from database import SessionLocal, QualityEvent, CorrelationEvent, EventStore, OverrideEvent, ReprocessRequest
from models import MESReprocessRequest

@app.post("/api/v1/quality-results/reprocess")
@app.post("/api/v1/mes/quality-events")
async def manual_reprocess(request: MESReprocessRequest, background_tasks: BackgroundTasks):
    db = SessionLocal()
    try:
        import os, json
        rules_path = os.path.join(os.path.dirname(__file__), 'rules.json')
        with open(rules_path, 'r') as f:
            rules_config = json.load(f)
        reprocess_rules = rules_config.get("eventProcessingRules", {}).get("reprocessingRules", {})
        
        target_event = db.query(EventStore).filter(EventStore.event_id == request.eventId).first()
        if not target_event:
            return JSONResponse(status_code=404, content={"message": "Target event not found"})
            
        allowed_statuses = reprocess_rules.get("allowedStatusesForRetry", [])
        if target_event.processing_status not in allowed_statuses and not request.overrideValidation:
            return JSONResponse(status_code=400, content={"message": f"Event status {target_event.processing_status} not allowed for reprocessing"})
            
        sql_mapping = {
            "reprocess_request_id": request.reprocessRequestId,
            "event_id": request.eventId,
            "correlation_id": request.correlationId,
            "requested_by": request.requestedBy,
            "requested_timestamp": request.requestedTimestamp,
            "reprocess_type": request.reprocessType,
            "reason_code": request.reasonCode,
            "reason_description": request.reasonDescription,
            "override_validation": request.overrideValidation,
            "approval_status": "PENDING"
        }

        approval_req = reprocess_rules.get("manualReplayPolicy", {}).get("approvalRequired", True)
        
        # Override Validation Specific Checks
        if request.overrideValidation:
            approval_req = True
            if not request.reasonCode:
                return JSONResponse(status_code=400, content={"message": "reasonCode is mandatory for validation override"})

        if approval_req and request.approvalStatus != "APPROVED":
            sql_mapping["status"] = "MANUAL_REPROCESS_PENDING"
            sql_mapping["approval_status"] = "PENDING"
            req_db = ReprocessRequest(**sql_mapping)
            db.add(req_db)
            db.commit()
            return {"status": "success", "message": "Reprocess request logged securely as PENDING"}
        
        sql_mapping["approval_status"] = request.approvalStatus or "APPROVED"
        sql_mapping["status"] = "MANUAL_REPROCESS_APPROVED"
        if request.approverId:
            sql_mapping["approver_id"] = request.approverId
            
        req_db = ReprocessRequest(**sql_mapping)
        db.add(req_db)
        
        target_event.processing_status = "REPLAY_IN_PROGRESS"
        
        from database import ProcessingAttempt
        attempt = ProcessingAttempt(
            event_id=request.eventId,
            attempt_number=(target_event.retry_attempt_count or 0) + 1,
            attempt_type=request.reprocessType,
            result_status="STARTED"
        )
        db.add(attempt)
        target_event.retry_attempt_count = (target_event.retry_attempt_count or 0) + 1
        
        db.commit()
        
        if target_event.payload:
            payload_dict = json.loads(target_event.payload)
            if request.approvalStatus:
                payload_dict["approvalStatus"] = request.approvalStatus
            if request.approverId:
                payload_dict["approverId"] = request.approverId
            re_payload = MESQualityResult(**payload_dict)
            await receive_quality_results(re_payload, background_tasks=background_tasks, is_reeval=True)
            return {"status": "success", "message": "Manual reprocessing initiated securely"}
        else:
            return JSONResponse(status_code=500, content={"message": "Original raw payload missing bounds"})
    finally:
        db.close()

async def re_evaluate_held_assemblies(target_serial_number, background_tasks: BackgroundTasks):
    if not target_serial_number:
        return
    import json
    from database import SessionLocal, CorrelationEvent
    from models import MESQualityResult
    db = SessionLocal()
    try:
        held = db.query(CorrelationEvent).filter(
            CorrelationEvent.entity_type == "ASSEMBLY",
            CorrelationEvent.correlation_status == "WAITING_DEPENDENCIES",
            CorrelationEvent.child_serial_number == target_serial_number
        ).all()
        for h in held:
            if h.payload:
                logger.info(f"Re-evaluating held assembly natively: {h.child_serial_number}")
                re_payload = MESQualityResult(**json.loads(h.payload))
                db.delete(h)
                db.commit()
                # Run correlation again natively bypassing duplication blocks!
                await receive_quality_results(re_payload, background_tasks=background_tasks, is_reeval=True)
    finally:
        db.close()

@app.post("/api/v1/quality-results")
async def receive_quality_results(payload: MESQualityResult, background_tasks: BackgroundTasks, is_reeval: bool = False):
    logger.info(f"Incoming MES payload: {payload.model_dump(mode='json', exclude_unset=True)}")
    logger.info("Validation result: PASS")
    
    import os, json
    from database import SessionLocal, QualityEvent, OverrideEvent, CorrelationEvent
    rules_path = os.path.join(os.path.dirname(__file__), 'rules.json')
    with open(rules_path, 'r') as f:
        rules_config = json.load(f)
        
    proc_rules = rules_config.get("eventProcessingRules", {})
    
    # 0. DUPLICATE EVENTS (Idempotency) & STATUS MODEL
    idemp_keys = ["eventId", "sourceSystem", "qualityResultFileId"]
    idemp_val = ""
    if not is_reeval:
        key_vals = [str(getattr(payload, k, "")) for k in idemp_keys if getattr(payload, k, None)]
        if key_vals:
            import hashlib
            idemp_val = hashlib.sha256(("".join(key_vals)).encode('utf-8')).hexdigest()
            from database import SessionLocal, EventStore, EventDependencyTracker
            db = SessionLocal()
            try:
                dup = db.query(EventStore).filter(EventStore.idempotency_key == idemp_val).first()
                if dup:
                    action = proc_rules.get("duplicateHandling", {}).get("duplicateAction", "IGNORE")
                    if action == "IGNORE":
                        logger.info(f"Duplicate ignored: {idemp_val}")
                        dup.processing_status = "DUPLICATE_IGNORED"
                        db.commit()
                        return {"status": "IGNORED", "reason": "DUPLICATE_EVENT"}
                    elif action == "RAISE_ALERT":
                        logger.error(f"ALERT: Duplicate payload {idemp_val}")
                        return JSONResponse(status_code=409, content={"status": "alert", "message": "Duplicate payload alert raised!"})
                    elif action == "UPDATE_EXISTING":
                        payload.eventType = "QUALITY_RESULT_UPDATE"
                        dup.processing_status = "VALIDATED"
                        import hashlib
                        dup.payload_hash = hashlib.sha256(payload.model_dump_json().encode('utf-8')).hexdigest()
                        db.commit()
                else:
                    raw_data_str = json.dumps(payload.payload) if payload.payload else None
                    warn_msg = payload.payload.get("deprecation_warning") if payload.payload else None
                    import hashlib
                    new_evt = EventStore(
                        event_id=payload.eventId,
                        source_system=payload.sourceSystem,
                        idempotency_key=idemp_val,
                        correlation_id=payload.correlationId,
                        serial_number=payload.serialNumber,
                        parent_serial_number=payload.parentSerialNumber,
                        event_timestamp=payload.eventTimestamp,
                        received_timestamp=payload.receivedTimestamp,
                        processing_status="RECEIVED",
                        payload_hash=hashlib.sha256(payload.model_dump_json().encode('utf-8')).hexdigest(),
                        payload=payload.model_dump_json(),
                        schema_version=payload.schemaVersion,
                        canonical_payload=payload.model_dump_json(),
                        raw_payload=raw_data_str,
                        normalization_status="NORMALIZED",
                        deprecation_warning=warn_msg
                    )
                    db.add(new_evt)
                    db.commit()
            finally:
                db.close()

    
    # 1. SUB_ASSEMBLY Intercept
    if payload.entityType == "SUB_ASSEMBLY":
        from services import log_correlation_to_db
        log_correlation_to_db(
            event_id=payload.eventId,
            source_system=payload.sourceSystem,
            parent_sn=payload.parentSerialNumber,
            child_sn=payload.serialNumber,
            entity_type="SUB_ASSEMBLY",
            step=payload.step,
            result=payload.result,
            correlation_status="PARTIAL_DATA",
            payload_str=payload.model_dump_json()
        )
        
        # Async Re-Evaluate natively using FastAPI BackgroundTasks!
        background_tasks.add_task(re_evaluate_held_assemblies, payload.parentSerialNumber, background_tasks)
        return {"status": "success", "message": f"Sub-assembly {payload.step} recorded"}
    
    # Workflow Logic Intercept (Overrides)
    is_override = payload.originalResult is not None or payload.overrideResult is not None
    if is_override:
        if payload.approvalStatus == "PENDING":
            record_workflow_pending(payload.model_dump(mode='json'), "Workflow approval is PENDING")
            return {"status": "workflow_pending", "message": "Event queued for approval workflow"}
        elif payload.approvalStatus == "REJECTED":
            record_workflow_rejected(payload.model_dump(mode='json'), "Workflow approval was REJECTED")
            return {"status": "workflow_rejected", "message": "Event override was rejected"}

    # 2. ASSEMBLY Correlation Validation + OUT-OF-ORDER
    sub_assemblies_data = [] 
    if payload.entityType in ["ASSEMBLY", "MAIN_ASSEMBLY"]:
        corr_rules = rules_config.get("correlationRules", {}).get(payload.step)
        if not corr_rules and payload.step == "DECKING_VISION":
            corr_rules = rules_config.get("correlationRules", {}).get("FINAL_ASSEMBLY")
            
        if corr_rules and corr_rules.get("requiresSubAssemblies"):
            db = SessionLocal()
            try:
                # Check Database natively for sub-components
                from database import CorrelationEvent
                subs = db.query(CorrelationEvent).filter(
                    CorrelationEvent.parent_serial_number == payload.serialNumber,
                    CorrelationEvent.entity_type == "SUB_ASSEMBLY",
                    CorrelationEvent.correlation_status == "PARTIAL_DATA"
                ).all()
                
                existing_steps = [sub.step for sub in subs]
                missing = [str(s) for s in corr_rules.get("subAssemblySteps", []) if s not in existing_steps and f"{s}_STEP" not in existing_steps]
                
                if missing:
                    out_of_order = proc_rules.get("outOfOrderHandling", {})
                    if out_of_order.get("enabled") and out_of_order.get("holdUntilDependenciesArrive"):
                        from services import log_correlation_to_db
                        log_correlation_to_db(
                            event_id=payload.eventId,
                            source_system=payload.sourceSystem,
                            parent_sn=None,
                            child_sn=payload.serialNumber,
                            entity_type="ASSEMBLY",
                            step=payload.step,
                            result=payload.result,
                            correlation_status="WAITING_DEPENDENCIES",
                            payload_str=payload.model_dump_json()
                        )
                        return {"status": "success", "message": "Event held waiting for dependencies"}
                    elif not corr_rules.get("allowPartial", False):
                        err_str = f"Incomplete correlation: Missing sub-assemblies for steps {', '.join(missing)}"
                        from services import log_correlation_to_db
                        log_correlation_to_db(
                            event_id=payload.eventId,
                            source_system=payload.sourceSystem,
                            parent_sn=None,
                            child_sn=payload.serialNumber,
                            entity_type="ASSEMBLY",
                            step=payload.step,
                            result=payload.result,
                            correlation_status="INCOMPLETE_CORRELATION"
                        )
                        return JSONResponse(status_code=400, content={"detail": err_str})
                    
                if corr_rules.get("validationStrategy") == "ALL_SUBASSEMBLIES_PASS":
                    for sub in subs:
                        if sub.result != "PASS":
                            payload.result = "FAIL" 
                            
                for sub in subs:
                    sub_assemblies_data.append({
                        "serial_no": sub.child_serial_number,
                        "step": sub.step,
                        "result": sub.result
                    })
                    
                from services import log_correlation_to_db
                log_correlation_to_db(
                    event_id=payload.eventId,
                    source_system=payload.sourceSystem,
                    parent_sn=None,
                    child_sn=payload.serialNumber,
                    entity_type="ASSEMBLY",
                    step=payload.step,
                    result=payload.result,
                    correlation_status="COMPLETE"
                )
            finally:
                db.close()
                
    try:
        transformed = transform_mes_to_flags(payload)
        
        # Inject Sub-Assemblies into transformed structure!
        if sub_assemblies_data:
            transformed["sub_assemblies"] = sub_assemblies_data
            
        logger.info(f"Transformed payload: {transformed}")
    except Exception as e:
        logger.error(f"Error details: Transformation Failure - {str(e)}")
        push_to_dlq(payload.model_dump(mode='json'), error_msg=f"Transformation Error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": f"Transformation Failure: {str(e)}"}
        )
    
    flags_url = "http://127.0.0.1:8000/flags/api/v1/quality"
    max_retries = 3
    base_delay = 1
    
    async with httpx.AsyncClient() as client:
        last_error = None
        for attempt in range(max_retries):
            try:
                response = await client.post(flags_url, json=transformed)
                response.raise_for_status() 
                
                logger.info(f"FLAGS response: HTTP {response.status_code} - {response.json()}")
                
                record_success(payload, transformed)
                
                return {
                    "status": "SUCCESS", 
                    "validation": "PASSED",
                    "sentToFlags": True,
                    "message": "Integrated with FLAGS", 
                    "flags_response": response.json()
                }
            except Exception as e:
                last_error = e
                logger.error(f"Error details: FLAGS API Failure - {str(e)}")
                
                if attempt < max_retries - 1:
                    logger.warning(f"FLAGS Integraton attempt {attempt + 1} failed. Retrying...")
                    await asyncio.sleep(base_delay * (2 ** attempt)) 
                else:
                    logger.error("FLAGS Integration failed after max retries")
        
        push_to_retry_queue(payload.model_dump(mode="json"), str(last_error))
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "Failed to integrate with FLAGS after 3 retries. Event queued."}
        )

@app.post("/flags/api/v1/quality")
async def mock_flags_ingest(payload: dict):
    if "defect_code" in payload and payload["defect_code"] == "NETWORK_ERROR_SIM":
        return JSONResponse(status_code=503, content={"error": "Service Unavailable"})
    return {"status": "success", "message": "Payload accepted and stored in FLAGS DB"}

@app.get("/api/v1/dashboard/success")
async def get_success_events():
    return {"data": success_store}

@app.get("/api/v1/dashboard/dlq")
async def get_dlq_events():
    return {"data": dlq_store}

@app.get("/api/v1/dashboard/events")
async def get_all_events():
    db = SessionLocal()
    try:
        events = db.query(QualityEvent).order_by(QualityEvent.created_at.desc()).limit(100).all()
        return {"data": events}
    finally:
        db.close()

@app.post("/api/v1/dashboard/retry/{event_id}")
async def retry_event(event_id: str):
    db = SessionLocal()
    try:
        event = db.query(QualityEvent).filter(QualityEvent.id == event_id).first()
        if not event or event.transmission_status == "SUCCESS" or not event.payload:
            return JSONResponse(status_code=400, content={"detail": "Cannot retry this event."})
        
        payload_dict = json.loads(event.payload)
    finally:
        db.close()
        
    try:
        mes_data = MESQualityResult(**payload_dict)
        return await receive_quality_results(mes_data)
    except Exception as e:
        return JSONResponse(status_code=400, content={"detail": f"Retry completely failed: {str(e)}"})

@app.get("/api/v1/dashboard/stats")
async def get_stats():
    db = SessionLocal()
    total_processed = db.query(QualityEvent).count()
    total_passed = db.query(QualityEvent).filter(QualityEvent.transmission_status == "SUCCESS").count()
    total_failed = db.query(QualityEvent).filter(QualityEvent.validation_status == "FAILED").count()
    total_retry = db.query(QualityEvent).filter(QualityEvent.validation_status == "PASSED", QualityEvent.transmission_status == "FAILED").count()
    db.close()
    
    return {
        "total_passed": total_passed,
        "total_failed": total_failed,
        "total_retry": total_retry,
        "total_processed": total_processed
    }
