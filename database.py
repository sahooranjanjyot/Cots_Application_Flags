from sqlalchemy import create_engine, Column, String, DateTime, Integer, Boolean, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timezone
import uuid

import os

SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./quality_engine.db")

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class ValidationRule(Base):
    __tablename__ = "validation_rules"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id = Column(String, index=True, unique=True, nullable=False)
    process_step = Column(String, index=True, nullable=False)
    assembly_level = Column(String, index=True, nullable=False)
    result_type = Column(String, index=True, nullable=False)
    mandatory_fields_json = Column(Text, nullable=False)
    forbidden_fields_json = Column(Text, nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class QualityEvent(Base):
    __tablename__ = "quality_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String, index=True, nullable=True)
    source_system = Column(String, nullable=True)
    entity_type = Column(String, nullable=True) # ASSEMBLY vs SUB_ASSEMBLY
    parent_serial_number = Column(String, index=True, nullable=True)
    product_id = Column(String, index=True, nullable=True)
    serial_number = Column(String, index=True, nullable=True)
    step = Column(String, nullable=True)
    result = Column(String, nullable=True)
    defect_code = Column(String, nullable=True)
    defect_description = Column(String, nullable=True)
    transmission_status = Column(String, index=True) 
    validation_status = Column(String, index=True) 
    error_message = Column(String, nullable=True)
    payload = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class OverrideEvent(Base):
    __tablename__ = "override_events"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String, index=True, nullable=True)
    source_system = Column(String, nullable=True)
    product_id = Column(String, index=True, nullable=True)
    serial_number = Column(String, index=True, nullable=True)
    step = Column(String, nullable=True)
    original_result = Column(String, nullable=True)
    override_result = Column(String, nullable=True)
    override_by = Column(String, nullable=True)
    override_timestamp = Column(String, nullable=True)
    override_reason_code = Column(String, nullable=True)
    override_reason_description = Column(String, nullable=True)
    approval_status = Column(String, nullable=True)
    approver_id = Column(String, nullable=True)
    transmission_status = Column(String, index=True)
    error_message = Column(String, nullable=True)
    payload = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class CorrelationGroup(Base):
    __tablename__ = "correlation_groups"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    parent_serial_number = Column(String, index=True, nullable=True)
    status = Column(String, index=True, default="IN_PROGRESS")
    expected_children_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    items = relationship("CorrelationItem", back_populates="group")

class CorrelationItem(Base):
    __tablename__ = "correlation_items"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id = Column(String, ForeignKey("correlation_groups.id"), index=True, nullable=True)
    serial_number = Column(String, index=True, nullable=True)
    parent_serial_number = Column(String, index=True, nullable=True)
    assembly_level = Column(String, nullable=True)
    process_step = Column(String, nullable=True)
    result_type = Column(String, nullable=True)
    validation_status = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    group = relationship("CorrelationGroup", back_populates="items")

class SchemaVersion(Base):
    __tablename__ = "schema_versions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    schema_version = Column(String, index=True, nullable=True)
    status = Column(String, nullable=True)
    effective_from = Column(DateTime, nullable=True)
    effective_to = Column(DateTime, nullable=True)
    config_json = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class EventStore(Base):
    __tablename__ = "event_store"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String, index=True, nullable=True)
    source_system = Column(String, index=True, nullable=True)
    idempotency_key = Column(String, index=True, nullable=True)
    correlation_id = Column(String, index=True, nullable=True)
    serial_number = Column(String, index=True, nullable=True)
    parent_serial_number = Column(String, index=True, nullable=True)
    event_timestamp = Column(String, nullable=True)
    received_timestamp = Column(String, nullable=True)
    processing_status = Column(String, index=True, nullable=True)
    payload_hash = Column(String, nullable=True)
    payload = Column(String, nullable=True)
    
    schema_version = Column(String, nullable=True)
    canonical_payload = Column(String, nullable=True)
    raw_payload = Column(String, nullable=True)
    normalization_status = Column(String, nullable=True)
    deprecation_warning = Column(String, nullable=True)
    
    retry_attempt_count = Column(Integer, default=0, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class EventDependencyTracker(Base):
    __tablename__ = "event_dependency_tracker"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    correlation_id = Column(String, index=True, nullable=True)
    required_dependency = Column(String, nullable=True)
    dependency_status = Column(String, index=True, nullable=True)
    timeout_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ReprocessRequest(Base):
    __tablename__ = "reprocess_requests"
    
    reprocess_request_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String, index=True, nullable=True)
    correlation_id = Column(String, index=True, nullable=True)
    requested_by = Column(String, nullable=True)
    requested_timestamp = Column(String, nullable=True)
    reprocess_type = Column(String, nullable=True)
    reason_code = Column(String, nullable=True)
    reason_description = Column(String, nullable=True)
    override_validation = Column(Boolean, default=False)
    approval_status = Column(String, index=True, default="PENDING")
    approver_id = Column(String, nullable=True)
    status = Column(String, index=True, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ProcessingAttempt(Base):
    __tablename__ = "processing_attempts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String, index=True)
    attempt_number = Column(Integer, default=1)
    attempt_type = Column(String, nullable=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    result_status = Column(String, index=True, nullable=True)
    error_message = Column(String, nullable=True)
    flags_response_code = Column(Integer, nullable=True)
    flags_response_body = Column(String, nullable=True)

class ExceptionEvent(Base):
    __tablename__ = "exception_events"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String, index=True)
    exception_type = Column(String, nullable=True)
    exception_reason = Column(String, nullable=True)
    raw_payload = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved = Column(Boolean, default=False)
    resolved_by = Column(String, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

Base.metadata.create_all(bind=engine)

def seed_static_limits():
    db = SessionLocal()
    try:
        from scripts.seed_validation_rules import generate_rules
        generate_rules()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Seeding val rules failed: {e}")
        db.rollback()
    finally:
        db.close()

seed_static_limits()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
