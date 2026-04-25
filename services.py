import logging
from typing import List, Dict, Any
import json
import os

from models import MESQualityResult
from database import SessionLocal, QualityEvent, OverrideEvent, CorrelationGroup, CorrelationItem

logger = logging.getLogger(__name__)

with open(os.path.join(os.path.dirname(__file__), 'mapping.json')) as f:
    MAPPING_CONFIG = json.load(f)

success_store: List[Dict[str, Any]] = []
dlq_store: List[Dict[str, Any]] = []
retry_queue_store: List[Dict[str, Any]] = []

def evaluate_correlation_timeouts(threshold_minutes: int = 60):
    db = SessionLocal()
    try:
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)
        groups = db.query(CorrelationGroup).filter(
            CorrelationGroup.status == "IN_PROGRESS",
            CorrelationGroup.created_at < cutoff
        ).all()
        
        timed_out = 0
        for g in groups:
            g.status = "FAILED"
            # Could also log an exception event here for the orphaned sub/main assemblies
            timed_out += 1
        db.commit()
        return timed_out
    finally:
        db.close()

def handle_correlation(mes_data_dict, rules_config):
    # Returns (is_complete, status, payload_for_flags_if_complete)
    assembly_level = mes_data_dict.get("entityType") or "MAIN_ASSEMBLY"
    parent_sn = mes_data_dict.get("parentSerialNumber")
    serial = mes_data_dict.get("serialNumber")
    step = mes_data_dict.get("step")
    result = mes_data_dict.get("result")
    
    group_sn = parent_sn if assembly_level == "SUB_ASSEMBLY" else serial
    if not group_sn:
        return True, "COMPLETE", mes_data_dict # No serial to link
        
    db = SessionLocal()
    try:
        group = db.query(CorrelationGroup).filter(CorrelationGroup.parent_serial_number == group_sn).first()
        if not group:
            group = CorrelationGroup(parent_serial_number=group_sn, status="IN_PROGRESS")
            db.add(group)
            db.commit()
            
        item = CorrelationItem(
            group_id=group.id,
            serial_number=serial,
            parent_serial_number=parent_sn,
            assembly_level=assembly_level,
            process_step=step,
            result_type=result,
            validation_status="PASSED"
        )
        db.add(item)
        db.commit()
        
        # Evaluate Completion!
        all_items = db.query(CorrelationItem).filter(CorrelationItem.group_id == group.id).all()
        main_item = next((i for i in all_items if i.assembly_level == "MAIN_ASSEMBLY"), None)
        
        if not main_item:
            return False, group.status, None
            
        corr_rules = rules_config.get("correlationRules", {}).get(main_item.process_step, {})
        req_subs = corr_rules.get("subAssemblySteps", [])
        if not req_subs:
            # If main assembly needs no correlation, just send it
            group.status = "COMPLETE"
            db.commit()
            return True, group.status, mes_data_dict
            
        present_subs = {i.process_step: i for i in all_items if i.assembly_level == "SUB_ASSEMBLY"}
        
        is_complete = True
        failed_subs = False
        for req in req_subs:
            if req not in present_subs:
                is_complete = False
            else:
                if present_subs[req].result_type != "PASS":
                    failed_subs = True
                    
        valid_strat = corr_rules.get("validationStrategy", "ALL_PASS")
        allow_part = corr_rules.get("allowPartial", False)
        
        if failed_subs and valid_strat in ["ALL_PASS", "ALL_SUBASSEMBLIES_PASS"]:
            group.status = "FAILED"
            db.commit()
            return True, "FAILED", None # Reached a state where it's dead, queue as FAILED Exception!
            
        if is_complete or allow_part:
            group.status = "COMPLETE"
            db.commit()
            
            # Reconstruct payload combining them!
            enhanced = mes_data_dict.copy()
            enhanced["sub_assemblies"] = []
            for sub in present_subs.values():
                enhanced["sub_assemblies"].append({
                    "serial_no": sub.serial_number,
                    "step": sub.process_step,
                    "result": sub.result_type
                })
            
            return True, "COMPLETE", enhanced
            
        return False, group.status, None
    finally:
        db.close()

def log_to_db(mes_data_dict, transmission_status, validation_status, error_msg):
    payload_str = json.dumps(mes_data_dict)
    try:
        db = SessionLocal()
        is_override = mes_data_dict.get("originalResult") is not None or mes_data_dict.get("overrideResult") is not None
        
        event_id = mes_data_dict.get("eventId")
        if is_override:
            event = db.query(OverrideEvent).filter(OverrideEvent.event_id == event_id).first()
            if not event:
                event = OverrideEvent(event_id=event_id)
                db.add(event)
            event.source_system = mes_data_dict.get("sourceSystem")
            event.product_id = mes_data_dict.get("productId")
            event.serial_number = mes_data_dict.get("serialNumber")
            event.step = mes_data_dict.get("step")
            event.original_result = mes_data_dict.get("originalResult")
            event.override_result = mes_data_dict.get("overrideResult")
            event.override_by = mes_data_dict.get("overrideBy")
            event.override_timestamp = mes_data_dict.get("overrideTimestamp")
            event.override_reason_code = mes_data_dict.get("overrideReasonCode")
            event.override_reason_description = mes_data_dict.get("overrideReasonDescription")
            event.approval_status = mes_data_dict.get("approvalStatus")
            event.approver_id = mes_data_dict.get("approverId")
            event.transmission_status = transmission_status
            event.error_message = error_msg
            event.payload = payload_str
        else:
            event = db.query(QualityEvent).filter(QualityEvent.event_id == event_id).first()
            if not event:
                event = QualityEvent(event_id=event_id)
                db.add(event)
            event.source_system = mes_data_dict.get("sourceSystem")
            event.entity_type = mes_data_dict.get("entityType")
            event.parent_serial_number = mes_data_dict.get("parentSerialNumber")
            event.product_id = mes_data_dict.get("productId")
            event.serial_number = mes_data_dict.get("serialNumber")
            event.step = mes_data_dict.get("step")
            event.result = mes_data_dict.get("result")
            event.defect_code = mes_data_dict.get("errorCode")
            event.defect_description = mes_data_dict.get("errorDescription")
            event.transmission_status = transmission_status
            event.validation_status = validation_status
            event.error_message = error_msg
            event.payload = payload_str

        db.commit()

    except Exception as e:
        logger.error(f"Failed to log event to DB: {e}")
    finally:
        db.close()

def log_to_exception_queue(event_id, exception_type, exception_reason, raw_payload_str):
    db = SessionLocal()
    try:
        from database import ExceptionEvent
        exc_event = ExceptionEvent(
            event_id=event_id,
            exception_type=exception_type,
            exception_reason=exception_reason,
            raw_payload=raw_payload_str
        )
        db.add(exc_event)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log to Exception Queue: {e}")
    finally:
        db.close()

def log_processing_attempt(event_id, attempt_num, attempt_type, status, error_msg, flags_code=None, flags_body=None):
    db = SessionLocal()
    try:
        from database import ProcessingAttempt
        attempt = ProcessingAttempt(
            event_id=event_id,
            attempt_number=attempt_num,
            attempt_type=attempt_type,
            result_status=status,
            error_message=error_msg,
            flags_response_code=flags_code,
            flags_response_body=flags_body
        )
        db.add(attempt)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log Processing Attempt: {e}")
    finally:
        db.close()

def push_to_dlq(payload_dict: Dict[str, Any], error_msg: str):
    log_to_db(payload_dict, "FAILED", "FAILED", error_msg)
    log_to_exception_queue(
        event_id=payload_dict.get("eventId"),
        exception_type="VALIDATION_FAILED",
        exception_reason=error_msg,
        raw_payload_str=json.dumps(payload_dict)
    )
    
    dlq_store.append({
        "payload": payload_dict,
        "error": error_msg,
        "queue": "DEAD_LETTER"
    })
    logger.error(f"Event pushed to DLQ. Reason: {error_msg}")

def push_to_retry_queue(payload_dict: Dict[str, Any], error_msg: str):
    log_to_db(payload_dict, "FAILED", "PASSED", f"RETRY EXHAUSTED: {error_msg}")
    log_to_exception_queue(
        event_id=payload_dict.get("eventId"),
        exception_type="TRANSMISSION_RETRY_EXHAUSTED",
        exception_reason=error_msg,
        raw_payload_str=json.dumps(payload_dict)
    )
    retry_queue_store.append({
        "payload": payload_dict,
        "error": error_msg,
        "queue": "RETRY_QUEUE",
        "attempts": 3
    })
    logger.warning(f"Event pushed to RETRY QUEUE after exhaustion. Error: {error_msg}")

def record_workflow_pending(payload_dict: Dict[str, Any], status_msg: str):
    log_to_db(payload_dict, "WORKFLOW_PENDING", "PASSED", status_msg)
    logger.info(f"Event held in workflow: {status_msg}")

def record_workflow_rejected(payload_dict: Dict[str, Any], status_msg: str):
    log_to_db(payload_dict, "FAILED", "PASSED", status_msg) # Transmission failed explicitly
    log_to_exception_queue(
        event_id=payload_dict.get("eventId"),
        exception_type="WORKFLOW_REJECTED",
        exception_reason=status_msg,
        raw_payload_str=json.dumps(payload_dict)
    )
    logger.info(f"Event rejected in workflow: {status_msg}")

def transform_mes_to_flags(mes_data) -> dict:
    transformed = {}
    mes_dict = mes_data if isinstance(mes_data, dict) else mes_data.model_dump(exclude_unset=True)
    result_val = mes_dict.get("result")
    
    for mes_field, flags_field in MAPPING_CONFIG.items():
        if mes_field in mes_dict and mes_dict[mes_field] is not None:
            if result_val == "PASS" and mes_field in ["errorCode", "errorDescription", "defectCode", "defectDescription"]:
                continue
            transformed[flags_field] = mes_dict[mes_field]
            
    if "sub_assemblies" in mes_dict:
        transformed["sub_assemblies"] = mes_dict["sub_assemblies"]
            
    return transformed

def record_success(mes_data: MESQualityResult, transformed_payload: dict):
    log_to_db(mes_data.model_dump(mode="json"), "SUCCESS", "PASSED", None)
    success_store.append(transformed_payload)
