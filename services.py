from models import MESQualityResult
from database import SessionLocal, QualityEvent, OverrideEvent, CorrelationEvent
import logging
from typing import List, Dict, Any
import json
import os

logger = logging.getLogger(__name__)

with open(os.path.join(os.path.dirname(__file__), 'mapping.json')) as f:
    MAPPING_CONFIG = json.load(f)

success_store: List[Dict[str, Any]] = []
dlq_store: List[Dict[str, Any]] = []
retry_queue_store: List[Dict[str, Any]] = []

def log_correlation_to_db(event_id, source_system, parent_sn, child_sn, entity_type, step, result, correlation_status, payload_str=None):
    db = SessionLocal()
    try:
        event = CorrelationEvent(
            event_id=event_id,
            source_system=source_system,
            parent_serial_number=parent_sn,
            child_serial_number=child_sn,
            entity_type=entity_type,
            step=step,
            result=result,
            correlation_status=correlation_status,
            payload=payload_str
        )
        db.add(event)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log correlation event: {e}")
    finally:
        db.close()

def log_to_db(mes_data_dict, transmission_status, validation_status, error_msg):
    payload_str = json.dumps(mes_data_dict)
    try:
        db = SessionLocal()
        is_override = mes_data_dict.get("originalResult") is not None or mes_data_dict.get("overrideResult") is not None
        
        if is_override:
            event = OverrideEvent(
                event_id=mes_data_dict.get("eventId"),
                source_system=mes_data_dict.get("sourceSystem"),
                product_id=mes_data_dict.get("productId"),
                serial_number=mes_data_dict.get("serialNumber"),
                step=mes_data_dict.get("step"),
                original_result=mes_data_dict.get("originalResult"),
                override_result=mes_data_dict.get("overrideResult"),
                override_by=mes_data_dict.get("overrideBy"),
                override_timestamp=mes_data_dict.get("overrideTimestamp"),
                override_reason_code=mes_data_dict.get("overrideReasonCode"),
                override_reason_description=mes_data_dict.get("overrideReasonDescription"),
                approval_status=mes_data_dict.get("approvalStatus"),
                approver_id=mes_data_dict.get("approverId"),
                transmission_status=transmission_status,
                error_message=error_msg,
                payload=payload_str
            )
        else:
            event = QualityEvent(
                event_id=mes_data_dict.get("eventId"),
                source_system=mes_data_dict.get("sourceSystem"),
                entity_type=mes_data_dict.get("entityType"),
                parent_serial_number=mes_data_dict.get("parentSerialNumber"),
                product_id=mes_data_dict.get("productId"),
                serial_number=mes_data_dict.get("serialNumber"),
                step=mes_data_dict.get("step"),
                result=mes_data_dict.get("result"),
                defect_code=mes_data_dict.get("errorCode"),
                defect_description=mes_data_dict.get("errorDescription"),
                transmission_status=transmission_status,
                validation_status=validation_status,
                error_message=error_msg,
                payload=payload_str
            )
        db.add(event)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log event to DB: {e}")
    finally:
        db.close()

def push_to_dlq(payload_dict: Dict[str, Any], error_msg: str):
    log_to_db(payload_dict, "FAILED", "FAILED", error_msg)
    
    dlq_store.append({
        "payload": payload_dict,
        "error": error_msg,
        "queue": "DEAD_LETTER"
    })
    logger.error(f"Event pushed to DLQ. Reason: {error_msg}")

def push_to_retry_queue(payload_dict: Dict[str, Any], error_msg: str):
    log_to_db(payload_dict, "FAILED", "PASSED", f"RETRY EXHAUSTED: {error_msg}")

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
    logger.info(f"Event rejected in workflow: {status_msg}")

def transform_mes_to_flags(mes_data: MESQualityResult) -> dict:
    transformed = {}
    mes_dict = mes_data.model_dump(exclude_unset=True)
    
    for mes_field, flags_field in MAPPING_CONFIG.items():
        if mes_field in mes_dict and mes_dict[mes_field] is not None:
            if getattr(mes_data, "result", None) == "PASS" and mes_field in ["errorCode", "errorDescription"]:
                continue
            transformed[flags_field] = mes_dict[mes_field]
            
    return transformed

def record_success(mes_data: MESQualityResult, transformed_payload: dict):
    log_to_db(mes_data.model_dump(mode="json"), "SUCCESS", "PASSED", None)
    success_store.append(transformed_payload)
