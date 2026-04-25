from fastapi import FastAPI, BackgroundTasks, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from models import MESQualityResult
from database import SessionLocal, QualityEvent, CorrelationGroup, CorrelationItem, EventStore, OverrideEvent
from services import (
    transform_mes_to_flags, log_to_db, record_success, 
    record_workflow_pending, record_workflow_rejected, logger, push_to_retry_queue,
    success_store, dlq_store, retry_queue_store, push_to_dlq
)
import httpx
import asyncio
import json
from datetime import datetime, timezone

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

from database import SessionLocal, QualityEvent, CorrelationGroup, CorrelationItem, EventStore, OverrideEvent, ReprocessRequest
from models import MESReprocessRequest

@app.post("/api/v1/quality-results/reprocess")
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


@app.post("/api/v1/quality-results")
@app.post("/api/v1/mes/quality-events")
async def receive_quality_results(payload: MESQualityResult, background_tasks: BackgroundTasks, is_reeval: bool = False):
    logger.info(f"Incoming MES payload: {payload.model_dump(mode='json', exclude_unset=True)}")
    logger.info("Validation result: PASS")
    
    import os, json
    from database import SessionLocal, QualityEvent, OverrideEvent
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

    # 0.5 OVERRIDE / WORKFLOW APPROVAL LOGIC
    if payload.overrideResult or getattr(payload, "overrideReasonCode", None):
        if getattr(payload, "approvalRequired", False):
            # Check approval Status
            app_status = getattr(payload, "approvalStatus", None)
            if app_status == "REJECTED":
                from services import record_workflow_rejected
                record_workflow_rejected(payload.model_dump(mode='json'), "Override rejected")
                return {"status": "WORKFLOW_REJECTED", "message": "Override request was rejected"}
            elif app_status not in ["APPROVED", "AUTO_APPROVED"]:
                from services import record_workflow_pending
                record_workflow_pending(payload.model_dump(mode='json'), "Pending manual approval")
                return {"status": "WORKFLOW_PENDING", "message": "Event is pending manual approval"}

    # 1. ASSEMBLY / SUB_ASSEMBLY Correlation
    if payload.entityType in ["SUB_ASSEMBLY", "MAIN_ASSEMBLY", "ASSEMBLY"]:
        from services import handle_correlation
        is_complete, corr_status, enhanced_payload = handle_correlation(payload.model_dump(mode='json'), rules_config)
        
        if corr_status == "FAILED":
            from services import log_to_exception_queue
            log_to_exception_queue(payload.eventId, "CORRELATION_FAILURE", "A required sub-assembly failed or timed out", payload.model_dump_json())
            return JSONResponse(status_code=400, content={"detail": "Correlation Failure: Sub-assemblies did not pass"})
            
        if not is_complete:
            return {"status": "success", "message": f"Event recorded. Group correlation is {corr_status}"}
            
        # Swap payload with the enhanced dict representing the complete built group!
        payload_to_transform = enhanced_payload
    else:
        payload_to_transform = payload
                
    try:
        transformed = transform_mes_to_flags(payload_to_transform)
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
    
    from services import log_processing_attempt
    async with httpx.AsyncClient() as client:
        last_error = None
        for attempt in range(max_retries):
            try:
                response = await client.post(flags_url, json=transformed)
                response.raise_for_status() 
                
                logger.info(f"FLAGS response: HTTP {response.status_code} - {response.json()}")
                
                if attempt == 0:
                    attempt_status = "SENT"
                else:
                    attempt_status = "RETRY_SUCCESS"
                log_processing_attempt(payload.eventId, attempt_num=attempt+1, attempt_type="TRANSMISSION", status=attempt_status, error_msg=None, flags_code=response.status_code, flags_body=response.text)
                
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
                resp_obj = getattr(e, "response", None)
                log_processing_attempt(payload.eventId, attempt_num=attempt+1, attempt_type="TRANSMISSION", status="FAILED", error_msg=str(e), flags_code=getattr(resp_obj, "status_code", None), flags_body=getattr(resp_obj, "text", None))
                
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

@app.get("/api/v1/events")
async def get_all_events():
    db = SessionLocal()
    try:
        events = db.query(QualityEvent).order_by(QualityEvent.created_at.desc()).limit(100).all()
        return {"data": events}
    finally:
        db.close()

@app.get("/api/v1/events/{eventId}")
async def get_event_details(eventId: str):
    db = SessionLocal()
    try:
        from database import ProcessingAttempt, ExceptionEvent
        event = db.query(QualityEvent).filter(QualityEvent.event_id == eventId).first()
        attempts = db.query(ProcessingAttempt).filter(ProcessingAttempt.event_id == eventId).all()
        exceptions = db.query(ExceptionEvent).filter(ExceptionEvent.event_id == eventId).all()
        return {
            "event": event,
            "attempts": attempts,
            "exceptions": exceptions
        }
    finally:
        db.close()

@app.post("/api/v1/events/{eventId}/retry")
async def manual_retry_event(eventId: str, background_tasks: BackgroundTasks):
    db = SessionLocal()
    try:
        event = db.query(QualityEvent).filter(QualityEvent.event_id == eventId).first()
        if not event:
            return JSONResponse(status_code=404, content={"detail": "Event not found"})
        if event.validation_status != "PASSED":
            return JSONResponse(status_code=400, content={"detail": "Cannot retry, validation failed. Try replay."})
        if event.transmission_status == "SUCCESS":
            return JSONResponse(status_code=400, content={"detail": "Already sent to FLAGS."})
        
        payload_dict = json.loads(event.payload)
    finally:
        db.close()
        
    try:
        mes_data = MESQualityResult(**payload_dict)
        return await receive_quality_results(mes_data, background_tasks, is_reeval=True)
    except Exception as e:
        return JSONResponse(status_code=400, content={"detail": f"Retry completely failed: {str(e)}"})

@app.post("/api/v1/events/{eventId}/replay")
async def replay_event(eventId: str, background_tasks: BackgroundTasks):
    db = SessionLocal()
    try:
        from database import ExceptionEvent
        exc = db.query(ExceptionEvent).filter(ExceptionEvent.event_id == eventId).order_by(ExceptionEvent.created_at.desc()).first()
        if not exc or not exc.raw_payload:
            event = db.query(QualityEvent).filter(QualityEvent.event_id == eventId).first()
            if not event or not event.payload:
                return JSONResponse(status_code=404, content={"detail": "Original raw payload not found for replay."})
            payload_str = event.payload
        else:
            payload_str = exc.raw_payload
            
        payload_dict = json.loads(payload_str)
    finally:
        db.close()
        
    try:
        from services import log_processing_attempt
        log_processing_attempt(eventId, attempt_num=1, attempt_type="REPLAY", status="IN_PROGRESS", error_msg=None)
        
        mes_data = MESQualityResult(**payload_dict)
        return await receive_quality_results(mes_data, background_tasks, is_reeval=True)
    except Exception as e:
        return JSONResponse(status_code=400, content={"detail": f"Replay mapping failed: {str(e)}"})

@app.get("/api/v1/events/failed")
async def get_failed_events():
    db = SessionLocal()
    try:
        events = db.query(QualityEvent).filter(
            (QualityEvent.validation_status == "FAILED") | 
            (QualityEvent.transmission_status == "FAILED")
        ).order_by(QualityEvent.created_at.desc()).limit(100).all()
        return {"data": events}
    finally:
        db.close()

@app.get("/api/v1/events/exceptions")
async def get_exceptions():
    db = SessionLocal()
    try:
        from database import ExceptionEvent
        events = db.query(ExceptionEvent).order_by(ExceptionEvent.created_at.desc()).limit(100).all()
        return {"data": events}
    finally:
        db.close()

@app.post("/api/v1/exceptions/{exceptionId}/resolve")
async def resolve_exception(exceptionId: str, resolvedBy: str = "SystemAdmin"):
    db = SessionLocal()
    try:
        from database import ExceptionEvent
        exc = db.query(ExceptionEvent).filter(ExceptionEvent.id == exceptionId).first()
        if not exc:
            return JSONResponse(status_code=404, content={"detail": "Exception not found"})
        exc.resolved = True
        exc.resolved_by = resolvedBy
        exc.resolved_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "success", "message": "Exception marked as resolved"}
    finally:
        db.close()

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

@app.get("/api/v1/rules")
async def get_rules():
    db = SessionLocal()
    try:
        from database import ValidationRule
        rules = db.query(ValidationRule).all()
        return {"data": rules}
    finally:
        db.close()

@app.post("/api/v1/rules")
async def create_rule(payload: dict):
    db = SessionLocal()
    try:
        from database import ValidationRule
        rule_id = f"{payload['processStep']}_{payload['assemblyLevel']}_{payload['resultType']}"
        rule = db.query(ValidationRule).filter(ValidationRule.rule_id == rule_id).first()
        if not rule:
            rule = ValidationRule(rule_id=rule_id)
            db.add(rule)
        rule.process_step = payload['processStep']
        rule.assembly_level = payload['assemblyLevel']
        rule.result_type = payload['resultType']
        rule.mandatory_fields_json = json.dumps(payload.get('mandatoryFields', []))
        rule.forbidden_fields_json = json.dumps(payload.get('forbiddenFields', []))
        rule.enabled = payload.get('enabled', True)
        db.commit()
        return {"status": "success"}
    finally:
        db.close()

@app.put("/api/v1/rules/{ruleId}")
async def update_rule(ruleId: str, payload: dict):
    db = SessionLocal()
    try:
        from database import ValidationRule
        rule = db.query(ValidationRule).filter(ValidationRule.rule_id == ruleId).first()
        if not rule:
            return JSONResponse(status_code=404, content={"detail": "Rule not found"})
        if 'mandatoryFields' in payload:
            rule.mandatory_fields_json = json.dumps(payload['mandatoryFields'])
        if 'forbiddenFields' in payload:
            rule.forbidden_fields_json = json.dumps(payload['forbiddenFields'])
        if 'enabled' in payload:
            rule.enabled = payload['enabled']
        db.commit()
        return {"status": "success"}
    finally:
        db.close()

@app.get("/api/v1/mappings")
async def get_mappings():
    import os
    mapping_path = os.path.join(os.path.dirname(__file__), 'mapping.json')
    if not os.path.exists(mapping_path):
        return {"data": {}}
    with open(mapping_path, 'r') as f:
        return {"data": json.load(f)}

@app.post("/api/v1/mappings")
async def create_mapping(payload: dict):
    import os
    mapping_path = os.path.join(os.path.dirname(__file__), 'mapping.json')
    with open(mapping_path, 'r') as f:
        config = json.load(f)
    config[payload['sourceField']] = payload['targetField']
    with open(mapping_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    # Reload in services natively via restarting or modifying global map. 
    # For now, it updates the json configuration reliably!
    from services import MAPPING_CONFIG
    MAPPING_CONFIG[payload['sourceField']] = payload['targetField']
    return {"status": "success"}

@app.put("/api/v1/mappings/{sourceField}")
async def update_mapping(sourceField: str, payload: dict):
    import os
    mapping_path = os.path.join(os.path.dirname(__file__), 'mapping.json')
    with open(mapping_path, 'r') as f:
        config = json.load(f)
    
    if sourceField in config:
        if 'targetField' in payload:
            config[sourceField] = payload['targetField']
            from services import MAPPING_CONFIG
            MAPPING_CONFIG[sourceField] = payload['targetField']
        
        with open(mapping_path, 'w') as f:
            json.dump(config, f, indent=2)
        return {"status": "success"}
    return JSONResponse(status_code=404, content={"detail": "Mapping not found"})@app.get("/api/v1/correlation")
def list_correlations():
    from database import SessionLocal, CorrelationGroup
    db = SessionLocal()
    try:
        groups = db.query(CorrelationGroup).order_by(CorrelationGroup.created_at.desc()).limit(100).all()
        return {"data": [{"id": g.id, "parent_serial_number": g.parent_serial_number, "status": g.status, "created_at": str(g.created_at)} for g in groups]}
    finally:
        db.close()

@app.get("/api/v1/correlation/{parent_serial_number}")
def view_correlation(parent_serial_number: str):
    from database import SessionLocal, CorrelationGroup, CorrelationItem
    db = SessionLocal()
    try:
        group = db.query(CorrelationGroup).filter(CorrelationGroup.parent_serial_number == parent_serial_number).first()
        if not group:
            return JSONResponse(status_code=404, content={"detail": "Correlation group not found"})
            
        items = db.query(CorrelationItem).filter(CorrelationItem.group_id == group.id).all()
        return {
            "id": group.id,
            "parent_serial_number": group.parent_serial_number,
            "status": group.status,
            "created_at": str(group.created_at),
            "updated_at": str(group.updated_at),
            "items": [
                {
                    "serial_number": i.serial_number,
                    "assembly_level": i.assembly_level,
                    "process_step": i.process_step,
                    "result_type": i.result_type,
                    "validation_status": i.validation_status
                } for i in items
            ]
        }
    finally:
        db.close()
